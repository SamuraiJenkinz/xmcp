---
phase: 13-infrastructure-scaffold
verified: 2026-03-27T21:00:00Z
status: gaps_found
score: 4/5 success criteria verified
gaps:
  - truth: "GET /api/me returns 401 or redirects to login when user is not authenticated"
    status: failed
    reason: "Phase 13 removed @app.route from index() making it a plain function, but auth.py was not updated. url_for('index') in login_required (auth.py:97) and logout (auth.py:179) now raises werkzeug.routing.exceptions.BuildError at runtime instead of redirecting. Unauthenticated requests to /api/me, /api/photo/*, and /chat produce HTTP 500 instead of the expected redirect/401."
    artifacts:
      - path: "chat_app/auth.py"
        issue: "url_for('index') on lines 97 and 179 references Flask endpoint 'index' that no longer exists. The endpoint was deregistered in commit 6846ef4 when @app.route('/') was removed from index()."
      - path: "chat_app/app.py"
        issue: "catch_all() was correctly updated to use url_for('catch_all', path='') on line 240, but the same fix was not applied to auth.py."
    missing:
      - "Update auth.py line 97: change url_for('index') to url_for('catch_all', path='') in login_required decorator"
      - "Update auth.py line 179: change url_for('index') to url_for('catch_all', path='') in logout route"
human_verification:
  - test: "Run npm run dev in frontend/ while Flask is running on :5000"
    expected: "Vite starts on :5173; React page renders Atlas title with dark theme; no CORS errors in browser console"
    why_human: "Dev server startup and CORS behavior cannot be verified without running both servers"
  - test: "With a valid MSAL session cookie, visit http://localhost:5173/api/me"
    expected: "JSON response with displayName, email, oid fields"
    why_human: "MSAL session requires live authentication flow against Azure AD"
  - test: "Set ATLAS_UI=react, restart Flask, navigate to http://localhost:5000/"
    expected: "frontend_dist/index.html served; React page with Atlas title renders correctly"
    why_human: "Requires running Flask with env var set and browser access"
---

# Phase 13: Infrastructure Scaffold Verification Report

**Phase Goal:** React + Vite + Fluent UI v9 + Tailwind v4 scaffold wired into Flask -- auth and SSE verified through the new integration layer; zero user-visible change
**Verified:** 2026-03-27T21:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | npm run dev starts Vite on :5173 and proxies API requests to Flask :5000 without CORS errors | NEEDS HUMAN | vite.config.ts has server.port 5173 and proxy for /api /login /logout /auth with changeOrigin true. Structure correct; live verification requires both servers running. |
| 2 | App in dev mode shows React-rendered page; user authenticated via MSAL session cookie | NEEDS HUMAN | main.tsx mounts on #app, App.tsx renders FluentProvider + Title1. Structurally correct; auth requires live Azure AD session. |
| 3 | GET /api/me returns displayName and email as JSON (200) or redirects/401 if unauthenticated | PARTIAL | /api/me exists and returns correct JSON for authenticated users (app.py lines 211-222). Unauthenticated requests produce HTTP 500 BuildError -- url_for('index') in login_required (auth.py:97) references deregistered endpoint. |
| 4 | FluentProvider renders without errors and applies webDarkTheme to the page shell | VERIFIED | App.tsx imports FluentProvider and webDarkTheme from @fluentui/react-components; wraps entire component tree. Built JS (239KB) confirms Fluent UI compiled. |
| 5 | npm run build produces a bundle in frontend_dist/ that Flask serves correctly with catch-all route | VERIFIED | frontend_dist/ exists with index.html, JS 239887 bytes, CSS 4331 bytes. Flask catch_all serves FRONTEND_DIST/index.html when ATLAS_UI=react. FRONTEND_DIST path resolves correctly to project root. |

