---
phase: 10-graph-client-foundation
plan: "01"
subsystem: api
tags: [msal, microsoft-graph, azure-ad, jwt, config]

# Dependency graph
requires:
  - phase: 07-chat-app-core
    provides: Flask app with Azure AD auth (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID already in Config)
provides:
  - Graph API configuration constants (GRAPH_BASE_URL, GRAPH_SEARCH_MAX_RESULTS, GRAPH_TIMEOUT) in Config
  - graph_client.py singleton module with init_graph(), _verify_roles(), is_graph_enabled()
  - Admin consent checkpoint for User.Read.All and ProfilePhoto.Read.All
affects:
  - 10-02 (token acquisition logic calls init_graph() from app.py)
  - 10-03 (colleague lookup endpoints use is_graph_enabled() gate)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level singleton pattern: _cca and _graph_enabled are module globals guarded by init_graph()"
    - "JWT payload decode for role verification without a full JWT library (base64 + json only)"
    - "Admin consent URL pattern logged on permission failure for operator action"

key-files:
  created:
    - chat_app/graph_client.py
  modified:
    - chat_app/config.py

key-decisions:
  - "Graph constants are class-level literals on Config (not env vars) — they are API contract values, not deployment-specific"
  - "init_graph() does NOT set _graph_enabled=True when roles are missing (logs error but does not set flag) — safer fail-open vs. silent failure distinction deferred to 10-02"
  - "Imports in graph_client.py include requests even though it is unused in skeleton — imported now to confirm dep is available at import time"

patterns-established:
  - "is_graph_enabled() gate: all Graph call sites check this before proceeding"
  - "Consent URL logged inline with errors so operators can action without reading docs"

# Metrics
duration: 1min
completed: 2026-03-24
---

# Phase 10 Plan 01: Graph Client Foundation Summary

**MSAL confidential-client singleton (graph_client.py) with JWT role verification and Graph config constants — paused at admin consent checkpoint**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-03-24T19:28:39Z
- **Completed:** 2026-03-24T19:29:31Z
- **Tasks:** 1/2 (paused at human-action checkpoint)
- **Files modified:** 2

## Accomplishments

- Added `GRAPH_BASE_URL`, `GRAPH_SEARCH_MAX_RESULTS`, `GRAPH_TIMEOUT` to `Config` as class-level constants
- Created `chat_app/graph_client.py` with `init_graph()`, `_verify_roles()`, `is_graph_enabled()`
- `init_graph()` acquires client-credentials token, logs admin consent URL on any permission failure
- `_verify_roles()` decodes JWT payload with base64/json (no extra deps) and checks `User.Read.All` + `ProfilePhoto.Read.All`
- Plan paused at Task 2 (human-action checkpoint) — admin consent must be granted before continuation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Graph constants to config.py and create graph_client.py skeleton** - `afc4b9f` (feat)

**Plan metadata:** (docs commit follows STATE.md update)

## Files Created/Modified

- `chat_app/config.py` - Added three Graph API constants after Azure OpenAI section
- `chat_app/graph_client.py` - New module: MSAL singleton, token acquisition, JWT role check, enabled flag

## Decisions Made

- Graph constants are class-level literals on Config (not env vars) because they are API contract values (base URL, timeout), not deployment-specific secrets.
- `init_graph()` sets `_graph_enabled = True` only after `_verify_roles()` completes — the flag is the source of truth for downstream callers.
- `requests` imported in graph_client.py even though unused in the skeleton, confirming the dependency is available at import time (used in Plan 02).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**Admin consent required before Task 2 can be completed.**

Grant application permissions on the existing Azure AD app registration:

1. Azure Portal > App registrations > [your app] > API permissions
2. Add application permission: `User.Read.All`
3. Add application permission: `ProfilePhoto.Read.All`
4. Click "Grant admin consent for [tenant]"

Or navigate directly to:
`https://login.microsoftonline.com/{your-tenant-id}/adminconsent?client_id={your-client-id}`

## Next Phase Readiness

- Task 1 complete: config constants and graph_client.py skeleton are in place
- **Blocker:** Task 2 (admin consent) must be completed before 10-02 can start
- Once consent is granted, reply "done" to continue — the continuation agent will verify and commit the checkpoint
- Plan 10-02 will call `init_graph()` from `app.py` and add token acquisition tests

---
*Phase: 10-graph-client-foundation*
*Completed: 2026-03-24 (partial — paused at checkpoint)*
