---
phase: 04-dag-and-database-tools
plan: 01
subsystem: dag-tools
tags: [exchange, dag, database-availability-group, powershell, async, mcp]

# Dependency graph
requires:
  - phase: 03-mailbox-tools
    provides: handler pattern (multi-cmdlet async, partial results, stub replacement), shared helpers (_escape_ps_single_quote, ExchangeClient client injection)

provides:
  - _list_dag_members_handler function in exchange_mcp/tools.py
  - Multi-cmdlet DAG query pattern: Get-DatabaseAvailabilityGroup + Get-ExchangeServer + Get-MailboxDatabaseCopyStatus
  - Partial results pattern for unreachable servers (error entry with null fields, not tool failure)
  - TOOL_DISPATCH updated: list_dag_members now real handler (11 stubs remain)

affects:
  - 04-02 (get_dag_health) — can follow same multi-cmdlet pattern
  - 04-03 (get_database_copies) — same partial-results pattern for per-server errors
  - Future phases — partial results pattern established for any multi-server query

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Multi-cmdlet handler: DAG metadata + per-member enrichment + per-member DB counts in sequence
    - Partial results: unreachable servers get error entry with null fields rather than failing the whole call
    - PowerShell ADObjectId projection: ForEach-Object { $_.Name } with @() wrapper for single-member DAGs
    - PowerShell object-to-string: .ToString() on ADObjectId/ADSite/ServerVersion objects
    - Single-result normalization: both dict and single-element list handled for all cmdlet results

key-files:
  created:
    - tests/test_tools_dag.py
  modified:
    - exchange_mcp/tools.py
    - tests/test_server.py

key-decisions:
  - "dag_name functionally required despite schema saying required:[]; raise RuntimeError before any Exchange call"
  - "Unreachable servers produce error entry with null fields in members list — not a tool-level failure"
  - "Use @() wrapper in ForEach-Object expressions to force array output even for single-member DAGs"
  - "PrimaryActiveManager/Site/AdminDisplayVersion use .ToString() — these are ADObjectId/ADSite/ServerVersion objects"
  - "Active count: Status == Mounted; everything else is passive (Healthy, Failed, Disconnected, etc.)"
  - "test_call_tool_not_implemented_raises updated to get_dag_health (next stub after list_dag_members)"

patterns-established:
  - "Multi-cmdlet Phase 4 pattern: 1 DAG-level call + N per-member calls (2 each), continue on per-member RuntimeError"
  - "ADObjectId collection projection: @($_.Property | ForEach-Object { $_.Name }) in Select-Object computed property"
  - "Partial results: append error dict to server_details on RuntimeError from per-server cmdlets"

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 4 Plan 01: list_dag_members Handler Summary

**Multi-cmdlet DAG member inventory handler using Get-DatabaseAvailabilityGroup + per-server Get-ExchangeServer + Get-MailboxDatabaseCopyStatus with partial results for unreachable nodes.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T14:17:10Z
- **Completed:** 2026-03-20T14:20:46Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments

- Implemented `_list_dag_members_handler` with three Exchange cmdlets per invocation: DAG metadata, per-server enrichment, per-server DB counts
- DAG-level response includes `dag_name`, `member_count`, `witness_server`, `witness_directory`, `primary_active_manager`
- Each member entry includes `name`, `operational`, `site`, `exchange_version`, `server_role`, `active_database_count`, `passive_database_count`, `error`
- Partial results pattern: unreachable servers get an error entry with null fields instead of failing the whole tool call
- Single-member DAG normalization: bare string `Members` value converted to list
- Single-result normalization: both dict and single-element list handled for DAG cmdlet result
- PowerShell ADObjectId projection using `@($_.Servers | ForEach-Object { $_.Name })` with array wrapper
- 10 unit tests created covering all handler paths; 107/110 total tests pass (3 pre-existing integration failures unchanged)
- `TOOL_DISPATCH` updated: `list_dag_members` now points to real handler (11 stubs remain)
- `test_call_tool_not_implemented_raises` in `test_server.py` updated to use `get_dag_health`

## Commits

| Hash | Message |
|------|---------|
| ac662be | feat(04-01): add _list_dag_members_handler to tools.py |
| 9fc4e03 | test(04-01): add unit tests for list_dag_members handler |

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| dag_name functionally required despite schema `required:[]` | CONTEXT.md: "DAG name always required as explicit parameter"; raise before any Exchange call |
| Partial results for unreachable servers | CONTEXT.md decision: include error entry with null fields, not tool failure — matches operational reality where one node may be down |
| @() wrapper on ForEach-Object projection | Forces array output for single-member DAGs where PowerShell would otherwise return a bare string |
| .ToString() on ADObjectId/ADSite/ServerVersion | These are complex objects; ToString() gives the canonical string representation |
| Active = Mounted, everything else = passive | Exchange status values: Mounted (active), Healthy/Failed/Disconnected (passive/other) |

## Deviations from Plan

None — plan executed exactly as written.

## Next Phase Readiness

- Plan 04-02 (get_dag_health): Can follow identical multi-cmdlet pattern. Uses `Get-MailboxDatabaseCopyStatus` per DAG member for replication health metrics.
- Plan 04-03 (get_database_copies): Same partial-results approach for per-server errors.
- The partial results pattern and ADObjectId projection pattern are now established for all Phase 4 handlers.
