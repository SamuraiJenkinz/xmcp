# Phase 26: Message Trace Tool - Research

**Researched:** 2026-04-06
**Domain:** Exchange Online message trace via Get-MessageTraceV2 + existing Exchange tool pattern
**Confidence:** HIGH

---

## Summary

Phase 26 adds one new MCP tool (`get_message_trace`) to the existing Exchange MCP server. The codebase has a proven, mature tool pattern from 17 prior tools. Research confirmed that Get-MessageTraceV2 is the correct cmdlet (Get-MessageTrace is deprecated as of September 2025), has well-documented parameters that map cleanly to the requirements, and that the existing `run_cmdlet_with_retry` + `_escape_ps_single_quote` pattern handles it without modification.

The primary complexity is not the PowerShell call — it is the input validation rules decided in CONTEXT.md (require sender OR recipient, reject ambiguous names, enforce 10-day max range) and the system prompt disambiguation section. The RBAC verification for INFRA-01 is a manual pre-implementation step (verify Atlas service principal has "Message Tracking" role in EXO RBAC) and does not require code changes.

**Primary recommendation:** Follow the established `_check_mail_flow_handler` pattern exactly. Add the tool definition to `TOOL_DEFINITIONS`, write the handler in `tools.py`, add to `TOOL_DISPATCH`, and append a disambiguation section to `SYSTEM_PROMPT` in `openai_client.py`.

---

## Standard Stack

All infrastructure already exists. No new packages.

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| `exchange_mcp.exchange_client.ExchangeClient` | existing | Runs PowerShell against EXO | All 17 existing tools use this |
| `client.run_cmdlet_with_retry` | existing | Retry-aware EXO cmdlet execution | Standard in all handlers |
| `mcp.types.Tool` | existing | MCP tool registration | Required by MCP SDK |
| `Get-MessageTraceV2` | EXO PowerShell | Exchange Online message trace | Get-MessageTrace deprecated Sep 2025 |
| EXO PowerShell V3 module >= 3.7.0 | installed on server | Required for V2 cmdlets | Documented Microsoft requirement |

### Supporting Helpers (existing in tools.py)
| Helper | Purpose |
|---|---|
| `_escape_ps_single_quote` | Sanitise string inputs before embedding in PS string literals |
| `_validate_upn` | Validate full email address format (regex) |
| `_UPN_RE` | Regex `r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"` |

**Installation:** No new packages required.

---

## Architecture Patterns

### Established Tool Pattern (from existing code)

Every Exchange tool follows this exact structure:

**1. Tool Definition** in `TOOL_DEFINITIONS` list in `exchange_mcp/tools.py`:
```python
# Source: exchange_mcp/tools.py lines 197-219 (check_mail_flow pattern)
types.Tool(
    name="get_message_trace",
    description=(
        "Tracks actual email delivery status for specific messages in Exchange Online. "
        "Use when asked whether an email arrived or was delivered: "
        "'Did my email to bob@contoso.com arrive?', "
        "'Show me emails from alice@contoso.com in the last 24 hours', "
        "'Was the invoice email delivered to finance@partner.com?'. "
        "Do NOT use for mail routing questions — use check_mail_flow for that."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "sender_address": {"type": "string", "description": "..."},
            "recipient_address": {"type": "string", "description": "..."},
            "start_date": {"type": "string", "description": "..."},
            "end_date": {"type": "string", "description": "..."},
            "subject_filter": {"type": "string", "description": "..."},
            "result_size": {"type": "integer", "description": "..."},
        },
        "required": [],
    },
),
```

**2. Handler function** in `exchange_mcp/tools.py`:
```python
# Source: exchange_mcp/tools.py lines 1047-1197 (check_mail_flow_handler pattern)
async def _get_message_trace_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    if client is None:
        raise RuntimeError("Exchange client is not available.")
    # validate inputs, build cmdlet, call run_cmdlet_with_retry, normalize, return
```

**3. Registration** in `TOOL_DISPATCH` dict at bottom of `tools.py`:
```python
# Source: exchange_mcp/tools.py lines 1967-1985
TOOL_DISPATCH: dict[str, Any] = {
    ...
    "get_message_trace": _get_message_trace_handler,
}
```

**4. System prompt section** appended to `SYSTEM_PROMPT` in `chat_app/openai_client.py`.

