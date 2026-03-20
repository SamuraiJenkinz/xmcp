# Phase 3: Mailbox Tools - Research

**Researched:** 2026-03-19
**Domain:** Exchange Online PowerShell cmdlets for mailbox statistics, mailbox search/filtering, and mailbox delegate permissions
**Confidence:** HIGH for cmdlet selection and parameters; MEDIUM for TotalItemSize serialization behavior (confirmed pattern, not directly testable without live Exchange)

## Summary

Phase 3 implements three tool handlers in `exchange_mcp/tools.py` that replace stub functions with real Exchange Online PowerShell calls routed through the existing `ExchangeClient` infrastructure. The scaffolding is complete — `_build_cmdlet_script()`, `run_cmdlet_with_retry()`, error classification, and the `handle_call_tool` dispatch are all production-ready from Phases 1 and 2. Phase 3 only adds Python logic inside three handler functions and a `_format_size()` helper.

**Cmdlet choices are the central research question.** Microsoft documents two tiers: legacy (`Get-Mailbox`, `Get-MailboxStatistics`, `Get-MailboxPermission`, `Get-RecipientPermission`) and modern EXO variants (`Get-EXOMailbox`, `Get-EXOMailboxStatistics`, etc.). The project uses `Connect-ExchangeOnline` from ExchangeOnlineManagement v3.9+; both tiers are available. The legacy cmdlets have a critical serialization difference that affects how sizes are extracted from JSON output.

**Primary recommendation:** Use legacy `Get-MailboxStatistics` and `Get-Mailbox` with explicit `Select-Object` to project only needed fields into JSON. For size fields, parse the serialized string format `"2.4 GB (2,578,497,536 bytes)"` in PowerShell before emitting JSON — extract byte counts and convert to human-readable string in the PowerShell script, not in Python. Use `Get-MailboxPermission` (FullAccess), `Get-RecipientPermission` (SendAs), and `Get-Mailbox -Identity x | Select GrantSendOnBehalfTo` (SendOnBehalf) for the three delegate permission types.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ExchangeOnlineManagement (PS) | 3.9.0 | Get-MailboxStatistics, Get-Mailbox, Get-MailboxPermission, Get-RecipientPermission | Already in use; all target cmdlets live in this module |
| exchange_mcp.exchange_client | Phase 1 | run_cmdlet_with_retry(), _build_cmdlet_script() | All PS execution goes through ExchangeClient — do not call ps_runner directly |
| re (stdlib) | Python 3.11 | UPN format validation regex | No extra deps; simple pattern match |
| json (stdlib) | Python 3.11 | Tool handler return serialization | Already in use throughout |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mcp.types (TextContent) | 1.26.0 | Not needed directly in tool handlers | server.py serializes the dict result; handlers just return dicts |
| exchange_mcp.tools (TOOL_DISPATCH) | Phase 2 | Replace stub handlers | Update dispatch table in-place |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Get-MailboxStatistics | Get-EXOMailboxStatistics | EXO variant has paged output, is preferred by Microsoft docs, but both return the same fields in this context. Legacy cmdlet is already verified via Phase 1 integration tests. Stick with legacy for consistency across Phase 3. |
| Get-MailboxPermission | Get-EXOMailboxPermission | EXO variant also works. Get-MailboxPermission is simpler to filter in PS script. |
| Three separate PS calls for delegates | One compound PS script | Three-call approach (one per permission type) is simpler to debug and aligns with run_cmdlet_with_retry() design. Three separate retry contexts. |

**Installation:** No new dependencies — all needed cmdlets are in ExchangeOnlineManagement 3.9.0 already installed.

## Architecture Patterns

### Recommended Project Structure

```
exchange_mcp/
├── exchange_client.py   # Unchanged — ExchangeClient already production-ready
├── server.py            # Unchanged — handle_call_tool already dispatches correctly
├── tools.py             # Phase 3 TARGET: replace three stubs + add _format_size helper
├── ps_runner.py         # Unchanged
├── dns_utils.py         # Unchanged
└── __init__.py

tests/
├── test_tools_mailbox.py   # New: unit tests for the three handlers (all mocked)
└── test_integration.py     # Existing: add @pytest.mark.exchange tests for live validation
```

### Pattern 1: Tool Handler Structure

**What:** Each tool handler is an async function with signature `(arguments: dict, client: ExchangeClient) -> dict`. It validates input, builds the cmdlet string, calls `client.run_cmdlet_with_retry()`, transforms the Exchange JSON into the target schema, and raises `RuntimeError` with a specific message on any logical error (mailbox not found, invalid format).

**When to use:** All three handlers follow this pattern exactly.

```python
# Source: tools.py Phase 2 pattern + CONTEXT.md decisions
async def _get_mailbox_stats_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    email = arguments.get("email_address", "").strip()
    _validate_upn(email)  # raises RuntimeError on bad format

    cmdlet = (
        f"Get-MailboxStatistics -Identity '{email}' "
        "| Select-Object DisplayName, TotalItemSize, ItemCount, "
        "LastLogonTime, MailboxTypeDetail, Database"
    )
    raw = await client.run_cmdlet_with_retry(cmdlet)

    # raw is [] when mailbox not found (empty output from PS)
    if not raw or (isinstance(raw, list) and len(raw) == 0):
        raise RuntimeError(
            f"No mailbox found for '{email}'. Check the email address and try again."
        )

    data = raw if isinstance(raw, dict) else raw[0]
    return _shape_mailbox_stats(data)
```

