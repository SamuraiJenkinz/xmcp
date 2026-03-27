---
phase: 13-infrastructure-scaffold
plan: 02
subsystem: api
tags: [flask, react, spa, feature-flag, msal, session, send_from_directory]

# Dependency graph
requires:
  - phase: 13-01
    provides: Vite/React/TypeScript frontend scaffold in /frontend, build outputs to /frontend_dist
provides:
  - /api/me endpoint returning {displayName, email, oid} from MSAL session
  - Feature-flagged catch-all route — ATLAS_UI=react serves frontend_dist, classic serves Jinja2
  - ATLAS_UI config key in Config class (defaults to 'classic')
  - FRONTEND_DIST path constant anchored to chat_app/ directory
affects:
  - 14-regression-tests (smoke tests must verify classic mode still works)
  - 15-react-shell (React mount connects to /api/me for user identity)
  - 16-thread-sidebar (sidebar uses /api/me OID for thread ownership)

# Tech tracking
tech-stack:
  added: [send_from_directory (Flask stdlib)]
  patterns: [feature-flag controlled SPA serving, catch-all with guard prefixes, MSAL session extraction in API endpoint]

key-files:
  created: []
  modified:
    - chat_app/app.py
    - chat_app/config.py

key-decisions:
  - "Catch-all registered LAST in create_app() — Flask resolves blueprint routes first by specificity, so API/auth/chat blueprints are never intercepted"
  - "index() function kept without @app.route decorator — catch-all calls it directly in classic mode, avoiding route conflict with catch-all's @app.route('/')"
  - "Guard tuple uses prefix matching (startswith) not exact match — prevents catch-all from serving api/health, auth/callback, etc. in react mode"
  - "FRONTEND_DIST uses os.path.abspath with os.path.dirname(__file__) — portable across dev/prod regardless of working directory at startup"

patterns-established:
  - "Feature flag pattern: app.config.get('ATLAS_UI') != 'react' gates SPA behavior — single config key, no code changes needed to toggle"
  - "SPA asset serving pattern: check os.path.isfile(asset) before send_from_directory, fall back to index.html for client-side routes"
  - "Guard prefix pattern: tuple of guarded prefixes checked before any SPA logic — extensible without modifying catch-all internals"

# Metrics
duration: 18min
completed: 2026-03-27
---

# Phase 13 Plan 02: Flask-React Integration Layer Summary

**Feature-flagged catch-all route and /api/me endpoint wiring Flask to serve React SPA (ATLAS_UI=react) or classic Jinja2 (default) with zero user-visible regression**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-27T00:00:00Z
- **Completed:** 2026-03-27T00:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `/api/me` endpoint returning `{displayName, email, oid}` from MSAL session, protected by `@login_required`
- Added `ATLAS_UI` feature flag to `Config` class (defaults to `'classic'` — zero user-visible change on deploy)
- Added feature-flagged catch-all route that serves `frontend_dist/index.html` when `ATLAS_UI=react`, delegates to Jinja2 `index()` when classic
- Refactored `index()` function to remove `@app.route("/")` decorator — called directly by catch-all, no Flask routing conflict
- Added `FRONTEND_DIST` path constant (absolute, anchored to `chat_app/`) for portable static file serving
- Added guard prefix tuple (`api/`, `auth/`, `chat/`, `login`, `logout`) preventing catch-all from intercepting existing routes
- 147 Flask/tool tests pass; 14 pre-existing Exchange PowerShell failures confirmed pre-existing, unrelated to this plan

## Task Commits

Each task was committed atomically:

1. **Task 1: Add /api/me endpoint and ATLAS_UI config** - `fa8cd24` (feat)
2. **Task 2: Add catch-all route for React SPA serving with feature flag guard** - `6846ef4` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `chat_app/app.py` - Added `send_from_directory` import, `FRONTEND_DIST` constant, removed `@app.route("/")` from `index()`, added `/api/me` endpoint, added catch-all route
- `chat_app/config.py` - Added `ATLAS_UI: str = os.environ.get('ATLAS_UI', 'classic')` in Flask section

## Decisions Made
- Catch-all is registered LAST in `create_app()` after all blueprints — Flask's route specificity ensures `/api/threads/*`, `/auth/callback`, `/chat/stream` are always resolved first without needing explicit guards, but guards are added as defense-in-depth
- `index()` kept as a plain function (no decorator) rather than deleting it — the catch-all calls it directly, keeping the Jinja2 classic-mode logic in one place
- `FRONTEND_DIST` computed at `create_app()` invocation time (not module level) so it's always relative to the actual `chat_app/` file, not the working directory
- Classic mode redirects unknown paths to `/` (via `catch_all` with empty path) rather than 404 — same behavior as before since only `/` was registered

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `send_from_directory` to Flask import line**
- **Found during:** Task 2 (catch-all route implementation)
- **Issue:** Plan stated "it's already in the Flask import line" — it was not present
- **Fix:** Added `send_from_directory` to the existing `from flask import ...` line
- **Files modified:** `chat_app/app.py`
- **Verification:** Import resolves without error; `grep 'send_from_directory' chat_app/app.py` confirms presence
- **Committed in:** `6846ef4` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — missing import)
**Impact on plan:** Required for Task 2 to function. No scope creep.

## Issues Encountered
- Pre-existing test failures in `test_exchange_client.py`, `test_integration.py`, `test_tools_flow.py`, `test_tools_hybrid.py` (14 total) — confirmed pre-existing via `git stash` before my changes. All relate to Exchange Online PowerShell connectivity, not Flask. The 147 Flask/tool-logic tests all pass.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Flask can now serve the React SPA by setting `ATLAS_UI=react` in the environment — ready for Phase 14 regression smoke tests
- `/api/me` is live and returns MSAL session data — React components can fetch user identity without additional Flask work
- Phase 14 smoke tests should cover: `/api/health` still returns JSON, `/chat` still redirects unauthenticated, `/api/me` returns 401 without session
- IIS ARR `responseBufferLimit="0"` still needs verification before production ship (tracked in STATE.md blockers)

---
*Phase: 13-infrastructure-scaffold*
*Completed: 2026-03-27*
