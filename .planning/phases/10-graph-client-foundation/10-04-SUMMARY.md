---
phase: 10
plan: 04
subsystem: graph-client
tags: [graph, msal, requests, unit-tests, pytest, mocking]

dependency-graph:
  requires:
    - 10-03 (search_users + get_user_photo_bytes implementations)
  provides:
    - unit test coverage for graph_client.py core operations
    - closed verification gap: "all three core operations tested in isolation"
  affects:
    - Phase 11 (Colleague Lookup MCP) — can now rely on tested graph_client

tech-stack:
  added: []
  patterns:
    - monkeypatch.setattr on module-level globals (_graph_enabled, _cca)
    - patch('requests.request') for full HTTP isolation
    - patch('time.sleep') to keep retry-loop tests fast
    - _make_response() helper for configurable fake responses

key-files:
  created:
    - tests/test_graph_client.py
  modified: []

decisions:
  - decision: Patch requests.request at the top level, not requests.get
    rationale: _graph_request_with_retry calls requests.request(method, url, ...) directly
    outcome: All HTTP calls fully isolated; no real network traffic
  - decision: Patch time.sleep to no-op
    rationale: Retry logic uses time.sleep with exponential backoff; without patching, the Timeout test would take 1+2=3 seconds
    outcome: Test suite runs in 0.2s

metrics:
  duration: 47s
  completed: 2026-03-24
---

# Phase 10 Plan 04: Graph Client Unit Tests Summary

**One-liner:** 10 pytest tests with fully mocked HTTP covering disabled-client fallback, ConsistencyLevel header, 404-to-None and 200-to-bytes photo paths, and exception-to-safe-default for search_users.

## What Was Built

`tests/test_graph_client.py` — a complete unit test file for `chat_app/graph_client.py` core operations. No real network calls are made; all HTTP is mocked via `patch('requests.request')` and the MSAL CCA via `monkeypatch.setattr`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create tests/test_graph_client.py with mocked unit tests | 1fa348c | tests/test_graph_client.py |

## Test Coverage Delivered

| Test Function | What It Proves |
|---------------|----------------|
| test_search_users_returns_empty_when_graph_disabled | [] returned, no HTTP call, when _graph_enabled=False |
| test_get_user_photo_bytes_returns_none_when_graph_disabled | None returned, no HTTP call, when _graph_enabled=False |
| test_search_users_empty_string_returns_empty | "" short-circuits before any network call |
| test_search_users_whitespace_only_returns_empty | "   " short-circuits before any network call |
| test_get_user_photo_bytes_empty_user_id_returns_none | "" user_id short-circuits before any network call |
| test_search_users_sends_consistency_level_header | ConsistencyLevel: eventual present in every search call |
| test_search_users_returns_value_array | {"value": [...]} response parsed and returned correctly |
| test_search_users_returns_empty_on_exception | Timeout exception swallowed, [] returned safely |
| test_get_user_photo_bytes_returns_none_on_404 | HTTP 404 → None (not an exception) |
| test_get_user_photo_bytes_returns_bytes_on_200 | HTTP 200 → raw bytes returned |

## Verification Results

- `pytest tests/test_graph_client.py -v` — 10 passed in 0.20s, zero failures
- `grep -c "def test_"` — 10 (meets ≥10 requirement)
- `grep "ConsistencyLevel"` — header assertion present
- `grep "404"` — 404 path covered
- `grep "_graph_enabled"` — disabled-client tests reference the flag

## Decisions Made

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Patch requests.request (not requests.get) | _graph_request_with_retry calls requests.request() directly | Correct interception point; all HTTP isolated |
| Patch time.sleep to no-op | Retry backoff sleeps would make Timeout test take 3+ seconds | Suite runs in 0.20s |
| monkeypatch.setattr on module globals | _graph_enabled and _cca are module-level variables; setattr is the correct override mechanism | Clean setup/teardown with pytest fixtures |

## Deviations from Plan

None — plan executed exactly as written. All 10 required test cases implemented and passing.

## Phase 10 Verification Gap Status

The single outstanding gap from 10-VERIFICATION.md — "All three core operations tested in isolation" — is now closed:

- `init_graph` — covered by human verification (real MSAL interaction; excluded from unit tests per plan)
- `search_users` — 6 unit tests (disabled, empty string, whitespace, ConsistencyLevel header, value array, exception safety)
- `get_user_photo_bytes` — 4 unit tests (disabled, empty user_id, 404, 200)

## Next Phase Readiness

Phase 11 (Colleague Lookup MCP) can proceed. The graph_client module is:
- Implemented (`search_users`, `get_user_photo_bytes`, `init_graph`, `is_graph_enabled`)
- Wired into Flask app startup (`init_graph` called in `create_app`)
- Covered by unit tests (this plan)
- Verified against live Graph API (10-VERIFICATION.md human verification items)
