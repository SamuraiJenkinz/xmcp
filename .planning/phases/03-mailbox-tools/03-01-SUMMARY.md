---
phase: 03-mailbox-tools
plan: "01"
subsystem: mailbox-tools
tags: [exchange, tools, mailbox, validation, formatting, handlers]

dependency-graph:
  requires:
    - 02-03 (tool definitions and dispatch table scaffold)
  provides:
    - _validate_upn helper (email format guard for all Phase 3-6 handlers)
    - _escape_ps_single_quote helper (PowerShell injection prevention)
    - _format_size helper (human-readable byte conversion)
    - _get_mailbox_stats_handler (first real Exchange tool implementation)
  affects:
    - 03-02 (search_mailboxes — will reuse _validate_upn and _format_size helpers)
    - 03-03 (get_shared_mailbox_owners — will reuse _validate_upn helper)
    - All Phase 4-6 handlers (shared helper infrastructure established)

tech-stack:
  added: []
  patterns:
    - Two-call handler pattern (stats cmdlet + quota cmdlet merged into one response)
    - Shared helper module section in tools.py for cross-handler reuse
    - "not found" error interception with user-friendly re-raise using `from None`
    - List normalization for single-result Exchange responses

file-tracking:
  created:
    - tests/test_tools_mailbox.py
  modified:
    - exchange_mcp/tools.py

decisions:
  - id: "03-01-a"
    description: "last_logon passed through as-is from Exchange (no date parsing)"
    rationale: "Exchange returns /Date(milliseconds)/ format which the LLM can interpret; avoid fragile date parsing"
  - id: "03-01-b"
    description: "total_size_bytes included alongside human-friendly total_size"
    rationale: "LLM needs raw bytes to compute quota percentages; human string is for display only"
  - id: "03-01-c"
    description: "Quota values passed as strings (not parsed)"
    rationale: "Exchange returns '49.5 GB (53,150,220,288 bytes)' — LLM reads natural language fine; no parsing needed"
  - id: "03-01-d"
    description: "test_call_tool_not_implemented_raises updated to use search_mailboxes stub"
    rationale: "get_mailbox_stats is now a real handler; the stub test must use a tool still in stub form"

metrics:
  duration: "~4 min"
  completed: "2026-03-20"
---

# Phase 3 Plan 01: Mailbox Stats Handler Summary

**One-liner:** First real Exchange handler with three shared helpers (_validate_upn, _format_size, _escape_ps_single_quote) establishing the two-call stats+quota pattern for all mailbox tools.

## What Was Built

Added the `get_mailbox_stats` tool handler and shared helper infrastructure to `exchange_mcp/tools.py`. This is the first real Exchange tool implementation, replacing the stub from Phase 2.

### Shared Helpers Added

- **`_validate_upn(email)`** — Regex-based email validation that raises `RuntimeError` with a user-friendly message echoing the bad input. Used by all Phase 3-6 handlers.
- **`_escape_ps_single_quote(value)`** — Doubles single quotes for safe embedding in PowerShell single-quoted strings. Prevents injection of malicious PowerShell via email addresses.
- **`_format_size(byte_count)`** — Converts raw byte counts to human-friendly strings (GB, MB, KB, B). Returns `None` for `None` input.

### Handler Pattern Established

`_get_mailbox_stats_handler` makes two sequential `run_cmdlet_with_retry` calls:
1. `Get-MailboxStatistics` — size, item count, last logon, database placement
2. `Get-Mailbox` — quota thresholds (warning, prohibit send, prohibit send+receive)

Results are merged into a single snake_case dict. "Not found" errors from Exchange are intercepted and re-raised with a friendly message; all other errors propagate unchanged for `server.py` sanitization.

## Test Coverage

Created `tests/test_tools_mailbox.py` with 19 tests:
- 12 unit tests for helper functions (all edge cases: None, zero, empty string, no-@ UPN, etc.)
- 7 handler tests covering: valid full path, invalid email, not-found interception, error propagation, null last_logon, no client, list normalization

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_call_tool_not_implemented_raises used get_mailbox_stats**

- **Found during:** Task 2 (full test suite run)
- **Issue:** `test_server.py::test_call_tool_not_implemented_raises` called `get_mailbox_stats` expecting the "not yet implemented" stub message, but the handler is now real and raises "Exchange client is not available." instead.
- **Fix:** Updated the test to use `search_mailboxes` (still a stub), which correctly raises "not yet implemented". Updated the module docstring to say "remaining stub tools".
- **Files modified:** `tests/test_server.py`
- **Commit:** 7e17224

## Next Phase Readiness

- `search_mailboxes` and `get_shared_mailbox_owners` handlers (Plans 02-03) can reuse `_validate_upn` and `_format_size` directly from this plan.
- The two-call pattern is proven: Phase 4 DAG handlers follow the same structure.
- No blockers.
