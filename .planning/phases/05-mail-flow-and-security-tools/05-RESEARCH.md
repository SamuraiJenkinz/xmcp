# Phase 5: Mail Flow and Security Tools - Research

**Researched:** 2026-03-20
**Domain:** Exchange PowerShell mail flow/transport cmdlets, DNS CNAME lookups via dnspython, ActiveSync device statistics
**Confidence:** HIGH (cmdlet signatures verified against official Microsoft docs; project patterns verified from live codebase)

---

## Summary

Phase 5 implements six handlers following the exact same pattern established in Phases 3-4: async handler function, `run_cmdlet_with_retry`, friendly not-found error translation, single-dict-vs-list normalization, and registration in `TOOL_DISPATCH`. The stubs are already in `tools.py`; this phase replaces them with working implementations.

Three tool categories have meaningfully different research concerns. Mail flow tools (`check_mail_flow`, `get_transport_queues`, `get_smtp_connectors`) are Exchange-only and run entirely through `run_cmdlet_with_retry`. Security tools split into two subsets: `get_dkim_config` calls Exchange (`Get-DkimSigningConfig`) then validates the CNAME records in DNS using the existing `dns_utils.get_txt_records` helper with `dns.rdatatype.CNAME`; `get_dmarc_status` calls no PowerShell at all — it uses only `dns_utils.get_dmarc_record` and `dns_utils.get_spf_record`, which are already tested and production-ready. `check_mobile_devices` uses `Get-MobileDeviceStatistics -Mailbox`.

Key architectural discovery: `Get-DkimSigningConfig` is **Exchange Online only** (cloud-based service). The project architecture targets on-premises Exchange 2019 via the ExchangeOnlineManagement module. DKIM signing config via PowerShell requires the Exchange Online connection. The codebase already connects via `Connect-ExchangeOnline`, so `Get-DkimSigningConfig` will work as long as the hybrid/cloud tenant is in scope. CNAME validation requires extending `dns_utils` to support CNAME lookups (`dns.rdatatype.CNAME` confirmed present in the installed dnspython 2.8.0).

**Primary recommendation:** Implement all six handlers in `tools.py` following the Phases 3-4 conventions exactly. Use `Get-Queue` (on-premises) for transport queues, `Get-SendConnector`/`Get-ReceiveConnector` for SMTP connectors, `Get-DkimSigningConfig` for DKIM, pure `dns_utils` for DMARC/SPF, `Get-MobileDeviceStatistics -Mailbox` for devices. Add a `get_cname_record()` function to `dns_utils.py` for DKIM DNS validation.

---

## Standard Stack

The project stack is locked. No new dependencies are needed.

### Core (all already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Exchange PowerShell | ExchangeOnlineManagement | All Exchange cmdlets | Project-wide decision |
| dnspython | >=2.8.0 | DNS lookups — TXT, CNAME | Already in pyproject.toml; `dns.rdatatype.CNAME` confirmed available |
| mcp | >=1.0.0 | MCP server framework | Project-wide decision |
| pytest / pytest-asyncio | >=9.0.2 / >=1.3.0 | Tests | Project-wide decision |

### No New Dependencies

All six tools can be implemented with the existing stack. No additional packages required.

**Installation:** N/A — all packages already present in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

All code lives in two files, matching Phases 3-4:

```
exchange_mcp/
├── dns_utils.py         # Add get_cname_record() function here
└── tools.py             # Add all six handler functions here; update TOOL_DISPATCH
tests/
└── test_tools_phase5.py # New test file, same structure as test_tools_dag.py
```

No new files except the test file. No new modules. No handlers directory — the prior phase decisions kept everything in `tools.py`.

### Pattern 1: Standard Exchange Handler (from Phases 3-4)

**What:** Async handler, single or multiple `run_cmdlet_with_retry` calls, not-found error translation, dict/list normalization, structured return.

**When to use:** All Exchange-backed tools (check_mail_flow, get_transport_queues, get_smtp_connectors, get_dkim_config, check_mobile_devices).

```python
# Source: tools.py lines 684-1000 (Phase 3-4 established pattern)
async def _handler_name(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    param = arguments.get("param_name", "").strip()
    if not param:
        raise RuntimeError("param_name is required. ...")
    safe = _escape_ps_single_quote(param)

    cmdlet = (
        f"Get-SomeCmdlet -Identity '{safe}' | Select-Object "
        "Field1, Field2, Field3"
    )

    try:
        raw = await client.run_cmdlet_with_retry(cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"Friendly error message for '{param}'. ..."
            ) from None
        raise

    # Normalize single dict vs list
    result = raw if isinstance(raw, dict) else (raw[0] if raw else {})

    return {
        "field1": result.get("Field1"),
        "field2": result.get("Field2"),
    }
```

