---
phase: 11-mcp-tools-photo-proxy
plan: 01
subsystem: api
tags: [graph-api, msal, requests, mcp, tool-definitions, colleague-lookup, photo]

# Dependency graph
requires:
  - phase: 10-graph-client-foundation
    provides: graph_client singleton with _graph_request_with_retry, _make_headers, search_users, get_user_photo_bytes
provides:
  - get_user_profile() in graph_client.py — user detail fields + manager displayName via $expand in one Graph call
  - get_user_photo_96() in graph_client.py — 96x96 thumbnail bytes via /photos/96x96/$value endpoint
  - search_colleagues tool schema in TOOL_DEFINITIONS
  - get_colleague_profile tool schema in TOOL_DEFINITIONS
affects:
  - 11-02 (MCP handlers that dispatch to get_user_profile and search_users)
  - 11-03 (photo proxy route that consumes get_user_photo_96)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Graph expand pattern: $expand=manager($select=displayName) fetches related entity in one call"
    - "96x96 thumbnail endpoint: /users/{id}/photos/96x96/$value for consistently-sized avatars"
    - "Defensive None return: all Graph functions return None on 404/error, never raise to caller"

key-files:
  created: []
  modified:
    - chat_app/graph_client.py
    - exchange_mcp/tools.py

key-decisions:
  - "Used $expand=manager($select=displayName) to fetch manager name without a second API call"
  - "96x96 endpoint chosen over default /photo/$value for consistent thumbnail sizing in UI"
  - "Tool schemas added without handlers — handlers deferred to Plan 11-02 (no TOOL_DISPATCH entries)"

patterns-established:
  - "New Graph functions follow identical defensive pattern to get_user_photo_bytes: early None, retry, 404 silent, exception caught"
  - "Tool definition schema added before dispatch entry — schema-first approach matches existing TOOL_DEFINITIONS structure"

# Metrics
duration: 8min
completed: 2026-03-25
---

# Phase 11 Plan 01: Graph Data Layer + Tool Schemas Summary

**Graph client extended with profile ($expand=manager) and 96x96 photo functions; TOOL_DEFINITIONS now at 17 with search_colleagues and get_colleague_profile schemas**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-25T00:00Z
- **Completed:** 2026-03-25T00:08Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `get_user_profile()` fetching 7 user fields plus manager displayName in a single Graph call using `$expand=manager($select=displayName)`
- Added `get_user_photo_96()` using the `/photos/96x96/$value` endpoint for consistently-sized thumbnails
- Extended TOOL_DEFINITIONS to 17 entries with `search_colleagues` and `get_colleague_profile` tool schemas
- Updated module docstring to reflect new tool count (17 mcp.types.Tool objects)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_user_profile and get_user_photo_96 to graph_client** - `49d7fec` (feat)
2. **Task 2: Add search_colleagues and get_colleague_profile tool schemas** - `d40e31d` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `chat_app/graph_client.py` — Added `get_user_profile()` and `get_user_photo_96()` after existing `get_user_photo_bytes()`
- `exchange_mcp/tools.py` — Appended two new `types.Tool` entries and updated module docstring

## Decisions Made

- Used `$expand=manager($select=displayName)` to retrieve the manager's name in a single Graph API call rather than two sequential requests. This avoids an extra round-trip at the cost of a slightly larger response payload — acceptable given the infrequency of profile lookups.
- Chose the `/photos/96x96/$value` endpoint over the default `/photo/$value` to guarantee a consistent thumbnail size suitable for the chat UI without client-side resizing.
- Tool handlers and TOOL_DISPATCH entries deliberately excluded from this plan — schema-first approach keeps Plan 11-01 atomic and Plan 11-02 responsible for handler wiring.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `get_user_profile()` and `get_user_photo_96()` are ready for Plan 11-02 handlers to call
- `search_colleagues` and `get_colleague_profile` schemas registered — Plan 11-02 adds TOOL_DISPATCH entries and handler implementations
- Plan 11-03 (photo proxy Flask route) can consume `get_user_photo_96()` directly from graph_client

---
*Phase: 11-mcp-tools-photo-proxy*
*Completed: 2026-03-25*
