---
phase: 07-chat-app-core
plan: "05"
subsystem: api
tags: [openai, mcp, tool-calling, flask, python]

# Dependency graph
requires:
  - phase: 07-03
    provides: openai_client.py with _message_to_dict, init_openai, get_client
  - phase: 07-04
    provides: mcp_client.py with init_mcp, call_mcp_tool, get_openai_tools, is_connected
provides:
  - run_tool_loop in openai_client.py: iterative tool-calling loop dispatching to MCP
  - chat_with_tools in openai_client.py: user message + tool loop convenience wrapper
  - Flask app startup wiring for OpenAI and MCP clients
  - /api/health endpoint reporting mcp_connected and tools_count
affects: ["07-06", "future chat endpoint plans"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tool-call loop: iterate completions.create until no tool_calls, max 5 iterations"
    - "Module-level _use_tools_param flag: fallback from tools/tool_choice to functions/function_call"
    - "Graceful degradation: init_openai and init_mcp wrapped in try/except in app factory"
    - "tool_events list: {name, status} per MCP dispatch for UI streaming"

key-files:
  created: []
  modified:
    - chat_app/openai_client.py
    - chat_app/app.py

key-decisions:
  - "json.loads(tc.function.arguments) with fallback to {} on JSONDecodeError — arguments may be empty string"
  - "_use_tools_param flag at module level so all requests in same process use consistent format after fallback"
  - "tool_events returned alongside messages — caller decides what to stream to UI"
  - "init_openai and init_mcp wrapped in try/except in create_app — app starts in degraded mode if either unavailable"
  - "/api/health returns tools_count via len(get_openai_tools()) — reflects actual cached tool count"

patterns-established:
  - "Tool loop: append assistant_msg → dispatch each tc.id → append role=tool → continue; break on no tool_calls"
  - "Legacy fallback: catch gateway rejection of 'tools' param, set _use_tools_param=False, retry with functions"

# Metrics
duration: 2min
completed: "2026-03-21"
---

# Phase 7 Plan 05: Tool-Calling Loop Summary

**`run_tool_loop` in openai_client.py: OpenAI-to-MCP tool dispatch loop with tools/functions fallback, max-5-iteration guard, and tool_events tracking**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-21T19:15:45Z
- **Completed:** 2026-03-21T19:17:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `run_tool_loop` iterates completion calls up to 5 times, dispatching each `tool_call` to MCP via `call_mcp_tool` and appending `role=tool` results with correct `tool_call_id`
- Module-level `_use_tools_param` flag enables transparent fallback from `tools`/`tool_choice` to deprecated `functions`/`function_call` when MMC gateway rejects the modern format
- Flask `create_app()` now calls `init_openai()` and `init_mcp(app)` at startup with graceful degradation; `/api/health` reports connection status and tool count

## Task Commits

Each task was committed atomically:

1. **Task 1: Add run_tool_loop to openai_client.py with MCP dispatch and API fallback** - `753342d` (feat)
2. **Task 2: Wire MCP and OpenAI initialization into Flask app startup** - `91c7eab` (feat)

**Plan metadata:** (see below)

## Files Created/Modified

- `chat_app/openai_client.py` - Added `_MAX_TOOL_ITERATIONS`, `_use_tools_param`, `run_tool_loop`, `chat_with_tools`; imports `json`, `call_mcp_tool`, `get_openai_tools`
- `chat_app/app.py` - Added `init_openai()` + `init_mcp(app)` calls in `create_app()`; added `/api/health` endpoint; imports `jsonify`, `init_mcp`, `is_connected`, `get_openai_tools`, `init_openai`

## Decisions Made

- `json.loads(tc.function.arguments)` with `except json.JSONDecodeError: arguments = {}` — arguments string may be empty or malformed from gateway
- `_use_tools_param` is module-level so the fallback persists across all requests after first detection — avoids repeated gateway rejections
- `tool_events` list returned alongside messages — Flask route caller decides what to stream vs. log
- Both `init_openai()` and `init_mcp(app)` wrapped in `try/except` in `create_app()` — app can start for dev/testing without Exchange access
- `/api/health` uses `len(get_openai_tools())` which returns the cached `_mcp_tools` list — accurate post-startup count

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `chat_with_tools` and `run_tool_loop` are ready for the chat API endpoint (07-06) to call
- `/api/health` available immediately for smoke-testing MCP connectivity post-deployment
- The `_use_tools_param` fallback means the app will work with both current and legacy MMC gateway API versions

---
*Phase: 07-chat-app-core*
*Completed: 2026-03-21*