### Pattern 2: Pure DNS Handler (get_dmarc_status)

**What:** Handler calls no Exchange PowerShell. Uses `dns_utils` directly.

**When to use:** `get_dmarc_status` only — pure DNS, no client required.

```python
# Source: dns_utils.py — get_dmarc_record() and get_spf_record() already exist
async def _get_dmarc_status_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    # client may be None — that is fine for this DNS-only tool
    domain = arguments.get("domain", "").strip().lower()
    if not domain:
        raise RuntimeError("domain is required.")

    try:
        dmarc = await dns_utils.get_dmarc_record(domain)
        spf = await dns_utils.get_spf_record(domain)
    except LookupError as exc:
        raise RuntimeError(f"DNS lookup failed for '{domain}': {exc}") from None

    return {
        "domain": domain,
        "dmarc": dmarc,
        "spf": spf,
    }
```

### Pattern 3: Hybrid Exchange + DNS Handler (get_dkim_config)

**What:** Exchange call to `Get-DkimSigningConfig`, then DNS CNAME validation using `get_cname_record()` added to `dns_utils`.

**When to use:** `get_dkim_config` only.

```python
# Requires new get_cname_record() in dns_utils.py
# dns.rdatatype.CNAME = 5 (confirmed available)
async def get_cname_record(name: str) -> str | None:
    """Resolve a CNAME record, returning the target or None if not found."""
    now = time.monotonic()
    cache_key = f"CNAME:{name}"
    if cache_key in _cache:
        records, expiry = _cache[cache_key]
        if now < expiry:
            return records[0] if records else None

    try:
        answer = await dns.asyncresolver.resolve(name, dns.rdatatype.CNAME)
        target = str(answer[0].target).rstrip(".")
        ttl = int(answer.rrset.ttl) if answer.rrset else _DEFAULT_TTL
        _cache[cache_key] = ([target], now + ttl)
        return target
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        _cache[cache_key] = ([], now + _DEFAULT_NEGATIVE_TTL)
        return None
    except dns.exception.DNSException as exc:
        raise LookupError(f"CNAME lookup failed for '{name}': {exc}") from exc
```

### Pattern 4: Multi-Server Iteration with Partial Results

**What:** Iterate over a list (servers, domains, etc.), collecting per-item results. Failures produce error entries rather than aborting the whole call.

**When to use:** `get_transport_queues` (iterate over transport servers), `get_smtp_connectors` (two separate cmdlets for send/receive).

**Example from Phase 4 (`_get_dag_health_handler`):**
```python
# Source: tools.py line 951-994 — per-server iteration with try/except per iteration
server_results = []
for member_name in members:
    try:
        raw = await client.run_cmdlet_with_retry(health_cmdlet)
    except RuntimeError as exc:
        server_results.append({
            "server": member_name,
            "copies": [],
            "error": f"Unable to query server '{member_name}': {exc}",
        })
        continue
    # ... process successful result
```

### Anti-Patterns to Avoid

- **Calling `Test-MailFlow`:** Sends actual test messages — side effects in production. Decision is locked to config-based routing inference.
- **Calling `Get-ExchangeServer` for transport server list in `get_transport_queues`:** Requires a separate call. Use `Get-Queue` with no `-Server` parameter — it collects all servers by default via the server-side parameter set.
- **ConvertTo-Json without -Depth 10:** Exchange objects nest deeply. Always rely on `ExchangeClient._build_cmdlet_script()` which wraps the cmdlet with `| ConvertTo-Json -Depth 10` automatically.
- **Storing state between calls:** Per-call PSSession — no state to persist.
- **Building a custom CNAME resolver:** `dns.rdatatype.CNAME` exists in the installed dnspython. Add `get_cname_record()` to `dns_utils.py`, not inline in the handler.

---

## Cmdlet Reference (Verified from Official Docs)

### check_mail_flow: Config-Based Route Inference

**Decision:** Infer routing from connector config — no `Test-MailFlow`. Two calls needed:

**Call 1 — Get transport servers:**
```powershell
Get-TransportService | Select-Object Name, InternalDNSAdapterEnabled, ExternalDNSAdapterEnabled
```
Returns list of all Mailbox transport servers. Use for "source" context.

**Call 2 — Get send connectors (route selection):**
```powershell
Get-SendConnector | Select-Object Name, AddressSpaces, DNSRoutingEnabled, SmartHosts, RequireTLS, TlsDomain, Enabled, SourceTransportServers, Fqdn
```
AddressSpaces determines which connector handles the recipient domain.

**Call 3 — Get receive connectors (for inbound context):**
```powershell
Get-ReceiveConnector | Select-Object Name, Bindings, RemoteIPRanges, AuthMechanism, RequireTLS, Enabled, TransportRole, Server
```