### Pattern 2: UPN Validation (Fail Fast)

**What:** Validate the email_address argument before making the Exchange call. A regex that checks for `user@domain.tld` structure fails fast with a specific error message that echoes the bad input.

**When to use:** `get_mailbox_stats` and `get_shared_mailbox_owners` both take `email_address` as required input.

```python
# Source: CONTEXT.md decision + standard UPN pattern
import re

_UPN_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

def _validate_upn(email: str) -> None:
    """Raise RuntimeError if email does not match a basic UPN pattern.

    Args:
        email: The email address string to validate.

    Raises:
        RuntimeError: With a user-friendly message echoing the bad input.
    """
    if not _UPN_RE.match(email):
        raise RuntimeError(
            f"'{email}' is not a valid email address. "
            "Expected format: user@domain.com"
        )
```

### Pattern 3: TotalItemSize Extraction in PowerShell

**What:** Exchange Online serializes `TotalItemSize` as a string like `"2.4 GB (2,578,497,536 bytes)"` when accessed via remote session. The `.Value.ToMB()` method does NOT work. The safest approach is to extract the byte count inside the PowerShell script using string splitting, then compute the human-readable string in Python.

**Why in PowerShell, not Python:** The ConvertTo-Json output of `TotalItemSize` in Exchange Online can be either a string `"2.4 GB (2,578,497,536 bytes)"` or a nested object with `Value` key depending on PowerShell version and session type. Extracting in PowerShell is deterministic.

```powershell
# Source: Multiple Exchange Online PowerShell community references (HIGH confidence pattern)
# Extract byte count from TotalItemSize string format "X.X GB (N,NNN,NNN bytes)"
$stats = Get-MailboxStatistics -Identity 'user@contoso.com'
$sizeStr = $stats.TotalItemSize.ToString()
# String is: "2.4 GB (2,578,497,536 bytes)"
$bytes = [long]($sizeStr.Split('(')[1].Split(' ')[0].Replace(',',''))
```

**Python side — convert bytes to human-readable string:**

```python
def _format_size(byte_count: int) -> str:
    """Convert raw byte count to human-friendly size string.

    Args:
        byte_count: Size in bytes.

    Returns:
        String like "2.4 GB", "512.0 MB", "48.3 KB", or "123 B".
    """
    if byte_count >= 1_073_741_824:  # 1 GB
        return f"{byte_count / 1_073_741_824:.1f} GB"
    elif byte_count >= 1_048_576:    # 1 MB
        return f"{byte_count / 1_048_576:.1f} MB"
    elif byte_count >= 1_024:        # 1 KB
        return f"{byte_count / 1_024:.1f} KB"
    else:
        return f"{byte_count} B"
```

**Alternative — do all size work inside the PowerShell script using a calculated property:**

```powershell
# Cleaner approach: project a computed bytes field directly in Select-Object
Get-MailboxStatistics -Identity 'user@contoso.com' | Select-Object `
    DisplayName,
    ItemCount,
    LastLogonTime,
    Database,
    @{Name='TotalItemSizeBytes';Expression={
        [long]($_.TotalItemSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))
    }}
| ConvertTo-Json -Depth 10
```

This emits `TotalItemSizeBytes` as a plain integer in the JSON — Python receives it directly as `int`. This is the recommended approach: avoids string parsing in Python entirely.

### Pattern 4: Quota Fields — Two Separate Calls Required

**What:** Quota information (ProhibitSendQuota, ProhibitSendReceiveQuota, IssueWarningQuota) is on the `Get-Mailbox` object, not `Get-MailboxStatistics`. Get-MailboxStatistics returns size and item count; Get-Mailbox returns quota limits and type information.

**IMPORTANT:** In on-premises Exchange, `UseDatabaseQuotaDefaults = True` means the per-mailbox quota fields are meaningless — you'd need `Get-MailboxDatabase` to get the actual limits. In Exchange Online, quotas are set per-mailbox by the service plan, so the values from `Get-Mailbox` are always authoritative.

**Approach for get_mailbox_stats:** Make two cmdlet calls: one to `Get-MailboxStatistics` for size/count/logon, one to `Get-Mailbox` for quota limits and type. Merge results in Python.

```python
# Two calls, one per data source
stats_cmdlet = (
    f"Get-MailboxStatistics -Identity '{email}' | Select-Object "
    "DisplayName, ItemCount, LastLogonTime, Database, "
    "@{Name='TotalItemSizeBytes';Expression={"
    "[long]($_.TotalItemSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))"
    "}}"
)
quota_cmdlet = (
    f"Get-Mailbox -Identity '{email}' | Select-Object "
    "DisplayName, PrimarySmtpAddress, RecipientTypeDetails, "
    "ProhibitSendQuota, ProhibitSendReceiveQuota, IssueWarningQuota, "
    "UseDatabaseQuotaDefaults"
)
```

**Alternative — single compound script:** Use `_build_cmdlet_script()` is designed for one cmdlet line. Running two cmdlets requires either a compound PowerShell script (not supported by `run_cmdlet_with_retry`) or two sequential awaited calls. Use two sequential calls — simpler, each has independent retry.

### Pattern 5: search_mailboxes Filter Logic

**What:** Three filter_type values map to different Get-Mailbox invocations.

```powershell
# filter_type = "database"
Get-Mailbox -Database 'DB01' -ResultSize 100 | Select-Object DisplayName, PrimarySmtpAddress, RecipientTypeDetails, Database