**5. Tool count** update in server.py docstring (currently says "17 tools", becomes "18 tools").

### Get-MessageTraceV2 PowerShell Pattern

```powershell
# Source: Microsoft Learn official docs (verified April 2026)
# All parameters are optional; no parameter is required by the cmdlet itself.
# Our tool enforces at least sender OR recipient as a guard.

Get-MessageTraceV2 `
    -SenderAddress 'alice@contoso.com' `
    -RecipientAddress 'bob@fabrikam.com' `
    -StartDate '2026-04-05T00:00:00Z' `
    -EndDate '2026-04-06T23:59:59Z' `
    -ResultSize 100 `
    -Subject 'Invoice' `
    -SubjectFilterType 'Contains' `
| Select-Object `
    SenderAddress, RecipientAddress, Received, Status, Subject, `
    MessageTraceId, Size, FromIP, ToIP, ConnectorId `
| ConvertTo-Json -Depth 10
```

Key cmdlet facts (HIGH confidence, verified from official docs):
- Default: returns last 48 hours, up to 1000 results
- `ResultSize` max: 5000; default: 1000
- `StartDate`/`EndDate` window max: 10 days per query (matches TRACE-02 requirement)
- Historical data: up to 90 days (V2 extends V1's 30-day limit)
- Output timestamps are UTC
- Results ordered by `Received` descending, then `RecipientAddress` ascending
- Throttle: 100 requests per 5-minute window at tenant level
- No pagination support — use `StartingRecipientAddress` + `EndDate` for subsequent pages
- `SubjectFilterType` values: `Contains`, `StartsWith`, `EndsWith` (MS recommends StartsWith/EndsWith over Contains for performance)

### Get-MessageTraceV2 Output Fields

Verified from official documentation and community sources:

| Field Name | Type | Notes |
|---|---|---|
| `SenderAddress` | String | Full sender email |
| `RecipientAddress` | String | Full recipient email |
| `Received` | DateTime | UTC timestamp |
| `Status` | String | One of 7 values (see TRACE-04) |
| `Subject` | String | Full subject line — must truncate in output |
| `MessageTraceId` | Guid | Unique per message in EXO |
| `MessageId` | String | SMTP Message-ID header |
| `Size` | Int | Message size in bytes |
| `FromIP` | String | Source IP address |
| `ToIP` | String | Destination IP (for outbound) |
| `ConnectorId` | String | Connector name if applicable |

The 7 delivery status values (TRACE-04):
- `Delivered` — message reached destination
- `Failed` — delivery attempt failed
- `Pending` — deferred, being retried
- `Quarantined` — held in quarantine
- `FilteredAsSpam` — marked as spam
- `Expanded` — distribution group expansion (no direct delivery)
- `GettingStatus` — status update still in progress

### Input Validation Pattern

From CONTEXT.md decisions:

```python
# Pattern from _check_mail_flow_handler and _validate_upn
sender = arguments.get("sender_address", "").strip()
recipient = arguments.get("recipient_address", "").strip()

# Require at least one of sender or recipient
if not sender and not recipient:
    raise RuntimeError(
        "At least one of sender_address or recipient_address is required. "
        "Provide a full or partial email address (e.g., user@domain.com)."
    )

# Reject ambiguous non-email inputs (e.g., "John")
# A valid input must contain "@" to be treated as an email
# OR be a partial address like "@contoso.com" (domain-only filter)
# Reject bare names with no @ sign
for addr, label in [(sender, "sender_address"), (recipient, "recipient_address")]:
    if addr and "@" not in addr:
        raise RuntimeError(
            f"'{addr}' in {label} is not a valid email address or domain. "
            "Provide a full email address (user@domain.com) or partial address "
            "containing '@' (e.g., @contoso.com)."
        )

# Date range validation: max 10 days
# Default: last 24 hours when no dates provided
```

**Note on SenderAddress/RecipientAddress with partial addresses:** Get-MessageTraceV2 accepts full email addresses for these parameters. It does NOT natively support wildcard or domain-only filters via these parameters. If domain-only filtering is needed, it must be done post-fetch in Python (filter results). The requirement says "reject with guidance asking for full or partial email address" — "partial" means something like a prefix, not a domain-only match.

### Date Handling Pattern

```python
from datetime import datetime, timezone, timedelta

