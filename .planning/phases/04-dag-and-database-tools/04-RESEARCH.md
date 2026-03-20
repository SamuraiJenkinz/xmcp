# Phase 4: DAG and Database Tools - Research

**Researched:** 2026-03-20
**Domain:** Exchange Server on-premises PowerShell cmdlets for DAG infrastructure, replication health, and database copy status
**Confidence:** HIGH for cmdlet selection and parameters (official Microsoft docs verified); MEDIUM for exact JSON serialization shapes of complex Exchange objects (confirmed patterns, not testable without live Exchange)

## Summary

Phase 4 implements three tool handlers in `exchange_mcp/tools.py` that replace stub functions. The existing infrastructure from Phases 1-3 is production-ready: `_build_cmdlet_script()`, `run_cmdlet_with_retry()`, error classification, and `handle_call_tool` dispatch are all in place. Phase 4 only adds Python logic inside three handler functions.

**These are on-premises Exchange cmdlets only.** The DAG cmdlets (`Get-DatabaseAvailabilityGroup`, `Get-MailboxDatabaseCopyStatus`) do not exist in Exchange Online — this project connects to on-premises Exchange via ExchangeOnlineManagement but the DAG tools use on-prem-only cmdlets. The `exchange_client.py` already connects via `Connect-ExchangeOnline` which for hybrid setups reaches on-prem Exchange; the cmdlets will work as long as the connected Exchange org has DAG infrastructure.

**Central research findings:**
1. `list_dag_members` needs two cmdlets: `Get-DatabaseAvailabilityGroup` (for member list, witness info) plus `Get-ExchangeServer` or `Get-MailboxServer` (for AD site, version, operational status).
2. `get_dag_health` uses `Get-MailboxDatabaseCopyStatus -Server <member>` looped over all DAG members, collecting per-copy replication fields.
3. `get_database_copies` uses `Get-MailboxDatabaseCopyStatus -Identity <database_name>` (returns all copies of that database) plus `Get-MailboxDatabase -Identity <database_name> -Status` for size and ActivationPreference.
4. ActivationPreference on `Get-MailboxDatabaseCopyStatus` can be incorrect (known Exchange bug) — use `Get-MailboxDatabase` for authoritative activation preference values.
5. Exchange complex objects (`ByteQuantifiedSize`, `DatabaseSize`) do not serialize cleanly to JSON via `ConvertTo-Json` — must use calculated properties or string extraction in PowerShell before emitting JSON.

**Primary recommendation:** Use explicit `Select-Object` with calculated properties on all cmdlets to project only scalar values into JSON. Never pipe raw Exchange complex objects directly to `ConvertTo-Json`. Follow the TotalItemSizeBytes pattern established in Phase 3.

## Standard Stack

### Core

These are the Exchange PowerShell cmdlets required for Phase 4. No additional Python libraries are needed — all work happens inside PowerShell strings passed to the existing `run_cmdlet_with_retry()`.

| Cmdlet | Purpose | Notes |
|--------|---------|-------|
| `Get-DatabaseAvailabilityGroup` | DAG metadata: member list, witness server/directory | Requires `-Status` switch for real-time OperationalServers |
| `Get-ExchangeServer` | Per-server: AD site name, AdminDisplayVersion (build) | More reliable than Get-MailboxServer for version info |
| `Get-MailboxDatabaseCopyStatus` | Per-copy health: Status, queue lengths, timestamps | Use `-Identity <db>` or `-Server <svr>` |
| `Get-MailboxDatabase` | Per-database: size, authoritative ActivationPreference | Requires `-Status` switch for DatabaseSize/Mounted |

### Supporting

