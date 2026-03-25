---
phase: 11-mcp-tools-photo-proxy
verified: 2026-03-25T00:00:00Z
status: gaps_found
score: 4/6 must-haves verified
gaps:
  - truth: search_colleagues callable via MCP returns up to 10 results with name/title/dept/email
    status: partial
    reason: Handler registered and produces correct output. Description uses "Use for" not "Use when", causing test_all_descriptions_contain_use_when to fail. search_colleagues excludes id from results leaving email as the only identifier passable to get_colleague_profile.
    artifacts:
      - path: exchange_mcp/tools.py
        issue: Line 374 description reads "Use for name lookups" -- missing required "Use when" phrase
    missing:
      - Change "Use for name lookups" to "Use when asked to find a colleague" in search_colleagues description
      - Document that email returned by search_colleagues can be passed as user_id to get_colleague_profile
  - truth: get_colleague_profile callable via MCP returns profile fields plus photo_url no binary photo data
    status: partial
    reason: Handler returns photo_url string (no binary data). Tool description missing example query in single quotes, causing test_all_descriptions_contain_example_query to fail. test_list_tools_returns_all_15 fails because it hardcodes 15 but there are now 17 tools.
    artifacts:
      - path: exchange_mcp/tools.py
        issue: Lines 391-394 get_colleague_profile description contains no single-quoted example query
      - path: tests/test_server.py
        issue: test_list_tools_returns_all_15 asserts len == 15 but there are now 17 tools
    missing:
      - Add example query in single quotes to get_colleague_profile description
      - Update test_list_tools_returns_all_15 assertion from 15 to 17
---

# Phase 11 Verification: MCP Tools + Photo Proxy

**Phase Goal:** Two new MCP tools are registered and callable, and authenticated users can retrieve colleague photos through a secure Flask proxy that absorbs 404s
**Verified:** 2026-03-25
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Must-Have Checks

### 1. search_colleagues callable via MCP and returns up to 10 results with name, job title, department, and email

**Status:** PARTIAL

**Evidence:**

Tool declared in TOOL_DEFINITIONS at `exchange_mcp/tools.py` lines 370-388 with correct inputSchema requiring `query`. Dispatched in TOOL_DISPATCH at line 1988. Handler `_search_colleagues_handler` at line 1890 calls `search_users` from graph_client, slices to `raw[:10]`, and maps displayName to name, jobTitle to jobTitle, department to department, mail to email. TOOL_DEFINITIONS is imported and returned by `handle_list_tools()` in server.py. TOOL_DISPATCH is imported and called by `handle_call_tool()`. The wiring is complete.

**Gap 1 -- description quality test failure:** The tool description at line 374 reads "Use for name lookups like..." -- it uses "Use for" not "Use when". The pre-existing test `test_all_descriptions_contain_use_when` in `tests/test_tool_descriptions.py` asserts every non-ping tool description must contain "Use when". This test now fails:

    FAILED tests/test_tool_descriptions.py::test_all_descriptions_contain_use_when
    search_colleagues: missing Use when trigger phrase

**Gap 2 -- user_id chaining:** `search_colleagues` deliberately excludes `id` from results (line 1917 comment). The description for `get_colleague_profile` says it requires "a user ID from search_colleagues results", but no ID is returned. The email field is returned, and Graph accepts UPN (email) as a user identifier so the chain works in practice, but the description is misleading.

---

### 2. get_colleague_profile callable via MCP and returns detailed profile fields plus a photo_url string -- no binary photo data

**Status:** PARTIAL

**Evidence:**

Tool declared at lines 389-406, dispatched at line 1989. Handler `_get_colleague_profile_handler` at line 1923 maps displayName/mail/jobTitle/department/officeLocation/businessPhones/manager. Line 1957 always sets `photo_url` to `/api/photo/{user_id}`. Binary photo data is never fetched in this handler.

**Gap 1 -- description quality test failure:** Tool description (lines 391-394) contains no example query in single quotes. The pre-existing test `test_all_descriptions_contain_example_query` checks for pattern matching single-quoted text. This test fails:

    FAILED tests/test_tool_descriptions.py::test_all_descriptions_contain_example_query
    get_colleague_profile: no example query found (expected text in single quotes)

**Gap 2 -- stale tool count test:** `tests/test_server.py::test_list_tools_returns_all_15` hardcodes `assert len(tools) == 15`. Phase 11 added 2 tools; the actual count is now 17. This test fails:

    FAILED tests/test_server.py::test_list_tools_returns_all_15
    AssertionError: 17 == 15

---

### 3. Searching for a name with no matches returns a clear no-results message, not an empty array or silence

**Status:** VERIFIED

**Evidence:**

`_search_colleagues_handler` at lines 1903-1904 returns a dict with a `message` key containing a human-readable sentence naming the query when `search_users` returns an empty list. Not an empty array, not silence.

---

### 4. GET /api/photo/<user_id> returns the JPEG photo for an authenticated user who has a photo

**Status:** VERIFIED

**Evidence:**

Route at `chat_app/app.py` line 175, decorated with `@login_required`. On cache miss, calls `get_user_photo_96(user_id)` from graph_client. If photo_bytes is not None, returns `Response(photo_bytes, status=200, mimetype="image/jpeg")` at line 196. On cache hit with bytes, returns same at line 185. `get_user_photo_96` fetches the 96x96 photo endpoint and returns raw bytes on success, None on 404.

