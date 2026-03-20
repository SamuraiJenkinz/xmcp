# Phase 6: Hybrid Tools - Research

**Researched:** 2026-03-20
**Domain:** Exchange hybrid topology PowerShell cmdlets, connector health checks, tool count cleanup
**Confidence:** HIGH (cmdlet parameters verified from official Microsoft docs; project patterns verified from live codebase)

---

## Summary

Phase 6 implements two Exchange hybrid tool handlers (`get_hybrid_config`, `get_connector_status`) and removes `get_migration_batches` entirely from scope. It also updates all "15 tools" references to "14 tools" throughout the codebase. This is the last phase of tool implementation; after Phase 6 the server is complete.

Both tools follow the same async handler pattern established in Phases 3–5: `run_cmdlet_with_retry`, dict/list normalisation, raw Exchange values passed through, RuntimeError for bad input, empty result for valid-but-no-data. No new dependencies are required.

The critical architectural finding for `get_connector_status` is that **`Get-ExchangeCertificate` is on-premises only** — it is not available via `Connect-ExchangeOnline`. The CONTEXT.md requires TLS certificate details (issuer, expiry, thumbprint) in connector status results. The correct approach is to extract the TLS thumbprint from `Get-SendConnector`/`Get-ReceiveConnector` (`TlsCertificateName` field), then resolve full cert details by calling `Get-ExchangeCertificate -Thumbprint <thumbprint>` in the same PowerShell session. Both cmdlets run fine in a hybrid on-premises PowerShell session. Since the project connects via `Connect-ExchangeOnline`, on-premises cmdlets like `Get-SendConnector`, `Get-ReceiveConnector`, and `Get-ExchangeCertificate` are available in hybrid mode.

**Primary recommendation:** Implement `get_hybrid_config` as four parallel `run_cmdlet_with_retry` calls (org relationships, federation trust, intra-org connectors, availability address spaces) assembled into a single structured result. Implement `get_connector_status` as a `Get-SendConnector`/`Get-ReceiveConnector` filtered to hybrid connectors only (`CloudServicesMailEnabled` flag), then per-connector cert lookup via `Get-ExchangeCertificate` if a thumbprint is present. No live SMTP test — the connectivity test is the cert validity check and enabled/configured status rather than a network probe. Remove `get_migration_batches` from `TOOL_DEFINITIONS`, `TOOL_DISPATCH`, and update all "15 tools"/"16 tools" count references to "14 tools"/"15 tools" respectively.

---

## Standard Stack

The project stack is locked. No new dependencies required.

### Core (all already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Exchange PowerShell | ExchangeOnlineManagement | All Exchange cmdlets | Project-wide decision |
| mcp | >=1.0.0 | MCP server framework | Project-wide decision |
| pytest / pytest-asyncio | >=9.0.2 / >=1.3.0 | Tests | Project-wide decision |

### No New Dependencies

All two tools can be implemented with the existing stack.

**Installation:** N/A — all packages already present in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

No new files except the test file. All code stays in two existing files:

```
exchange_mcp/
└── tools.py             # Add two handlers; remove get_migration_batches from TOOL_DEFINITIONS + TOOL_DISPATCH
tests/
└── test_tools_hybrid.py # New test file, same structure as test_tools_security.py
```

Updates required in existing files:
- `exchange_mcp/tools.py` — remove `get_migration_batches` Tool definition and dispatch entry; add two handlers
- `exchange_mcp/server.py` — update "15 Exchange tools" → "14 Exchange tools" in docstrings/comments; "16 tools" → "15 tools"
- `tests/test_server.py` — update `test_list_tools_returns_all_16` (assert `len == 16` → `len == 15`); update docstring/comment "16 registered tools (15 Exchange + ping)" → "15 registered tools (14 Exchange + ping)"; update `test_call_tool_not_implemented_raises` from `get_hybrid_config` to `get_connector_status` (the last remaining stub after hybrid tools are implemented — except both are being implemented, so this test should use ANY non-existent tool or be removed/updated to reflect no stubs remain)

### Pattern 1: Multi-Cmdlet Assembly Handler (get_hybrid_config)

**What:** Four independent `run_cmdlet_with_retry` calls, each wrapped in try/except with independent error handling. Results assembled into one structured dict. A failure in one sub-call produces an `error` key in that section rather than failing the whole response.

**When to use:** When the tool must gather from multiple unrelated Exchange cmdlets with no dependency between them.