# filter_type = "type" (e.g. SharedMailbox, UserMailbox, RoomMailbox)
Get-Mailbox -RecipientTypeDetails SharedMailbox -ResultSize 100 | Select-Object DisplayName, PrimarySmtpAddress, RecipientTypeDetails, Database

# filter_type = "name" (wildcard/ANR search)
Get-Mailbox -Anr 'john' -ResultSize 100 | Select-Object DisplayName, PrimarySmtpAddress, RecipientTypeDetails, Database
```

**Key points:**
- `-Anr` (Ambiguous Name Resolution) searches CN, DisplayName, FirstName, LastName, and Alias — it is NOT a filter, it is an implicit wildcard prefix match. `'john'` matches `John Smith`, `John Doe`, `Johnson, Kelly`.
- `-Anr` does NOT support the `*` wildcard syntax. The user's query `'john*'` should be stripped of trailing `*` before being passed to `-Anr` (or passed through, since ANR already does prefix matching).
- `-Database` is on-premises only; for Exchange Online it may not be applicable. Flag this in implementation — document that database filtering may return no results in Exchange Online.
- `-RecipientTypeDetails` accepts case-insensitive string values: `SharedMailbox`, `UserMailbox`, `RoomMailbox`, `EquipmentMailbox`, `DiscoveryMailbox`.
- `-ResultSize` caps the result — always pass the `max_results` argument (default 100).

**Truncation detection:** `Get-Mailbox -ResultSize N` silently truncates when there are more than N results. To detect truncation, request `N+1` results, then cap the returned list at `N` and set `truncated: true` if `len(results) > max_results`.

```python
# Request one extra to detect truncation
actual_max = max_results + 1
cmdlet = f"Get-Mailbox -Anr '{query}' -ResultSize {actual_max} | ..."
raw = await client.run_cmdlet_with_retry(cmdlet)

results = raw if isinstance(raw, list) else ([raw] if raw else [])
truncated = len(results) > max_results
results = results[:max_results]
```

### Pattern 6: get_shared_mailbox_owners — Three Permission Queries

**What:** Three distinct permission types require three separate Exchange cmdlets:

| Permission Type | Cmdlet | Output Field |
|----------------|--------|-------------|
| Full Access | `Get-MailboxPermission -Identity x` | Filter: `AccessRights -contains 'FullAccess'` and `Deny -eq $false` |
| Send As | `Get-RecipientPermission -Identity x -AccessRights SendAs` | Trustee field |
| Send on Behalf | `Get-Mailbox -Identity x \| Select GrantSendOnBehalfTo` | GrantSendOnBehalfTo multi-value property |

**Full Access — filtering noise:**

Get-MailboxPermission returns many system entries by default (`NT AUTHORITY\SELF`, `NT AUTHORITY\SYSTEM`, `Exchange Servers`, etc.). Filter these out in PowerShell:

```powershell
Get-MailboxPermission -Identity 'shared@contoso.com' |
    Where-Object { $_.AccessRights -contains 'FullAccess' -and
                   $_.Deny -eq $false -and
                   $_.User -notlike 'NT AUTHORITY\*' -and
                   $_.User -notlike 'S-1-5-*' } |
    Select-Object User, IsInherited
```

**Send As — RecipientPermission:**

```powershell
Get-RecipientPermission -Identity 'shared@contoso.com' -AccessRights SendAs |
    Where-Object { $_.Trustee -notlike 'NT AUTHORITY\*' } |
    Select-Object Trustee, IsInherited
```

**Send on Behalf — GrantSendOnBehalfTo:**

`GrantSendOnBehalfTo` is a multi-valued property on the mailbox object containing display names (distinguished names in on-premises). In Exchange Online it contains the DN or UPN of each delegate. It does NOT have IsInherited or per-entry metadata.

```powershell
Get-Mailbox -Identity 'shared@contoso.com' |
    Select-Object GrantSendOnBehalfTo
```

Returns: `{ "GrantSendOnBehalfTo": ["CN=John Smith,...", ...] }` or `{ "GrantSendOnBehalfTo": null }` if empty.

**Inherited permission flag:** `Get-MailboxPermission` has `IsInherited` property (True/False). `Get-RecipientPermission` also has `IsInherited`. GrantSendOnBehalfTo has no inheritance concept — treat all entries as directly assigned.

**Note on `via_group` field:** CONTEXT.md requests `via_group: "IT-Team"` for inherited permissions. Exchange does not expose which group caused the inheritance via these cmdlets — `IsInherited = True` only says it's inherited, not from which group. Therefore: set `inherited: true` when `IsInherited = True`, but always set `via_group: null` (we do not have this information without a separate AD lookup). Document this limitation in the response schema.

### Pattern 7: Resolving Display Names for Delegates

**What:** `Get-MailboxPermission` returns `User` as a security principal (e.g., `DOMAIN\username` or `user@contoso.com`). `Get-RecipientPermission` returns `Trustee` similarly. Both may NOT include a human-readable display name. The CONTEXT.md decision requires each delegate entry to include both `display_name` and `identity` (UPN).

**Resolution approach:** Use PowerShell's `| ForEach-Object` to resolve each delegate to a `Get-Recipient` call for display name. However, this per-delegate call approach has N×2-4s latency for N delegates, which is impractical.

**Pragmatic approach for Phase 3:** Return the `User`/`Trustee` value as the `identity` field. If it contains `@`, it's already a UPN — use it as both `identity` and attempt display name derivation by stripping the domain. If it's a `DOMAIN\user` format, return it as-is. Set `display_name` to `null` when not resolvable without an additional call.

**Better alternative:** Use `-IncludeUserWithDisplayName` parameter (Exchange Online only) on `Get-MailboxPermission`. This flag enriches the `User` field to include the display name:

```powershell
Get-MailboxPermission -Identity 'shared@contoso.com' -IncludeUserWithDisplayName |
    Where-Object { $_.AccessRights -contains 'FullAccess' -and
                   $_.Deny -eq $false -and
                   $_.User -notlike 'NT AUTHORITY\*' } |
    Select-Object User, UserDisplayName, IsInherited
