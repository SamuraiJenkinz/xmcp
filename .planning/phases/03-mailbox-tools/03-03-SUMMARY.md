---
phase: 03-mailbox-tools
plan: "03"
subsystem: mailbox-tools
tags: [exchange, tools, mailbox, permissions, delegates, full-access, send-as, send-on-behalf]

dependency-graph:
  requires:
    - 03-01 (shared helpers _validate_upn, _escape_ps_single_quote)
    - 03-02 (handler pattern: three-query Exchange calls, not-found interception)
  provides:
    - _get_shared_mailbox_owners_handler (three-permission-type delegate query)
  affects:
    - Phase 4+ (all Phase 3 mailbox tools now complete; handler pattern established for DAG/DB tools)

tech-stack:
  added: []
  patterns:
    - Three sequential Exchange calls per handler (FullAccess + SendAs + SendOnBehalf)
    - System account filtering in PowerShell (NT AUTHORITY\*, S-1-5-*, SELF) rather than Python
    - GrantSendOnBehalfTo null/string/list normalization via isinstance branching
    - Consistent delegate entry shape across all permission types
    - Not-found interception with user-friendly message echoing the email address

file-tracking:
  created: []
  modified:
    - exchange_mcp/tools.py
    - tests/test_tools_mailbox.py

decisions:
  - id: "03-03-a"
    description: "System account filtering in PowerShell Where-Object, not Python"
    rationale: "Reduces data transferred and processed; keeps filter logic co-located with query"
  - id: "03-03-b"
    description: "via_group always null — Exchange cmdlets do not expose source group for inherited permissions"
    rationale: "Get-MailboxPermission shows inherited=True but not which group caused it; field reserved for future enhancement"
  - id: "03-03-c"
    description: "SendAs display_name always null — Get-RecipientPermission has no display name field"
    rationale: "Would require a second Get-Recipient call per delegate; not worth the latency at this stage"
  - id: "03-03-d"
    description: "GrantSendOnBehalfTo identity returned as-is (DN/UPN string) without resolution"
    rationale: "Resolving each DN to a display name would require N additional Get-Recipient calls; LLM can interpret the raw value"

metrics:
  duration: "~2 min"
  completed: "2026-03-20"
---

# Phase 3 Plan 03: Get Shared Mailbox Owners Summary

**get_shared_mailbox_owners handler with three Exchange permission queries (FullAccess via Get-MailboxPermission, SendAs via Get-RecipientPermission, SendOnBehalf via Get-Mailbox GrantSendOnBehalfTo) — completes Phase 3 mailbox tools.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-20T10:27:28Z
- **Completed:** 2026-03-20T10:29:41Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implemented `_get_shared_mailbox_owners_handler` with three sequential Exchange cmdlet calls
- System accounts (NT AUTHORITY\*, S-1-5-*, SELF) filtered in PowerShell before data is returned to Python
- All edge cases handled: GrantSendOnBehalfTo null/string/list, single-result dict vs list normalization
- 10 new unit tests added to `tests/test_tools_mailbox.py` (41 total in mailbox test file)
- All 3 Phase 3 mailbox tool stubs replaced with real handlers — 12 stubs remain for Phases 4-6
- Full test suite: 97 passed, 3 pre-existing Exchange integration failures (require live EXO connection)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_shared_mailbox_owners handler to tools.py** - `580a644` (feat)
2. **Task 2: Add unit tests and run full test suite** - `bd7bb51` (test)

**Plan metadata:** `[pending]` (docs: complete plan)

## Files Created/Modified

- `exchange_mcp/tools.py` - Added `_get_shared_mailbox_owners_handler` (100 lines); updated TOOL_DISPATCH to use real handler
- `tests/test_tools_mailbox.py` - Added 10 tests for `get_shared_mailbox_owners`; updated module docstring; added import

## Decisions Made

- System account filtering in PowerShell `Where-Object` rather than Python post-processing — reduces data transferred and keeps filter logic co-located with the query
- `via_group` is always null — Exchange cmdlets (`Get-MailboxPermission`) show `IsInherited=True` but do not expose which group caused the inheritance; field is reserved for a future enhancement
- `display_name` is null for SendAs entries — `Get-RecipientPermission` has no display name field; adding one would require a second `Get-Recipient` call per delegate
- GrantSendOnBehalfTo identity returned as-is (DN/UPN string) — resolving each to a display name would require N additional `Get-Recipient` calls; LLM can interpret the raw value

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. All 10 tests passed on first run. The 3 integration test failures are pre-existing (require `ExchangeOnlineManagement` module and live Exchange Online credentials).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 3 (Mailbox Tools) is complete: `get_mailbox_stats`, `search_mailboxes`, `get_shared_mailbox_owners` all have real handlers
- Phase 4 (DAG and Database Tools) can begin: `list_dag_members`, `get_dag_health`, `get_database_copies`
- The three-call handler pattern established here (sequential Exchange queries + not-found interception) is the template for Phase 4 multi-query tools
- No blockers

---
*Phase: 03-mailbox-tools*
*Completed: 2026-03-20*