| Pattern | Purpose | When to Use |
|---------|---------|-------------|
| `Select-Object` with `@{Name=...;Expression={...}}` calculated properties | Extract scalar values from complex Exchange objects | Always — never pass raw objects to ConvertTo-Json |
| `.ToString()` string extraction | Extract size bytes from `ByteQuantifiedSize` string format `"X GB (N bytes)"` | For DatabaseSize field |
| `Where-Object { $_.Identity -like '*<dag_name>*' }` | Filter databases by DAG membership | When listing databases for a specific DAG |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Get-ExchangeServer` for version | `Get-MailboxServer` | Both work; Get-ExchangeServer returns `AdminDisplayVersion` as a string like "Version 15.2 (Build 1118.7)" which is cleanly serializable; Get-MailboxServer `AdminDisplayVersion` is the same type |
| `Get-MailboxDatabaseCopyStatus -Server <svr>` loop | Single call with no filter | No-filter returns all org copies; per-server loop scoped to DAG members is cleaner |
| `Get-MailboxDatabase -Status` for ActivationPreference | `Get-MailboxDatabaseCopyStatus` ActivationPreference | MUST use Get-MailboxDatabase — the copy status cmdlet has a known bug returning wrong values |

## Architecture Patterns

### Recommended Project Structure

No new files needed. All three handlers go into the existing `exchange_mcp/tools.py` following the Phase 3 mailbox handler pattern:

```
exchange_mcp/
└── tools.py          # Add three handlers after Phase 3 handlers, update TOOL_DISPATCH
tests/
└── test_tools_dag.py # New test file (mirrors test_tools_mailbox.py structure)
```

### Pattern 1: DAG Name Validation Before Exchange Call

All three tools should validate `dag_name` is non-empty before calling Exchange. The `get_database_copies` tool does NOT take `dag_name` — it only takes `database_name`. This prevents the Exchange `$null` caution: if `dag_name` is None or empty and is passed directly to `-Identity`, Exchange returns ALL DAGs.

```python
# Source: established project pattern from Phase 3
dag_name = arguments.get("dag_name", "").strip()
if not dag_name:
    raise RuntimeError(
        "dag_name is required. Provide the name of the DAG to inspect."
    )
safe = _escape_ps_single_quote(dag_name)
```

**Important discrepancy**: The existing tool definition for `list_dag_members` has `"required": []` (dag_name is optional, with description "If omitted, returns members for all DAGs"). But the CONTEXT.md decision says "DAG name always required as explicit parameter — no auto-discovery". The planner must resolve this: implement `dag_name` as required (raise if missing) to match CONTEXT.md, but the tool schema already says optional. The safest resolution is: accept the existing schema (don't change it), but in the handler raise RuntimeError if dag_name is missing. This makes dag_name functionally required while keeping backward compatibility with the defined schema.

### Pattern 2: DAG Not Found → isError: true

When `Get-DatabaseAvailabilityGroup` is called with a non-existent DAG name, Exchange raises "Couldn't find the object". Map this to a RuntimeError with a user-friendly message (same pattern as Phase 3 mailbox not-found):

```python
# Source: Phase 3 pattern from exchange_mcp/tools.py
try:
    dag_raw = await client.run_cmdlet_with_retry(dag_cmdlet)
except RuntimeError as exc:
    msg = str(exc).lower()
    if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
        raise RuntimeError(
            f"No DAG found with name '{dag_name}'. "
            "Check the DAG name and try again."
        ) from None
    raise