**Score: 3/5 automated checks pass cleanly; SC3 partial failure; SC1 and SC2 require human verification**

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| frontend/vite.config.ts | Vite config with proxy and outDir | VERIFIED | Proxy /api /login /logout /auth to :5000; outDir ../frontend_dist; port 5173 |
| frontend/src/App.tsx | FluentProvider + webDarkTheme | VERIFIED | 12 lines; real @fluentui/react-components import; FluentProvider wraps output; tw: classes present |
| frontend/src/main.tsx | React 19 StrictMode on #app | VERIFIED | createRoot(getElementById('app')) with StrictMode; 10 lines |
| frontend/src/index.css | Tailwind v4 @import prefix(tw) | VERIFIED | Single @import "tailwindcss" prefix(tw) directive |
| frontend/index.html | div#app mount point | VERIFIED | Title Atlas; div id=app; module script src/main.tsx |
| frontend/package.json | React 19, FluentUI v9, Tailwind v4, Vite 8 | VERIFIED | All specified versions present in dependencies/devDependencies |
| frontend_dist/index.html | Built SPA entry point | VERIFIED | Hashed asset references; div id=app present |
| frontend_dist/assets/index-*.js | Built JS bundle | VERIFIED | 239887 bytes; React + FluentUI code confirmed by grep |
| chat_app/app.py | /api/me + catch-all + FRONTEND_DIST | VERIFIED (partial) | Structurally correct. Authenticated path works. Unauthenticated path broken -- see gap. |
| chat_app/config.py | ATLAS_UI feature flag | VERIFIED | ATLAS_UI = os.environ.get('ATLAS_UI', 'classic') at line 42 |
| chat_app/auth.py | login_required redirects correctly | FAILED | url_for('index') on lines 97 and 179 references deregistered endpoint |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| frontend/src/main.tsx | frontend/index.html #app | getElementById('app') | WIRED | createRoot call matches div id=app in HTML |
| frontend/vite.config.ts | Flask :5000 | server.proxy | WIRED | Four proxy entries with changeOrigin true |
| frontend/src/App.tsx | @fluentui/react-components | FluentProvider webDarkTheme | WIRED | Direct import; wraps entire component output |
| chat_app/app.py api_me | session['user'] | MSAL session data | WIRED | session.get('user', {}) on line 215 |
| chat_app/app.py catch_all | frontend_dist/ | send_from_directory | WIRED | send_from_directory(FRONTEND_DIST, 'index.html') on line 247 |
| chat_app/app.py catch_all | chat_app/config.py | ATLAS_UI feature flag | WIRED | app.config.get('ATLAS_UI') != 'react' on line 236 |
| chat_app/auth.py login_required | / splash page | url_for('index') | NOT_WIRED | References non-existent endpoint; BuildError at runtime |
| chat_app/auth.py logout | / splash page | url_for('index') | NOT_WIRED | References non-existent endpoint; BuildError at runtime |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| FRAME-01 Vite + React scaffold | SATISFIED | All scaffold files exist, build verified |
| FRAME-02 Flask integration layer | PARTIAL | /api/me authenticated path works; unauthenticated path returns 500 |
| FRAME-03 Feature flag zero regression | PARTIAL | Classic mode root works; unauthenticated requests to protected routes return 500 -- regression introduced in phase 13 |
| FRAME-07 FluentProvider + webDarkTheme | SATISFIED | FluentProvider wraps app, webDarkTheme applied, compiled successfully |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| chat_app/auth.py | 97 | url_for('index') endpoint does not exist | Blocker | Unauthenticated requests to /api/me /api/photo/* /chat return HTTP 500 |
| chat_app/auth.py | 179 | url_for('index') endpoint does not exist | Blocker | Logout returns HTTP 500 BuildError instead of redirecting to splash page |

### Human Verification Required

#### 1. Dev Server and Proxy (SC1)
**Test:** Run cd frontend and npm run dev while Flask is running on :5000. Open http://localhost:5173/api/health in browser.
**Expected:** Vite starts on :5173; browser shows JSON health response proxied from Flask; no CORS errors in console.
**Why human:** Cannot start two servers and observe network traffic programmatically.

#### 2. MSAL Session Cookie Auth (SC2)
**Test:** Navigate to http://localhost:5173 while authenticated with a valid MSAL session cookie from prior Flask login.
**Expected:** React-rendered page with Atlas title and dark Fluent UI theme. The #app div is populated by React, not blank.
**Why human:** MSAL session requires live Azure AD auth flow.

#### 3. Flask React Mode Serving (SC5 end-to-end)
**Test:** Set ATLAS_UI=react in environment, start Flask, navigate to http://localhost:5000/.
**Expected:** Flask serves frontend_dist/index.html; React hydrates correctly; no 404 on assets.
**Why human:** Requires live Flask instance with env var set.

### Gaps Summary

One structural gap blocks SC3 and introduces a regression affecting all users.

Phase 13 task 2 (commit 6846ef4) correctly removed @app.route('/') from index() to prevent a route conflict with the new catch-all. The catch-all itself was updated to use url_for('catch_all', path='') for its own classic-mode redirect (line 240 of app.py). However, chat_app/auth.py was not modified -- it still calls url_for('index') in two places:

1. login_required decorator (auth.py line 97): fires on unauthenticated access to any @login_required route
2. logout route (auth.py line 179): fires when a user logs out

Both raise werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'index' at runtime, returning HTTP 500 instead of the expected redirect.

**Impact on success criteria:** SC3 partial failure -- the "redirects/401 if unauthenticated" requirement returns 500 instead. Logout is also broken for all users regardless of ATLAS_UI mode, meaning the "zero user-visible change" goal is not fully met.

**Fix is two lines in auth.py:** Change url_for('index') to url_for('catch_all', path='') on lines 97 and 179. The catch_all endpoint accepts a path parameter and url_for('catch_all', path='') generates the URL '/'.

**SSE guard verification:** The catch-all guard tuple includes 'chat/' which prevents the catch-all from intercepting /chat/stream. The SSE endpoint is structurally protected. The /chat proxy is intentionally absent from vite.config.ts because Phase 13 React shell makes no SSE calls -- that is Phase 14 work.

---

_Verified: 2026-03-27T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
