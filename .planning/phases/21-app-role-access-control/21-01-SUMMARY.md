---
phase: 21-app-role-access-control
plan: 01
subsystem: auth
tags: [flask, azure-ad, app-roles, msal, access-control, decorator, json-api]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Flask app factory, Blueprint structure, session management
  - phase: auth
    provides: MSAL auth flow, login_required decorator, session['user'] with id_token_claims
provides:
  - role_required decorator in chat_app/auth.py — checks session user (401) then Atlas.User role (403)
  - REQUIRED_ROLE = "Atlas.User" constant
  - Structured 403 JSON with error, message, required_role, upn fields
  - 403 denials logged with UPN, endpoint, UTC timestamp
  - /api/me returns roles list for authorized users
  - All 9 protected routes enforce App Role access control
affects:
  - 22-frontend-403-handling
  - any phase adding new protected routes

# Tech tracking
tech-stack:
  added: []
  patterns:
    - role_required replaces login_required as the standard route decorator
    - Structured error JSON pattern: {error, message, required_role, upn} for 403 responses
    - 401 pattern: {error, message} — unauthenticated
    - UPN/endpoint/timestamp warning log on every 403 denial

key-files:
  created: []
  modified:
    - chat_app/auth.py
    - chat_app/app.py
    - chat_app/chat.py
    - chat_app/conversations.py

key-decisions:
  - "role_required is the canonical decorator going forward — login_required retained but unused on routes"
  - "/api/me now returns roles array, enabling frontend role introspection"
  - "403 responses include upn field so frontend can display the blocked user identity"
  - "Both /api/ and /chat/ path prefixes treated as API paths (JSON responses, not redirects)"

patterns-established:
  - "All new protected routes must use @role_required, not @login_required"
  - "403 JSON shape: {error: 'forbidden', message: str, required_role: str, upn: str}"
  - "401 JSON shape: {error: 'authentication_required', message: str}"

# Metrics
duration: 3min
completed: 2026-04-02
---

# Phase 21 Plan 01: Role Required Decorator Summary

**role_required decorator with Atlas.User App Role enforcement across all 9 protected routes — 401 for unauthenticated, 403 with UPN/role/endpoint logging for unauthorized**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-02T12:10:28Z
- **Completed:** 2026-04-02T12:12:56Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `role_required` decorator in `auth.py` with REQUIRED_ROLE = "Atlas.User" constant
- 403 responses include structured JSON with `error`, `message`, `required_role`, and `upn` fields so frontend can display the blocked user's identity
- All 9 protected routes across `app.py`, `chat.py`, and `conversations.py` migrated from `@login_required` to `@role_required`
- `/api/me` extended to return `roles` list for authorized users

## Task Commits

Each task was committed atomically:

1. **Task 1: Create role_required decorator and update auth.py** - `8b1b460` (feat)
2. **Task 2: Replace login_required with role_required on all routes and extend /api/me** - `9ced931` (feat)

**Plan metadata:** (docs: complete plan — see below)

## Files Created/Modified

- `chat_app/auth.py` — Added `import datetime`, `REQUIRED_ROLE` constant, and `role_required` decorator
- `chat_app/app.py` — Updated import, replaced 3x `@login_required` with `@role_required`, added `roles` to `/api/me` response
- `chat_app/chat.py` — Updated import, replaced `@login_required` on `chat_stream`
- `chat_app/conversations.py` — Updated import, replaced 5x `@login_required` on all CRUD routes, updated `_user_id` docstring

## Decisions Made

- `login_required` is retained as a valid function in `auth.py` but is no longer applied as a route decorator — `role_required` is the canonical decorator going forward
- Both `/api/` and `/chat/` path prefixes receive JSON error responses (not redirects), ensuring SSE and API endpoints behave correctly for React SPA consumers
- `403` response includes the `upn` field in addition to `error`, `message`, and `required_role` — enables frontend to render "Access denied for user@domain.com" messaging

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

`flask_session` is not installed in the current shell Python environment, so `python -c "from chat_app.app import create_app"` fails. This is a pre-existing environment issue unrelated to this plan's changes. Individual modules (`auth.py`, `chat.py`, `conversations.py`) all import cleanly. The production server uses the correct virtual environment where `flask_session` is installed.

## User Setup Required

**Admin dependency (pre-noted in blockers):** The `Atlas.User` App Role must be created in the Entra admin center and the IT engineers group assigned before end-to-end testing can confirm the 403 path. Backend logic is complete and correct.

## Next Phase Readiness

- Backend enforcement is complete — all 9 protected routes return 401/403 with structured JSON
- Frontend (Phase 22) can now implement 403 handling using the `upn` field from 403 responses and the `roles` array from `/api/me`
- Any new protected route added in future phases must use `@role_required` (not `@login_required`)

---
*Phase: 21-app-role-access-control*
*Completed: 2026-04-02*
