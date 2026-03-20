---
phase: 04-dag-and-database-tools
plan: 03
subsystem: exchange-tools
tags: [exchange, powershell, mcp, dag, database-copies, activation-preference, replication]

# Dependency graph
requires:
  - phase: 04-dag-and-database-tools/04-02
    provides: get_dag_health handler and DAG health test patterns

provides:
  - _get_database_copies_handler in exchange_mcp/tools.py
  - Two-call Exchange pattern: Get-MailboxDatabaseCopyStatus + Get-MailboxDatabase
  - Authoritative activation preference from Get-MailboxDatabase (not buggy CopyStatus)
  - ByteQuantifiedSize extraction pattern (same as Phase 3 TotalItemSizeBytes)
  - 11 unit tests for get_database_copies in tests/test_tools_dag.py
  - All 3 Phase 4 DAG/database tool stubs replaced with real handlers

affects:
  - Phase 5 (mail flow tools) - can reuse two-call Exchange pattern
  - Future plans needing database metadata - activation preference source decision documented

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-call Exchange pattern: separate calls for operational data vs metadata"
    - "Authoritative activation preference from Get-MailboxDatabase -Status (not CopyStatus)"
    - "ByteQuantifiedSize extraction: .Split('(')[1].Split(' ')[0].Replace(',','') in PowerShell"
    - "Dual ActivationPreference deserialization: dict {k:v} and list [{Key,Value}] formats"
    - "Zero-result guard: raise RuntimeError immediately for empty copies list"

key-files:
  created: []
  modified:
    - exchange_mcp/tools.py
    - tests/test_tools_dag.py
    - tests/test_server.py

key-decisions:
  - "Activation preference from Get-MailboxDatabase (authoritative), not Get-MailboxDatabaseCopyStatus (known bug)"
  - "Both dict and list ActivationPreference serialization formats handled (Exchange version-dependent)"
  - "database_size computed from DatabaseSizeBytes via _format_size, not from Exchange string directly"
  - "Zero copies raises RuntimeError (abnormal database state, not valid empty result)"
  - "test_call_tool_not_implemented_raises updated to check_mail_flow (Phase 5 first stub)"

patterns-established:
  - "Activation preference lookup: build act_pref_map before iterating copies"
  - "Independent not-found interception for each Exchange call (copies call vs DB info call)"
  - "Copy normalization: list passthrough, dict → single-item list, empty dict → empty list"

# Metrics
duration: 6min
completed: 2026-03-20
---

# Phase 4 Plan 03: get_database_copies Handler Summary

**get_database_copies handler with dual-call Exchange pattern: copy status from Get-MailboxDatabaseCopyStatus + authoritative activation preference and size from Get-MailboxDatabase, completing all three Phase 4 DAG/database tools**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-20T14:43:49Z
- **Completed:** 2026-03-20T14:49:49Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented `_get_database_copies_handler` with two independent Exchange calls: `Get-MailboxDatabaseCopyStatus` for copy operational data and `Get-MailboxDatabase -Status` for authoritative activation preferences and database size
- Activation preference correctly sourced from `Get-MailboxDatabase` (authoritative) — not from `Get-MailboxDatabaseCopyStatus` which has a known bug returning incorrect values
- Handles both Exchange serialization formats for ActivationPreference: direct dict `{"EX01": 1}` and list-of-key-value-pairs `[{"Key": "EX01", "Value": 1}]`
- Added 11 unit tests covering all edge cases; all 3 Phase 4 DAG tool stubs now replaced with real handlers (9 stubs remain for Phases 5-6)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _get_database_copies_handler to tools.py** - `c1712a0` (feat)
2. **Task 2: Add unit tests for get_database_copies and run full suite** - `b68d6d0` (test)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `exchange_mcp/tools.py` - Added `_get_database_copies_handler` (114 lines), updated TOOL_DISPATCH entry from stub to handler
- `tests/test_tools_dag.py` - Added 11 tests (tests 21-31) for get_database_copies; updated module docstring and imports
- `tests/test_server.py` - Updated `test_call_tool_not_implemented_raises` to use `check_mail_flow` (Phase 5 first stub)

## Decisions Made

- **Activation preference source:** Get-MailboxDatabase is authoritative; Get-MailboxDatabaseCopyStatus has a known Exchange bug where ActivationPreference values can be incorrect. Always use Get-MailboxDatabase.
- **Dual ActivationPreference format handling:** Exchange serializes ActivationPreference differently depending on version and ConvertTo-Json depth. Older versions serialize as dict `{server: int}`, newer as list `[{Key: server, Value: int}]`. Handler handles both.
- **database_size field:** Computed from `DatabaseSizeBytes` via `_format_size()` (same pattern as Phase 3 `total_size`). The raw bytes value is also included as `database_size_bytes` for LLM calculations.
- **Zero copies error:** Empty copies list raises `RuntimeError` with "No database copies found" — this is an abnormal state (a database with no copies is misconfigured), not a valid empty search result.
- **test_call_tool_not_implemented_raises:** Updated to `check_mail_flow` stub (Phase 5) since `get_database_copies` is now implemented.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected incorrect database_size assertion in test_valid**

- **Found during:** Task 2 (test execution)
- **Issue:** Test comment said `_format_size(594718752768) → 554.0 GB` but actual result is `553.9 GB` (594718752768 / 1073741824 = 553.938...)
- **Fix:** Updated assertion from `"554.0 GB"` to `"553.9 GB"` and corrected the comment
- **Files modified:** tests/test_tools_dag.py
- **Verification:** Test passes after correction
- **Committed in:** b68d6d0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — incorrect test assertion)
**Impact on plan:** Fix required for test correctness; no scope creep.

## Issues Encountered

None beyond the auto-fixed test assertion error above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 3 Phase 4 DAG/database tools are implemented and tested: `list_dag_members`, `get_dag_health`, `get_database_copies`
- Phase 5 (mail flow tools) can begin immediately: `check_mail_flow`, `get_transport_queues`, `get_smtp_connectors`
- 9 stubs remain (Phases 5-6): check_mail_flow, get_transport_queues, get_smtp_connectors, get_dkim_config, get_dmarc_status, check_mobile_devices, get_hybrid_config, get_migration_batches, get_connector_status
- 128 unit tests passing, 3 pre-existing integration failures (require live Exchange Online)

---
*Phase: 04-dag-and-database-tools*
*Completed: 2026-03-20*