```

**Note:** `-IncludeUserWithDisplayName` is marked "Exchange Online only" and fills in a `UserDisplayName` property. Use this for FullAccess. For SendAs, `Get-RecipientPermission` has a similar `TrusteeDisplayName` (check availability). For GrantSendOnBehalfTo, the DN values require a separate `Get-Recipient` call.

### Anti-Patterns to Avoid

- **Calling ps_runner directly from tool handlers:** All execution must go through `ExchangeClient.run_cmdlet_with_retry()` — not `ps_runner.run_ps()`. The client owns connect/disconnect lifecycle, retry logic, and JSON parsing.
- **Using `.Value.ToMB()` on TotalItemSize:** This method is unavailable in Exchange Online remote sessions. Always use the string splitting approach or a calculated property.
- **Passing filter_value unsanitized to PowerShell:** A filter_value containing a single quote would break the PowerShell string. Escape single quotes by doubling them: `filter_value.replace("'", "''")`).
- **Assuming Get-Mailbox -Database works in Exchange Online:** The `-Database` parameter is an on-premises-only parameter for listing. In Exchange Online, `Get-Mailbox -Database x` returns all mailboxes (ignores the parameter silently) or errors. Return a clear error: "Database filtering is only supported for on-premises Exchange."
- **Letting GrantSendOnBehalfTo = null propagate to JSON as null:** Return an empty list `[]` instead of null for any permission type with no delegates — consistent with the decided schema `{full_access: [], ...}`.
- **Not filtering NT AUTHORITY and system accounts from FullAccess:** The output includes `NT AUTHORITY\SELF`, `NT AUTHORITY\SYSTEM`, and Exchange internal accounts by default. These must be filtered before returning to the LLM.
- **Assuming a single result from Get-MailboxStatistics:** When the Identity parameter is given a value that doesn't exist in Exchange Online, the cmdlet raises an error (`couldn't find the object`) — not an empty result. This IS caught by the existing `_NON_RETRYABLE_PATTERNS` in exchange_client.py and raises RuntimeError immediately.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UPN format validation | Complex RFC 5321 email parser | Simple regex: `^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$` | Full RFC compliance is overkill; Exchange will reject invalid addresses anyway — this is a fail-fast pre-check only |
| Size unit conversion from bytes | Custom if/elif chain | `_format_size(bytes)` helper — single function | Already needed; just write it once and test it |
| Delegate display name resolution | N × Get-Recipient calls | `-IncludeUserWithDisplayName` flag on Get-MailboxPermission | Avoids N additional PS sessions; one call gets names |
| Wildcard name search | Manual `-Filter {DisplayName -like 'X*'}` | `-Anr` parameter | ANR handles ambiguous resolution across multiple name fields; `-Filter` requires exact property knowledge |
| Result size cap + truncation detection | Custom pagination logic | Request N+1, cap at N, set truncated flag | Simple, reliable, no Exchange paging API needed |

**Key insight:** The ExchangeClient is already a complete infrastructure layer. Phase 3 adds only the thin transformation layer between raw Exchange JSON and the target output schema. Don't reach below ExchangeClient.

## Common Pitfalls

### Pitfall 1: TotalItemSize Serialization Is a String, Not an Object

**What goes wrong:** After `ConvertTo-Json -Depth 10`, `TotalItemSize` comes back as a string `"2.4 GB (2,578,497,536 bytes)"`, not a structured object. Trying to access `.Value` or `.ToMB()` in Python fails because Python received a string.

**Why it happens:** Exchange Online serializes ByteQuantifiedSize objects as formatted strings across the remote PowerShell boundary. On-premises Exchange with direct access retains the object type.

**How to avoid:** Use a calculated property in `Select-Object` inside the PowerShell script to emit `TotalItemSizeBytes` as a plain `[long]` integer. The Python handler then calls `_format_size(data["TotalItemSizeBytes"])`.

**Warning signs:** Python receives `"TotalItemSize": "2.4 GB (2,578,497,536 bytes)"` in the parsed JSON instead of an integer.

### Pitfall 2: Empty vs Not-Found vs Error Distinguish

**What goes wrong:** When `Get-MailboxStatistics -Identity bad@domain.com` is run, Exchange raises `"Couldn't find the object 'bad@domain.com'."` which exits PS with code 1. The `_NON_RETRYABLE_PATTERNS` in exchange_client.py catches `"couldn't find the object"` and raises `RuntimeError` immediately (no retry). This RuntimeError propagates to `handle_call_tool` in server.py, which calls `_sanitize_error()` and re-raises as a sanitized `RuntimeError` → the SDK creates `isError: true`.

**This is correct behavior.** However, the sanitized error message from `_sanitize_error()` starts with `"Exchange error: Couldn't find the object..."` — the tool handler should intercept this specific RuntimeError pattern BEFORE it reaches server.py and replace it with a more user-friendly message that echoes the input email.