# Default: last 24 hours
now = datetime.now(timezone.utc)
end_dt = now
start_dt = now - timedelta(hours=24)

# Format for PowerShell: ISO 8601 works reliably
start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# Validate 10-day max
if (end_dt - start_dt).days > 10:
    raise RuntimeError(
        "Date range exceeds 10 days. Get-MessageTraceV2 supports a maximum of 10 days per query."
    )
```

Note: `datetime` is already available in the Python stdlib. No new imports needed.

### Subject Truncation Pattern

```python
# CONTEXT.md: truncate to 30 characters
def _truncate_subject(subject: str | None, max_len: int = 30) -> str | None:
    if subject is None:
        return None
    if len(subject) <= max_len:
        return subject
    return subject[:max_len] + "..."
```

### Result Cap Pattern (from _search_mailboxes_handler)

```python
# Source: exchange_mcp/tools.py lines 634-715
max_results = int(arguments.get("result_size") or 100)
max_results = min(max_results, 1000)  # cap at 1000 per TRACE-05

# Request one extra to detect truncation
result_size_ps = max_results + 1

# ... after fetching ...
truncated = len(results) > max_results
results = results[:max_results]
```

### System Prompt Disambiguation Pattern

System prompt already has two disambiguation sections as models:

**"On-Premises vs Exchange Online Tools" section** (lines 49-56 of SYSTEM_PROMPT):
- Distinguishes tool scope by environment
- Lists specific rules numbered sequentially

**"Connector Queries" section** (lines 58-68 of SYSTEM_PROMPT):
- Uses intent-based rules: "When a user asks about X, use tool A; if Y, use tool B"
- Includes explicit negative rules ("do NOT use X when...")

The new section follows this model:

```
## Message Trace vs Mail Flow

You have two different tools for email delivery questions:
- get_message_trace: Tracks actual delivery status of specific messages already sent.
  Use when: "Did my email arrive?", "Was the invoice delivered?", "Show emails from
  alice in the last hour", "Why did bob's email fail?"
- check_mail_flow: Tests whether email CAN flow between two addresses (routing topology).
  Use when: "Can Alice email Bob?", "Is there a connector for fabrikam.com?",
  "Why is mail from sales blocked to partner@external.com?"

Rules:
[N]. When asked about a specific email's delivery status (did it arrive, was it delivered,
     show sent emails), use get_message_trace.
[N+1]. When asked about routing configuration or whether mail CAN flow, use check_mail_flow.
[N+2]. Do NOT use check_mail_flow when the user asks about whether a specific email arrived.
[N+3]. If unsure whether the user wants delivery tracking or routing analysis, ask:
     "Are you asking about a specific email that was already sent (delivery status), or
      about mail routing configuration?"
```

### Audit Logging Pattern

The CONTEXT.md decision says "trace queries logged for audit purposes." The server.py `handle_call_tool` already logs all tool calls:

```python
# Source: exchange_mcp/server.py lines 190-191
logger.info("tool_call name=%s args=%r", name, arguments)
logger.info("tool_ok name=%s duration=%.2fs", name, duration)
```

This means sender/recipient/date arguments are already captured in the server log for every tool call. No additional audit logging code is required in the handler itself — the existing infrastructure already satisfies the audit requirement. Confirm this interpretation is acceptable (it may be enough).

### RBAC Verification (INFRA-01)

This is a pre-implementation manual verification step, not a code task.

**What to verify:** Atlas service principal has the "Message Tracking" management role (or is a member of a role group that includes it) in Exchange Online.

**Required role groups** for message trace (HIGH confidence, from official docs):
- Organization Management
- Compliance Management
- Help Desk

**How to check:**
```powershell
# Run against EXO as admin
Get-ManagementRoleAssignment -RoleAssignee "atlas-service-principal@tenant.onmicrosoft.com" |
    Where-Object { $_.Role -like "*Message Tracking*" } |
    Select-Object Name, Role, RoleAssigneeName
