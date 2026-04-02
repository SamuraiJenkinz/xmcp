---
phase: 21-app-role-access-control
verified: 2026-04-02T12:21:49Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: Sign in with an Azure AD account that lacks the Atlas.User App Role
    expected: See AccessDenied card with UPN copy button and Request Access mailto link
    why_human: Requires Azure AD tenant with Atlas.User App Role in Entra and an excluded account
  - test: Open browser with no session and navigate to the app
    expected: HTTP 401 from /api/me and redirect to /login not 403
    why_human: Requires live HTTP requests with no active session cookie
  - test: Authenticated without Atlas.User role call POST /chat/stream and GET /api/threads
    expected: Both return 403 JSON with error=forbidden and upn field
    why_human: Requires authenticated session without the role claim in Entra
  - test: IT engineer with Atlas.User assigned loads the app
    expected: Chat interface loads identically to v1.2 no regression
    why_human: Requires assigned role in Azure AD tenant
---

# Phase 21: App Role Access Control Verification Report

**Phase Goal:** Only authorized IT engineers (holding the Atlas.User App Role) can access the application. All other authenticated users see a Fluent 2 access denied experience instead of the chat interface.
**Verified:** 2026-04-02T12:21:49Z
**Status:** human_needed (all automated checks PASSED)
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Authenticated user lacking Atlas.User receives 403 from /api/me and sees AccessDenied | VERIFIED | role_required auth.py L109-157 returns 403 JSON with upn; fetchMe me.ts L11-18 maps HTTP 403 to forbidden with UPN; AuthGuard App.tsx L24-26 renders AccessDenied for status=forbidden |
| 2 | User with no session receives 401 and is redirected to /login distinct from 403 path | VERIFIED | role_required L125-131 returns 401 for missing session; fetchMe L10 maps 401 to unauth; AuthGuard L20-22 maps unauthenticated/error to window.location.href=/login separate branch from forbidden |
| 3 | /chat/stream and all /api/conversations routes return 403 for authenticated-but-no-role | VERIFIED | All 9 routes use @role_required: chat.py L130 app.py L148/183/212 conversations.py L41/54/75/99/120; no @login_required on any route |
| 4 | IT engineer with Atlas.User sees no behavior change | VERIFIED | role_required L155 passes through when role present; AuthGuard L28 returns children into same ThreadProvider/ChatProvider/AppLayout tree |
| 5 | Access denied page shows UPN with one-click copy and mailto link | VERIFIED | AccessDenied.tsx L97-109 UPN display; L71-79 copy with checkmark feedback; L81-85 pre-filled mailto; L18 VITE_ADMIN_EMAIL env var with fallback |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| chat_app/auth.py | role_required decorator REQUIRED_ROLE 403 JSON with upn | VERIFIED | L27 REQUIRED_ROLE=Atlas.User L109-157 full decorator 401/403 branches |
| chat_app/app.py | 3 protected routes /api/me returns roles | VERIFIED | L14 imports role_required L148/183/212 decorators L219 roles in response |
| chat_app/chat.py | /chat/stream uses @role_required | VERIFIED | L51 imports L130 decorator |
| chat_app/conversations.py | 5 CRUD routes @role_required | VERIFIED | L14 imports L41/54/75/99/120 all decorated |
| frontend/src/types/index.ts | AuthStatus union ForbiddenResponse User.roles | VERIFIED | L58 roles field L62 AuthStatus L64-70 ForbiddenResponse |
| frontend/src/api/me.ts | fetchMe discriminates 401 vs 403 extracts UPN | VERIFIED | L10 maps 401 to unauth L11-18 maps 403 to forbidden with UPN parse |
| frontend/src/contexts/AuthContext.tsx | status union upn field on forbidden state | VERIFIED | L6-10 AuthState L29-30 forbidden branch with upn |
| frontend/src/components/AccessDenied.tsx | Fluent 2 card UPN copy button mailto VITE_ADMIN_EMAIL | VERIFIED | 124 lines all Fluent 2 full implementation |
| frontend/src/App.tsx | AuthGuard forbidden branch AccessDenied before providers | VERIFIED | L7 import L24-26 forbidden renders AccessDenied L44 AuthGuard wraps providers |
| frontend/src/hooks/useStreamingMessage.ts | SSE 401/403 triggers window.location.reload | VERIFIED | L112-116 reload branch before onError |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| @role_required | 403 JSON response | REQUIRED_ROLE not in roles check | WIRED | auth.py L133-152 structured 403 with upn |
| fetchMe | AuthContext forbidden status | result.status=forbidden branch | WIRED | me.ts L18 to AuthContext.tsx L29-30 |
| AuthContext.status | AccessDenied render | AuthGuard status=forbidden | WIRED | App.tsx L24-26 |
| AccessDenied.upn | copy button | navigator.clipboard.writeText | WIRED | AccessDenied.tsx L71-79 |
| AccessDenied | mailto link | mailtoHref with pre-filled UPN | WIRED | AccessDenied.tsx L81-85 L116 |
| SSE hook 401/403 | page reload | window.location.reload before onError | WIRED | useStreamingMessage.ts L112-116 |
| AuthGuard unauthenticated/error | /login redirect | window.location.href=/login | WIRED | App.tsx L21 |

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| AUTH-01 Atlas.User enforced on all protected routes | SATISFIED | All 9 routes @role_required |
| AUTH-02 401 unauthenticated 403 authenticated-unauthorized | SATISFIED | role_required L125-131 and L133-152 distinct branches |
| AUTH-03 403 structured JSON with upn field | SATISFIED | auth.py L144-150 error message required_role upn |
| AUTH-04 403 denials logged with UPN endpoint timestamp | SATISFIED | auth.py L135-139 logger.warning |
| AUTH-05 Frontend discriminates 401 from 403 distinct UI | SATISFIED | fetchMe to AuthContext to AuthGuard chain |
| AUTH-06 Fluent 2 AccessDenied with UPN copy and mailto | SATISFIED | AccessDenied.tsx fully implemented |
| AUTH-07 SSE returns 403 for no-role and hook reloads | SATISFIED | @role_required on /chat/stream hook L112-116 |

