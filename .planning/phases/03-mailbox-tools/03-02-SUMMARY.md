---
phase: 03-mailbox-tools
plan: "02"
subsystem: mailbox-tools
tags: [exchange, tools, mailbox, search, filtering, truncation]

dependency-graph:
  requires:
    - 03-01 (shared helpers _validate_upn, _escape_ps_single_quote, _format_size)
  provides:
    - _search_mailboxes_handler (mailbox search with 3 filter modes)
  affects:
    - 03-03 (get_shared_mailbox_owners — completes Phase 3 mailbox tools)

tech-stack:
  added: []
  patterns:
    - Three-mode filter dispatch (database, type, name/ANR)
    - Truncation detection via max_results+1 request trick
    - "Not found" errors returned as empty results for search operations (not re-raised)
    - ANR wildcard stripping for PowerShell -Anr parameter

file-tracking:
  created: []
  modified:
    - exchange_mcp/tools.py
    - tests/test_tools_mailbox.py
    - tests/test_server.py

decisions:
  - id: "03-02-a"
    description: "ANR trailing wildcard stripped before passing to -Anr"
    rationale: "PowerShell -Anr does implicit prefix matching; trailing * is redundant and could confuse the cmdlet"
  - id: "03-02-b"
    description: "Database not-found returns empty result (not error)"
    rationale: "Search finding nothing is a valid outcome; errors should be reserved for actual failures"
  - id: "03-02-c"
    description: "RecipientTypeDetails passed unquoted to PowerShell"
    rationale: "It is an enum parameter in PowerShell, not a string — quoting would cause parse errors"
  - id: "03-02-d"
    description: "test_call_tool_not_implemented_raises updated to use list_dag_members stub"
    rationale: "search_mailboxes is now a real handler; the stub test must use a tool still in stub form"

metrics:
  duration: "~5 min"
  completed: "2026-03-20"
---

# Phase 3 Plan 02: Search Mailboxes Handler Summary

**One-liner:** search_mailboxes handler with three filter modes (database, type, name/ANR), ResultSize capping with truncation detection, and empty result handling.

## What Was Built

Added `_search_mailboxes_handler` to `exchange_mcp/tools.py`, replacing the Phase 2 stub. The handler supports three filter modes:

1. **database** — `Get-Mailbox -Database '{value}'` — find mailboxes on a specific database
2. **type** — `Get-Mailbox -RecipientTypeDetails {value}` — find mailboxes by type (UserMailbox, SharedMailbox, etc.)
3. **name** — `Get-Mailbox -Anr '{value}'` — Ambiguous Name Resolution search across display name, alias, email

### Key Features

- **Truncation detection:** Requests `max_results + 1` from Exchange, returns `max_results`, sets `truncated: true` if more exist
- **Empty results:** Returns structured `{results: [], count: 0, message: "..."}` instead of errors
- **ANR wildcard stripping:** Trailing `*` from user input is stripped since `-Anr` does implicit prefix matching
- **Not-found as empty:** Database not-found errors return empty results (search finding nothing is valid)

## Test Coverage

Added 12 tests to `tests/test_tools_mailbox.py` (total now 31):
- All three filter modes (name, type, database)
- Empty results, truncation detection
- Invalid filter_type, empty filter_value
- Single-result dict normalization, no client
- Wildcard stripping, not-found-returns-empty, default max_results

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_call_tool_not_implemented_raises used search_mailboxes**

- **Found during:** Full test suite regression check
- **Issue:** `test_server.py::test_call_tool_not_implemented_raises` called `search_mailboxes` expecting the "not yet implemented" stub message, but the handler is now real.
- **Fix:** Updated the test to use `list_dag_members` (still a stub).
- **Files modified:** `tests/test_server.py`

## Next Phase Readiness

- `get_shared_mailbox_owners` (Plan 03) is the final mailbox tool — reuses the same helper pattern.
- No blockers.