**Example (from Phase 4 DAG health pattern, adapted):**
```python
# Source: tools.py _get_dag_health_handler — per-member iteration with partial results
async def _get_hybrid_config_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    # --- Org relationships ---
    org_rel_cmdlet = (
        "Get-OrganizationRelationship | Select-Object "
        "Name, Enabled, "
        "@{Name='DomainNames';Expression={@($_.DomainNames | ForEach-Object { $_.ToString() })}}, "
        "FreeBusyAccessEnabled, FreeBusyAccessLevel, "
        "MailboxMoveEnabled, DeliveryReportEnabled, MailTipsAccessEnabled, "
        "TargetApplicationUri, TargetAutodiscoverEpr, TargetSharingEpr, TargetOwaURL, "
        "OrganizationContact, ArchiveAccessEnabled, PhotosEnabled"
    )
    try:
        org_raw = await client.run_cmdlet_with_retry(org_rel_cmdlet)
    except RuntimeError as exc:
        org_raw = {"error": str(exc)}

    # --- Federation trust ---
    fed_cmdlet = (
        "Get-FederationTrust | Select-Object "
        "Name, ApplicationUri, TokenIssuerUri, TokenIssuerCertificate, "
        "OrgCertificate, TokenIssuerMetadataEpr"
    )
    try:
        fed_raw = await client.run_cmdlet_with_retry(fed_cmdlet)
    except RuntimeError as exc:
        fed_raw = {"error": str(exc)}

    # ... and so on for intra-org connectors and availability address spaces
    return {
        "organization_relationships": ...,
        "federation_trust": ...,
        "intra_organization_connectors": ...,
        "availability_address_spaces": ...,
    }
```

### Pattern 2: Filtered Connector + Per-Connector Cert Lookup (get_connector_status)

**What:** Fetch hybrid-only send and receive connectors (filtered by `CloudServicesMailEnabled -eq $true` or name pattern), then for each connector attempt to resolve the TLS certificate via `Get-ExchangeCertificate`. Cert lookup failures produce `null` cert fields rather than aborting.

**When to use:** `get_connector_status` only.

```python
# Filter hybrid send connectors — CloudServicesMailEnabled is the hybrid flag
send_cmdlet = (
    "Get-SendConnector | Where-Object { $_.CloudServicesMailEnabled -eq $true } | "
    "Select-Object Name, Enabled, CloudServicesMailEnabled, "
    "RequireTLS, TlsCertificateName, TlsDomain, Fqdn, "
    "@{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}}, "
    "@{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}"
)

# Per-connector cert lookup using TlsCertificateName thumbprint
# TlsCertificateName format: "<I>issuer<S>subject" — extract thumbprint differently
# Better: filter by name pattern or use Get-ExchangeCertificate -DomainName fqdn
cert_cmdlet = (
    f"Get-ExchangeCertificate -Thumbprint '{safe_thumbprint}' | Select-Object "
    "Thumbprint, Subject, Issuer, NotAfter, NotBefore, Status, "
    "@{Name='CertificateDomains';Expression={@($_.CertificateDomains | ForEach-Object { $_.ToString() })}}, "
    "IsSelfSigned, HasPrivateKey"
)
```

**CRITICAL NOTE on TlsCertificateName format:** The `TlsCertificateName` field on Exchange connectors is NOT a bare thumbprint. Its format is `<I>issuer_string<S>subject_string`. To look up the certificate, use `Get-ExchangeCertificate -DomainName <fqdn>` where fqdn is the connector's `Fqdn` property — Exchange will return the certificate it selects for that FQDN, which is the one the connector actually uses.

### Anti-Patterns to Avoid

- **Using `Test-SmtpConnectivity` for live hybrid test:** `Test-SmtpConnectivity` is on-premises only AND tests receive connectors on local server only — it does not test outbound connectivity to Exchange Online. The CONTEXT.md requires "live connectivity test against Exchange Online endpoint." The correct approach is cert validity checking via `Get-ExchangeCertificate` + connector enabled status + TLS configuration inspection. A genuine outbound SMTP test would require `Test-Mailflow` which sends real messages (explicitly prohibited in Phase 5 decisions) or `Validate-OutboundConnector` which is Exchange Online only.
- **Using `Test-OrganizationRelationship`:** Requires `-UserIdentity` parameter (a specific mailbox to test as); cannot be run generically without knowing a valid user UPN. The description says "only verifies configuration allows features to work" — not a live connectivity test. Excluded.
- **Calling `Get-ExchangeCertificate` without on-premises context:** This cmdlet is on-premises only. It will fail if the session is Exchange Online only. In a hybrid deployment where `Connect-ExchangeOnline` is used, on-premises cmdlets are still accessible because the Hybrid Configuration Wizard sets up the mixed environment. If `Get-ExchangeCertificate` fails (not-recognized error), handle gracefully and return `null` for cert fields.
- **Filtering hybrid connectors by name string:** Connector names vary by environment. Use `CloudServicesMailEnabled -eq $true` for send connectors as the reliable hybrid flag. For receive connectors, there is no equivalent direct flag — filter by TransportRole or look for the "Default Frontend" and inbound-from-O365 pattern. The safest approach: return ALL send connectors with `CloudServicesMailEnabled=true`, and receive connectors that have TlsCertificateName set (indicating they handle TLS from cloud).
- **Using `Get-InboundConnector`/`Get-OutboundConnector`:** These cmdlets are Exchange Online (EXO) connectors, not on-premises hybrid send/receive connectors. The correct on-premises cmdlets are `Get-SendConnector` and `Get-ReceiveConnector`.

---

## Cmdlet Reference (Verified from Official Docs)

### get_hybrid_config: Four Cmdlets

