---
phase: 10-graph-client-foundation
plan: "01"
subsystem: api
tags: [msal, microsoft-graph, azure-ad, jwt, config, client-credentials]

# Dependency graph
requires:
  - phase: 07-chat-app-core
    provides: Flask app with Azure AD auth (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID already in Config)
provides:
  - Graph API configuration constants (GRAPH_BASE_URL, GRAPH_SEARCH_MAX_RESULTS, GRAPH_TIMEOUT) in Config
  - graph_client.py singleton module with init_graph(), _verify_roles(), is_graph_enabled()
  - Admin consent confirmed for User.Read.All and ProfilePhoto.Read.All (application permissions)
affects:
  - 10-02 (token acquisition logic calls init_graph() from app.py, builds on this skeleton)
  - 10-03 (colleague lookup endpoints use is_graph_enabled() gate)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level singleton pattern: _cca and _graph_enabled are module globals guarded by init_graph()"
    - "JWT payload decode for role verification without a full JWT library (base64 + json only)"
    - "Admin consent URL logged inline on permission failure for operator action"

key-files:
  created:
    - chat_app/graph_client.py
  modified:
    - chat_app/config.py

key-decisions:
  - "Graph constants are class-level literals on Config (not env vars) — API contract values, not deployment-specific"
  - "init_graph() does not set _graph_enabled=True if roles are missing — safer than silent fail-open"
  - "requests imported in graph_client.py even though unused in skeleton — confirms dep available at import time"
  - "Application permissions (not delegated) required for client-credentials flow — no user context"

patterns-established:
  - "is_graph_enabled() gate: all Graph call sites check this before proceeding"
  - "Consent URL logged inline with errors so operators can action without reading docs"

# Metrics
duration: ~30min (across two sessions with async consent checkpoint)
completed: 2026-03-24
---

# Phase 10 Plan 01: Graph Client Foundation Summary

**MSAL confidential-client singleton (graph_client.py) with JWT role verification, Graph config constants, and admin consent confirmed for User.Read.All + ProfilePhoto.Read.All**

## Performance

- **Duration:** ~30 min (including async consent checkpoint between sessions)
- **Started:** 2026-03-24T19:28:39Z
- **Completed:** 2026-03-24 (resumed after admin consent granted)
- **Tasks:** 2/2 complete
- **Files modified:** 2

## Accomplishments

- Added `GRAPH_BASE_URL`, `GRAPH_SEARCH_MAX_RESULTS`, `GRAPH_TIMEOUT` to `Config` as class-level constants
- Created `chat_app/graph_client.py` with `init_graph()`, `_verify_roles()`, `is_graph_enabled()`
- `init_graph()` acquires client-credentials token via MSAL, logs admin consent URL on any permission failure
- `_verify_roles()` decodes JWT payload with base64/json (no extra deps) and checks `User.Read.All` + `ProfilePhoto.Read.All`
- Tenant admin granted admin consent for both application permissions via Azure Portal

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Graph constants to config.py and create graph_client.py skeleton** - `afc4b9f` (feat)
2. **Task 2: Grant admin consent for Graph API permissions** - No commit (human action — Azure Portal)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `chat_app/config.py` - Added three Graph API constants after Azure OpenAI section
- `chat_app/graph_client.py` - New module: MSAL singleton, token acquisition, JWT role check, enabled flag

## Decisions Made

- Graph constants are class-level literals on `Config` (not env vars) because they are API contract values (base URL, timeout), not deployment-specific secrets.
- `init_graph()` sets `_graph_enabled = True` only after `_verify_roles()` completes — the flag is the source of truth for downstream callers.
- `requests` imported in graph_client.py even though unused in the skeleton, confirming the dependency is available at import time (used in Plan 02).
- Application permissions selected (not delegated) — client-credentials flow operates with no user context, so delegated permissions would not apply.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

Task 2 was an intentional human-action checkpoint requiring tenant admin intervention:

1. Admin consent granted for `User.Read.All` (Application permission) via Azure Portal
2. Admin consent granted for `ProfilePhoto.Read.All` (Application permission) via Azure Portal

This is normal plan flow, not a deviation.

## Issues Encountered

None.

## User Setup Required

None — admin consent was the only external configuration step and has been completed.

## Next Phase Readiness

- Config constants and `graph_client.py` skeleton fully in place
- Admin consent confirmed — MSAL token acquisition in Plan 02 will succeed
- `is_graph_enabled()` guard pattern established for all downstream Graph call sites
- Plan 10-02 can proceed: wire `init_graph()` into `app.py` startup and add token acquisition tests

---
*Phase: 10-graph-client-foundation*
*Completed: 2026-03-24*