**Implementation pattern:**

```python
try:
    raw = await client.run_cmdlet_with_retry(cmdlet)
except RuntimeError as exc:
    msg = str(exc).lower()
    if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
        raise RuntimeError(
            f"No mailbox found for '{email}'. "
            "Check the email address and try again."
        ) from None
    raise  # Re-raise other RuntimeErrors for server.py to sanitize
```

**Warning signs:** Error messages reaching the LLM say "Exchange error: Couldn't find the object..." instead of the user-friendly version.

### Pitfall 3: filter_value Single-Quote Injection

**What goes wrong:** If `filter_value` contains a single quote (e.g., `"O'Brien"`), the PowerShell string `'Get-Mailbox -Anr 'O'Brien''` breaks with a parse error.

**Why it happens:** PowerShell string literals are delimited by single quotes; embedded single quotes must be doubled.

**How to avoid:** Always escape: `safe_value = filter_value.replace("'", "''")`

**Warning signs:** RuntimeError from PowerShell with "unexpected token" or "missing closing '"` in the error message.

### Pitfall 4: NT AUTHORITY and System Accounts in FullAccess Results

**What goes wrong:** `Get-MailboxPermission` returns 10-15 entries per mailbox by default, most of them system accounts (`NT AUTHORITY\SELF`, `NT AUTHORITY\SYSTEM`, `Exchange Servers`, `Exchange Trusted Subsystem`, etc.). Without filtering, the LLM receives a list of system accounts instead of human delegates.

**Why it happens:** Exchange records system-level permissions explicitly in mailbox ACLs.

**How to avoid:** Add `-notlike 'NT AUTHORITY\*'` and `-notlike 'S-1-5-*'` (SID format) to the Where-Object filter. Also filter `$_.Deny -eq $false` to exclude deny-permission entries.

**Warning signs:** `full_access` list contains entries like `NT AUTHORITY\SELF` or `Exchange Trusted Subsystem`.

### Pitfall 5: LastLogonTime Is Null for New or Inactive Mailboxes

**What goes wrong:** `LastLogonTime` is `null` in Exchange Online for mailboxes that have never been accessed or haven't been accessed via MAPI (Outlook) — web access via OWA may not update this field consistently.

**Why it happens:** LastLogonTime tracks MAPI client sessions, not all access methods.

**How to avoid:** Handle `null` explicitly: return `"last_logon": null` and add a note in the schema. Do NOT return a fabricated date. Separately: `LastUserActionTime` is being deprecated by Microsoft — do not use it.

**Warning signs:** Python receives `"LastLogonTime": null` in JSON, causing a `None` comparison failure if not handled.

### Pitfall 6: Get-Mailbox -Database Is On-Premises Only

**What goes wrong:** In Exchange Online, `-Database` parameter on `Get-Mailbox` may be silently ignored or may error. The `search_mailboxes` handler must detect when database filtering is requested and return an appropriate error for Exchange Online environments.

**Why it happens:** Exchange Online does not expose database-level objects in the same way as on-premises. Databases exist but are not user-controllable.

**How to avoid:** Either (a) attempt the call and return results (may work in hybrid), or (b) document that database filtering is primarily for on-premises Exchange and the tool will attempt it but results may be empty.

**Recommendation:** Attempt the call. If it returns empty or errors, return `{results: [], count: 0, message: "No mailboxes found on database '...'. Database filtering may not be available in Exchange Online environments."}`.

### Pitfall 7: search_mailboxes Returns a Dict When Only One Result

**What goes wrong:** Exchange cmdlets via `ConvertTo-Json` serialize single-object results as a JSON `{}` dict and multi-object results as a JSON `[]` array. If `Get-Mailbox -Anr 'specificname'` finds exactly one mailbox, `run_cmdlet()` returns a dict, not a list of one dict.

**Why it happens:** PowerShell's `ConvertTo-Json` on a single object vs. an array of objects produces different JSON structures.

**How to avoid:** Always normalize: `results = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])`. This is consistent with existing usage in the codebase.

**Warning signs:** `TypeError: list is required` when the handler tries to iterate `raw` expecting a list.

## Code Examples

Verified patterns derived from official Exchange PowerShell docs and established community practices:

### get_mailbox_stats — Full Handler

```python
# Source: tools.py — Phase 3 implementation pattern
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exchange_mcp.exchange_client import ExchangeClient

_UPN_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _validate_upn(email: str) -> None:
    if not _UPN_RE.match(email):
        raise RuntimeError(
            f"'{email}' is not a valid email address. "
            "Expected format: user@domain.com"
        )


def _format_size(byte_count: int | None) -> str | None:
    if byte_count is None:
        return None
    if byte_count >= 1_073_741_824:
        return f"{byte_count / 1_073_741_824:.1f} GB"
    elif byte_count >= 1_048_576:
        return f"{byte_count / 1_048_576:.1f} MB"
    elif byte_count >= 1_024:
        return f"{byte_count / 1_024:.1f} KB"
    return f"{byte_count} B"