**Route inference algorithm:**
1. Extract recipient domain from `recipient` parameter.
2. Find the matching send connector by comparing `AddressSpaces` patterns against recipient domain.
3. If multiple connectors match, highest-cost AddressSpace (most specific) wins.
4. Identify TLS requirement from `RequireTLS` and `TlsDomain` on matched connector.
5. Report: source → matched connector name → smart host or DNS → destination domain.

**Key fields confirmed from official docs:**
- `Get-SendConnector`: `AddressSpaces`, `DNSRoutingEnabled`, `SmartHosts`, `RequireTLS`, `TlsDomain`, `Enabled`, `SourceTransportServers`, `Fqdn`, `MaxMessageSize`
- `Get-TransportService`: `Name`, `InternalDNSAdapterEnabled`, `ExternalDNSAdapterEnabled`

### get_transport_queues: Get-Queue

**Confirmed fields from official docs (queue-properties):**
- `Identity` — `<Server>\<Queue>` format
- `MessageCount` — number of messages
- `DeliveryType` — see DeliveryType values below
- `NextHopDomain` — next hop name (domain, DAG, AD site, etc.)
- `NextHopConnector` — GUID of connector
- `NextHopCategory` — `Internal` or `External`
- `Status` — `Active`, `Connecting`, `Suspended`, `Ready`, `Retry`
- `LastError` — last connection error string
- `Velocity` — drain rate (positive = healthy, negative = backing up)

**Valid DeliveryType values (confirmed from official docs):**
`SmtpDeliveryToMailbox`, `SmartHostConnectorDelivery`, `DnsConnectorDelivery`, `SmtpRelayToRemoteAdSite` (full name: `SmtpRelayToRemoteActiveDirectorySite`), `SmtpRelayToDag`, `SmtpRelayToConnectorSourceServers`, `SmtpRelayToServers`, `ShadowRedundancy`, `Unreachable`, `Undefined`, `DeliveryAgent`, `NonSmtpGatewayDelivery`

**Cmdlet for all queues across all servers:**
```powershell
Get-Queue -ResultSize Unlimited | Select-Object Identity, MessageCount, DeliveryType, NextHopDomain, NextHopConnector, NextHopCategory, Status, LastError, Velocity
```
Note: `Get-Queue` without `-Server` runs on the local server. To get all servers, need to iterate via `Get-TransportService` or use `Get-QueueDigest` (but that only returns queues with 10+ messages by default). The correct pattern is to get all transport servers first, then call `Get-Queue -Server <name>` per server.

**Confirmed parameter sets from official docs:**
- `Get-Queue [-Server <name>] [-Filter <string>]` — Server parameter set
- `Get-Queue [[-Identity] <QueueIdentity>]` — Identity parameter set
- Server and Identity cannot be combined

**Default backlog threshold recommendation:** 50 messages (visible single-digit queues are normal; 50+ indicates a problem worth flagging). The tool description says default 100 — use 100 as the documented default to match the tool schema already in `tools.py`.

### get_smtp_connectors: Get-SendConnector + Get-ReceiveConnector

**Get-SendConnector confirmed fields:**
```powershell
Get-SendConnector | Select-Object Name, AddressSpaces, DNSRoutingEnabled, SmartHosts, RequireTLS, TlsDomain, TlsCertificateName, Enabled, Fqdn, MaxMessageSize, SourceTransportServers, AuthenticationCredential, CloudServicesMailEnabled, UseExternalDNSServersEnabled
```

**Get-ReceiveConnector confirmed fields:**
```powershell
Get-ReceiveConnector | Select-Object Name, Bindings, RemoteIPRanges, AuthMechanism, PermissionGroups, RequireTLS, TlsCertificateName, Enabled, TransportRole, Server, MaxMessageSize, MaxRecipientsPerMessage, Fqdn
```

**Connector type filtering** is decided by the `connector_type` parameter (`send`, `receive`, `all`). Run whichever cmdlets are needed. For `all`, run both and combine results under `send_connectors` and `receive_connectors` keys.

**Key insight:** `AddressSpaces` on Send connectors is a collection — serializes in PowerShell JSON as an array of objects with `Domain`, `AddressSpaceType`, `Cost` fields. Use `@($_.AddressSpaces | ForEach-Object { $_.ToString() })` or Select the `.ToString()` to flatten.

### get_dkim_config: Get-DkimSigningConfig + DNS CNAME validation

**Important: Exchange Online only.** From official docs: "This cmdlet is available only in the cloud-based service." Project uses `Connect-ExchangeOnline` which connects to Exchange Online, so this works.

**Confirmed cmdlet:**
```powershell
# All domains:
Get-DkimSigningConfig | Select-Object Name, Enabled, Status, Selector1CNAME, Selector2CNAME, KeyCreationTime, RotateOnDate

# Specific domain:
Get-DkimSigningConfig -Identity 'contoso.com' | Select-Object Name, Enabled, Status, Selector1CNAME, Selector2CNAME, KeyCreationTime, RotateOnDate
```