```

### Pattern 3: Single-Result Dict Normalization

Exchange cmdlets return a dict (not a list) when exactly one object matches. Always normalize:

```python
# Source: Phase 3 pattern from exchange_mcp/tools.py
results = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])
```

### Pattern 4: Calculated Properties for Complex Objects

Never pass `ByteQuantifiedSize`, `ADObjectId`, or other complex Exchange types directly to `ConvertTo-Json`. Use calculated properties in PowerShell to emit scalars:

```powershell
# Source: Phase 3 established pattern (TotalItemSizeBytes)
# For database size extraction from ByteQuantifiedSize:
@{Name='DatabaseSizeBytes';Expression={
    [long]($_.DatabaseSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))
}}
```

The `ByteQuantifiedSize.ToString()` produces `"553.9 GB (594,718,752,768 bytes)"` — split on `(`, take index 1, split on space, take index 0, remove commas, cast to long.

### Pattern 5: Unreachable Servers — Partial Results Pattern

For `get_dag_health`, loop over DAG member servers and catch errors per-server rather than failing the whole call:

```powershell
# PowerShell per-server error isolation pattern
# Run Get-MailboxDatabaseCopyStatus per server, wrap in try/catch
# On failure emit error_status field for that server
```

In Python, this means running N cmdlets (one per DAG member) and aggregating results, tolerating individual server failures. This is a departure from Phase 3's pattern of raising on any error — Phase 4 prefers partial results.

### Pattern 6: ActivationPreference Source of Truth

For `get_database_copies`, activation preference must come from `Get-MailboxDatabase`:

```powershell
# Get-MailboxDatabase -Identity 'DB01' | Select-Object -ExpandProperty ActivationPreference
# Returns: {[EX01, 1], [EX02, 2], [EX03, 3]}
# This is a System.Collections.Generic.SortedDictionary
# Under ConvertTo-Json -Depth 10, it serializes as an object with server names as keys
```

The `Get-MailboxDatabaseCopyStatus` ActivationPreference field is unreliable (known Exchange bug where all copies show same value). Use `Get-MailboxDatabase` and cross-reference by server name to get per-copy preference number.

### Anti-Patterns to Avoid

- **Piping raw Exchange objects to ConvertTo-Json without Select-Object**: `ByteQuantifiedSize`, `ADObjectId`, `MailboxDatabase`, collection objects — all produce unusable JSON with nested type metadata.
- **Using $null or empty Identity parameter**: Exchange returns ALL objects when Identity is $null/empty. Always validate dag_name before building the cmdlet string.
- **Trusting ActivationPreference from Get-MailboxDatabaseCopyStatus**: Known bug in Exchange 2013/2016/2019 can return identical (wrong) values. Use `Get-MailboxDatabase` instead.
- **Calling Get-MailboxDatabase without -Status**: Without `-Status`, the `Mounted` and `DatabaseSize` fields are not populated.
- **Using -ResultSize with DAG cmdlets**: `Get-DatabaseAvailabilityGroup` and `Get-MailboxDatabaseCopyStatus` do not accept `-ResultSize` — only mailbox-related cmdlets do.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Byte size formatting | Custom byte→GB converter in Python | `_format_size()` already in tools.py | Already implemented in Phase 3; reuse |
| PS single-quote escaping | Custom escaper | `_escape_ps_single_quote()` in tools.py | Already implemented in Phase 3 |
| DAG not-found detection | Custom error parser | Same "couldn't find" / "could not find" pattern from Phase 3 | Error strings are consistent across Exchange cmdlets |
| Complex object serialization | Python post-processing | PowerShell calculated properties in Select-Object | Exchange objects don't serialize cleanly; fix at source |

**Key insight:** All complexity in Phase 4 is in the PowerShell cmdlet strings — the Python handlers are thin wrappers. Keep Python logic minimal; push all data shaping into PowerShell `Select-Object` calculated properties.

## Common Pitfalls

### Pitfall 1: ConvertTo-Json Depth Truncation on Exchange Objects

**What goes wrong:** Exchange cmdlets return deeply nested objects. `ConvertTo-Json` default depth is 2. At depth 2, `ByteQuantifiedSize` and collection properties truncate to `"..."` or serialize as `{}`.

**Why it happens:** PowerShell's `ConvertTo-Json` silently truncates at the specified depth without error. The existing `_build_cmdlet_script()` already uses `-Depth 10`, but this only helps if the Properties are scalar after Select-Object projection.

**How to avoid:** Always `Select-Object` to project only scalar properties before `ConvertTo-Json`. Never rely on `-Depth 10` alone to handle complex Exchange type trees.

**Warning signs:** JSON fields showing `{}` or `""` for size/version properties.

### Pitfall 2: $null Identity Returns All Objects

**What goes wrong:** `Get-DatabaseAvailabilityGroup -Identity $null` or `Get-DatabaseAvailabilityGroup -Identity ''` returns ALL DAGs, not an error. Same for `Get-MailboxDatabaseCopyStatus -Identity ''`.

**Why it happens:** Exchange cmdlets treat $null Identity as "no filter", per Microsoft's own caution in the docs: "The value $null or a non-existent value for the Identity parameter returns *all* objects."

**How to avoid:** Validate `dag_name` and `database_name` are non-empty BEFORE building the cmdlet string. Raise RuntimeError immediately if empty.

**Warning signs:** Tools returning data for unexpected objects when given empty input.

### Pitfall 3: ActivationPreference on Get-MailboxDatabaseCopyStatus is Unreliable

**What goes wrong:** All copies of a database show the same ActivationPreference value (e.g., all show 4) because the cmdlet queries the server directly rather than Active Directory.

**Why it happens:** `Get-MailboxDatabaseCopyStatus` queries local server data for performance; ActivationPreference is an AD attribute. The local server cache may be stale or wrong.

**How to avoid:** For `get_database_copies`, retrieve ActivationPreference from `Get-MailboxDatabase -Identity <db> | Select-Object -ExpandProperty ActivationPreference`. This returns a dictionary `{ServerName: PreferenceNumber}` from Active Directory (authoritative source).

**Warning signs:** Multiple copies showing identical ActivationPreference values.

### Pitfall 4: ByteQuantifiedSize Serialization

**What goes wrong:** `DatabaseSize` from `Get-MailboxDatabase -Status` is a `ByteQuantifiedSize` object. `ConvertTo-Json` serializes it as a nested object with type metadata, not as a number or string.

**Why it happens:** `ByteQuantifiedSize` is a .NET type with properties, not a primitive. ConvertTo-Json emits all public properties of the type.

**How to avoid:** Use a PowerShell calculated property to extract bytes before JSON serialization:
```powershell
@{Name='DatabaseSizeBytes';Expression={
    [long]($_.DatabaseSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))
}}
```
The `.ToString()` output format is guaranteed: `"X.X Unit (N bytes)"`.

**Warning signs:** `DatabaseSize` field in JSON is an object with `Value`, `IsUnlimited`, etc. instead of a number.

### Pitfall 5: Get-DatabaseAvailabilityGroup Servers Property — Complex Object

**What goes wrong:** The `Servers` property of a DAG object is a collection of `ADObjectId` objects, not plain server name strings. Direct JSON serialization produces nested objects with DN, ObjectGuid, etc.

**Why it happens:** Exchange stores server references as Active Directory object identifiers. The display-friendly name is accessible via `.Name` or `.ToString()`.

**How to avoid:** In PowerShell, use a `ForEach-Object` or `@{Name='Members';Expression={$_.Servers | ForEach-Object { $_.Name }}}` calculated property to project server names as a string array.

**Warning signs:** `servers` field in JSON contains objects instead of strings.

### Pitfall 6: Per-Server Cmdlet Failures in get_dag_health Loop

**What goes wrong:** If one DAG member server is unreachable, querying `Get-MailboxDatabaseCopyStatus -Server <svr>` raises RuntimeError and the entire tool call fails.

**Why it happens:** The existing `run_cmdlet_with_retry()` raises on any non-zero PowerShell exit code.

**How to avoid:** The CONTEXT.md decision is "Unreachable DAG member servers included in results with error status (partial results preferred over omission)". Implement per-server isolation: run one cmdlet per server, catch RuntimeError per server, add an error entry to the results list for that server, and continue.

**Warning signs:** Tool returning isError: true when only 1 of 3 DAG servers is down.

### Pitfall 7: Get-MailboxDatabaseCopyStatus Status = "Mounted" for Active Copy

**What goes wrong:** Confusing which copy is the active (mounted) copy. The `Status` field is `"Mounted"` for the active copy and other values (`Healthy`, `Failed`, etc.) for passive copies.

**Why it happens:** "Mounted" is a status value, not a separate boolean field.

**How to avoid:** In the Python handler, set `is_mounted` based on `status == "Mounted"`. Document this in code comments. The CONTEXT.md decision explicitly requires flagging the active/mounted copy.

**Warning signs:** Treating all copies as passive when one should be flagged as active.

## Code Examples

Verified patterns from official sources and established project conventions:

### list_dag_members — PowerShell Cmdlet Pattern

```powershell
# Source: Microsoft Learn - Get-DatabaseAvailabilityGroup docs + Get-ExchangeServer docs
# Step 1: Get DAG metadata (member list, witness info)
$dag = Get-DatabaseAvailabilityGroup -Identity 'DAG01' -Status | Select-Object `
    Name,
    @{Name='Members';Expression={$_.Servers | ForEach-Object { $_.Name }}},
    WitnessServer,
    WitnessDirectory,
    @{Name='OperationalServers';Expression={$_.OperationalServers | ForEach-Object { $_.Name }}},
    PrimaryActiveManager

# Step 2: Per-member enrichment via Get-ExchangeServer
# For each member name, call Get-ExchangeServer -Identity <name>
# Fields: AdminDisplayVersion (string), Site (string via .ToString()), ServerRole
Get-ExchangeServer -Identity 'EX01' | Select-Object Name, AdminDisplayVersion, `
    @{Name='Site';Expression={$_.Site.ToString()}}, ServerRole