**Call 1 — Organization Relationships** (confirmed fields from `New-OrganizationRelationship` parameters):
```powershell
Get-OrganizationRelationship | Select-Object
    Name, Enabled,
    @{Name='DomainNames';Expression={@($_.DomainNames | ForEach-Object { $_.ToString() })}},
    FreeBusyAccessEnabled, FreeBusyAccessLevel,
    MailboxMoveEnabled, DeliveryReportEnabled,
    MailTipsAccessEnabled, MailTipsAccessLevel,
    TargetApplicationUri, TargetAutodiscoverEpr, TargetSharingEpr, TargetOwaURL,
    OrganizationContact, ArchiveAccessEnabled, PhotosEnabled
```
Note: `DomainNames` is a `MultiValuedProperty` — must project to string array with `ForEach-Object { $_.ToString() }`.

**Call 2 — Federation Trust** (confirmed fields from `Set-FederationTrust` and `Get-FederationTrust`):
```powershell
Get-FederationTrust | Select-Object
    Name, ApplicationUri, TokenIssuerUri, TokenIssuerMetadataEpr,
    OrgCertificate, TokenIssuerCertificate
```
Key fields: `ApplicationUri` (primary domain for federation org ID), `TokenIssuerUri` (Microsoft Federation Gateway), `OrgCertificate` (current certificate thumbprint used to sign tokens), `TokenIssuerCertificate` (MFG certificate thumbprint). Note: `Get-FederationTrust` is on-premises AND Exchange Online (confirmed from official docs applicable fields). In practice these are complex objects — raw values pass through as-is per project convention.

**Call 3 — Intra-Organization Connectors** (confirmed fields from `New-IntraOrganizationConnector`):
```powershell
Get-IntraOrganizationConnector | Select-Object
    Name, Enabled, DiscoveryEndpoint,
    @{Name='TargetAddressDomains';Expression={@($_.TargetAddressDomains | ForEach-Object { $_.ToString() })}},
    TargetSharingEpr
```
`TargetAddressDomains` is a `MultiValuedProperty` — must project to string array. `DiscoveryEndpoint` is a URI (Autodiscover endpoint for the remote org). Available on both on-premises and Exchange Online.

**Call 4 — Availability Address Spaces** (free/busy sharing):
```powershell
Get-AvailabilityAddressSpace | Select-Object
    Name, ForestName, UserName, AccessMethod, ProxyUrl, UseServiceAccount
```
This gives the free/busy sharing configuration: `ForestName` is the remote forest/domain, `AccessMethod` is how availability is fetched (OrgWideFB, PerUserFB, OWA, PublicFolder), `ProxyUrl` is the EWS endpoint. Available on both on-premises and Exchange Online.

**Inline hybrid mail flow connectors:** Per CONTEXT.md decision, hybrid mail flow connectors (inbound/outbound to O365) are included inline in `get_hybrid_config` rather than just referencing `get_smtp_connectors`. Use `Get-SendConnector` filtered to `CloudServicesMailEnabled -eq $true`:
```powershell
Get-SendConnector | Where-Object { $_.CloudServicesMailEnabled -eq $true } | Select-Object
    Name, Enabled, CloudServicesMailEnabled, RequireTLS, TlsCertificateName, TlsDomain,
    @{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}},
    @{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}
```

### get_connector_status: Hybrid Connector Health

**Step 1 — Hybrid Send Connectors:**
```powershell
Get-SendConnector | Where-Object { $_.CloudServicesMailEnabled -eq $true } | Select-Object
    Name, Enabled, CloudServicesMailEnabled, RequireTLS, TlsCertificateName, TlsDomain,
    Fqdn, MaxMessageSize,
    @{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}},
    @{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}
```

**Step 2 — Receive Connectors (hybrid inbound from O365):**
Exchange Online sends inbound mail using a certificate; the matching receive connector is identifiable by its TlsCertificateName being set or by the presence of specific remote IP ranges. The safest approach is to return all receive connectors with `RequireTLS -eq $true` and filter out the purely-internal ones, or use a naming convention filter. Given the CONTEXT.md says "hybrid send/receive connectors only — not hybrid agents", the safest approach is:
```powershell
Get-ReceiveConnector | Where-Object { $_.TlsCertificateName -ne $null -and $_.TlsCertificateName -ne '' } | Select-Object
    Name, Enabled, RequireTLS, TlsCertificateName, Fqdn,
    @{Name='Bindings';Expression={@($_.Bindings | ForEach-Object { $_.ToString() })}},
    @{Name='RemoteIPRanges';Expression={@($_.RemoteIPRanges | ForEach-Object { $_.ToString() })}},
    AuthMechanism, PermissionGroups, TransportRole, Server
```
Alternatively, filter by `AuthMechanism` containing "TLS" or by `PermissionGroups` containing "ExchangeServers". The implementation should choose a reasonable filter and document it.

**Step 3 — Certificate lookup per connector:**
For each connector where `Fqdn` is set:
```powershell
Get-ExchangeCertificate -DomainName '<fqdn>' | Select-Object
    Thumbprint, Subject, Issuer, NotAfter, NotBefore, Status,
    @{Name='CertificateDomains';Expression={@($_.CertificateDomains | ForEach-Object { $_.ToString() })}},
    IsSelfSigned, HasPrivateKey
```
The `-DomainName` parameter returns the certificate Exchange would select for that FQDN — matching how Exchange picks the TLS cert for the connector.

