# Phase 21: App Role Access Control - Research

**Researched:** 2026-04-02
**Domain:** MSAL Python App Roles, Flask auth decorators, React AuthGuard, Fluent UI v9 access-denied page
**Confidence:** HIGH (primary findings all verified against official sources or live codebase)

---

## Summary

Phase 21 gates the Atlas chat application behind the `Atlas.User` App Role in Microsoft Entra ID. The implementation spans three areas: (1) Python/Flask backend — a new `role_required` decorator that checks the `roles` claim in `session["user"]`, replacing `login_required` on all protected routes; (2) React frontend — extending `AuthContext` and `AuthGuard` to distinguish 401 (unauthenticated) from 403 (authenticated but no role) and render an access-denied page for 403; and (3) a new `AccessDenied` React component that is a centered Fluent 2 card with mailto and copy-UPN actions.

The `roles` claim is already present in `session["user"]` (which holds `id_token_claims`) after a successful MSAL auth code flow — no new token calls are needed. The claim is a `list[str]` keyed as `"roles"` in the `id_token_claims` dict. Microsoft's official docs confirm this claim is included in the ID token when the user is assigned an App Role directly (not via group-to-role assignment, which has a known limitation).

The existing `login_required` decorator in `chat_app/auth.py` is the only backend auth chokepoint and covers every protected route (`/chat`, `/api/me`, `/api/threads*`, `/chat/stream`, `/api/photo/*`). The new `role_required` replaces it globally. The SSE endpoint `/chat/stream` can safely return a non-streaming `Response` with `content_type="application/json"` and status 403 before the `stream_with_context` generator is entered — this is already the pattern used for other pre-stream validation errors in that file.

**Primary recommendation:** Derive `role_required` from the existing `login_required` pattern; check `"Atlas.User" in (session["user"] or {}).get("roles", [])`. Extend the `/api/me` response to include a `roles` list so the React frontend can distinguish 403 without a separate endpoint.

---

## Standard Stack

The application already uses every library needed. No new dependencies are required.

### Core (already installed)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `msal` | current | Auth code flow, token cache | `id_token_claims` already in `session["user"]` |
| `flask` | current | Routes, decorators, session | `functools.wraps` pattern already used |
| `flask-session` | current | Server-side filesystem sessions | Session dir at `SESSION_FILE_DIR` |
| `@fluentui/react-components` | `^9.73.5` | Card, Body1, Subtitle2, Title3, Button, Spinner | Already installed |
| `react` | `^19.2.4` | AuthContext, AuthGuard, new component | Already installed |

### No new installs needed
All implementation uses existing packages. The Fluent 2 `Card`, `CardHeader`, `Body1`, `Subtitle2`, `Button`, `Spinner` components are all exported from the already-installed `@fluentui/react-components`.

---

## Architecture Patterns

### How App Roles flow into the Flask session (HIGH confidence)

When a user authenticates via MSAL auth code flow, `acquire_token_by_auth_code_flow()` returns a result dict. `result.get("id_token_claims")` is stored as `session["user"]`. The `id_token_claims` dict contains a `"roles"` key whose value is a `list[str]` of role values (matching the **Value** field set in the Entra admin center, e.g. `"Atlas.User"`). This key is absent (not an empty list) when the user has no assigned roles.

Official Microsoft docs (ID token claims reference, updated 2025-10-02): "roles — Array of strings — The set of roles that were assigned to the user who is logging in."

Confirmed from the official Azure-Samples Python webapp pattern:
```python
user_claims = session["user"]["id_token_claims"]
if "roles" not in user_claims or "Atlas.User" not in user_claims["roles"]:
    return jsonify({"error": "forbidden", ...}), 403
```

**Critical limitation (HIGH confidence):** If an App Role is assigned to a *group* and the user is a member of that group, the `roles` claim is NOT emitted in the token. Roles must be assigned directly to the user (or to the security group via the Enterprise Applications pane — not via API Permissions). The CONTEXT.md blocker note reflects this: the `Atlas.User` App Role must be created in Entra admin center and the IT engineers group assigned before end-to-end testing is possible.