async def _get_mailbox_stats_handler(
    arguments: dict[str, Any], client: "ExchangeClient"
) -> dict[str, Any]:
    email = arguments.get("email_address", "").strip()
    _validate_upn(email)
    safe = email.replace("'", "''")  # escape single quotes

    # Call 1: size + logon stats
    stats_cmdlet = (
        f"Get-MailboxStatistics -Identity '{safe}' | Select-Object "
        "DisplayName, ItemCount, LastLogonTime, Database, "
        "@{Name='TotalItemSizeBytes';Expression={"
        "[long]($_.TotalItemSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))"
        "}}"
    )
    # Call 2: quota limits
    quota_cmdlet = (
        f"Get-Mailbox -Identity '{safe}' | Select-Object "
        "PrimarySmtpAddress, RecipientTypeDetails, "
        "ProhibitSendQuota, ProhibitSendReceiveQuota, IssueWarningQuota"
    )

    try:
        stats_raw = await client.run_cmdlet_with_retry(stats_cmdlet)
        quota_raw = await client.run_cmdlet_with_retry(quota_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No mailbox found for '{email}'. "
                "Check the email address and try again."
            ) from None
        raise

    stats = stats_raw if isinstance(stats_raw, dict) else (stats_raw[0] if stats_raw else {})
    quota = quota_raw if isinstance(quota_raw, dict) else (quota_raw[0] if quota_raw else {})

    return {
        "email_address": email,
        "display_name": stats.get("DisplayName"),
        "mailbox_type": quota.get("RecipientTypeDetails"),
        "database": stats.get("Database"),
        "total_size": _format_size(stats.get("TotalItemSizeBytes")),
        "item_count": stats.get("ItemCount"),
        "last_logon": _format_datetime(stats.get("LastLogonTime")),
        "quotas": {
            "issue_warning": str(quota.get("IssueWarningQuota") or ""),
            "prohibit_send": str(quota.get("ProhibitSendQuota") or ""),
            "prohibit_send_receive": str(quota.get("ProhibitSendReceiveQuota") or ""),
        },
    }
```

### search_mailboxes — Filter Dispatch

```python
# Source: tools.py — Phase 3 implementation pattern
async def _search_mailboxes_handler(
    arguments: dict[str, Any], client: "ExchangeClient"
) -> dict[str, Any]:
    filter_type = arguments.get("filter_type", "")
    filter_value = arguments.get("filter_value", "").strip()
    max_results = int(arguments.get("max_results") or 100)

    safe_val = filter_value.replace("'", "''")
    select_fields = (
        "DisplayName, PrimarySmtpAddress, RecipientTypeDetails, Database"
    )

    # Request one extra to detect truncation
    result_size = max_results + 1

    if filter_type == "database":
        cmdlet = f"Get-Mailbox -Database '{safe_val}' -ResultSize {result_size} | Select-Object {select_fields}"
    elif filter_type == "type":
        cmdlet = f"Get-Mailbox -RecipientTypeDetails {safe_val} -ResultSize {result_size} | Select-Object {select_fields}"
    elif filter_type == "name":
        # Strip trailing wildcard — ANR is already a prefix match
        anr_val = safe_val.rstrip("*")
        cmdlet = f"Get-Mailbox -Anr '{anr_val}' -ResultSize {result_size} | Select-Object {select_fields}"
    else:
        raise RuntimeError(
            f"Unknown filter_type '{filter_type}'. "
            "Valid values are: database, type, name"
        )

    raw = await client.run_cmdlet_with_retry(cmdlet)
    results = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])

    truncated = len(results) > max_results
    results = results[:max_results]

    if not results:
        return {
            "results": [],
            "count": 0,
            "truncated": False,
            "message": f"No mailboxes matched the filter '{filter_value}'.",
        }

    mailboxes = [
        {
            "display_name": r.get("DisplayName"),
            "email_address": r.get("PrimarySmtpAddress"),
            "mailbox_type": r.get("RecipientTypeDetails"),
            "database": r.get("Database"),
        }
        for r in results
    ]

    result: dict[str, Any] = {
        "results": mailboxes,
        "count": len(mailboxes),
        "truncated": truncated,
    }
    if truncated:
        result["message"] = (
            f"Results capped at {max_results}. Narrow your search to see all matches."
        )
    return result
