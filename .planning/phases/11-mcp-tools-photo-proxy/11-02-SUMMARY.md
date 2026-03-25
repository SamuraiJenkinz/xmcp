---
phase: 11-mcp-tools-photo-proxy
plan: 02
subsystem: api
tags: [mcp, graph-api, async, asyncio, tool-dispatch, colleagues]

# Dependency graph
requires:
  - phase: 11-01
    provides: get_user_profile, search_users in graph_client; search_colleagues and get_colleague_profile schemas in TOOL_DEFINITIONS
provides:
  - _search_colleagues_handler async function registered in TOOL_DISPATCH
  - _get_colleague_profile_handler async function registered in TOOL_DISPATCH
  - TOOL_DISPATCH extended from 15 to 17 entries
  - photo_url pattern (/api/photo/{user_id}) established for binary photo proxy
affects: [11-03-photo-proxy, chat_app tool-calling loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.to_thread wrapping sync graph_client calls in async MCP handlers"
    - "Lazy import of graph_client inside handler bodies to avoid module-scope Config evaluation"
    - "Falsy-value omission pattern for profile dicts (omit None, empty string, empty list)"
    - "photo_url indirection: return URL string, never binary bytes in tool result"

key-files:
  created: []
  modified:
    - exchange_mcp/tools.py
    - exchange_mcp/server.py

key-decisions:
  - "photo_url always included in get_colleague_profile result even if user has no photo — proxy handles fallback"
  - "user ID deliberately excluded from search_colleagues results (search returns name/title/dept/email only)"
  - "graph_client imported inside handler function body — avoids Config evaluation at import time"
  - "asyncio.to_thread used for sync graph_client calls — keeps MCP event loop non-blocking"

patterns-established:
  - "Handler-local import pattern: from chat_app.graph_client import X inside async def, not at module scope"
  - "photo_url proxy pattern: /api/photo/{user_id} — binary data stays out of tool results"

# Metrics
duration: 12min
completed: 2026-03-25
---

# Phase 11 Plan 02: MCP Tool Handlers Summary

**search_colleagues and get_colleague_profile handlers wired into TOOL_DISPATCH using asyncio.to_thread + lazy graph_client imports, with ID-stripped search results and photo_url proxy indirection**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-25T00:15Z
- **Completed:** 2026-03-25T00:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Implemented `_search_colleagues_handler` — validates query, checks Graph enabled, wraps sync `search_users` in `asyncio.to_thread`, slices to 10, strips IDs, omits falsy fields
- Implemented `_get_colleague_profile_handler` — validates user_id, checks Graph enabled, wraps sync `get_user_profile` in `asyncio.to_thread`, omits falsy fields, always appends `photo_url`
- TOOL_DISPATCH extended from 15 to 17 entries — both new tools callable end-to-end
- server.py tool count comments updated to 17

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement _search_colleagues_handler and _get_colleague_profile_handler** - `d954dfe` (feat)
2. **Task 2: Update server.py tool count comment** - `38b29fb` (docs)

## Files Created/Modified
- `exchange_mcp/tools.py` — Added `asyncio` import, two handler functions (~75 lines), two TOOL_DISPATCH entries
- `exchange_mcp/server.py` — Updated tool count comments from 15 to 17 (two locations)

## Decisions Made
- photo_url always included regardless of whether user has a photo — the /api/photo proxy (plan 11-03) handles the fallback gracefully, so handler never needs to check photo existence
- user ID excluded from search_colleagues results per CONTEXT.md design decision — prevents LLM from leaking IDs to users; get_colleague_profile requires explicit ID so that's an intentional caller-supplied parameter
- Graph client imported inside handler function body — avoids Config evaluation at module import time (Config reads env vars; if Azure creds missing, module import would fail)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required for this plan.

## Next Phase Readiness
- Both MCP tools are now callable end-to-end by the LLM tool-calling loop
- photo_url field in get_colleague_profile results references `/api/photo/{user_id}` — plan 11-03 must implement this Flask route to serve binary photo bytes (or a fallback avatar)
- No blockers for 11-03

---
*Phase: 11-mcp-tools-photo-proxy*
*Completed: 2026-03-25*