```

**How to add if missing:**
```powershell
# Add to Help Desk role group (least privilege that includes Message Tracking)
Add-RoleGroupMember -Identity "Help Desk" -Member "AtlasServiceAccount"
```

**Note:** The service principal uses CBA (certificate-based auth) for PowerShell. RBAC here means Exchange management role assignments, not Azure AD App Registration roles. The Application RBAC system documented at learn.microsoft.com/exchange/permissions-exo/application-rbac applies only to Microsoft Graph and EWS, NOT to EXO PowerShell cmdlets.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| PowerShell execution | Custom subprocess runner | `client.run_cmdlet_with_retry` | Already handles auth, retry, JSON, errors |
| Input sanitisation | Custom escaping | `_escape_ps_single_quote` | Already handles PS injection risk |
| Email validation | Custom regex | `_validate_upn` | Tested, consistent with other tools |
| Error sanitisation | Custom stripping | `_sanitize_error` in server.py | Already strips PS tracebacks |
| MCP registration | Custom routing | `TOOL_DEFINITIONS` + `TOOL_DISPATCH` | Established pattern |
| Retry on throttle | Custom backoff | `run_cmdlet_with_retry` | Already implements exponential backoff |

**Key insight:** The entire PowerShell execution pipeline exists and is battle-tested. The handler only needs to: (a) validate inputs, (b) build the cmdlet string, (c) call `run_cmdlet_with_retry`, (d) normalise the result, (e) return a dict.

---

## Common Pitfalls

### Pitfall 1: Using Get-MessageTrace instead of Get-MessageTraceV2
**What goes wrong:** Get-MessageTrace was deprecated September 1, 2025. Using it will eventually fail when Microsoft removes it (Reporting Webservice deadline extended to March 18, 2026 but PowerShell cmdlet deprecation is September 2025).
**How to avoid:** Use `Get-MessageTraceV2` explicitly.
**Warning signs:** If the cmdlet works but returns data in a slightly different shape than expected.

### Pitfall 2: No pagination in V2 (unlike V1)
**What goes wrong:** V1 had `-Page` parameter. V2 has no pagination. Results are capped at `ResultSize` (max 5000). Attempting to loop using `-Page` will fail.
**How to avoid:** Use `ResultSize` to cap results. For this tool, cap at 1000 (our default) which is the API default anyway. Document that results may be truncated.
**Warning signs:** PS error mentioning `-Page` is not a valid parameter.

### Pitfall 3: Timestamps come back as UTC from PowerShell
**What goes wrong:** The `Received` field is a `DateTime` object in PowerShell. After `ConvertTo-Json -Depth 10`, it becomes an ISO 8601 string in UTC. If the user provides dates in local time, the comparison may be off.
**How to avoid:** Treat all dates as UTC internally. In the tool description, note "results are in UTC". This is consistent with EXO behaviour.

### Pitfall 4: Size field is in bytes not KB
**What goes wrong:** CONTEXT.md says "message size in KB" in the output. Get-MessageTraceV2 returns `Size` in bytes.
**How to avoid:** Divide by 1024 when building the output dict: `"size_kb": round(r.get("Size", 0) / 1024, 1)`.

### Pitfall 5: Subject field contains full PII content
**What goes wrong:** Returning the full `Subject` field exposes email content in tool results.
**How to avoid:** Apply `_truncate_subject` (30 char limit per CONTEXT.md) before returning. Never return the raw `Subject` field directly.

### Pitfall 6: Empty result vs error distinction
**What goes wrong:** `run_cmdlet` returns `[]` for empty results (legitimate no-match). The PowerShell catch block writes an error dict and exits 1, raising RuntimeError. These are different cases and need different handling.
**How to avoid:** Use the same pattern as `_search_mailboxes_handler`: catch RuntimeError, check for "not found" patterns, return empty result dict rather than propagating.

### Pitfall 7: Get-MessageTraceV2 with no filters returns 48 hours of all mail
**What goes wrong:** If sender and recipient are both empty, the cmdlet still runs and may return a massive dataset (all mail in the org for 48h).
**How to avoid:** Enforce the "at least sender OR recipient" rule before building the cmdlet. The requirement (CONTEXT.md) already mandates this.

### Pitfall 8: `_validate_upn` rejects partial addresses like "@contoso.com"
**What goes wrong:** The existing `_validate_upn` requires the full `user@domain.com` format. If partial address filtering is desired (domain-only), the validator would reject it.
**How to avoid:** For this tool, require full email addresses (user@domain.com format) for sender and recipient. The CONTEXT.md decision says "ask for full or partial email address" but the ambiguous case is bare names like "John" — not partial email fragments. Keep using `_validate_upn` for sender/recipient, which accepts `user@domain.com` format.

### Pitfall 9: PowerShell ResultSize +1 trick and 5000 cap
**What goes wrong:** Requesting `result_size + 1` to detect truncation fails if the user asks for 5000 (the API max is 5000; requesting 5001 may error).
**How to avoid:** Cap the internal PS ResultSize at `min(result_size + 1, 5000)`. If the cap is hit, set `truncated: true` anyway since results at 5000 are almost certainly incomplete.

---

## Code Examples

### Handler Skeleton (following check_mail_flow pattern)

```python
# Source: pattern from exchange_mcp/tools.py _check_mail_flow_handler
async def _get_message_trace_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Track email delivery status via Get-MessageTraceV2."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    from datetime import datetime, timezone, timedelta

    sender = arguments.get("sender_address", "").strip()
    recipient = arguments.get("recipient_address", "").strip()

    # Require at least one filter
    if not sender and not recipient:
        raise RuntimeError(
            "At least one of sender_address or recipient_address is required. "
            "Provide a full email address (e.g. user@domain.com)."
        )

    # Reject bare names (no @)
    for addr, field in [(sender, "sender_address"), (recipient, "recipient_address")]:
        if addr and "@" not in addr:
            raise RuntimeError(
                f"'{addr}' is not a valid email address for {field}. "
                "Provide a full email address (user@domain.com)."
            )

    # Validate full UPN format for addresses that look like full emails
    if sender and sender.count("@") == 1 and not sender.startswith("@"):
        _validate_upn(sender)
    if recipient and recipient.count("@") == 1 and not recipient.startswith("@"):
        _validate_upn(recipient)

    # Date range handling
    now = datetime.now(timezone.utc)
    start_date_str = arguments.get("start_date", "").strip()
    end_date_str = arguments.get("end_date", "").strip()

    if not start_date_str and not end_date_str:
        end_dt = now
        start_dt = now - timedelta(hours=24)
    else:
        # Parse provided dates, enforce 10-day max
        ...

    # Result size cap
    result_size = min(int(arguments.get("result_size") or 100), 1000)
    ps_result_size = min(result_size + 1, 5000)

    # Build cmdlet
    parts = ["Get-MessageTraceV2"]
    if sender:
        safe_sender = _escape_ps_single_quote(sender)
        parts.append(f"-SenderAddress '{safe_sender}'")
    if recipient:
        safe_recipient = _escape_ps_single_quote(recipient)
        parts.append(f"-RecipientAddress '{safe_recipient}'")
    parts.append(f"-StartDate '{start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}'")
    parts.append(f"-EndDate '{end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}'")
    parts.append(f"-ResultSize {ps_result_size}")

    subject_filter = arguments.get("subject_filter", "").strip()
    if subject_filter:
        safe_subj = _escape_ps_single_quote(subject_filter)
        parts.append(f"-Subject '{safe_subj}' -SubjectFilterType 'Contains'")

    select_fields = (
        "SenderAddress, RecipientAddress, Received, Status, Subject, "
        "MessageTraceId, Size, FromIP, ToIP, ConnectorId"
    )
    cmdlet = " ".join(parts) + f" | Select-Object {select_fields}"

    try:
        raw = await client.run_cmdlet_with_retry(cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "not found" in msg:
            return {"results": [], "count": 0, "truncated": False, "query_summary": {...}}
        raise

    # Normalise
    results_raw = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])

    truncated = len(results_raw) > result_size
    results_raw = results_raw[:result_size]

    messages = [
        {
            "sender": r.get("SenderAddress"),
            "recipient": r.get("RecipientAddress"),
            "received": r.get("Received"),
            "status": r.get("Status"),
            "subject_snippet": _truncate_subject(r.get("Subject")),
            "message_trace_id": str(r.get("MessageTraceId") or ""),
            "size_kb": round((r.get("Size") or 0) / 1024, 1),
            "from_ip": r.get("FromIP"),
            "to_ip": r.get("ToIP"),
            "connector": r.get("ConnectorId"),
        }
        for r in results_raw
    ]

    return {
        "results": messages,
        "count": len(messages),
        "truncated": truncated,
        "query_summary": {
            "sender": sender or None,
            "recipient": recipient or None,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
        },
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| `Get-MessageTrace` | `Get-MessageTraceV2` | GA: Early 2026, Deprecated: Sep 2025 | V2 required for new implementations |
| PageSize parameter | ResultSize parameter | V2 GA | No pagination; max 5000 results |
| 30-day historical window | 90-day historical window | V2 GA | Broader historical queries possible |
| EXO PowerShell V2 module | EXO PowerShell V3 module >= 3.7.0 | Required for V2 cmdlets | Must verify module version on server |

**Deprecated/outdated:**
- `Get-MessageTrace`: Deprecated September 1, 2025; do not use
- `-Page` parameter: Was on Get-MessageTrace; does not exist on V2
- `PageSize` parameter: Replaced by `ResultSize` on V2

---

## Open Questions

1. **EXO PowerShell module version on server**
   - What we know: V3 >= 3.7.0 is required for Get-MessageTraceV2
   - What's unclear: Current installed version on the Atlas server
   - Recommendation: First plan task should verify `(Get-Module ExchangeOnlineManagement).Version` is >= 3.7.0. If not, update is required before implementation can proceed.

2. **INFRA-01: Atlas service principal RBAC role**
   - What we know: Message trace requires "Message Tracking" role (included in Organization Management, Compliance Management, or Help Desk role groups)
   - What's unclear: Current role assignments for the Atlas service principal / service account
   - Recommendation: Plan task to verify this before writing the handler. No code changes needed if the role is already assigned.

3. **Audit log detail level**
   - What we know: CONTEXT.md says "trace queries logged for audit purposes (who searched for what sender/recipient/date)"; server.py already logs all tool calls with args
   - What's unclear: Whether the existing server-level log satisfies the audit requirement or whether a dedicated audit log (different file, different retention) is needed
   - Recommendation: Treat existing server logger as satisfying the requirement unless stakeholders specify otherwise. No code changes needed.

4. **Subject filter position in PS cmdlet**
   - What we know: `-SubjectFilterType` must accompany `-Subject`; MS recommends `StartsWith` or `EndsWith` over `Contains` for performance
   - What's unclear: Whether users will provide subject prefixes or keywords (affects which filter type to default to)
   - Recommendation: Default to `Contains` for correctness; the tool description can note this. If performance becomes an issue, expose `subject_filter_type` as a parameter.

---

## Sources

### Primary (HIGH confidence)
- Microsoft Learn - Get-MessageTraceV2 official docs: https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps
- Microsoft Learn - New Message Trace in Exchange Online: https://learn.microsoft.com/en-us/exchange/monitoring/trace-an-email-message/new-message-trace
- Microsoft Learn - Feature permissions in Exchange Online: https://learn.microsoft.com/en-us/exchange/permissions-exo/feature-permissions
- Microsoft Learn - Application RBAC: https://learn.microsoft.com/en-us/Exchange/permissions-exo/application-rbac
- Codebase: `exchange_mcp/tools.py` — all 17 existing handlers
- Codebase: `exchange_mcp/exchange_client.py` — ExchangeClient pattern
- Codebase: `exchange_mcp/server.py` — error handling, logging
- Codebase: `chat_app/openai_client.py` — SYSTEM_PROMPT pattern
- Codebase: `chat_app/auth.py` — role_required decorator

### Secondary (MEDIUM confidence)
- Microsoft Tech Community blog (GA announcement): https://techcommunity.microsoft.com/blog/exchange/announcing-general-availability-ga-of-the-new-message-trace-in-exchange-online/4420243
- Get-MessageTrace deprecation notification: legacy deprecated September 1, 2025; Reporting Webservice extended to March 18, 2026

### Tertiary (LOW confidence)
- Community blog: https://blog.icewolf.ch/archive/2024/12/19/exchange-online-message-trace-V2-public-preview/ — confirms output field names match official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing infrastructure
- Get-MessageTraceV2 parameters: HIGH — from official Microsoft Learn docs
- Output fields: MEDIUM-HIGH — documented in official blog/docs; exact field names confirmed across multiple sources; authoritative type info requires running cmdlet
- Architecture: HIGH — follows identical pattern to 17 proven existing tools
- RBAC requirements: HIGH — documented in official permissions page
- Pitfalls: HIGH — derived from official docs and direct code analysis

**Research date:** 2026-04-06
**Valid until:** 2026-07-06 (stable Exchange API; Get-MessageTraceV2 now GA)