**Confirmed fields from official Microsoft DKIM docs:**
- `Name` — domain name
- `Enabled` — boolean
- `Status` — `Valid`, `CnameMissing`, `NoDKIMKeys`
- `Selector1CNAME` — expected CNAME target for `selector1._domainkey.<domain>`
- `Selector2CNAME` — expected CNAME target for `selector2._domainkey.<domain>`
- `KeyCreationTime` — when key pair was created
- `RotateOnDate` — when key rotation is scheduled

**DNS validation logic for get_cname_record:**
1. Look up CNAME for `selector1._domainkey.<domain>` and `selector2._domainkey.<domain>`
2. Compare resolved target to `Selector1CNAME` / `Selector2CNAME` from Exchange
3. Return `dns_match: true/false` per selector — answers "is DKIM working?"

**Optional domain parameter behavior:**
- If `domain` provided: call `Get-DkimSigningConfig -Identity '<domain>'`
- If omitted: call `Get-DkimSigningConfig` (returns all) — normalize as list

### get_dmarc_status: Pure DNS (no PowerShell)

**All infrastructure already exists in `dns_utils.py`:**
- `get_dmarc_record(domain)` — queries `_dmarc.<domain>` TXT, parses, returns structured dict
- `get_spf_record(domain)` — queries `<domain>` TXT for SPF, parses, returns structured dict

