---
phase: 07-chat-app-core
plan: 04
subsystem: mcp-client
tags: [mcp, asyncio, threading, openai, flask, subprocess, stdio]

# Dependency graph
requires:
  - phase: 07-01
    provides: Flask app factory (create_app) and startup lifecycle for init_mcp hook
  - phase: 02-01
    provides: exchange_mcp.server MCP server over stdio transport
provides:
  - MCP subprocess lifecycle management (spawn once at Flask startup, alive for app lifetime)
  - Async bridge: daemon thread event loop + run_coroutine_threadsafe pattern
  - tools/list cached as OpenAI function schemas (15 tools)
  - call_mcp_tool() synchronous wrapper with threading lock for Flask routes
  - is_connected() health check
affects:
  - 07-05 (chat completion route injects get_openai_tools() and calls call_mcp_tool())
  - 07-06 (any further MCP integration or health endpoints)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Daemon thread event loop: asyncio loop runs in daemon thread; Flask never calls asyncio.run()"
    - "run_coroutine_threadsafe bridge: submit coroutine to background loop, block for result"
    - "AsyncExitStack for MCP session lifecycle: single stack owns stdio_client + ClientSession contexts"
    - "threading.Lock for MCP serialisation: stdio JSON-RPC stream is single-lane, lock prevents interleaving"
    - "OpenAI schema conversion: mcp.types.Tool → {type:function, function:{name,description,parameters}}"
    - "Lazy init: module import is side-effect-free; subprocess only spawned on explicit init_mcp()"

key-files:
  created:
    - chat_app/mcp_client.py
  modified: []

key-decisions:
  - "Daemon thread owns asyncio.new_event_loop() and calls loop.run_forever() — cleanest isolation from Flask's sync context"
  - "_async_run() uses run_coroutine_threadsafe().result(timeout) — standard bridge, no asyncio.run() in Flask handlers"
  - "AsyncExitStack entered once in _connect_mcp() and kept alive in _exit_stack — correct async context manager lifecycle"
  - "threading.Lock wraps every call_mcp_tool() call — MCP stdio session is single JSON-RPC stream, concurrent calls would corrupt it"
  - "init_mcp(app=None) accepts optional Flask app for extension pattern compatibility but does not use it"
  - "Timeout for init_mcp connection set to 120s — Exchange auth startup can be slow on cold sessions"
  - "call_mcp_tool extracts .text from all content items — handles multi-segment tool responses"

patterns-established:
  - "Flask-to-asyncio bridge: daemon thread loop + run_coroutine_threadsafe (reuse for any future async integration)"
  - "MCP tool schema cache: call get_openai_tools() per request — cheap list return, no re-enumeration"

# Metrics
duration: 5min
completed: 2026-03-21
---

# Phase 7 Plan 04: MCP Client Integration Summary

**Async bridge spawning exchange_mcp.server subprocess via stdio, caching 15 tools as OpenAI function schemas, and providing a threading-lock-serialised call_mcp_tool() for synchronous Flask routes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-21T19:07:20Z
- **Completed:** 2026-03-21T19:12:49Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Daemon thread owns dedicated asyncio event loop — asyncio.run() never called from Flask request handlers
- StdioServerParameters spawns `uv run python -m exchange_mcp.server` subprocess via stdio_client
- tools/list result (15 tools) converted to OpenAI `{type:function, function:{name,description,parameters}}` schemas and cached in-memory
- threading.Lock serialises all MCP tool calls — single JSON-RPC stream can only handle one request at a time
- Module import is side-effect-free — subprocess only spawns when init_mcp() is explicitly called

## Task Commits

Each task was committed atomically:

1. **Task 1: Create mcp_client.py with async bridge, subprocess lifecycle, and tool dispatch** - `735036d` (feat)

**Plan metadata:** _(pending final commit)_

## Files Created/Modified
- `chat_app/mcp_client.py` - MCP async bridge: daemon thread event loop, stdio_client subprocess lifecycle, tool schema cache, synchronous call_mcp_tool wrapper

## Decisions Made
- **Daemon thread + run_forever**: `asyncio.new_event_loop()` in daemon thread calling `loop.run_forever()` is the cleanest isolation pattern — no interference with Flask's WSGI synchronous model
- **AsyncExitStack held as module state**: `_exit_stack` keeps the `stdio_client` and `ClientSession` async context managers alive for the app's lifetime, avoiding premature cleanup
- **threading.Lock wraps every call_mcp_tool()**: MCP stdio sessions use a single JSON-RPC byte stream; concurrent calls from multiple Flask worker threads would corrupt the stream
- **120s init timeout**: Exchange Online MCP server does auth at startup which can be slow; 60s would risk timing out on cold start
- **init_mcp(app=None)**: Optional Flask `app` parameter accepted for Flask extension pattern compatibility (e.g. `init_mcp(app)` in factory) but the connection is process-global, not app-scoped

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The MCP SDK's `stdio_client` is an async context manager that yields `(read_stream, write_stream)`, and `ClientSession` is also an async context manager — both fit cleanly into `AsyncExitStack`. The `run_coroutine_threadsafe` bridge pattern worked as expected.

## User Setup Required

None - no external service configuration required beyond what was already established for the MCP server in prior phases.

## Next Phase Readiness
- `chat_app/mcp_client.py` is ready for 07-05 to import `init_mcp`, `get_openai_tools`, and `call_mcp_tool`
- `init_mcp(app)` should be called from `create_app()` in `app.py` (07-05 or 07-06 wires this up)
- Blocker remains: MMC Azure OpenAI API version 2023-05-15 `tools` parameter support — verify before 07-05 tool-call loop implementation

---
*Phase: 07-chat-app-core*
*Completed: 2026-03-21*