### Backend: `role_required` decorator pattern

The existing `login_required` in `chat_app/auth.py` (line 92) is a `functools.wraps` decorator that checks `session.get("user")`. `role_required` follows the same pattern with an additional roles check:

```python
# Source: auth.py (existing login_required pattern) + official Azure-Samples
REQUIRED_ROLE = "Atlas.User"

def role_required(f):
    """Decorator: 401 if unauthenticated, 403 if authenticated without Atlas.User role."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        if not user:
            if request.path.startswith("/api/") or request.path.startswith("/chat/"):
                return jsonify({"error": "authentication_required", "message": "Login required"}), 401
            return redirect(url_for("catch_all", path=""))
        roles = (user.get("id_token_claims") or user).get("roles", [])
        # session["user"] IS id_token_claims (set as result.get("id_token_claims"))
        # so just: user.get("roles", [])
        if REQUIRED_ROLE not in roles:
            logger.warning(
                "403 Forbidden: upn=%s endpoint=%s ts=%s",
                user.get("preferred_username", "unknown"),
                request.path,
                datetime.datetime.utcnow().isoformat(),
            )
            if request.path.startswith("/api/") or request.path.startswith("/chat/"):
                return jsonify({
                    "error": "forbidden",
                    "message": "Atlas.User role required",
                    "required_role": REQUIRED_ROLE,
                }), 403
            # For HTML routes (non-API), return 403 with a flag so React can render the denied page.
            # In React mode the catch_all serves index.html — so the SPA handles the 403 UI.
            # Signal via HTTP 403 on the /api/me endpoint instead (see frontend section).
            return redirect(url_for("catch_all", path=""))
        return f(*args, **kwargs)
    return decorated_function
```

**Session structure note:** In the existing `auth_callback`, `session["user"] = result.get("id_token_claims")`. So `session["user"]` IS the `id_token_claims` dict. Roles are accessed as `session["user"].get("roles", [])` — no `.get("id_token_claims")` nesting needed.

### Backend: `/api/me` endpoint changes

`/api/me` is the React SPA's bootstrap call (fetched once at mount in `AuthContext`). Currently returns `displayName`, `email`, `oid`. It should also return `roles` so the frontend can distinguish 403 states without a separate check endpoint.

The `role_required` decorator on `/api/me` handles the 403 case. The `/api/me` response shape for an authorized user:
```json
{
  "displayName": "Jane Doe",
  "email": "jane.doe@mercer.com",
  "oid": "...",
  "roles": ["Atlas.User"]
}
```

For a 403 from the decorator:
```json
{"error": "forbidden", "message": "Atlas.User role required", "required_role": "Atlas.User"}
```

### Frontend: AuthContext and AuthGuard (403 vs 401)

Current `fetchMe()` in `api/me.ts`:
- `401` → returns `null` (maps to "not authenticated")
- non-ok → throws (maps to `error` state)

New behavior needed:
- `401` → unauthenticated → `window.location.href = '/login'` (existing behavior)
- `403` → authenticated but no role → new `AccessDenied` component
- `5xx`/network error → retry logic or error state

Cleanest approach: add an `authStatus` discriminated union to AuthContext state:

```typescript
// Source: codebase pattern + research
type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'forbidden' | 'error';

interface AuthState {
  status: AuthStatus;
  user: User | null;
  error: string | null;
}
```

`fetchMe()` needs to expose the 403 case:
```typescript
// api/me.ts — extend to return status alongside user
export async function fetchMe(): Promise<{ user: User | null; status: 'ok' | 'unauth' | 'forbidden' }> {
  const res = await fetch('/api/me');
  if (res.status === 401) return { user: null, status: 'unauth' };
  if (res.status === 403) return { user: null, status: 'forbidden' };
  if (!res.ok) throw new Error(`fetchMe failed: ${res.status}`);
  const data = await res.json() as User;
  return { user: data, status: 'ok' };
}
```