# Step 3: Database counts per server — use Get-MailboxDatabaseCopyStatus -Server <svr>
# Count Status eq 'Mounted' for active_count, others for passive_count
```

### get_dag_health — PowerShell Cmdlet Pattern

```powershell
# Source: Microsoft Learn - Get-MailboxDatabaseCopyStatus docs + Monitor DAGs guide
# Per-server call (loop over DAG member names):
Get-MailboxDatabaseCopyStatus -Server 'EX01' | Select-Object `
    Name,
    Status,
    CopyQueueLength,
    ReplayQueueLength,
    ContentIndexState,
    LastCopiedLogTime,
    LastInspectedLogTime,
    LastReplayedLogTime,
    MailboxServer
```

### get_database_copies — PowerShell Cmdlet Pattern

```powershell
# Source: Microsoft Learn - Get-MailboxDatabaseCopyStatus docs + ActivationPreference bug docs
# Call 1: Copy status for all copies of the database
Get-MailboxDatabaseCopyStatus -Identity 'DB01' | Select-Object `
    Name,
    Status,
    CopyQueueLength,
    ReplayQueueLength,
    ContentIndexState,
    LastCopiedLogTime,
    LastInspectedLogTime,
    LastReplayedLogTime,
    MailboxServer

# Call 2: Authoritative ActivationPreference + database size
Get-MailboxDatabase -Identity 'DB01' -Status | Select-Object `
    Name,
    @{Name='DatabaseSizeBytes';Expression={
        [long]($_.DatabaseSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))
    }},
    Mounted,
    MountedOnServer
```