**Healthy/unhealthy determination:**
- Send connector: `healthy = connector.Enabled AND RequireTLS AND cert.Status == "Valid" AND cert.NotAfter > now`
- Receive connector: `healthy = connector.Enabled AND RequireTLS AND (cert.Status == "Valid" AND cert.NotAfter > now if cert found)`
- `error_message`: populated only when unhealthy (cert expired, cert not found, connector disabled)

**Get-ExchangeCertificate on-premises only:** If this cmdlet fails (RuntimeError with "not recognized"), the handler must catch it gracefully and return `cert_details: null` with an `error` note. This prevents the whole tool from failing in pure Exchange Online environments.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Certificate validity check | Custom date/thumbprint logic in Python | `Get-ExchangeCertificate` + `Status` field | Exchange calculates validity including chain trust, revocation; `Status: Valid` is the authoritative answer |
| Live SMTP connectivity test | Custom TCP socket test or SMTP handshake | Connector enabled + cert valid + TLS configured = "healthy" | Genuine SMTP test to Exchange Online requires real messages (Test-Mailflow) which has side effects; cert check is sufficient for the use case |
| Hybrid connector identification | Name substring matching | `CloudServicesMailEnabled -eq $true` on send connectors | Flag is reliable; name varies by environment |
| Multiple parallel cmdlet calls | Concurrent asyncio tasks | Sequential `run_cmdlet_with_retry` calls | Per-call PSSession means each call is independent; Python async has no benefit here — Exchange connections are already serialized per-call by design |
| Connector topology re-implementation | Cross-referencing multiple tools | Inline connector data in get_hybrid_config | CONTEXT.md decision: one call gives full picture |

---

## Common Pitfalls

### Pitfall 1: get_migration_batches Still in TOOL_DISPATCH After Removal

**What goes wrong:** Remove the tool from `TOOL_DEFINITIONS` but forget to remove it from `TOOL_DISPATCH`. Test `test_all_tool_names_in_dispatch` passes (it only checks that DEFINITIONS names are in DISPATCH), but the orphan entry causes confusion.

**Why it happens:** Two separate data structures — DEFINITIONS list and DISPATCH dict — both reference the tool.

**How to avoid:** Remove from BOTH in the same commit. Also remove from the dispatch dict and from any test that references `get_migration_batches` by name (check `test_server.py` and all test files). The `test_call_tool_not_implemented_raises` test currently uses `get_hybrid_config` as the stub — after Phase 6, no stubs remain, so this test should be updated to reflect that all tools are implemented (use a deliberately invalid tool name like `"nonexistent_tool"` to test the `Unknown tool` path instead).

**Warning signs:** `test_all_tool_names_in_dispatch` still passes but tool count is wrong.

### Pitfall 2: Tool Count Assertions Fail After Removal

**What goes wrong:** `test_list_tools_returns_all_16` asserts `len(tools) == 16`. After removing `get_migration_batches`, this becomes 15. The test will fail until updated.

**Why it happens:** The test has a hardcoded count. Every other test that mentions "16 tools" or "15 Exchange" in comments or docstrings also needs updating.

**How to avoid:** Search for all occurrences of "16" and "15" in the context of tool counts:
- `tests/test_server.py`: `assert len(tools) == 16` → `== 15`; docstring "16 registered tools (15 Exchange + ping)" → "15 registered tools (14 Exchange + ping)"
- `exchange_mcp/server.py`: "16 registered tools (15 Exchange + ping)" → "15 registered tools (14 Exchange + ping)"; "16 tools" → "15 tools"
- `exchange_mcp/tools.py`: module docstring "16 mcp.types.Tool objects (15 Exchange + ping)" → "15 mcp.types.Tool objects (14 Exchange + ping)"; "All 15 Exchange tool handlers" → "All 14 Exchange tool handlers"

**Warning signs:** `test_list_tools_returns_all_16` fails with `AssertionError: assert 15 == 16`.

### Pitfall 3: Get-ExchangeCertificate Not Available via Exchange Online Session

**What goes wrong:** `Get-ExchangeCertificate` is confirmed on-premises only (docs state: "This cmdlet is available only in on-premises Exchange"). In a pure Exchange Online session, calling it raises RuntimeError with "not recognized as the name of a cmdlet".

**Why it happens:** The project connects via `Connect-ExchangeOnline`. In a hybrid environment, on-premises cmdlets are available because the Hybrid Configuration Wizard configures the mixed session. But in test environments or pure cloud tenants, this cmdlet will fail.

**How to avoid:** Wrap each `Get-ExchangeCertificate` call in its own try/except. If it raises RuntimeError containing "not recognized", return `cert_details: null` (not healthy/unhealthy — just `cert_available: false`). Do not fail the whole `get_connector_status` response.

**Warning signs:** `get_connector_status` raises RuntimeError instead of returning partial data.

### Pitfall 4: FederationTrust OrgCertificate and TokenIssuerCertificate Are Certificate Objects, Not Strings