### Anti-Patterns Found

None. No TODOs, stubs, placeholders, empty handlers, or console.log-only implementations in any modified file.

### Human Verification Required

All code is structurally complete and correct. The following require live Azure AD environment testing due to the external dependency on the Atlas.User App Role existing in Entra.

#### 1. Forbidden (403) path - authenticated without role

**Test:** Sign in with an Azure AD account NOT assigned Atlas.User App Role.
**Expected:** Fluent 2 AccessDenied card centered on full viewport showing the signed-in UPN, a copy button (checkmark for 1.5s), and a Request Access button opening a pre-addressed email.
**Why human:** Requires Atlas.User App Role created in Entra and a test account lacking the assignment.

#### 2. Unauthenticated (401) path - no session

**Test:** Clear cookies or use incognito, navigate to the app, or call GET /api/me with no session cookie.
**Expected:** Browser redirects to /login. API returns HTTP 401 with error=authentication_required not 403.
**Why human:** Requires stateless HTTP client or cleared browser session.

#### 3. Direct API access from authenticated-but-no-role session

**Test:** With a session cookie lacking Atlas.User, call POST /chat/stream and GET /api/threads directly.
**Expected:** Both return HTTP 403 with error=forbidden required_role=Atlas.User and the signed-in upn.
**Why human:** Requires authenticated session cookie lacking the role claim.

#### 4. Authorized user regression

**Test:** Sign in with an account holding Atlas.User and use the app normally.
**Expected:** No change from v1.2 behavior. Chat, SSE streaming, and thread CRUD all function normally.
**Why human:** Requires an account with Atlas.User assigned in Entra.

### Gaps Summary

No gaps. All automated checks passed across all 5 observable truths, all 10 required artifacts, and all 7 key links. The human_needed status reflects the external Azure AD dependency - it does not indicate a code deficiency.

---
*Verified: 2026-04-02T12:21:49Z*
*Verifier: Claude (gsd-verifier)*
