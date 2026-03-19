---
phase: 02-mcp-server-scaffold
plan: 01
subsystem: mcp-server
tags: [mcp, stdio, anyio, python, logging, exchange-online, error-sanitization]

# Dependency graph
requires:
  - phase: 01-exchange-client-foundation
    provides: ExchangeClient with verify_connection(), auth_mode, run_cmdlet()

provides:
  - exchange_mcp/server.py — runnable MCP server with stdio transport, ping tool, startup validation
  - _sanitize_error() — PS traceback stripping with transient/non-transient classification
  - handle_list_tools() / handle_call_tool() — MCP decorator-registered handlers
  - logging discipline (stderr-only) established for all subsequent plans
  - Startup validation pattern: verify_connection() before stdio_server() opens

affects:
  - 02-02 (tool registration builds on server.py handlers)
  - 02-03 (integration/smoke tests use server.py entry point)
  - 03-06 (all tool phases add tools to handle_call_tool dispatch)

# Tech tracking
tech-stack:
  added:
    - mcp 1.26.0 low-level Server class (decorator-based, no FastMCP)
    - mcp.server.stdio.stdio_server (stdio transport context manager)
    - anyio.run() (entry point — matches mcp SDK's own runtime)
  patterns:
    - Logging to sys.stderr as first executable act (before all other imports)
    - Startup validation before stdio_server() opens (fail fast, clean exit)
    - _sanitize_error() template for error wrapping across all tool handlers
    - raise RuntimeError(sanitized_msg) from None — SDK catches and creates isError=True
    - SIGTERM handler wrapped in try/except for Windows compatibility

key-files:
  created:
    - exchange_mcp/server.py
    - tests/test_server.py
  modified: []

key-decisions:
  - "Low-level mcp.server.Server used (not FastMCP) — locked project decision"
  - "anyio.run(main) as entry point — matches mcp SDK runtime; asyncio.run() works but anyio is idiomatic"
  - "Human-readable log format chosen over structured JSON — simpler for internal admin tool"
  - "Startup validation before stdio_server() — ensures clean sys.exit(1) on auth failure"
  - "_sanitize_error() raises RuntimeError(clean_msg) from None — SDK's _make_error_result(str(e)) creates isError=True"

patterns-established:
  - "Error wrapping: catch Exception → _sanitize_error(exc) → raise RuntimeError(msg) from None"
  - "Logging: stderr-only, configured before any other imports, INFO level"
  - "Tool handlers: async def, return list[types.TextContent], log start/end/duration"
  - "Transient error detection: check _NON_TRANSIENT_PATTERNS first, then _TRANSIENT_PATTERNS"

# Metrics
duration: 7min
completed: 2026-03-19
---

# Phase 2 Plan 1: MCP Server Scaffold Summary

**stdio MCP server with stderr logging, Exchange startup validation, ping placeholder tool, and PS-traceback-stripping error sanitization pattern**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-19T22:43:14Z
- **Completed:** 2026-03-19T22:50:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `exchange_mcp/server.py` as a fully runnable MCP server that imports cleanly and establishes all core conventions
- Implemented `_sanitize_error()` — the reusable error wrapper that strips PowerShell stderr tracebacks, removes `PowerShell exited with code N.` prefixes, and appends a transient retry hint for network/connection errors
- Established the critical logging discipline: `logging.basicConfig(stream=sys.stderr)` as the absolute first executable code, before all other imports
- 7 unit tests pass without live Exchange connection, covering ping tool, error sanitization, and server instance

## Task Commits

Each task was committed atomically:

1. **Task 1: Create server.py with logging, stdio transport, placeholder tool, startup validation, and shutdown** - `d6d4b38` (feat)
2. **Task 2: Write unit tests for server scaffold** - `08a70e4` (test)

## Files Created/Modified

- `exchange_mcp/server.py` — Runnable MCP server entry point; logging first, Server instance, list_tools/call_tool handlers, _sanitize_error(), SIGTERM handler, anyio.run(main)
- `tests/test_server.py` — 7 unit tests covering ping tool, call_tool dispatch, error sanitization (stderr stripping, transient/non-transient hints), and server instance

## Decisions Made

- **anyio.run(main) over asyncio.run(main())**: anyio is the correct runtime since mcp SDK uses anyio internally; asyncio.run works but anyio.run is idiomatic and avoids potential backend selection edge cases.
- **Human-readable log format**: `"%(asctime)s %(levelname)-8s %(name)s: %(message)s"` chosen over structured JSON. Internal admin tool — terminal readability is more valuable than machine-parseable logs at this stage.
- **raise RuntimeError(sanitized) from None**: The SDK's `call_tool` decorator catches all exceptions and calls `_make_error_result(str(e))` — raising a pre-sanitized RuntimeError ensures the LLM only sees the clean message, not the PS traceback.
- **SIGTERM handler in try/except**: Windows may behave differently for SIGTERM; wrapping in try/except allows the server to start normally on Windows even if SIGTERM registration fails.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — `uv` binary was not in the bash PATH (found at `/c/Users/taylo/uv_install/uv.exe`); used full path for all verification commands.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `exchange_mcp/server.py` is ready for Plan 02 tool registration — `handle_list_tools()` and `handle_call_tool()` are the extension points
- `_sanitize_error()` is the established pattern for all 15 Exchange tools in Phases 3-6
- No blockers for Plan 02 (tool registration)

---
*Phase: 02-mcp-server-scaffold*
*Completed: 2026-03-19*