```

### get_shared_mailbox_owners — Three Permission Queries

```python
# Source: tools.py — Phase 3 implementation pattern
async def _get_shared_mailbox_owners_handler(
    arguments: dict[str, Any], client: "ExchangeClient"
) -> dict[str, Any]:
    email = arguments.get("email_address", "").strip()
    _validate_upn(email)
    safe = email.replace("'", "''")

    # Full Access
    fa_cmdlet = (
        f"Get-MailboxPermission -Identity '{safe}' -IncludeUserWithDisplayName | "
        "Where-Object { $_.AccessRights -contains 'FullAccess' -and "
        "$_.Deny -eq $false -and "
        "$_.User -notlike 'NT AUTHORITY\\*' -and "
        "$_.User -notlike 'S-1-5-*' } | "
        "Select-Object User, UserDisplayName, IsInherited"
    )
    # Send As
    sa_cmdlet = (
        f"Get-RecipientPermission -Identity '{safe}' -AccessRights SendAs | "
        "Where-Object { $_.Trustee -notlike 'NT AUTHORITY\\*' } | "
        "Select-Object Trustee, IsInherited"
    )
    # Send on Behalf
    sob_cmdlet = (
        f"Get-Mailbox -Identity '{safe}' | Select-Object GrantSendOnBehalfTo"
    )

    try:
        fa_raw = await client.run_cmdlet_with_retry(fa_cmdlet)
        sa_raw = await client.run_cmdlet_with_retry(sa_cmdlet)
        sob_raw = await client.run_cmdlet_with_retry(sob_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No mailbox found for '{email}'. "
                "Check the email address and try again."
            ) from None
        raise

    fa_list = fa_raw if isinstance(fa_raw, list) else ([fa_raw] if fa_raw else [])
    sa_list = sa_raw if isinstance(sa_raw, list) else ([sa_raw] if sa_raw else [])

    sob_data = sob_raw if isinstance(sob_raw, dict) else (sob_raw[0] if sob_raw else {})
    sob_raw_list = sob_data.get("GrantSendOnBehalfTo") or []
    sob_entries = sob_raw_list if isinstance(sob_raw_list, list) else [sob_raw_list]

    def _fa_entry(r: dict) -> dict:
        return {
            "display_name": r.get("UserDisplayName"),
            "identity": str(r.get("User", "")),
            "inherited": bool(r.get("IsInherited", False)),
            "via_group": None,  # Exchange does not expose source group via this cmdlet
        }

    def _sa_entry(r: dict) -> dict:
        return {
            "display_name": None,  # Get-RecipientPermission has no display name flag
            "identity": str(r.get("Trustee", "")),
            "inherited": bool(r.get("IsInherited", False)),
            "via_group": None,
        }

    def _sob_entry(dn: str) -> dict:
        return {
            "display_name": None,  # DN value; would need Get-Recipient to resolve
            "identity": dn,
            "inherited": False,  # GrantSendOnBehalfTo has no inheritance concept
            "via_group": None,
        }

    full_access = [_fa_entry(r) for r in fa_list]
    send_as = [_sa_entry(r) for r in sa_list]
    send_on_behalf = [_sob_entry(dn) for dn in sob_entries if dn]

    return {
        "mailbox": email,
        "full_access": full_access,
        "full_access_count": len(full_access),
        "send_as": send_as,
        "send_as_count": len(send_as),
        "send_on_behalf": send_on_behalf,
        "send_on_behalf_count": len(send_on_behalf),
    }
```

### PowerShell String for FullAccess With System Account Filter

```powershell
# Source: Microsoft Learn - Get-MailboxPermission + community pattern for system account exclusion
Get-MailboxPermission -Identity 'shared@contoso.com' -IncludeUserWithDisplayName |
    Where-Object {
        $_.AccessRights -contains 'FullAccess' -and
        $_.Deny -eq $false -and
        $_.User -notlike 'NT AUTHORITY\*' -and
        $_.User -notlike 'S-1-5-*' -and
        $_.User -ne 'SELF'
    } |
    Select-Object User, UserDisplayName, IsInherited |
    ConvertTo-Json -Depth 10
```

### Test Pattern for Tool Handlers

```python
# Source: test_exchange_client.py pattern — same mock approach
# tests/test_tools_mailbox.py
from unittest.mock import AsyncMock, patch
import json
import pytest
from exchange_mcp.tools import TOOL_DISPATCH

@pytest.fixture
def mock_client():
    """Return a mock ExchangeClient with run_cmdlet_with_retry patched."""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock()
    return client

