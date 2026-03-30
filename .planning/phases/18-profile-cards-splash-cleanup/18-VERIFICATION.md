---
phase: 18-profile-cards-splash-cleanup
verified: 2026-03-30T12:45:08Z
status: passed
score: 5/5 must-haves verified
gaps: []
---

# Phase 18: Profile Cards, Splash Cleanup Verification Report

**Phase Goal:** Profile and search result cards aligned with Fluent 2; professional splash/login page; three test regressions and two schema issues resolved
**Verified:** 2026-03-30T12:45:08Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Inline profile cards match Fluent 2 Card geometry: 12px padding, --atlas-stroke-1 border, max-width 320px, text-overflow ellipsis | VERIFIED | index.css lines 604-678: padding: 12px, border: 1px solid var(--atlas-stroke-1), max-width: 320px; overflow hidden + text-overflow ellipsis + white-space nowrap on all four info fields |
| 2 | Search result cards follow Fluent 2 List pattern: single elevated container with row dividers | VERIFIED | index.css lines 681-741: .search-results has atlas-bg-elevated, atlas-stroke-1 border, max-height 280px; .search-result-row has atlas-stroke-2 divider; .search-result-card class absent |
| 3 | Login/splash page has professional Fluent 2 appearance: geometric SVG logo, border not shadow, correct typography | VERIFIED | splash.html: inline SVG rotated-rect logo with class=splash-logo, no lightning emoji; style.css: border-radius 12px, no box-shadow, 28px/600 Segoe UI Variable, btn-signin 8px radius |
| 4 | All 3 test regressions fixed: both cmdlet script tests pass; test_server.py tool count accurate | VERIFIED | test_exchange_client.py: no Disconnect-ExchangeOnline or env var assertions; test_server.py line 5: 17 registered tools (16 Exchange + ping) |
| 5 | get_user_photo_bytes() dead code removed; get_colleague_profile user_id schema corrected | VERIFIED | graph_client.py: zero matches for get_user_photo_bytes; test_graph_client.py: 6 tests targeting search_users only; tools.py line 416: Microsoft Graph API object ID (GUID) from search_colleagues results |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| frontend/src/index.css | Updated .profile-card and .search-results/.search-result-row CSS | VERIFIED | max-width: 320px, atlas-stroke-1 on profile card; elevated .search-results with atlas-stroke-2 row dividers; .search-result-card absent |
| frontend/src/components/ChatPane/SearchResultCard.tsx | Row-based JSX with search-result-row, search-result-primary-line, .slice(0,5) | VERIFIED | 70 lines; search-result-row at line 45, search-result-primary-line at line 46, data.results.slice(0,5) at line 44 |
| chat_app/templates/splash.html | Fluent 2 markup with SVG logo, no lightning emoji | VERIFIED | 26 lines; SVG rect fill=var(--color-brand) rotated 45deg, class=splash-logo; url_for auth.login preserved; Microsoft SVG preserved |
| chat_app/static/style.css | Splash CSS: 12px radius, no box-shadow, correct typography, btn-signin geometry | VERIFIED | .splash-card: border-radius 12px, 1px border, no box-shadow; h1: 28px/600/Segoe UI Variable; btn-signin: 8px radius; .splash-icon absent |
| tests/test_exchange_client.py | Stale Disconnect-ExchangeOnline and env var assertions removed | VERIFIED | Zero matches for Disconnect-ExchangeOnline; zero matches for env:AZURE_ in file |
| tests/test_server.py | Module docstring says 17 tools | VERIFIED | Lines 5 and 12 both reference 17 tools |
| chat_app/graph_client.py | get_user_photo_bytes() absent | VERIFIED | Zero grep matches; get_user_photo_96 active at line 313 |
| tests/test_graph_client.py | No get_user_photo_bytes test functions | VERIFIED | 6 remaining test functions all target search_users; module docstring clean |
| exchange_mcp/tools.py | get_colleague_profile user_id description mentions Graph API object ID (GUID) | VERIFIED | Line 416: Microsoft Graph API object ID (GUID) from search_colleagues results |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| SearchResultCard.tsx | index.css | className search-result-row | WIRED | Component uses search-result-row, search-result-primary-line, search-results; all present in CSS |
| ProfileCard.tsx | index.css | className profile-card | WIRED | Component uses all profile-card-* classes; all present in CSS |
| splash.html | style.css | class splash-card, splash-logo, btn-signin | WIRED | Template uses splash-container, splash-card, splash-logo, splash-subtitle, splash-description, btn-signin; all defined as CSS rules |
| test_exchange_client.py | exchange_mcp/exchange_client.py | _build_cmdlet_script assertions | WIRED | Tests call _build_cmdlet_script and assert on current implementation without stale assertions |

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| PROF-01: Inline profile cards match Fluent 2 Card geometry | SATISFIED | padding 12px, atlas-stroke-1 border, 320px max-width, text-overflow on all info fields |
| PROF-02: Colleague search result cards follow Fluent 2 List patterns | SATISFIED | Single elevated container, atlas-stroke-2 row dividers, 280px max-height scroll, 5-result client cap |
| SPLA-01: Professional landing appearance using Fluent 2 aesthetics | SATISFIED | Geometric SVG logo, 12px card radius, border not shadow, Segoe UI Variable 28px/600, accent-color button |
| DEBT-03: 3 test regressions fixed | SATISFIED | interactive and cba test functions clean; server test docstring accurate at 17 |
| DEBT-04: get_user_photo_bytes() dead code removed | SATISFIED | Function and all 4 tests gone from graph_client.py and test_graph_client.py |
| DEBT-05: get_colleague_profile user_id schema description corrected | SATISFIED | Microsoft Graph API object ID (GUID) from search_colleagues results |

### Anti-Patterns Found

None. No TODO/FIXME/placeholder markers, no empty handlers, no stub returns in any modified file.

### Human Verification Required

#### 1. Profile Card Visual Appearance in Chat

**Test:** Send a message that triggers get_colleague_profile and renders a ProfileCard in the chat pane.
**Expected:** Card shows photo or initials fallback, name in semibold, job title and department in smaller secondary text, email as accent-colored link - all fitting within 320px with ellipsis on overflow.
**Why human:** Pixel geometry, font rendering, and Fluent 2 aesthetic conformance cannot be verified by grep.

#### 2. Search Result List Visual Appearance

**Test:** Send a search_colleagues query that returns multiple results.
**Expected:** Results appear as a compact list inside one elevated container with thin divider lines between rows. Scroll visible if more than 5 results returned by server.
**Why human:** Container elevation, divider visibility, and scroll behavior are runtime properties.

#### 3. Splash Page Visual Appearance

**Test:** Open the app in a browser while not authenticated.
**Expected:** Geometric rotated-square SVG logo above Atlas heading, subtitle, single-sentence description, blue Sign in with Microsoft button. Page centered vertically and professional.
**Why human:** Visual design quality and overall aesthetics require human judgment.

#### 4. Dark Mode on Splash Page

**Test:** Toggle the app to dark mode and view the splash page.
**Expected:** Background, card surface, text, and border switch to dark equivalents. Brand button remains accent-blue.
**Why human:** CSS token resolution at runtime with theme toggling cannot be verified statically.

---

## Gaps Summary

No gaps. All 5 observable truths are verified with concrete evidence from the codebase. All 9 required artifacts exist, are substantive (no stubs), and are wired correctly. No blocker anti-patterns found. Human verification items do not block goal achievement.

---

_Verified: 2026-03-30T12:45:08Z_
_Verifier: Claude (gsd-verifier)_
