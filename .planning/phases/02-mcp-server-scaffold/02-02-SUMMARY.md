---
phase: 02-mcp-server-scaffold
plan: "02"
subsystem: api
tags: [mcp, tools, dispatch, exchange, python, asyncio]

# Dependency graph
requires:
  - phase: 02-01
    provides: server scaffold with ping tool, error sanitization, _sanitize_error, SIGTERM handler
provides:
  - TOOL_DEFINITIONS list with 16 types.Tool objects (15 Exchange + ping) in exchange_mcp/tools.py
  - TOOL_DISPATCH dict mapping all 16 tool names to async handlers in exchange_mcp/tools.py
  - server.py handle_list_tools returning all TOOL_DEFINITIONS
  - server.py handle_call_tool dispatching via TOOL_DISPATCH with NotImplementedError/Exception branching
  - 13 passing tests covering tool registration, dispatch, schemas, stubs, and error paths
affects:
  - 02-03
  - 03-mailbox-tools
  - 04-dag-database-tools
  - 05-mail-flow-security-tools
  - 06-hybrid-tools

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TOOL_DEFINITIONS + TOOL_DISPATCH separation: definitions in one list, handlers in a separate dict"
    - "Stub pattern via _make_stub(tool_name): closure factory producing named async stubs raising NotImplementedError"
    - "Three-branch error handling in call_tool: NotImplementedError → plain RuntimeError, ValueError → RuntimeError via sanitize, Exception → sanitized RuntimeError"
    - "TYPE_CHECKING guard on ExchangeClient import in tools.py to avoid circular imports"

key-files:
  created:
    - exchange_mcp/tools.py
  modified:
    - exchange_mcp/server.py
    - tests/test_server.py

key-decisions:
  - "NotImplementedError from stubs is caught separately and re-raised as RuntimeError with the raw message (no _sanitize_error) — the stub message is already clean"
  - "Startup banner reads len(TOOL_DEFINITIONS) directly rather than calling handle_list_tools() — avoids async call in sync context and is simpler"
  - "TYPE_CHECKING guard used for ExchangeClient in tools.py — dispatch handlers receive client at call time, not import time"

patterns-established:
  - "Stub factory pattern: _make_stub(name) returns a closure so every stub has a unique __name__ for debugging"
  - "JSON Schema inputSchema with enum for constrained strings, required only for truly mandatory params"
  - "Tool descriptions: plain language, under 800 chars, include 'Use when asked about...' with 2-3 examples"

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 2 Plan 02: Tool Registration and Dispatch Table Summary

**16 Exchange MCP tools registered with JSON Schema definitions, stub dispatch table, and three-branch error handling; all 13 tests pass**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T22:53:23Z
- **Completed:** 2026-03-19T22:57:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `exchange_mcp/tools.py` with 16 `types.Tool` objects (15 Exchange + ping) grouped by phase, each with natural-language descriptions under 800 chars and correct JSON Schema inputSchemas
- Created `TOOL_DISPATCH` mapping every tool name to an async handler — ping fully implemented, all 15 Exchange tools stubbed with `NotImplementedError`
- Updated `server.py` handle_list_tools and handle_call_tool to use tools.py, with three-branch error handling (NotImplementedError, ValueError, generic Exception)
- Expanded test suite from 7 to 13 tests covering tool count, dispatch completeness, schema structure, stub error paths, and ping dispatch

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tools.py with all 15 tool definitions and dispatch table** - `ce70297` (feat)
2. **Task 2: Update server.py to use tools.py and add dispatch logic** - `03b20e8` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `exchange_mcp/tools.py` - TOOL_DEFINITIONS (16 types.Tool) and TOOL_DISPATCH (16 async handlers); ping implemented, Exchange tools stubbed
- `exchange_mcp/server.py` - handle_list_tools returns TOOL_DEFINITIONS; handle_call_tool dispatches via TOOL_DISPATCH with NotImplementedError/Exception branches
- `tests/test_server.py` - Expanded from 7 to 13 tests; 6 new tests cover tool count, dispatch completeness, description lengths, stub error, ping dispatch, schema structure

## Decisions Made

- NotImplementedError from stubs is re-raised as plain `RuntimeError(str(exc))` without going through `_sanitize_error` — the stub message is already a clean, LLM-friendly string
- Startup banner in `main()` uses `len(TOOL_DEFINITIONS)` directly instead of calling `await handle_list_tools()` — simpler and avoids unnecessary async call
- TYPE_CHECKING guard on `ExchangeClient` import in tools.py — handlers receive the client instance at call time as a parameter; the import is only needed for type hints

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 16 tools are registered and enumerable via `mcp dev exchange_mcp/server.py`
- All 15 Exchange tool stubs return clean "not yet implemented" RuntimeErrors through the SDK's isError=True path
- Phase 3 (mailbox tools) can directly replace the three stub handlers in TOOL_DISPATCH without changing any other code
- The dispatch pattern, error branching, and schema conventions are established for Phases 3-6 to follow

---
*Phase: 02-mcp-server-scaffold*
*Completed: 2026-03-19*
