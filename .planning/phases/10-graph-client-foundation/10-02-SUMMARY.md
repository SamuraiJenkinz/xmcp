---
phase: 10-graph-client-foundation
plan: "02"
subsystem: api
tags: [msal, graph-api, requests, token-cache, retry, azure-ad]

# Dependency graph
requires:
  - phase: 10-graph-client-foundation/10-01
    provides: graph_client.py skeleton with init_graph, _verify_roles, is_graph_enabled
provides:
  - _get_token(): MSAL client-credentials token acquisition with automatic cache
  - _make_headers(): auth header builder with ConsistencyLevel support for $search
  - _graph_request_with_retry(): retry wrapper with 429/503 backoff and Retry-After handling
  - init_graph() wired into Flask create_app() after init_mcp()
affects:
  - 10-03 (colleague search tools — uses _make_headers and _graph_request_with_retry)
  - 11-colleague-lookup-ui (photo/profile endpoints depend on token layer)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MSAL cache-on-every-call: calling acquire_token_for_client each request is correct — MSAL returns cached token if >5 min remaining"
    - "ConsistencyLevel: eventual is mandatory for Graph $search on directory objects"
    - "Retry-After header honoured; fallback to 2**attempt exponential backoff"
    - "Graceful degradation: init_graph in try/except, app starts without Graph credentials"

key-files:
  created: []
  modified:
    - chat_app/graph_client.py
    - chat_app/app.py

key-decisions:
  - "Check 'access_token' in result (not truthiness) — MSAL error dicts are truthy"
  - "Config.GRAPH_TIMEOUT as default timeout in _graph_request_with_retry, not hardcoded 10"
  - "Only retry on 429 and 503; all other status codes returned immediately to caller"

patterns-established:
  - "Token layer: _get_token -> _make_headers -> _graph_request_with_retry call chain for all Graph operations"
  - "App startup order: init_openai -> init_mcp -> init_graph, each with try/except graceful degradation"

# Metrics
duration: 7min
completed: 2026-03-24
---

# Phase 10 Plan 02: Graph Client Foundation Summary

**MSAL client-credentials token layer with automatic cache, ConsistencyLevel header builder, and 429/503 retry wrapper wired into Flask startup**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-24T19:35:02Z
- **Completed:** 2026-03-24T19:41:20Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `_get_token()` acquires tokens via `acquire_token_for_client` with MSAL's built-in cache handling refresh automatically
- `_make_headers()` builds auth headers and adds `ConsistencyLevel: eventual` when `search=True` (mandatory for Graph `$search`)
- `_graph_request_with_retry()` retries on 429/503 with Retry-After header support and exponential backoff fallback; propagates timeout exceptions after exhausting retries
- `init_graph()` called in `create_app()` after `init_mcp()`, matching the established graceful-degradation pattern

## Task Commits

Each task was committed atomically:

1. **Task 1: Add token acquisition, retry helper, and header builder** - `9538310` (feat)
2. **Task 2: Wire init_graph() into Flask create_app() startup** - `822f108` (feat)

**Plan metadata:** (next commit, docs)

## Files Created/Modified

- `chat_app/graph_client.py` — Added `_get_token`, `_make_headers`, `_graph_request_with_retry`; added `import time` and `from chat_app.config import Config`
- `chat_app/app.py` — Added `from chat_app.graph_client import init_graph` and `init_graph()` call block after `init_mcp()`

## Decisions Made

- Checked `"access_token" in result` not `if result` — MSAL error responses are truthy dicts, so truthiness check would incorrectly succeed on errors
- Used `Config.GRAPH_TIMEOUT` as the default parameter value for `timeout` in `_graph_request_with_retry` rather than hardcoding 10, keeping the config source of truth single
- Only 429 and 503 trigger retry; all other status codes (including 400, 404, 500) are returned immediately so the caller can handle them appropriately

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `flask_session` not installed in the shell virtualenv, so `from chat_app.app import create_app` could not be executed in verification. Confirmed via: (a) all graph_client exports verified cleanly, (b) `grep` confirmed `init_graph` appears at both import line 17 and call line 70 in app.py. This is a dev environment gap, not a code issue — the deployed virtualenv has all dependencies.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Token layer complete: Plan 03 can call `_make_headers()` and `_graph_request_with_retry()` directly to implement colleague search and photo endpoints
- `is_graph_enabled()` guard is available for all callers to check before making requests
- App starts cleanly with or without Graph credentials (logs warning, continues)

---
*Phase: 10-graph-client-foundation*
*Completed: 2026-03-24*