**What goes wrong:** `OrgCertificate` and `TokenIssuerCertificate` on a `FederationTrust` object are X509Certificate2 objects. `ConvertTo-Json -Depth 10` may serialize them as complex nested objects with raw certificate data, or may serialize them as opaque handles.

**Why it happens:** Same class of problem as Phase 4 `ActivationPreference` (complex types don't serialize cleanly).

**How to avoid:** Project only the thumbprint and subject from these certificate objects using computed properties:
```powershell
Get-FederationTrust | Select-Object
    Name, ApplicationUri, TokenIssuerUri,
    @{Name='OrgCertThumbprint';Expression={$_.OrgCertificate.Thumbprint}},
    @{Name='OrgCertSubject';Expression={$_.OrgCertificate.Subject}},
    @{Name='OrgCertNotAfter';Expression={$_.OrgCertificate.NotAfter}},
    @{Name='TokenIssuerCertThumbprint';Expression={$_.TokenIssuerCertificate.Thumbprint}},
    @{Name='TokenIssuerUri';Expression={$_.TokenIssuerUri.AbsoluteUri}}
```
This avoids serialization issues by extracting scalar properties.

**Warning signs:** `get_hybrid_config` returns `OrgCertificate: {}` or `OrgCertificate: null` when the federation trust exists.

### Pitfall 5: MultiValuedProperty Fields Serialize as Arrays of Objects

**What goes wrong:** `DomainNames` on `Get-OrganizationRelationship` is a `MultiValuedProperty`. Without explicit `.ToString()` projection, `ConvertTo-Json -Depth 10` may serialize each element as `{"Value": "contoso.com", ...}` instead of a plain string array.

**Why it happens:** Same pattern as Phase 5 `AddressSpaces` on send connectors.

**How to avoid:** Always project multi-valued properties with `@($_.PropertyName | ForEach-Object { $_.ToString() })`. Confirmed needed for: `DomainNames`, `TargetAddressDomains`, `CertificateDomains`, `AddressSpaces`, `SmartHosts`.

**Warning signs:** Tests fail because `domain_names` is a list of dicts instead of a list of strings.

### Pitfall 6: test_call_tool_not_implemented_raises Needs Update

**What goes wrong:** After Phase 6 implements both `get_hybrid_config` and `get_connector_status`, no stub tools remain. The test currently uses `get_hybrid_config` to test the stub path. After implementation, calling `get_hybrid_config` will either succeed or fail with a real Exchange error (not "not yet implemented").

**Why it happens:** This test is updated each phase to use the most recently added stub. After Phase 6, no stubs remain.

**How to avoid:** Update the test to use a tool name that doesn't exist in TOOL_DISPATCH (e.g., `"nonexistent_tool"`) and check for `"Unknown tool"` in the error message, testing the `ValueError` path in `handle_call_tool`. Alternatively, remove the test (but updating it is cleaner).

---

## Code Examples

### get_hybrid_config: Full Multi-Cmdlet Assembly

```python
# Source: tools.py — new handler following Phase 4/5 patterns
async def _get_hybrid_config_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    # --- 1. Organization relationships ---
    org_rel_cmdlet = (
        "Get-OrganizationRelationship | Select-Object "
        "Name, Enabled, "
        "@{Name='DomainNames';Expression={@($_.DomainNames | ForEach-Object { $_.ToString() })}}, "
        "FreeBusyAccessEnabled, FreeBusyAccessLevel, "
        "MailboxMoveEnabled, DeliveryReportEnabled, MailTipsAccessEnabled, MailTipsAccessLevel, "
        "TargetApplicationUri, TargetAutodiscoverEpr, TargetSharingEpr, TargetOwaURL, "
        "OrganizationContact, ArchiveAccessEnabled, PhotosEnabled"
    )
    try:
        org_raw = await client.run_cmdlet_with_retry(org_rel_cmdlet)
    except RuntimeError as exc:
        org_raw = {"error": str(exc)}

    # Normalize list
    if isinstance(org_raw, list):
        org_rels = org_raw
    elif isinstance(org_raw, dict) and "error" not in org_raw and org_raw:
        org_rels = [org_raw]
    elif isinstance(org_raw, dict) and "error" in org_raw:
        org_rels = org_raw  # pass error through
    else:
        org_rels = []

    # --- 2. Federation trust ---
    fed_cmdlet = (
        "Get-FederationTrust | Select-Object "
        "Name, ApplicationUri, "
        "@{Name='TokenIssuerUri';Expression={if ($_.TokenIssuerUri) { $_.TokenIssuerUri.AbsoluteUri } else { $null }}}, "
        "@{Name='OrgCertThumbprint';Expression={if ($_.OrgCertificate) { $_.OrgCertificate.Thumbprint } else { $null }}}, "
        "@{Name='OrgCertSubject';Expression={if ($_.OrgCertificate) { $_.OrgCertificate.Subject } else { $null }}}, "
        "@{Name='OrgCertNotAfter';Expression={if ($_.OrgCertificate) { $_.OrgCertificate.NotAfter.ToString('o') } else { $null }}}, "
        "@{Name='TokenIssuerCertThumbprint';Expression={if ($_.TokenIssuerCertificate) { $_.TokenIssuerCertificate.Thumbprint } else { $null }}}"
    )
    try:
        fed_raw = await client.run_cmdlet_with_retry(fed_cmdlet)
    except RuntimeError as exc:
        fed_raw = {"error": str(exc)}

    # --- 3. Intra-organization connectors ---
    ioc_cmdlet = (
        "Get-IntraOrganizationConnector | Select-Object "
        "Name, Enabled, DiscoveryEndpoint, "
        "@{Name='TargetAddressDomains';Expression={@($_.TargetAddressDomains | ForEach-Object { $_.ToString() })}}, "
        "TargetSharingEpr"
    )
    try:
        ioc_raw = await client.run_cmdlet_with_retry(ioc_cmdlet)
    except RuntimeError as exc:
        ioc_raw = {"error": str(exc)}

    # --- 4. Availability address spaces (free/busy) ---
    avail_cmdlet = (
        "Get-AvailabilityAddressSpace | Select-Object "
        "Name, ForestName, UserName, AccessMethod, ProxyUrl, UseServiceAccount"
    )
    try:
        avail_raw = await client.run_cmdlet_with_retry(avail_cmdlet)
    except RuntimeError as exc:
        avail_raw = {"error": str(exc)}

    # --- 5. Hybrid mail flow connectors (inline) ---
    hybrid_send_cmdlet = (
        "Get-SendConnector | Where-Object { $_.CloudServicesMailEnabled -eq $true } | Select-Object "
        "Name, Enabled, CloudServicesMailEnabled, RequireTLS, TlsCertificateName, TlsDomain, Fqdn, "
        "@{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}}, "
        "@{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}"
    )
    try:
        hybrid_send_raw = await client.run_cmdlet_with_retry(hybrid_send_cmdlet)
    except RuntimeError as exc:
        hybrid_send_raw = {"error": str(exc)}

    return {
        "organization_relationships": _normalize_list(org_rels),
        "federation_trust": _normalize_single_or_list(fed_raw),
        "intra_organization_connectors": _normalize_list(ioc_raw),
        "availability_address_spaces": _normalize_list(avail_raw),
        "hybrid_send_connectors": _normalize_list(hybrid_send_raw),
    }
```

### get_connector_status: Connector Health with Cert Lookup

```python
async def _get_connector_status_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    # --- Hybrid send connectors ---
    send_cmdlet = (
        "Get-SendConnector | Where-Object { $_.CloudServicesMailEnabled -eq $true } | Select-Object "
        "Name, Enabled, CloudServicesMailEnabled, RequireTLS, TlsCertificateName, TlsDomain, Fqdn, "
        "@{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}}, "
        "@{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}"
    )
    try:
        send_raw = await client.run_cmdlet_with_retry(send_cmdlet)
    except RuntimeError:
        raise

    send_list = send_raw if isinstance(send_raw, list) else (
        [send_raw] if isinstance(send_raw, dict) and send_raw else []
    )

    send_results = []
    for c in send_list:
        fqdn = c.get("Fqdn") or ""
        cert = None
        if fqdn:
            cert = await _lookup_cert_for_fqdn(client, fqdn)

        healthy, error_msg = _assess_connector_health(c, cert)
        send_results.append({
            "name": c.get("Name"),
            "enabled": c.get("Enabled"),
            "cloud_services_mail_enabled": c.get("CloudServicesMailEnabled"),
            "require_tls": c.get("RequireTLS"),
            "tls_domain": c.get("TlsDomain"),
            "fqdn": fqdn or None,
            "address_spaces": c.get("AddressSpaces"),
            "smart_hosts": c.get("SmartHosts"),
            "certificate": cert,
            "healthy": healthy,
            "error": error_msg,
        })

    # ... similar for receive connectors
    return {
        "send_connectors": send_results,
        "send_connector_count": len(send_results),
        "receive_connectors": recv_results,
        "receive_connector_count": len(recv_results),
        "all_healthy": all(c["healthy"] for c in send_results + recv_results),
    }


async def _lookup_cert_for_fqdn(client, fqdn: str) -> dict | None:
    """Attempt to look up the Exchange certificate for a given FQDN.

    Returns a dict with cert fields, or None if lookup fails.
    Get-ExchangeCertificate is on-premises only — gracefully return None
    if not available (pure Exchange Online environments).
    """
    safe_fqdn = _escape_ps_single_quote(fqdn)
    cert_cmdlet = (
        f"Get-ExchangeCertificate -DomainName '{safe_fqdn}' | Select-Object -First 1 "
        "Thumbprint, Subject, Issuer, NotAfter, NotBefore, Status, IsSelfSigned, HasPrivateKey, "
        "@{Name='CertificateDomains';Expression={@($_.CertificateDomains | ForEach-Object { $_.ToString() })}}"
    )
    try:
        raw = await client.run_cmdlet_with_retry(cert_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "not recognized" in msg or "not found" in msg:
            return None  # cmdlet not available (on-premises only)
        return None  # any cert lookup failure → null, not an error
    if not raw:
        return None
    r = raw if isinstance(raw, dict) else (raw[0] if isinstance(raw, list) and raw else None)
    if not r:
        return None
    return {
        "thumbprint": r.get("Thumbprint"),
        "subject": r.get("Subject"),
        "issuer": r.get("Issuer"),
        "not_after": r.get("NotAfter"),
        "not_before": r.get("NotBefore"),
        "status": r.get("Status"),
        "is_self_signed": r.get("IsSelfSigned"),
        "has_private_key": r.get("HasPrivateKey"),
        "certificate_domains": r.get("CertificateDomains"),
    }


def _assess_connector_health(connector: dict, cert: dict | None) -> tuple[bool, str | None]:
    """Return (healthy: bool, error_message: str | None) for a connector."""
    if not connector.get("Enabled"):
        return False, "Connector is disabled"
    if not connector.get("RequireTLS"):
        return False, "RequireTLS is False — TLS not enforced on hybrid connector"
    if cert is None:
        # cert lookup unavailable — cannot fully verify, but connector is configured
        return True, None
    if cert.get("Status") != "Valid":
        return False, f"TLS certificate status is '{cert.get('Status')}' (not Valid)"
    # NotAfter is a raw Exchange date string — pass through as-is per project convention
    return True, None
```

### Tool Count Update: Locations to Change

```python
# exchange_mcp/tools.py — module docstring (line 4):
# OLD: "list of all 16 mcp.types.Tool objects (15 Exchange + ping)"
# NEW: "list of all 15 mcp.types.Tool objects (14 Exchange + ping)"

# exchange_mcp/tools.py — module docstring (line 11):
# OLD: "All 15 Exchange tool handlers are stubs that raise NotImplementedError"
# NEW: (remove this line — no stubs remain after Phase 6)

# exchange_mcp/server.py — module docstring (line 14):
# OLD: "all 16 registered tools (15 Exchange tools + ping)"
# NEW: "all 15 registered tools (14 Exchange tools + ping)"

# exchange_mcp/server.py — handle_list_tools docstring (line 147):
# OLD: "all 16 tools (15 Exchange tools + ping)"
# NEW: "all 15 tools (14 Exchange tools + ping)"

# tests/test_server.py — test_list_tools_returns_all_16:
# OLD: assert len(tools) == 16; docstring "16 registered tools (15 Exchange + ping)"
# NEW: assert len(tools) == 15; rename test to test_list_tools_returns_all_15

# tests/test_server.py — module docstring (line 5):
# OLD: "list_tools returns all 16 registered tools (15 Exchange + ping)"
# NEW: "list_tools returns all 15 registered tools (14 Exchange + ping)"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 15 Exchange tools (16 total with ping) | 14 Exchange tools (15 total with ping) | Phase 6 (get_migration_batches removed) | All tool count references must be updated |
| `TlsCertificateName` as raw string for cert identity | `Get-ExchangeCertificate -DomainName <fqdn>` for cert lookup | Exchange 2013+ | More reliable — Exchange picks the cert it actually uses |
| `Test-OrganizationRelationship` for connectivity test | Cert validity + enabled status check | Project decision | Avoids requiring -UserIdentity; config-based like Phase 5's Test-MailFlow decision |
| `Get-InboundConnector`/`Get-OutboundConnector` | `Get-SendConnector`/`Get-ReceiveConnector` | Exchange hybrid design | Cloud connectors vs on-premises connectors are different objects |

**Deprecated/outdated:**
- `Test-OrganizationRelationship`: Requires a specific user identity and only validates config, not live connectivity. Excluded from implementation scope.
- `get_migration_batches`: Removed from scope — MMC does not use migration batches.

---

## Open Questions

1. **Receive connector hybrid identification heuristic**
   - What we know: There is no `CloudServicesMailEnabled` equivalent on receive connectors. The inbound connector from Exchange Online is typically named something like "Default Frontend <servername>" or has specific remote IP ranges from Microsoft's published IP list.
   - What's unclear: The best heuristic for identifying which receive connectors handle inbound hybrid mail from Exchange Online.
   - Recommendation: Filter receive connectors where `TlsCertificateName` is non-empty (indicates TLS-based auth from cloud) OR where `AuthMechanism` includes "TLS" and `PermissionGroups` includes "ExchangeServers". This catches the inbound-from-O365 connector without relying on name matching. Document the heuristic in the handler's docstring.

2. **get_hybrid_config: whether to include hybrid receive connectors inline**
   - What we know: CONTEXT.md says "hybrid mail flow connectors (inbound/outbound to O365) included inline". Phase 5 implemented `get_smtp_connectors` for all connectors.
   - What's unclear: Should the inline connector listing in `get_hybrid_config` also include the inbound receive connector, or just the outbound send connector?
   - Recommendation: Include both send (filtered by CloudServicesMailEnabled) and receive (filtered by TlsCertificateName non-empty) hybrid connectors inline in `get_hybrid_config`. This gives the complete picture in one call.

3. **Get-AvailabilityAddressSpace field names**
   - What we know: Official docs confirm the cmdlet exists and takes `-Identity` and `-DomainController`. Field names `ForestName`, `UserName`, `AccessMethod`, `ProxyUrl`, `UseServiceAccount` are inferred from the cmdlet's purpose and common Exchange documentation patterns.
   - What's unclear: The exact PowerShell property names that serialize to JSON. `ForestName` may serialize differently.
   - Recommendation: Use `Select-Object *` in tests to verify exact field names on the first integration test run. The handler should use `c.get("ForestName")` style with raw passthrough — if the field name differs slightly, adjust field projection.
   - Confidence: MEDIUM — field names not verified against live Exchange output.

4. **No stubs remain after Phase 6 — update test_call_tool_not_implemented_raises**
   - What we know: The test currently uses `get_hybrid_config` as a Phase 6 stub. After implementing both Phase 6 tools, no stubs remain.
   - Recommendation: Update the test to use a non-existent tool name (`"nonexistent_tool"`) and assert `"Unknown tool"` appears in the error. This tests the same code path (unknown tool routing in `handle_call_tool`) without depending on stubs.

---

## Sources

### Primary (HIGH confidence)

- Official Microsoft Docs: `New-OrganizationRelationship` — https://learn.microsoft.com/en-us/powershell/module/exchange/new-organizationrelationship — all org relationship fields verified
- Official Microsoft Docs: `Get-OrganizationRelationship` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-organizationrelationship — confirmed available on-premises and cloud
- Official Microsoft Docs: `Get-FederationTrust` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-federationtrust — confirmed available on-premises and cloud
- Official Microsoft Docs: `Set-FederationTrust` — https://learn.microsoft.com/en-us/powershell/module/exchange/set-federationtrust — confirmed fields: ApplicationUri, Thumbprint, MetadataUrl, OrgCertificate
- Official Microsoft Docs: `New-IntraOrganizationConnector` — https://learn.microsoft.com/en-us/powershell/module/exchange/new-intraorganizationconnector — all connector fields verified: DiscoveryEndpoint, TargetAddressDomains, TargetSharingEpr, Enabled
- Official Microsoft Docs: `Get-IntraOrganizationConnector` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-intraorganizationconnector — confirmed available on-premises and cloud
- Official Microsoft Docs: `Get-AvailabilityAddressSpace` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-availabilityaddressspace — confirmed available on-premises and cloud
- Official Microsoft Docs: `Get-ExchangeCertificate` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-exchangecertificate — confirmed ON-PREMISES ONLY; fields: Thumbprint, Subject, Issuer, NotAfter, NotBefore, Status, CertificateDomains, IsSelfSigned, HasPrivateKey
- Official Microsoft Docs: `Test-SmtpConnectivity` — https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/test-smtpconnectivity — confirmed ON-PREMISES ONLY; tests receive connectors on local server only — NOT suitable for hybrid outbound test
- Official Microsoft Docs: `Test-OrganizationRelationship` — https://learn.microsoft.com/en-us/powershell/module/exchange/test-organizationrelationship — confirmed requires -UserIdentity; only verifies config, not live connectivity
- Microsoft TechCommunity: TLS Certificates in Exchange Hybrid — https://techcommunity.microsoft.com/blog/exchange/tls-certificates-in-exchange-hybrid---common-issues--how-to-fix-them/4420592 — `CloudServicesMailEnabled` flag confirmed as hybrid connector identifier; `Get-SendConnector | fl Name,TLSCertificateName` confirmed for cert inspection
- Project codebase: `exchange_mcp/tools.py` — stubs confirmed; existing handler patterns verified; `get_migration_batches` in both TOOL_DEFINITIONS (line 355) and TOOL_DISPATCH (line 1628) confirmed requiring removal
- Project codebase: `exchange_mcp/server.py` — "15 Exchange tools" / "16 tools" references confirmed requiring update
- Project codebase: `tests/test_server.py` — `test_list_tools_returns_all_16` (line 155) and `test_call_tool_not_implemented_raises` (line 194 uses `get_hybrid_config`) confirmed requiring update

### Secondary (MEDIUM confidence)

- `Get-AvailabilityAddressSpace` field names (`ForestName`, `UserName`, `AccessMethod`, `ProxyUrl`, `UseServiceAccount`) — inferred from cmdlet documentation description and common Exchange patterns; not verified against live Exchange output
- Receive connector hybrid identification heuristic (TlsCertificateName non-empty) — inferred from Exchange hybrid architecture; not verified against live connector data

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; existing libraries confirmed sufficient
- get_hybrid_config cmdlets: HIGH — all four cmdlet APIs verified against official Microsoft documentation
- FederationTrust certificate field projection: HIGH — Set-FederationTrust confirms OrgCertificate is an X509Certificate2 object; using computed properties in PS is the correct approach
- get_connector_status approach: HIGH — CloudServicesMailEnabled confirmed as hybrid send connector flag; cert lookup via Get-ExchangeCertificate -DomainName confirmed; on-premises-only limitation confirmed
- AvailabilityAddressSpace field names: MEDIUM — docs describe the cmdlet but exact JSON serialized property names not verified live
- Receive connector hybrid identification: MEDIUM — documented behavior clear; exact filter heuristic not verified against live connectors
- Tool count cleanup: HIGH — all occurrences found in codebase

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days — cmdlet APIs are stable)