---

### 5. GET /api/photo/<user_id> returns a placeholder image with HTTP 200 (not 404) when the user has no photo

**Status:** VERIFIED

**Evidence:**

When `get_user_photo_96` returns None, route executes at lines 199-201 returning an SVG placeholder with `status=200`. `_generate_placeholder_svg` at line 62 returns a colored SVG circle with initials or "?". `get_user_photo_96` in graph_client.py lines 299-300 explicitly returns None on HTTP 404, absorbing the error. Cache path for no-photo also returns SVG placeholder at lines 187-189. HTTP 200 is explicit in both cached and uncached code paths.

The placeholder is SVG not JPEG, but the criterion says "placeholder image with HTTP 200 (not 404)" -- HTTP 200 is satisfied.

---

### 6. GET /api/photo/<user_id> returns 401/302-to-login for unauthenticated requests

**Status:** VERIFIED

**Evidence:**

Route at line 176 applies `@login_required`. Decorator in `chat_app/auth.py` lines 91-100 redirects unauthenticated requests (no user in session) to `url_for("index")`, producing HTTP 302. Satisfies "401/302-to-login".

---

## Observable Truths Summary

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | search_colleagues callable, up to 10 with name/title/dept/email | PARTIAL | Functional but description fails Use-when test |
| 2 | get_colleague_profile callable, profile + photo_url, no binary | PARTIAL | Functional but description fails example-query test; test_list_tools count stale |
| 3 | No-results returns clear message | VERIFIED | Returns message key with named query |
| 4 | /api/photo returns JPEG on 200 for user with photo | VERIFIED | Response(photo_bytes, 200, image/jpeg) |
| 5 | /api/photo returns placeholder HTTP 200 when no photo | VERIFIED | SVG placeholder with explicit status=200 |
| 6 | /api/photo returns 302-to-login for unauthenticated | VERIFIED | @login_required redirects to index |

**Score:** 4/6 truths verified (2 partial due to test regressions)

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| exchange_mcp/tools.py TOOL_DEFINITIONS | search_colleagues + get_colleague_profile declared | VERIFIED | Lines 370-406 |
| exchange_mcp/tools.py TOOL_DISPATCH | Both tools dispatched | VERIFIED | Lines 1988-1989 |
| exchange_mcp/tools.py _search_colleagues_handler | Substantive handler | VERIFIED | Lines 1890-1920, 30 lines |
| exchange_mcp/tools.py _get_colleague_profile_handler | Substantive handler with photo_url | VERIFIED | Lines 1923-1959, 37 lines |
| chat_app/app.py /api/photo route | @login_required, JPEG or SVG placeholder | VERIFIED | Lines 175-201 |
| chat_app/graph_client.py get_user_photo_96 | Fetches photo, absorbs 404 | VERIFIED | Lines 347-390 |
| chat_app/graph_client.py get_user_profile | Fetches profile with manager expand | VERIFIED | Lines 308-344 |
| chat_app/graph_client.py search_users | Searches by displayName and mail | VERIFIED | Lines 231-271 |

## Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| server.py handle_list_tools | TOOL_DEFINITIONS | direct import | VERIFIED |
| server.py handle_call_tool | TOOL_DISPATCH | direct import + dict lookup | VERIFIED |
| _search_colleagues_handler | graph_client.search_users | asyncio.to_thread | VERIFIED |
| _get_colleague_profile_handler | graph_client.get_user_profile | asyncio.to_thread | VERIFIED |
| photo_proxy route | graph_client.get_user_photo_96 | direct import | VERIFIED |
| photo_proxy route | @login_required | decorator | VERIFIED |

## Test Regressions Introduced by Phase 11

| Test | File | Failure |
|------|------|---------|
| test_all_descriptions_contain_use_when | tests/test_tool_descriptions.py | search_colleagues uses Use-for not Use-when |
| test_all_descriptions_contain_example_query | tests/test_tool_descriptions.py | get_colleague_profile has no single-quoted example query |
| test_list_tools_returns_all_15 | tests/test_server.py | Asserts 15; now 17 tools exist |

Pre-existing failures not caused by phase 11: test_exchange_client.py (2 tests re PS script content), test_integration.py (3 tests requiring live Exchange connectivity).

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| exchange_mcp/tools.py | 374 | Use-for instead of Use-when in search_colleagues description | Blocker | breaks description quality test |
| exchange_mcp/tools.py | 391-394 | No single-quoted example query in get_colleague_profile description | Blocker | breaks example query test |
| tests/test_server.py | ~155 | assert len(tools) == 15 -- stale after adding 2 tools | Blocker | test regression |

## Gaps Summary

The photo proxy (criteria 4-6) is fully correct. The no-results message (criterion 3) is correctly implemented. Both MCP tool handlers produce correct output and are correctly wired into the server dispatch.

The three failing tests require small targeted fixes with no handler logic changes:

1. Add "Use when" phrasing to search_colleagues description (1 line change)
2. Add a single-quoted example query to get_colleague_profile description (1 line change)
3. Update test_list_tools_returns_all_15 assertion from 15 to 17 (1 line change)

---

_Verified: 2026-03-25_
_Verifier: Claude (gsd-verifier)_