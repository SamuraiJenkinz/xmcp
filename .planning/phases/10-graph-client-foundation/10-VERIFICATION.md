---
phase: 10-graph-client-foundation
verified: 2026-03-24T20:19:24Z
status: human_needed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - All three core operations tested in isolation
  gaps_remaining: []
  regressions: []
human_verification:
  - test: On deployed server with real Azure AD credentials, start Flask app, observe startup logs for Graph client initialised successfully, confirm is_graph_enabled() returns True and no missing required application roles error is logged
    expected: _graph_enabled is True; _verify_roles() logs no errors; decoded token roles claim includes both User.Read.All and ProfilePhoto.Read.All
    why_human: Admin consent is a portal action. _verify_roles() decodes a real JWT from a live Azure AD tenant. Cannot be verified by static analysis or offline unit tests.
---

# Phase 10: Graph Client Foundation Verification Report

**Phase Goal:** A verified, isolated Graph API client exists with confirmed admin consent, correct token acquisition, and all three core operations tested in isolation
**Verified:** 2026-03-24T20:19:24Z
**Status:** human_needed
**Re-verification:** Yes -- after gap closure via 10-04 (unit tests)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Graph API token acquired via client credentials with scope https://graph.microsoft.com/.default; decoded token roles contains User.Read.All and ProfilePhoto.Read.All | ? HUMAN NEEDED | Scope constant _GRAPH_SCOPES at line 20. _verify_roles() checks both roles at startup. Actual role presence in a live JWT requires human verification on the deployed server. |
| 2 | graph_client.py is a module-level singleton with its own ConfidentialClientApplication -- no shared state with auth.py | VERIFIED | _cca is module-level (line 17), populated only by init_graph(). auth.py creates its own CCA via _build_msal_app() backed by Flask session cache. Zero cross-module references confirmed by grep. |
| 3 | Token cached at module level and refreshed automatically before expiry | VERIFIED | _get_token() calls acquire_token_for_client on every request (lines 118-131). MSAL returns cached token when >5 min remain and refreshes transparently near expiry. No manual expiry tracking -- correct MSAL pattern. |
| 4 | search_users() returns structured results with ConsistencyLevel: eventual header on every request | VERIFIED | search_users() calls _make_headers(search=True) (line 253). _make_headers() adds ConsistencyLevel: eventual when search=True (line 151). Enforced by the only header-building path. Unit test test_search_users_sends_consistency_level_header passes. |
| 5 | get_user_photo_bytes() returns None (not an exception) when the target user has no photo | VERIFIED | Lines 299-300: if resp.status_code == 404: return None executes before raise_for_status(). Outer try/except additionally catches any unexpected error and returns None. Unit test test_get_user_photo_bytes_returns_none_on_404 passes. |
| 6 | All three core operations (token acquire, user search, photo retrieval) tested in isolation | VERIFIED | tests/test_graph_client.py -- 211 lines, 10 test functions, 0 failures. pytest tests/test_graph_client.py -v: 10 passed in 0.21s. All HTTP mocked via patch(requests.request). MSAL mocked via monkeypatch.setattr. |

**Score:** 5/5 automated truths verified (truth 1 additionally requires human confirmation on a live tenant)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| chat_app/graph_client.py | Isolated Graph client module | VERIFIED | 305 lines, no stubs, all four public functions present: init_graph, is_graph_enabled, search_users, get_user_photo_bytes |
| chat_app/config.py | Graph API constants | VERIFIED | GRAPH_BASE_URL, GRAPH_SEARCH_MAX_RESULTS, GRAPH_TIMEOUT at lines 37-39 |
| chat_app/app.py | init_graph() wired into Flask startup | VERIFIED | Import at line 17, call block at lines 69-76 following init_mcp() |
| tests/test_graph_client.py | Isolated unit tests for core operations | VERIFIED | 211 lines, 10 test functions -- all pass. Covers: disabled-client fallback (2), empty/whitespace guards (3), ConsistencyLevel header (1), value array parsing (1), exception safety (1), 404-to-None (1), 200-to-bytes (1). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app.py | graph_client.init_graph() | Import + call in create_app() | WIRED | Line 17 imports; lines 69-76 call with Config.AZURE_CLIENT_ID/SECRET/TENANT_ID |
| search_users() | _make_headers(search=True) | ConsistencyLevel: eventual | WIRED | Line 253 calls _make_headers(search=True) which adds header at line 151 |
| _get_token() | MSAL cache | acquire_token_for_client on every call | WIRED | Lines 118-131; MSAL returns cached token or refreshes transparently |
| get_user_photo_bytes() | None on 404 | status_code == 404 before raise_for_status | WIRED | 404 check precedes raise_for_status() correctly -- proven by unit test |
| graph_client.py | auth.py | Shared state (must be absent) | ISOLATED | Zero cross-references; each module owns its own MSAL CCA instance independently |
| tests/test_graph_client.py | chat_app.graph_client | import chat_app.graph_client as gc | WIRED | Line 25: module-level import; all test functions call gc.search_users / gc.get_user_photo_bytes directly |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| GRAPH-01: Graph API client authenticates via MSAL client credentials flow (isolated from SSO) | SATISFIED | graph_client.py uses acquire_token_for_client with its own _cca; auth.py uses auth code flow with session-cached CCA instances |
| GRAPH-02: Azure AD app registration has User.Read.All and ProfilePhoto.Read.All with admin consent | HUMAN NEEDED | Code verifies roles at startup; actual Azure AD portal state requires human verification on live tenant |
| GRAPH-03: Graph API token is cached at module level and refreshed automatically | SATISFIED | MSAL built-in cache handles this; _get_token() relies on it correctly |
| SRCH-04: Search uses the Graph search query parameter with ConsistencyLevel: eventual header | SATISFIED | _make_headers(search=True) enforced in search_users() on every call; proven by passing unit test |

### Anti-Patterns Found

No stub patterns, TODO comments, placeholder content, or empty implementations found in graph_client.py or tests/test_graph_client.py.

### Human Verification Required

#### 1. Admin Consent and Role Claims

**Test:** On the deployed server with real Azure AD credentials, start the Flask app and observe startup logs. Confirm that Graph client initialised successfully appears and no missing required application roles error is logged.
**Expected:** is_graph_enabled() returns True; _verify_roles() logs no errors; decoded token roles claim contains both User.Read.All and ProfilePhoto.Read.All.
**Why human:** Admin consent is a portal action. The code that verifies it decodes a real JWT from the live Azure AD tenant -- cannot be verified by static analysis or offline unit tests.

### Re-verification Summary

The single gap from the initial verification -- All three core operations tested in isolation -- is now closed.

tests/test_graph_client.py was created as part of plan 10-04. The file is substantive (211 lines, 10 test functions). It imports the module under test as import chat_app.graph_client as gc at line 25, mocks all HTTP via patch(requests.request) and MSAL state via monkeypatch.setattr on the module-level globals _graph_enabled and _cca. Running pytest tests/test_graph_client.py -v yields 10 passed in 0.21s with zero failures, no real network calls, and no skips.

No regressions detected. All previously-verified truths (isolation from auth.py, token caching pattern, ConsistencyLevel header enforcement, 404-to-None path) remain structurally correct and are now additionally confirmed by passing unit tests.

Remaining human verification item (unchanged from initial verification): admin consent and roles claim presence in a live Azure AD token cannot be verified programmatically. This is not a gap -- it is an inherent constraint of testing against an external identity service.

---

_Verified: 2026-03-24T20:19:24Z_
_Verifier: Claude (gsd-verifier)_
