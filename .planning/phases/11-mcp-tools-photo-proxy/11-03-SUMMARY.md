---
phase: 11-mcp-tools-photo-proxy
plan: 03
subsystem: api
tags: [flask, graph-api, photo-proxy, caching, svg, threading]

requires:
  - phase: 11-01
    provides: get_user_photo_96() function in graph_client.py returning bytes or None

provides:
  - Flask route GET /api/photo/<user_id> with @login_required protection
  - In-memory TTL photo cache with sentinel-based miss detection
  - SVG placeholder generator with initials from ?name= query param
  - Thread-safe _photo_cache with 1-hour TTL and expiry eviction

affects:
  - UI rendering of profile cards (img src="/api/photo/...")
  - Any future MCP handler that returns colleague data with photo URLs

tech-stack:
  added: []
  patterns:
    - "Sentinel object pattern: _MISS = object() to distinguish 'not cached' from 'cached as None'"
    - "In-memory TTL dict cache with threading.Lock for thread safety"
    - "SVG placeholder generation with deterministic color from hash(user_id)"

key-files:
  created: []
  modified:
    - chat_app/app.py

key-decisions:
  - "Use _MISS sentinel (not None) to distinguish cache miss from cached no-photo — avoids repeated Graph calls for photoless users"
  - "Always return HTTP 200 (never 404) — SVG placeholder for no-photo case"
  - "Cache None results for photoless users to prevent repeated Graph API calls"
  - "Lazy import get_user_photo_96 inside route to avoid circular import risk at module load"
  - "Accept optional ?name=First+Last for initials in SVG; fall back to '?' if absent"

patterns-established:
  - "Photo proxy pattern: cache → Graph API → cache result → return JPEG or SVG"
  - "SVG placeholder: deterministic color from _PALETTE[hash(user_id) % len], initials from name parts"

duration: 6min
completed: 2026-03-25
---

# Phase 11 Plan 03: Photo Proxy Summary

**Flask /api/photo/<user_id> proxy with 1-hour in-memory TTL cache, _MISS sentinel for photoless users, and SVG circle-with-initials placeholder — all behind @login_required**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-25T07:35:17Z
- **Completed:** 2026-03-25T07:41:29Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `GET /api/photo/<user_id>` route to `app.py` protected by `@login_required`
- Built thread-safe in-memory TTL cache using `_MISS` sentinel to distinguish "not cached" from "cached as no-photo (None)"
- `_generate_placeholder_svg()` produces colored SVG circle with initials from optional `?name=` query param, deterministic color from `hash(user_id)`
- Route returns `image/jpeg` (200) for users with photos, `image/svg+xml` (200) for no-photo — never 404

## Task Commits

1. **Task 1: Add photo proxy route with cache and SVG placeholder to app.py** - `1ee46f0` (feat)

## Files Created/Modified

- `chat_app/app.py` - Added `threading`, `time` imports; `Response`, `request` to Flask imports; module-level `_MISS`, `_photo_cache`, `_cache_lock`, `_PHOTO_TTL`, `_get_cached_photo()`, `_cache_photo()`, `_PALETTE`, `_generate_placeholder_svg()`; `photo_proxy` route at `/api/photo/<user_id>`

## Decisions Made

- `_MISS = object()` sentinel chosen over `None` because `None` is a valid cached value (means "this user has no photo") — sentinel cleanly separates the two states
- `get_user_photo_96` lazy-imported inside the route function to avoid potential circular imports at module load time
- Always HTTP 200 for all non-error cases (both photo found and placeholder) — caller never needs to handle 404

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Photo proxy complete and ready for use in profile card UI (`<img src="/api/photo/{user_id}?name=First+Last">`)
- Phase 11 plans: 11-01 (Graph data layer) done, 11-02 (MCP tool handlers) and 11-03 (photo proxy) done — Phase 11 complete

---
*Phase: 11-mcp-tools-photo-proxy*
*Completed: 2026-03-25*