### DAG Not Found Error Detection

```python
# Source: Phase 3 established pattern (exchange_mcp/tools.py)
except RuntimeError as exc:
    msg = str(exc).lower()
    if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
        raise RuntimeError(
            f"No DAG found with name '{dag_name}'. "
            "Check the DAG name and try again."
        ) from None
    raise
```

### Database Name Not Found / Zero Copies

```python
# For get_database_copies: empty result from Get-MailboxDatabaseCopyStatus
# means database exists but has zero copies, OR database not found
# Check: if Exchange raises not-found → isError True
# If Exchange returns [] (zero copies) → isError True
# Both should raise RuntimeError that becomes isError: true via server.py
if not copies:
    raise RuntimeError(
        f"No database copies found for '{database_name}'. "
        "The database may not exist or has no copies configured."
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Exchange 2010: No `Get-MailboxDatabaseCopyStatus -Server` param | 2013+: `-Server` param available | Exchange 2013 | Can now query per-server instead of only per-database |
| Use `Get-MailboxDatabaseCopyStatus` ActivationPreference | Use `Get-MailboxDatabase` ActivationPreference | Known since 2013-2016 | Must use Get-MailboxDatabase for correct values |
| `ConvertTo-Json` default depth 2 | Always specify `-Depth 10` | PowerShell 5+ | The project already does this in `_build_cmdlet_script()` |

**Deprecated/outdated:**
- `Get-MailboxDatabaseCopyStatus` ActivationPreference field: Present but unreliable (bug). Use `Get-MailboxDatabase` instead.
- `ConnectionStatus` parameter of `Get-MailboxDatabaseCopyStatus`: Deprecated, no longer used per official docs.

## Open Questions

1. **list_dag_members dag_name requirement conflict**
   - What we know: Tool schema says `"required": []` (optional), CONTEXT.md says "DAG name always required".
   - What's unclear: Should the handler raise if dag_name is missing (making it functionally required despite schema), or allow omission and return all DAGs?
   - Recommendation: Raise RuntimeError if dag_name is empty (honor CONTEXT.md decision). The schema mismatch is a pre-existing definition that the planner should flag but not change unilaterally.

2. **Per-server isolation strategy for get_dag_health**
   - What we know: CONTEXT.md says partial results preferred; unreachable servers should appear with error status.
   - What's unclear: How many cmdlet calls are acceptable? Each DAG member requires its own PowerShell call (2-4s latency per call). A 4-member DAG needs 4 sequential calls = 8-16s total.
   - Recommendation: Accept the latency as per the project decision ("Per-call PSSession, no pooling — accept 2-4s latency; benchmark before optimizing"). Run sequentially, collect partial results.

3. **ActivationPreference serialization format from Get-MailboxDatabase**
   - What we know: `ActivationPreference` is a `SortedDictionary<ADObjectId, int>`. Under `ConvertTo-Json`, server names are keys, integers are values.
   - What's unclear: Exact JSON shape after ConvertTo-Json — may need to project it explicitly.
   - Recommendation: In PowerShell, expand ActivationPreference to a JSON-friendly format using `Select-Object -ExpandProperty ActivationPreference` and then a calculated property to convert dictionary entries to a list of `{server, preference}` objects.

4. **Get-ExchangeServer vs Get-MailboxServer for server enrichment in list_dag_members**
   - What we know: Both return `AdminDisplayVersion` (version string) and `Site` (AD site). Get-ExchangeServer works for all server roles; Get-MailboxServer is specific to Mailbox servers.
   - What's unclear: Whether the `Site` property serializes as a plain string or requires `.ToString()`.
   - Recommendation: Use `@{Name='Site';Expression={$_.Site.ToString()}}` to be safe. Both cmdlets should work; Get-ExchangeServer is more general.

## Sources

### Primary (HIGH confidence)

- [Get-DatabaseAvailabilityGroup docs](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-databaseavailabilitygroup?view=exchange-ps) — Parameters, -Status switch behavior, Servers property type
- [Get-MailboxDatabaseCopyStatus docs](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-mailboxdatabasecopystatus?view=exchange-ps) — Parameters, Identity/Server parameter sets
- [Monitor DAGs guide](https://learn.microsoft.com/en-us/exchange/high-availability/manage-ha/monitor-dags) — Complete table of all Status field values (12 values documented)
- [Get-MailboxDatabase docs](https://learn.microsoft.com/en-us/powershell/module/exchange/get-mailboxdatabase?view=exchange-ps) — -Status switch for Mounted/DatabaseSize
- [Get-ExchangeServer docs](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-exchangeserver?view=exchange-ps) — AdminDisplayVersion, Site properties

### Secondary (MEDIUM confidence)

- [List Active Database Copies - Practical365](https://practical365.com/powershell-tip-list-active-mailbox-database-copies-exchange-server-database-availability-group/) — Confirms available fields: Name, Status, MailboxServer, ActivationPreference, ContentIndexState, CopyQueueLength, ReplayQueueLength, LastInspectedLogTime
- [ActivationPreference Bug - Practical365](https://practical365.com/get-mailboxdatabasecopystatus-displays-incorrect-activation-preference-value/) — Documents known bug; recommends using Get-MailboxDatabase instead
- [Change DAG Activation Preference - alitajran.com](https://www.alitajran.com/change-dag-database-activation-preference/) — Confirms ActivationPreference format: `{[EX02, 1], [EX01, 2]}`

### Tertiary (LOW confidence)

- WebSearch results confirming ByteQuantifiedSize.ToString() format — pattern consistent across multiple community sources but not tested against live Exchange

## Metadata

**Confidence breakdown:**
- Standard stack (cmdlet selection): HIGH — confirmed from official Microsoft docs for Exchange 2016/2019/SE
- Architecture (handler patterns): HIGH — follows established Phase 3 patterns directly
- PowerShell cmdlet field selection: MEDIUM — field names confirmed from docs and community, exact JSON shape of complex objects (ActivationPreference dict, Site ADSite) requires validation against live Exchange
- Pitfalls: HIGH — ByteQuantifiedSize issue and ActivationPreference bug are well-documented in official sources and community

**Research date:** 2026-03-20
**Valid until:** 2026-06-20 (Exchange on-prem cmdlets are stable; 90 days)

## Complete Status Values Reference

From official Microsoft documentation (Monitor DAGs guide), all valid `Status` values from `Get-MailboxDatabaseCopyStatus`:

| Status | Description |
|--------|-------------|
| Failed | Not suspended, not able to copy/replay logs; system retries |
| Seeding | Database copy or content index is being seeded |
| SeedingSource | Being used as source for seeding operation |
| Suspended | Manually suspended by administrator |
| Healthy | Successfully copying and replaying log files |
| ServiceDown | Exchange Replication service not available |
| Initializing | Startup state; should last <30 seconds |
| Resynchronizing | Comparing with active copy to check for divergence |
| Mounted | **Active copy only** — online and accepting client connections |
| Dismounted | **Active copy only** — offline, not accepting connections |
| Mounting | **Active copy only** — coming online |
| Dismounting | **Active copy only** — going offline |
| DisconnectedAndHealthy | Lost connection to active copy; was Healthy when disconnected |
| DisconnectedAndResynchronizing | Lost connection to active copy; was Resynchronizing |
| FailedAndSuspended | Requires administrator intervention to resolve |
| SinglePageRestore | Single page restore operation in progress |