**Design decision (Claude's Discretion):** Single domain input. Multi-domain is less natural for LLM tool-calling — an LLM asking "check DMARC for contoso.com and fabrikam.com" will simply call the tool twice. Single domain keeps the response compact and clear.

**Return structure:**
```python
{
    "domain": "contoso.com",
    "dmarc": {
        "found": True,
        "domain": "contoso.com",
        "version": "DMARC1",
        "policy": "reject",
        "subdomain_policy": "reject",
        "pct": 100,
        "rua": "mailto:dmarc@contoso.com",
        "ruf": None,
        "adkim": "r",
        "aspf": "r",
        "raw": "v=DMARC1; p=reject; ..."
    },
    "spf": {
        "found": True,
        "domain": "contoso.com",
        "version": "spf1",
        "mechanisms": ["include:spf.protection.outlook.com", "-all"],
        "all": "-all",
        "raw": "v=spf1 include:spf.protection.outlook.com -all"
    }
}
```

### check_mobile_devices: Get-MobileDeviceStatistics

**Confirmed cmdlet (official docs):**
```powershell
Get-MobileDeviceStatistics -Mailbox 'user@contoso.com' | Select-Object DeviceFriendlyName, DeviceModel, DeviceOS, DeviceUserAgent, DeviceID, DeviceType, LastSyncAttemptTime, Status, DeviceAccessState, DeviceWipeSentTime, DeviceWipeRequestTime, DeviceWipeAckTime, LastDeviceWipeRequestor
```

**Confirmed parameter sets:**
- `-Mailbox <MailboxIdParameter>` — by mailbox UPN/email (use this)
- `-Identity <MobileDeviceIdParameter>` — by specific device object

**Available on:** Exchange Server 2013, 2016, 2019, SE, Exchange Online (confirmed both environments).

**Key wipe history fields confirmed from official docs:**
The docs confirm this cmdlet "returns a list of statistics about each mobile device" and the `-ShowRecoveryPassword` switch can expose recovery passwords. The `DeviceWipeSentTime`, `DeviceWipeRequestTime`, `DeviceWipeAckTime`, `LastDeviceWipeRequestor` fields are the security incident use case.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DMARC record parsing | Custom regex parser | `dns_utils.parse_dmarc()` | Already implemented, tested, RFC 7489 compliant |
| SPF record parsing | Custom parser | `dns_utils.parse_spf()` | Already implemented, tested, RFC 7208 compliant |
| DNS TXT caching | Custom cache dict | `dns_utils.get_txt_records()` | TTL-respecting cache already built |
| CNAME lookup | Custom resolver | Extend `dns_utils` with `get_cname_record()` | Same pattern as existing TXT resolver — keep cache in same module |
| Queue server iteration | Custom discovery | `Get-TransportService` → iterate `Get-Queue -Server` | Exchange already knows all transport servers |
| AddressSpaces matching | Custom SMTP domain matching | PowerShell string matching in cmdlet | PowerShell handles edge cases (wildcards, cost) natively |
| Multiple PowerShell scripts | Per-cmdlet script builder | `ExchangeClient.run_cmdlet_with_retry()` | Handles retries, connect/disconnect, JSON parsing |

**Key insight:** The DNS utilities in `dns_utils.py` are production-ready. `get_dmarc_status` should import and call them directly — no DNS code belongs in `tools.py`.

---

## Common Pitfalls

### Pitfall 1: Get-Queue Scope — Local Server Only

**What goes wrong:** `Get-Queue` without `-Server` returns queues for the server where the PowerShell session runs, not all servers. In Exchange Online sessions, `Get-Queue` may not be available at all (it's an on-premises cmdlet).

**Why it happens:** The cmdlet is designed for on-premises use on the local transport server. Exchange Online has no equivalent (cloud queues aren't exposed this way).

**How to avoid:**
1. First call `Get-TransportService` to get all transport server names.
2. Then iterate: `Get-Queue -Server '<server_name>'` per server.
3. Aggregate results per-server in Python.
4. Handle `RuntimeError` per server for partial results (same pattern as `_get_dag_health_handler`).

**Warning signs:** Queue results look incomplete (only one server's queues returned).

### Pitfall 2: Get-DkimSigningConfig — Exchange Online Module Required

**What goes wrong:** Calling `Get-DkimSigningConfig` against an on-premises Exchange Management Shell session (not Exchange Online) will fail with "command not found".

**Why it happens:** The cmdlet is Exchange Online only. However, the project already uses `Connect-ExchangeOnline`, so this should work as long as the DKIM config scope includes the organization's accepted domains.

**How to avoid:** Use the existing `run_cmdlet_with_retry` which already uses `Connect-ExchangeOnline`. No special handling needed. If the organization has no Exchange Online DKIM configuration, the cmdlet will return empty results (not an error).

**Warning signs:** RuntimeError containing "not recognized" or "command not found" — indicates Exchange Online connection is failing.

### Pitfall 3: AddressSpaces Serialization

**What goes wrong:** `AddressSpaces` on `Get-SendConnector` is a `SmtpAddressSpace` collection. `ConvertTo-Json -Depth 10` may serialize it as an array of objects with opaque internal fields, or may use `.ToString()` automatically — behavior varies by Exchange version.

**Why it happens:** Exchange PowerShell complex types don't always serialize cleanly to JSON. The `ActivationPreference` issue in Phase 4 (serialized as both dict and list-of-KV depending on Exchange version) is the same class of problem.

**How to avoid:** Explicitly project `AddressSpaces` to strings in the PowerShell cmdlet:
```powershell
@{Name='AddressSpaces'; Expression={ @($_.AddressSpaces | ForEach-Object { $_.ToString() }) }}
```
Similarly for `SmartHosts`, `SourceTransportServers`, `RemoteIPRanges` — any multi-valued property.

**Warning signs:** Tests fail because `address_spaces` is a list of dicts instead of a list of strings.

### Pitfall 4: get_transport_queues Backlog Flag Visibility

**What goes wrong:** The tool returns queues but the LLM can't spot which ones are over the threshold without doing math.

**Why it happens:** Raw queue data doesn't highlight problems.

**How to avoid:** Add an explicit `over_threshold: True/False` boolean field on each queue object, and a top-level `servers_with_backlog` count or list in the result. The context decisions explicitly require: "backlog flagging should be obvious in the output."

### Pitfall 5: check_mobile_devices — Empty Device List vs Error

**What goes wrong:** A user with no mobile devices returns an empty list from `Get-MobileDeviceStatistics`. An invalid UPN raises a not-found error.

**Why it happens:** Exchange returns empty results for valid users with no partnerships — this is not an error condition.

**How to avoid:** Handle the not-found error (invalid UPN) with a friendly message. Treat an empty result list as a valid "no devices" response, not an error. The CONTEXT.md decision says "return ALL devices ever synced, including stale partnerships" — an empty list is fine.

### Pitfall 6: check_mail_flow — Route Inference Complexity

**What goes wrong:** Connector matching logic for `AddressSpaces` can be complex. Exchange supports wildcard domains (`*`), cost values, and multiple connectors.

**Why it happens:** Mail routing in Exchange involves the categorizer evaluating multiple connectors with cost and address space specificity rules.

**How to avoid:** Keep the implementation simple and honest. Match recipient domain against `AddressSpaces` patterns. If multiple connectors match, prefer the most specific (longest matching prefix) or flag ambiguity. Do NOT attempt to replicate the full Exchange categorizer logic — describe the connector candidates and let the LLM reason about it.

### Pitfall 7: DKIM CNAME Format Changed May 2025

**What goes wrong:** The expected CNAME format changed in May 2025. New custom domains use a different format (`selector1-contoso-com._domainkey.contoso.n-v1.dkim.mail.microsoft`) vs old format (`selector1-contoso-com._domainkey.contoso.onmicrosoft.com`).

**Why it happens:** Microsoft updated the DKIM infrastructure. The `Selector1CNAME` field from `Get-DkimSigningConfig` always returns the correct expected value for the domain — old or new format.

**How to avoid:** Do NOT hardcode the expected CNAME format. Always use `Selector1CNAME`/`Selector2CNAME` values from Exchange as the source of truth. The DNS CNAME lookup validates against these values, not against a hardcoded template.

---

## Code Examples

### check_mail_flow: Route Inference Pattern

```python
# Source: tools.py — new handler following Phase 4 pattern
async def _check_mail_flow_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    sender = arguments.get("sender", "").strip()
    recipient = arguments.get("recipient", "").strip()
    _validate_upn(sender)
    _validate_upn(recipient)

    safe_sender = _escape_ps_single_quote(sender)
    safe_recipient = _escape_ps_single_quote(recipient)

    # Extract recipient domain for connector matching
    recipient_domain = recipient.split("@")[1].lower()

    # Get send connectors — route selection
    send_conn_cmdlet = (
        "Get-SendConnector | Select-Object "
        "Name, Enabled, "
        "@{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}}, "
        "DNSRoutingEnabled, "
        "@{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}, "
        "RequireTLS, TlsDomain, Fqdn, "
        "@{Name='SourceTransportServers';Expression={@($_.SourceTransportServers | ForEach-Object { $_.Name })}}"
    )

    # Get receive connectors — inbound context
    recv_conn_cmdlet = (
        "Get-ReceiveConnector | Select-Object "
        "Name, Enabled, AuthMechanism, PermissionGroups, RequireTLS, "
        "TransportRole, Server, "
        "@{Name='RemoteIPRanges';Expression={@($_.RemoteIPRanges | ForEach-Object { $_.ToString() })}}"
    )

    try:
        send_raw = await client.run_cmdlet_with_retry(send_conn_cmdlet)
        recv_raw = await client.run_cmdlet_with_retry(recv_conn_cmdlet)
    except RuntimeError:
        raise

    send_list = send_raw if isinstance(send_raw, list) else ([send_raw] if isinstance(send_raw, dict) and send_raw else [])
    recv_list = recv_raw if isinstance(recv_raw, list) else ([recv_raw] if isinstance(recv_raw, dict) and recv_raw else [])

    # Match connectors to recipient domain
    matching_connectors = []
    for conn in send_list:
        if not conn.get("Enabled"):
            continue
        for addr_space in (conn.get("AddressSpaces") or []):
            addr_lower = addr_space.lower()
            if (recipient_domain in addr_lower or
                    addr_lower.startswith("*") or
                    addr_lower == "*"):
                matching_connectors.append(conn)
                break

    return {
        "sender": sender,
        "recipient": recipient,
        "recipient_domain": recipient_domain,
        "matching_send_connectors": matching_connectors,
        "matching_connector_count": len(matching_connectors),
        "receive_connectors": recv_list,
        "routing_summary": _build_routing_summary(recipient_domain, matching_connectors),
    }
```

### get_transport_queues: Per-Server Pattern

```python
# Pattern: get transport servers first, then per-server queue query
servers_cmdlet = "Get-TransportService | Select-Object Name"

# Per server:
queue_cmdlet = (
    f"Get-Queue -Server '{safe_server}' -ResultSize Unlimited | Select-Object "
    "Identity, MessageCount, DeliveryType, NextHopDomain, NextHopCategory, "
    "Status, LastError, Velocity"
)

# Backlog flag — add to each queue object:
queue_entry = {
    "identity": q.get("Identity"),
    "message_count": count,
    "over_threshold": count > threshold,  # explicit boolean
    "delivery_type": q.get("DeliveryType"),
    "next_hop_domain": q.get("NextHopDomain"),
    "status": q.get("Status"),
    "last_error": q.get("LastError"),
    "velocity": q.get("Velocity"),
}
```

### get_dkim_config: Exchange + DNS Combined Pattern

```python
# Source: new handler using existing dns_utils pattern
async def _get_dkim_config_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    domain = arguments.get("domain", "").strip().lower()
    safe = _escape_ps_single_quote(domain) if domain else ""

    if domain:
        dkim_cmdlet = (
            f"Get-DkimSigningConfig -Identity '{safe}' | Select-Object "
            "Name, Enabled, Status, Selector1CNAME, Selector2CNAME, KeyCreationTime, RotateOnDate"
        )
    else:
        dkim_cmdlet = (
            "Get-DkimSigningConfig | Select-Object "
            "Name, Enabled, Status, Selector1CNAME, Selector2CNAME, KeyCreationTime, RotateOnDate"
        )

    try:
        raw = await client.run_cmdlet_with_retry(dkim_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if domain and ("couldn't find" in msg or "object not found" in msg):
            raise RuntimeError(
                f"No DKIM signing configuration found for domain '{domain}'."
            ) from None
        raise

    configs = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])

    results = []
    for cfg in configs:
        cfg_domain = (cfg.get("Name") or "").lower()
        sel1_cname = cfg.get("Selector1CNAME")
        sel2_cname = cfg.get("Selector2CNAME")

        # DNS CNAME validation
        sel1_dns = None
        sel2_dns = None
        sel1_match = None
        sel2_match = None
        if cfg_domain:
            try:
                sel1_dns = await dns_utils.get_cname_record(f"selector1._domainkey.{cfg_domain}")
                sel2_dns = await dns_utils.get_cname_record(f"selector2._domainkey.{cfg_domain}")
                sel1_match = (sel1_dns is not None and sel1_cname is not None and
                              sel1_dns.lower().rstrip(".") == sel1_cname.lower().rstrip("."))
                sel2_match = (sel2_dns is not None and sel2_cname is not None and
                              sel2_dns.lower().rstrip(".") == sel2_cname.lower().rstrip("."))
            except LookupError:
                pass  # DNS error — leave match as None (unknown)

        results.append({
            "domain": cfg_domain,
            "enabled": cfg.get("Enabled"),
            "status": cfg.get("Status"),
            "selector1_cname_expected": sel1_cname,
            "selector1_cname_published": sel1_dns,
            "selector1_dns_match": sel1_match,
            "selector2_cname_expected": sel2_cname,
            "selector2_cname_published": sel2_dns,
            "selector2_dns_match": sel2_match,
            "key_creation_time": cfg.get("KeyCreationTime"),
            "rotate_on_date": cfg.get("RotateOnDate"),
        })

    return {
        "domains": results,
        "domain_count": len(results),
    }
```

### check_mobile_devices: Get-MobileDeviceStatistics Pattern

```python
# Source: official docs — use -Mailbox parameter
devices_cmdlet = (
    f"Get-MobileDeviceStatistics -Mailbox '{safe}' | Select-Object "
    "DeviceFriendlyName, DeviceModel, DeviceOS, DeviceUserAgent, DeviceID, DeviceType, "
    "LastSyncAttemptTime, Status, DeviceAccessState, "
    "DeviceWipeSentTime, DeviceWipeRequestTime, DeviceWipeAckTime, LastDeviceWipeRequestor"
)

# Return ALL devices (including stale) — no filter
# Empty list = valid "no devices" response
devices = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])

return {
    "email_address": email,
    "device_count": len(devices),
    "devices": [
        {
            "friendly_name": d.get("DeviceFriendlyName"),
            "model": d.get("DeviceModel"),
            "os": d.get("DeviceOS"),
            "user_agent": d.get("DeviceUserAgent"),
            "device_id": d.get("DeviceID"),
            "device_type": d.get("DeviceType"),
            "last_sync": d.get("LastSyncAttemptTime"),
            "status": d.get("Status"),
            "access_state": d.get("DeviceAccessState"),
            "wipe_sent_time": d.get("DeviceWipeSentTime"),
            "wipe_request_time": d.get("DeviceWipeRequestTime"),
            "wipe_ack_time": d.get("DeviceWipeAckTime"),
            "wipe_requestor": d.get("LastDeviceWipeRequestor"),
        }
        for d in devices
    ],
}
```

### dns_utils: get_cname_record Addition

```python
# Source: dns_utils.py — extend existing module, same cache dict, same pattern
async def get_cname_record(name: str) -> str | None:
    """Resolve a DNS CNAME record, returning the target or None if not found.

    Args:
        name: Fully-qualified hostname to resolve CNAME for.

    Returns:
        CNAME target string (trailing dot stripped) or None if no CNAME exists.

    Raises:
        LookupError: On unexpected DNS failures (network errors, SERVFAIL).
    """
    now = time.monotonic()
    cache_key = f"CNAME:{name}"

    if cache_key in _cache:
        records, expiry = _cache[cache_key]
        if now < expiry:
            return records[0] if records else None

    try:
        answer = await dns.asyncresolver.resolve(name, dns.rdatatype.CNAME)
        target = str(answer[0].target).rstrip(".")
        ttl = int(answer.rrset.ttl) if answer.rrset else _DEFAULT_TTL
        _cache[cache_key] = ([target], now + ttl)
        return target

    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        _cache[cache_key] = ([], now + _DEFAULT_NEGATIVE_TTL)
        return None

    except dns.exception.DNSException as exc:
        raise LookupError(
            f"CNAME lookup failed for '{name}': {type(exc).__name__}: {exc}"
        ) from exc
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Test-MailFlow` cmdlet | Config-based route inference | Project decision | Safe to run in production, no test messages sent |
| DKIM TXT records | CNAME records pointing to Microsoft infrastructure | Microsoft 365 DKIM 2020+ | Handler must look up CNAME, not TXT, to validate |
| Old CNAME format (`selector1-domain._domainkey.tenant.onmicrosoft.com`) | New format with DynamicPartitionCharacter (`selector1-domain._domainkey.tenant.X-v1.dkim.mail.microsoft`) | May 2025 | Use `Selector1CNAME` from Exchange as source of truth — do NOT hardcode format |
| `Get-EXOMobileDeviceStatistics` (Exchange Online) | `Get-MobileDeviceStatistics -Mailbox` | Exchange Server 2013+ | On-premises cmdlet is the right one for this hybrid environment |

**Deprecated/outdated:**
- `MapiDelivery` DeliveryType: Not used in Exchange 2013+; included in data for backwards compat only
- `Test-MailFlow`: Sends real test messages; avoid in production use

---

## Open Questions

1. **Get-Queue availability in Exchange Online sessions**
   - What we know: `Get-Queue` is documented as "on-premises only". The project connects via `Connect-ExchangeOnline`.
   - What's unclear: Whether `Get-Queue` is accessible via the ExchangeOnlineManagement module when connected to a hybrid tenant, or if it fails entirely.
   - Recommendation: Add error handling for "not recognized" error from `Get-Queue` — surface a clear message: "Transport queue data requires on-premises Exchange access. This environment may be Exchange Online only." This is the same class of problem as any on-premises-only cmdlet in a cloud session. Consider noting in the tool description that this requires on-premises Exchange connectivity.

2. **Backlog threshold default value (Claude's Discretion)**
   - What we know: Tool schema already documents "Default is 100" in the tool description. Tools.py already has this in the input schema.
   - Recommendation: Use 100 as the default to match the existing tool schema. Do not change the schema now.

3. **check_mail_flow — `Get-Recipient` for internal recipient resolution**
   - What we know: For internal senders/recipients, the routing goes through `SmtpDeliveryToMailbox` directly, not through a send connector.
   - What's unclear: Should the handler detect when sender and recipient are both internal (same Exchange organization) and report "direct mailbox delivery" without connector lookup?
   - Recommendation: Yes — after collecting send connectors, check if recipient domain matches any accepted domain (`Get-AcceptedDomain`). If yes, report as internal mailbox delivery. If no matching connector exists and domain is not accepted, report as unroutable.

---

## Sources

### Primary (HIGH confidence)

- Official Microsoft Docs: `Get-Queue` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-queue
- Official Microsoft Docs: Queue properties — https://learn.microsoft.com/en-us/exchange/mail-flow/queues/queue-properties
- Official Microsoft Docs: Queue DeliveryType values — https://learn.microsoft.com/en-us/exchange/mail-flow/queues/queues
- Official Microsoft Docs: `Get-DkimSigningConfig` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-dkimsigningconfig
- Official Microsoft Docs: DKIM configure — https://learn.microsoft.com/en-us/microsoft-365/security/office-365-security/email-authentication-dkim-configure (includes CNAME format change May 2025)
- Official Microsoft Docs: `Get-MobileDeviceStatistics` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-mobiledevicestatistics
- Official Microsoft Docs: `Get-SendConnector` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-sendconnector
- Official Microsoft Docs: `Get-ReceiveConnector` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-receiveconnector
- Official Microsoft Docs: `Get-TransportService` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-transportservice
- Official Microsoft Docs: `Get-AcceptedDomain` — https://learn.microsoft.com/en-us/powershell/module/exchange/get-accepteddomain
- Project codebase: `dns_utils.py` — confirmed `dns.rdatatype.CNAME` available in installed dnspython 2.8.0
- Project codebase: `tools.py` — all six stubs confirmed, handler pattern verified from Phases 3-4
- Project codebase: `exchange_client.py` — `run_cmdlet_with_retry` API confirmed
- Project codebase: `tests/test_tools_dag.py` — test pattern confirmed (AsyncMock, side_effect lists)

### Tertiary (LOW confidence — not validated against live Exchange)

- Phase 4 precedent for `ActivationPreference` serialization variance: AddressSpaces may exhibit similar variance between dict and list-of-KV forms. LOW confidence on exact JSON shape until tested against live Exchange.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; existing libraries confirmed sufficient
- Cmdlet signatures: HIGH — verified against official Microsoft documentation for each cmdlet
- AddressSpaces serialization: MEDIUM — pattern applies from Phase 4 ActivationPreference lesson; exact JSON shape not tested live
- Get-Queue on-premises scope: MEDIUM — documented behavior clear; runtime behavior in hybrid session unverified
- get_cname_record implementation: HIGH — `dns.rdatatype.CNAME` confirmed present, same pattern as existing `get_txt_records`
- DKIM CNAME format: HIGH — official docs confirm Selector1CNAME field is source of truth regardless of format version

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (30 days — cmdlet APIs are stable; DKIM format change already captured)
