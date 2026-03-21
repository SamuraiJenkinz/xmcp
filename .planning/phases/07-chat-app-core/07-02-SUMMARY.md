---
phase: 07-chat-app-core
plan: "02"
subsystem: auth
tags: [msal, azure-ad, entra-id, flask, sso, oauth2, auth-code-flow, token-cache]

# Dependency graph
requires:
  - phase: 07-01
    provides: Flask app factory, server-side sessions (flask-session filesystem), Config class with AZURE_CLIENT_ID/SECRET/AUTHORITY/TENANT_ID

provides:
  - MSAL auth code flow blueprint (auth_bp) with /login, /auth/callback, /logout
  - SerializableTokenCache stored in flask-session for silent re-auth
  - login_required decorator for protecting Flask routes
  - get_token_silently() helper for downstream token acquisition
  - Protected /chat route — unauthenticated users redirected to splash
  - Conditional Access / interaction_required error handling

affects:
  - 07-03 (chat/stream endpoint needs get_token_silently for on-behalf-of or session user token)
  - 07-04 onwards (all protected routes use login_required)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - MSAL auth code flow with SerializableTokenCache in flask-session
    - Flask Blueprint for auth routes isolated from app factory
    - login_required decorator pattern for route protection
    - ValueError catch on acquire_token_by_auth_code_flow for CSRF protection
    - interaction_required Conditional Access redirect-to-login (not error page)

key-files:
  created:
    - chat_app/auth.py
  modified:
    - chat_app/app.py
    - chat_app/templates/splash.html
    - chat_app/templates/base.html

key-decisions:
  - "Conditional Access interaction_required redirects to /login (not error page) — MSAL will include required claims in next auth request"
  - "ValueError on acquire_token_by_auth_code_flow catches CSRF/state mismatch — redirect to /login, not 400 error"
  - "get_token_silently() exposed as module-level helper — 07-03 chat endpoint will use this for API calls"
  - "login_required checks session['user'], redirects to url_for('index') — splash page is the unauthenticated landing"
  - "auth_callback redirects to url_for('chat') on success — assumes /chat route exists (registered in same app factory)"

patterns-established:
  - "Blueprint pattern: auth routes isolated in auth.py Blueprint, registered via app.register_blueprint(auth_bp)"
  - "Token cache pattern: _load_cache() / _save_cache(cache) wrap every MSAL operation that may mutate the cache"
  - "Route protection: @login_required decorator applied at route definition, checks session['user']"

# Metrics
duration: 8min
completed: 2026-03-21
---

# Phase 7 Plan 02: Azure AD SSO via MSAL Auth Code Flow Summary

**MSAL auth code flow with SerializableTokenCache in flask-session — /login initiates OAuth2, /auth/callback exchanges code for tokens and stores id_token_claims, /chat protected by login_required decorator**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-21T19:00:06Z
- **Completed:** 2026-03-21T19:07:38Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- Azure AD / Entra ID SSO wired end-to-end: /login → Microsoft login page → /auth/callback → /chat
- SerializableTokenCache persisted in flask-session enables silent re-auth without browser redirect
- Conditional Access errors (interaction_required, invalid_grant) handled gracefully via redirect to /login
- CSRF protection via ValueError catch on state mismatch in auth callback
- /chat route now protected by login_required — unauthenticated GET → 302 to splash

## Task Commits

1. **Task 1: Create auth.py with MSAL auth code flow routes** - `45197f8` (feat)
2. **Task 2: Register auth blueprint, protect chat route, update template links** - `2e27c2c` (feat)

## Files Created/Modified

- `/c/xmcp/chat_app/auth.py` - Flask Blueprint with /login, /auth/callback, /logout routes; _build_msal_app, _load_cache, _save_cache, get_token_silently helpers; login_required decorator
- `/c/xmcp/chat_app/app.py` - Removed stub login/logout routes; registered auth_bp; applied @login_required to /chat
- `/c/xmcp/chat_app/templates/splash.html` - Updated url_for('login') → url_for('auth.login')
- `/c/xmcp/chat_app/templates/base.html` - Updated url_for('logout') → url_for('auth.logout')

## Decisions Made

- **Conditional Access handling:** `interaction_required` and `invalid_grant` errors redirect back to `/login` rather than showing an error page. MSAL includes the required claims/MFA prompt in the next auth request automatically.
- **CSRF protection:** `ValueError` from `acquire_token_by_auth_code_flow` (state mismatch, stale flow) redirects to `/login` — silent failure is appropriate since this is a replay/CSRF scenario.
- **get_token_silently exposed as public helper:** The 07-03 chat streaming endpoint will need to acquire a token on behalf of the authenticated user for any downstream API calls; `get_token_silently()` is the entry point.
- **login_required redirects to `index`:** The splash page is the unauthenticated landing, not directly to `/login`, so users see the branded entry point before being asked to sign in.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no additional external service configuration required for this plan. Azure AD app registration (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID) is already a prerequisite from the project setup.

## Next Phase Readiness

- Auth is complete. Any route decorated with `@login_required` will require an authenticated session.
- `get_token_silently()` is available for 07-03 to acquire access tokens for the Azure OpenAI / MCP call chain.
- `session['user']` contains the full `id_token_claims` dict (includes `name`, `preferred_username`, `oid`, `tid`).
- The redirect URI `/auth/callback` must be registered in the Azure AD app registration's "Redirect URIs" — this is an external setup step the operator must confirm before live testing.

---
*Phase: 07-chat-app-core*
*Completed: 2026-03-21*