Updated `AuthGuard` in `App.tsx`:
```typescript
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  if (status === 'loading') return <div className="loading">Loading...</div>;
  if (status === 'unauthenticated') {
    window.location.href = '/login';
    return null;
  }
  if (status === 'forbidden') return <AccessDenied user={user} />;
  // status === 'authenticated'
  return <>{children}</>;
}
```

The `user` passed to `AccessDenied` may be null (the 403 response from `role_required` doesn't return user data). To show the UPN on the access denied page, the `/api/me` 403 response can optionally include the UPN, or the component can display a generic message. The CONTEXT.md marks this as Claude's Discretion ("display name + UPN vs UPN only").

### Frontend: `AccessDenied` component

Centered Fluent 2 card on a blank page (no sidebar, no app chrome). The component renders outside the `ThreadProvider`/`ChatProvider` tree (inside `AuthGuard` wrapping logic in `App.tsx`) so it has no context dependencies.

Available from `@fluentui/react-components` (already installed, v9):
- `Card` — container
- `CardHeader` — header with title
- `Body1`, `Subtitle1`, `Title3` — typography
- `Button` — mailto link and Copy UPN

Pattern (Fluent 2 design system, confirmed from existing codebase usage):
```tsx
// Source: @fluentui/react-components v9 — all these are exported from the installed package
import {
  Card, CardHeader,
  Title3, Body1, Subtitle2,
  Button,
  makeStyles, tokens,
} from '@fluentui/react-components';

const useStyles = makeStyles({
  root: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: tokens.colorNeutralBackground1,
  },
  card: {
    maxWidth: '480px',
    width: '100%',
    padding: tokens.spacingVerticalXXL,
  },
});
```

**Copy UPN feedback:** Use inline text swap (not toast) — the existing `CopyButton` in `components/shared/CopyButton.tsx` already implements this pattern (copied → shows checkmark for 1500ms). The `AccessDenied` component can use the same approach or import `CopyButton` directly.

**Mailto link format:**
```typescript
const adminEmail = import.meta.env.VITE_ADMIN_EMAIL ?? 'it-admin@mercer.com';
const subject = encodeURIComponent('Atlas Access Request');
const body = encodeURIComponent(`Hi,\n\nI'd like access to Atlas.\n\nMy UPN is: ${upn}`);
const mailtoHref = `mailto:${adminEmail}?subject=${subject}&body=${body}`;
```

The admin email must be passed to the frontend at build time via a `VITE_` env var (Vite exposes only `VITE_*` prefix env vars to the browser). Alternatively it can be returned by `/api/me` error response or a separate `/api/config` endpoint. The env var approach is simpler and already matches the pattern decided in CONTEXT.md ("config-driven via environment variable").

### SSE endpoint 403 handling (HIGH confidence)

`/chat/stream` uses `stream_with_context`. All pre-stream validation (no message, no thread_id, wrong thread ownership) already returns a plain `Response` object with `content_type="text/event-stream"` containing a single SSE error event. This is the existing pattern for those cases.

For the 403 case, return a proper JSON response BEFORE entering the generator:
```python
@chat_bp.route("/chat/stream", methods=["POST"])
@role_required  # replaces @login_required
def chat_stream() -> Response:
    # role_required handles 401/403 before this body runs
    ...
```

Because `role_required` runs the check and returns before the route body executes, the SSE generator is never entered. The frontend `EventSource` or `fetch`-based SSE client must handle a non-`200` HTTP status from `/chat/stream`. The existing `useStreamingMessage` hook should check `response.ok` before reading the stream.

### Session handling for existing sessions without `roles` claim (AUTH-07)

**The problem:** Existing authenticated sessions stored in filesystem files (`SESSION_FILE_DIR`) contain `session["user"]` without a `roles` key. At deploy, these sessions will pass the `session.get("user")` check in `role_required` but then fail the roles check, returning 403 to a potentially authorized user who just needs to re-login to get the `roles` claim issued.

**Recommended approach — graceful handling via re-login:**
The `role_required` decorator should detect the "authenticated but roles claim absent" case and offer the user a path to re-authenticate. For API routes a 403 with a message like `"session_missing_roles"` is sufficient. The React frontend can distinguish this from a true "not assigned" 403 and redirect to `/login` automatically (since re-login will re-issue the token with the roles claim if the user is assigned).

**Session flush option:** Physically deleting all files in `SESSION_FILE_DIR` before deploy is the blunt but clean option. This forces all users to re-authenticate and get fresh tokens with roles. Since all session state is in the Flask session (not the database), this causes no data loss — threads/messages are in SQLite. The deploy runbook should include this step.

Recommended: do both — handle gracefully in code (redirect to re-login for sessions without roles) AND flush sessions at deploy.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| App Role check from id_token | Custom JWT decode | `session["user"].get("roles", [])` | MSAL already decoded the token and stored claims |
| Auth header/middleware framework | Custom middleware class | `functools.wraps` decorator (existing pattern) | Already proven, Flask-idiomatic |
| Admin email config | Hardcoded value | `VITE_ADMIN_EMAIL` env var via `import.meta.env` | Matches CONTEXT.md, Vite convention |
| Copy-to-clipboard feedback | Custom toast system | Inline state swap (existing `CopyButton` pattern) | No `Toaster` provider is set up in the app |
| Theme-aware styles on AccessDenied | Custom dark/light CSS | Fluent 2 `tokens.*` via `makeStyles` or CSS vars `--atlas-*` | Already established patterns in the codebase |

---

## Common Pitfalls

### Pitfall 1: `roles` key absent vs empty list
**What goes wrong:** `user.get("roles", [])` returns `[]` for both "user has no roles" and "old session missing claim." Treat both as 403, but consider logging `"session_missing_roles"` as a distinct log marker for observability.
**How to avoid:** `"Atlas.User" in session["user"].get("roles", [])` — simple membership check handles both cases correctly.

### Pitfall 2: Group-to-App-Role assignment doesn't emit `roles` in token
**What goes wrong:** If admins assign the security group to the App Role in the wrong place (API Permissions pane instead of Enterprise Applications > Users and groups), the `roles` claim won't appear in the token.
**How to avoid:** Assignment must be done via Enterprise Applications > Users and Groups > Add user/group > Select role. Document this in the runbook. The `roles` claim only appears when users are assigned via the Enterprise Applications pane.

### Pitfall 3: `session["user"]` structure
**What goes wrong:** Confusing `session["user"]` with a nested structure. In this codebase, `session["user"]` IS `id_token_claims` directly (set as `result.get("id_token_claims")` in `auth_callback`). Accessing `session["user"]["id_token_claims"]` would be a KeyError.
**How to avoid:** Access roles as `session["user"].get("roles", [])` directly.

### Pitfall 4: Vite env vars require `VITE_` prefix
**What goes wrong:** Setting `ADMIN_EMAIL` env var on the server — Vite doesn't expose it to the React bundle.
**How to avoid:** Use `VITE_ADMIN_EMAIL` in the build environment. In `import.meta.env.VITE_ADMIN_EMAIL`.

### Pitfall 5: AccessDenied page inside providers it can't access
**What goes wrong:** Placing `AccessDenied` render inside `<ThreadProvider>` or `<ChatProvider>` when the user is 403 — those providers assume an authenticated user and will make API calls that also 403.
**How to avoid:** Render `AccessDenied` in `AuthGuard` *before* `ThreadProvider`/`ChatProvider` are mounted (status === 'forbidden' branch in AuthGuard short-circuits the rest).

### Pitfall 6: `login_required` left on any route
**What goes wrong:** A route with `@login_required` instead of `@role_required` allows any authenticated user (without Atlas.User role) through.
**How to avoid:** After replacing all usages, grep for remaining `login_required` decorators on routes (it remains importable but should only be used internally within `role_required`'s logic chain, or removed entirely).

### Pitfall 7: SSE client not checking HTTP status before reading stream
**What goes wrong:** If `useStreamingMessage` opens an SSE connection with `fetch()` and doesn't check `response.ok` before calling `response.body.getReader()`, a 403 response body is read as if it were an SSE stream.
**How to avoid:** Check `if (!response.ok)` after the `await fetch(...)` call and handle 401/403 as auth errors rather than stream errors.

---

## Code Examples

### Backend: `role_required` decorator

```python
# Source: codebase auth.py pattern + official Azure-Samples/msid-add-authnz-python-webapp
import datetime
import functools
import logging
from flask import jsonify, redirect, request, session, url_for

logger = logging.getLogger(__name__)
REQUIRED_ROLE = "Atlas.User"


def role_required(f):
    """Decorator: 401 if unauthenticated, 403 if authenticated without Atlas.User role.
    
    Replaces login_required on all protected routes.
    Logs all 403 denials with UPN, endpoint, and timestamp (AUTH-06 requirement).
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        # Not authenticated
        if not user:
            if request.path.startswith("/api/") or request.path.startswith("/chat/"):
                return jsonify({"error": "authentication_required", "message": "Login required"}), 401
            return redirect(url_for("catch_all", path=""))
        # Authenticated but no role
        if REQUIRED_ROLE not in user.get("roles", []):
            upn = user.get("preferred_username", "unknown")
            logger.warning(
                "403 Forbidden: upn=%s endpoint=%s ts=%s",
                upn, request.path, datetime.datetime.utcnow().isoformat(),
            )
            if request.path.startswith("/api/") or request.path.startswith("/chat/"):
                return jsonify({
                    "error": "forbidden",
                    "message": "Atlas.User role required",
                    "required_role": REQUIRED_ROLE,
                }), 403
            return redirect(url_for("catch_all", path=""))
        return f(*args, **kwargs)
    return decorated_function
```

### Frontend: extended `AuthContext` with `authStatus`

```typescript
// Source: existing AuthContext.tsx + research
type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'forbidden' | 'error';

interface AuthState {
  status: AuthStatus;
  user: User | null;
  error: string | null;
}

interface AuthContextValue extends AuthState {}

// fetchMe() returns discriminated result
export async function fetchMe(): Promise<{ user: User | null; status: 'ok' | 'unauth' | 'forbidden' }> {
  try {
    const res = await fetch('/api/me');
    if (res.status === 401) return { user: null, status: 'unauth' };
    if (res.status === 403) return { user: null, status: 'forbidden' };
    if (!res.ok) throw new Error(`fetchMe failed: ${res.status}`);
    const data = await res.json() as User;
    return { user: data, status: 'ok' };
  } catch {
    throw new Error('Network error checking auth');
  }
}
```

### Frontend: `AuthGuard` in `App.tsx`

```tsx
// Source: existing App.tsx + research
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === 'loading') return <div className="loading">Loading...</div>;
  if (status === 'unauthenticated') {
    window.location.href = '/login';
    return null;
  }
  if (status === 'forbidden') return <AccessDenied />;
  return <>{children}</>;
}
```

### Frontend: `AccessDenied` component skeleton

```tsx
// Source: @fluentui/react-components v9 (already installed) + existing atlas CSS vars
import { Card, Body1, Title3, Button, makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  root: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: tokens.colorNeutralBackground1,
  },
  card: { maxWidth: '480px', width: '100%', padding: tokens.spacingVerticalXXL },
});

export function AccessDenied() {
  const styles = useStyles();
  const adminEmail = import.meta.env.VITE_ADMIN_EMAIL as string ?? '';
  // upn: optional — if 403 response includes it, show it; otherwise omit
  // Copy UPN uses the existing inline-swap pattern from CopyButton.tsx
  ...
}
```

### Config: new env var additions

```python
# chat_app/config.py — add to Config class
ATLAS_ADMIN_EMAIL: str = os.environ.get("ATLAS_ADMIN_EMAIL", "")
```

And in `secrets.py` `load_secrets()` keys list:
```python
"ATLAS_ADMIN_EMAIL",
```

For Vite (frontend build), `VITE_ADMIN_EMAIL` is set in the build environment — not in `config.py`.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `@login_required` on all routes | `@role_required` replaces it | All protected routes enforce role, not just auth |
| `AuthGuard` redirects on any non-user | `AuthGuard` shows `AccessDenied` for 403 | Authenticated-but-unauthorized users get proper UX |
| `fetchMe()` returns `null` or throws | Returns typed `{status, user}` | Frontend can distinguish 401 from 403 |
| `api/me` returns 3 fields | Returns 4 fields (adds `roles`) | Frontend has role info without extra requests |

---

## Open Questions

1. **UPN in 403 response from `/api/me`**
   - What we know: The `role_required` decorator has access to `session["user"]["preferred_username"]` at the time of the 403. It could include it in the JSON body.
   - What's unclear: CONTEXT.md marks "display name + UPN vs UPN only" as Claude's Discretion.
   - Recommendation: Include UPN in the 403 response body as `"upn"` field. The AccessDenied component uses it for the mailto pre-fill and the copy button. Only the UPN (not display name) is strictly needed for the mailto body.

2. **`VITE_ADMIN_EMAIL` vs `/api/config` endpoint**
   - What we know: Vite exposes `VITE_*` env vars at build time. To change the admin email without a rebuild, a `/api/config` endpoint is needed.
   - What's unclear: Whether hot-change-without-rebuild is a real operational requirement.
   - Recommendation: Start with `VITE_ADMIN_EMAIL` (simpler, consistent with other config). Add `/api/config` in a future phase if needed.

3. **`useStreamingMessage` hook 403 handling**
   - What we know: The hook uses `fetch()` and reads the response body as an event stream. If `/chat/stream` returns 403 before streaming starts, the body is JSON not SSE.
   - Recommendation: Add an `if (!response.ok)` check after the `await fetch(...)` before reading the stream. On 401 → redirect to login. On 403 → dispatch an auth error or trigger a full-page reload to show AccessDenied.

---

## Sources

### Primary (HIGH confidence)
- [Microsoft Docs — ID token claims reference](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference) — confirmed `roles` claim format (`Array of strings`), updated 2025-10-02
- [Microsoft Docs — Add app roles and get them from a token](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps) — confirmed assignment flow, group limitation, token inclusion, updated 2024-11-13
- [Azure-Samples/msid-add-authnz-python-webapp](https://github.com/Azure-Samples/msid-add-authnz-python-webapp/blob/main/app.py) — official Python role check pattern using `id_token_claims`
- Codebase: `chat_app/auth.py`, `chat_app/app.py`, `chat_app/chat.py`, `chat_app/conversations.py`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/App.tsx`, `frontend/src/api/me.ts` — live code read directly

### Secondary (MEDIUM confidence)
- [Fluent UI React v9 Component Roadmap](https://github.com/microsoft/fluentui/wiki/Fluent-UI-React-v9-Component-Roadmap) — Card, Button, Body1 all stable in `@fluentui/react-components` v9
- `frontend/package.json` — confirmed `@fluentui/react-components: ^9.73.5` installed

### Tertiary (LOW confidence)
- WebSearch results on Flask-Session filesystem flush — no single authoritative source; session delete-files approach is a documented community pattern but not in official Flask-Session docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in package.json/pyproject.toml
- Backend roles claim access: HIGH — verified against official Microsoft ID token docs and Azure-Samples
- Backend decorator pattern: HIGH — live codebase read, exact existing pattern
- Frontend AuthContext changes: HIGH — live codebase read, straightforward discriminated union
- Fluent 2 AccessDenied components: HIGH — package confirmed installed, component names verified from @fluentui/react-components exports
- SSE 403 approach: HIGH — existing code confirms pattern of returning Response before generator
- Session flush on deploy: MEDIUM — community pattern, not single authoritative source

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable domain — MSAL and Fluent 2 APIs are stable)