@pytest.mark.asyncio
async def test_get_mailbox_stats_valid(mock_client):
    """Handler returns shaped dict with snake_case fields on success."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # stats call result
        {"DisplayName": "Alice Smith", "ItemCount": 1234,
         "TotalItemSizeBytes": 2578497536, "LastLogonTime": "/Date(1708000000000)/",
         "Database": "DB01"},
        # quota call result
        {"PrimarySmtpAddress": "alice@contoso.com",
         "RecipientTypeDetails": "UserMailbox",
         "ProhibitSendQuota": "49.5 GB (53,150,220,288 bytes)",
         "ProhibitSendReceiveQuota": "50 GB (53,687,091,200 bytes)",
         "IssueWarningQuota": "49 GB (52,613,349,376 bytes)"},
    ]
    handler = TOOL_DISPATCH["get_mailbox_stats"]
    result = await handler({"email_address": "alice@contoso.com"}, mock_client)

    assert result["email_address"] == "alice@contoso.com"
    assert result["total_size"] == "2.4 GB"  # formatted from 2578497536 bytes
    assert result["item_count"] == 1234
    assert "quotas" in result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `TotalItemSize.Value.ToMB()` | String splitting on `"(N bytes)"` pattern | EXO V3 remote session | `.Value.ToMB()` not available in remote PS sessions |
| `LastUserActionTime` for last active date | `LastLogonTime` (but note: may be null) | 2024+ — being deprecated | Don't use LastUserActionTime; use LastLogonTime and handle null |
| `Get-Mailbox` for all listing | `Get-EXOMailbox` (recommended by MSFT) | EXO V3 module | EXO variant has better performance, but legacy works for Phase 3 |
| Per-call Get-Recipient to resolve display names | `-IncludeUserWithDisplayName` flag | Exchange Online | Single flag avoids N additional PS calls |

**Deprecated/outdated:**
- `LastUserActionTime` on Get-MailboxStatistics: Deprecated by Microsoft, do not use.
- `TotalItemSize.Value.ToMB()`: Does not work in Exchange Online remote sessions.
- `-Credential` on `Connect-ExchangeOnline`: Removed (not relevant to Phase 3 but contextual).

## Open Questions

1. **`-IncludeUserWithDisplayName` flag availability**
   - What we know: Microsoft docs for Get-MailboxPermission list this as an Exchange Online parameter. It adds `UserDisplayName` to the output.
   - What's unclear: Whether it's available in the current version of ExchangeOnlineManagement (3.9.0) or requires a newer module. The parameter appears in the official docs but has no detailed description ("Fill IncludeUserWithDisplayName Description").
   - Recommendation: Attempt to use it in the handler; if it causes a "parameter not recognized" error (which would match `_NON_RETRYABLE_PATTERNS`), fall back to returning `display_name: null` for FullAccess entries. Add a fallback code path.

2. **GrantSendOnBehalfTo value format in Exchange Online**
   - What we know: `GrantSendOnBehalfTo` is a multi-valued property. In on-premises Exchange it contains distinguished names like `CN=John Smith,OU=Users,...`. In Exchange Online it may contain UPNs or display names directly.
   - What's unclear: The exact string format in Exchange Online via ConvertTo-Json — whether it's DN strings, UPN strings, or objects.
   - Recommendation: Log the raw value during first live test. The `_sob_entry` function passes through whatever string it receives as `identity`. If it's a DN, the LLM will receive it in that form, which is not ideal but not broken.

3. **Get-Mailbox -Database behavior in Exchange Online**
   - What we know: `-Database` is documented as on-premises only for the DatabaseSet parameter of Get-Mailbox.
   - What's unclear: Whether Exchange Online silently ignores it, returns all mailboxes, or raises an error.
   - Recommendation: The test plan should include an integration test with `filter_type: "database"` against a live Exchange Online environment to characterize the behavior. Plan the handler to catch and surface a clear message if it fails.

4. **Single-quote escaping vs. parameterized PowerShell**
   - What we know: The project uses string interpolation for cmdlet lines: `f"Get-Mailbox -Identity '{safe}'"`. The `safe = email.replace("'", "''")` escaping handles the common case.
   - What's unclear: Whether there are other special characters in Exchange identities (backslash, dollar sign, backtick) that could cause similar issues.
   - Recommendation: Email addresses (UPNs) by definition contain only `[local-part]@[domain]` — special PS characters are extremely unlikely. The single-quote escape is sufficient for well-formed UPNs.

## Sources

### Primary (HIGH confidence)

- `https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-mailboxstatistics?view=exchange-ps` — Get-MailboxStatistics parameter reference: Identity, LastLogonTime, TotalItemSize, Database. LastUserActionTime deprecation note confirmed.
- `https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-mailboxpermission?view=exchange-ps` — Get-MailboxPermission: FullAccess AccessRights, IsInherited, Deny, -IncludeUserWithDisplayName, default system account permissions.
- `https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-recipientpermission?view=exchange-ps` — Get-RecipientPermission: SendAs, Trustee, Identity, AccessRights filter. Exchange Online only.
- `https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-mailbox?view=exchange-ps` — Get-Mailbox: -Anr, -Database, -RecipientTypeDetails, -ResultSize, UseDatabaseQuotaDefaults, GrantSendOnBehalfTo, quota fields.
- `/c/xmcp/exchange_mcp/exchange_client.py` — ExchangeClient._build_cmdlet_script(), run_cmdlet_with_retry(), _NON_RETRYABLE_PATTERNS. Phase 1 implementation already handles "couldn't find the object" as non-retryable.
- `/c/xmcp/exchange_mcp/tools.py` — Existing TOOL_DISPATCH stubs and TOOL_DEFINITIONS for all three mailbox tools. Phase 2 structure confirmed.
- `/c/xmcp/exchange_mcp/server.py` — _sanitize_error(), handle_call_tool(). Confirmed that RuntimeError from handlers propagates as isError=True.

### Secondary (MEDIUM confidence)

- `https://automatica.com.au/2020/07/show-object-sizes-in-bytes-or-mb-in-powershell-with-office-365/` — TotalItemSize serialization as `"422.2 MB (442,706,389 bytes)"` string in Exchange Online. Extraction pattern: `.Split('(')[1].Split(' ')[0].Replace(',','')`.
- `https://techwizard.cloud/2021/10/20/tip-exchange-totalitemsize-value-tomb-or-togb-stopped-working/` — Confirms `.Value.ToMB()` stopped working in Exchange Online. Same string extraction workaround.
- `https://learn.microsoft.com/en-us/exchange/recipients-in-exchange-online/manage-permissions-for-recipients` — Official docs for delegate permission types: FullAccess, SendAs, SendOnBehalf. Cmdlet mapping confirmed.

### Tertiary (LOW confidence)

- WebSearch results for `RecipientTypeDetails` valid values: SharedMailbox, UserMailbox, RoomMailbox, EquipmentMailbox, DiscoveryMailbox. Confirmed by multiple sources but not directly verified against schema enum list.
- Community patterns for filtering `NT AUTHORITY\*` from MailboxPermission output — widely documented pattern, not in official docs explicitly.

## Metadata

**Confidence breakdown:**
- Cmdlet selection (Get-MailboxStatistics, Get-Mailbox, Get-MailboxPermission, Get-RecipientPermission): HIGH — official Microsoft Learn docs confirmed
- TotalItemSize serialization as string in Exchange Online: HIGH — confirmed by two independent technical sources with code examples
- UPN validation regex: HIGH — standard pattern, well-understood
- `-IncludeUserWithDisplayName` availability: MEDIUM — listed in docs but description says "Fill IncludeUserWithDisplayName Description" (incomplete)
- GrantSendOnBehalfTo value format in Exchange Online: LOW — DN vs. UPN format uncertain without live test
- Get-Mailbox -Database behavior in Exchange Online: LOW — documented as on-premises only, live behavior unverified

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (30 days) — Exchange Online cmdlet behavior is stable; recheck if ExchangeOnlineManagement module is upgraded past 3.9.0
