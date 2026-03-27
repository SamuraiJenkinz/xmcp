# Architecture Patterns: UI/UX Redesign — Frontend Framework Integration

**Project:** Atlas — Exchange Infrastructure Chat App
**Milestone:** Full UI/UX Overhaul (Subsequent Milestone)
**Researched:** 2026-03-27
**Scope:** How a modern frontend framework integrates with the existing Flask/Waitress/Jinja2 backend without disrupting the working API layer.

---

## Executive Summary

The recommended approach for Atlas is the **Flask-served SPA** pattern: Svelte 5 (compiled via Vite) is built to a static bundle, served by Flask from a dedicated `frontend/dist/` directory, and the entire app runs on a single origin (same host, same port). This preserves the session-cookie auth flow intact, eliminates all CORS complexity, and requires zero changes to the Flask API routes or auth blueprint.

The current Jinja2 templates are replaced by the compiled SPA index.html. Flask gets one catch-all route that returns the index.html for any non-API, non-auth path, enabling client-side routing. During development a Vite dev server proxies all `/api/*`, `/chat/*`, `/login`, `/auth/*`, and `/logout` requests back to Flask, keeping cookies on localhost same-origin.

This is the lowest-risk path for a single developer because: (1) the SSE streaming already uses `fetch()` + `ReadableStream` (not `EventSource`), so it ports directly to Svelte with no protocol changes; (2) auth is fully server-side MSAL — the frontend never touches tokens; (3) Flask stays unchanged except for three config lines and one catch-all route.

---

## Current Architecture (Baseline)

```
Browser (on-prem / VPN)
    |
    | HTTPS (self-signed cert, Waitress WSGI)
    v
+--------------------------------------------------+
|  Flask 3.x / Waitress                            |
|  Blueprints:                                     |
|    auth_bp      → /login, /auth/callback,        |
|                   /logout                        |
|    chat_bp      → POST /chat/stream (SSE)        |
|    conversations_bp → /api/threads (CRUD)        |
|  Routes (app.py):                                |
|    GET  /            → splash.html (Jinja2)      |
|    GET  /chat        → chat.html (Jinja2)        |
|    GET  /api/photo/<user_id>  → Graph photo proxy|
|    GET  /api/health           → JSON             |
|  Session: filesystem (flask-session, signed)     |
|  Auth: MSAL ConfidentialClientApplication        |
|  DB: SQLite WAL (threads + messages tables)      |
|  MCP: async subprocess JSON-RPC stdio            |
+--------------------------------------------------+
    |
    | JSON-RPC stdio
    v
+---------------------------+
|  exchange_mcp server      |
|  (Python subprocess)      |
+---------------------------+
```

**Static assets:** `chat_app/static/app.js` (~400 lines vanilla JS), `style.css` (~800 lines), served by Flask.

**Jinja2 data injection:** `chat.html` receives `user`, `display_name`, `last_thread_id` from the `/chat` route. The `last_thread_id` is passed via a `data-last-thread-id` attribute on `.app-layout`. `base.html` injects `session.user.name` into the header.

---

## Integration Options Evaluated

### Option A: Flask-Served SPA (Recommended)

Svelte/Vite builds to `frontend/dist/`. Flask serves this directory as the SPA. Single origin. Auth cookies require no reconfiguration.

**How it works in production:**
- Flask `static_folder` → `frontend/dist/assets/` (hashed JS/CSS bundles)
- Flask catch-all route → returns `frontend/dist/index.html`
- All `/api/*`, `/chat/*`, `/login`, `/auth/*`, `/logout` routes continue as-is
- `flask-session` cookies set with `SameSite=Lax`, `Secure` (already on HTTPS) — unchanged

**How it works in development:**
- Vite dev server runs on `:5173`, Flask on `:5000`
- `vite.config.js` proxy: any path matching `/api/*`, `/chat/*`, `/login`, `/auth/*`, `/logout`, `/static/*` is forwarded to `http://localhost:5000`
- Browser talks to Vite at `:5173` — cookies set by Flask arrive as same-origin because Vite proxy strips the cross-origin boundary
- `credentials: 'include'` on fetch calls handles cookie forwarding through the proxy

**Confidence:** HIGH — this pattern is documented by Flask's official SPA patterns page and confirmed working with Waitress.

---

### Option B: Separate Frontend Server (Not Recommended)

SPA runs on `:5173` or `:3000` in production (e.g., served by Nginx). Flask on `:5000`. Cross-origin in production.

**Problems for Atlas specifically:**
1. `SameSite=Lax` session cookies do not cross origins. Would require `SameSite=None; Secure`, which changes security posture.
2. MSAL auth code flow redirects to `/auth/callback` — the callback lands on Flask, sets session cookie, then must redirect to the frontend origin. This requires tracking the frontend origin in the Flask redirect, adding complexity.
3. CORS middleware (`flask-cors`) must be added and configured for exact origin with `supports_credentials=True`.
4. The `/api/photo/<user_id>` photo proxy would need CORS headers for image responses.
5. On-prem with self-signed cert: two separate HTTPS origins means two separate cert exceptions for users.

**Single-developer cost:** Meaningful — adds CORS config, changes cookie settings, complicates auth callback, adds Nginx config for production.

**Verdict:** Rejected. No benefit for this deployment model.

---

### Option C: Enhanced Vanilla JS (Defer the Framework Decision)

Keep Jinja2 templates and vanilla JS, but rewrite `app.js` as ES modules with a cleaner component model. Add a CSS design system.

**When appropriate:** If UI polish is the primary goal and the team wants zero build tooling risk.

**Problems:**
- No component reactivity — DOM manipulation code grows proportionally with UI complexity
- No TypeScript — harder to maintain as features expand
- CSS-in-JS or scoped styles require manual discipline
- Cannot use modern component libraries (shadcn/svelte, etc.)

**Verdict:** Valid fallback if the framework migration proves too complex, but forfeits the long-term maintainability gains. Not recommended as the primary approach.

---

## Recommended Architecture: Flask-Served Svelte 5 SPA

### Why Svelte 5 Over React and Vue 3

| Criterion | React 18 | Vue 3 | Svelte 5 |
|-----------|----------|-------|----------|
| Bundle size (typical SPA) | ~42KB runtime + app | ~20KB runtime + app | ~1.6KB runtime + app |
| Build tooling | Vite (Create React App deprecated) | Vite | Vite (native) |
| Flask + Vite integration templates | Many | Many | Specific Flask+Svelte5 template exists |
| SSE (fetch/ReadableStream) support | Standard | Standard | Standard |
| Reactivity model | Hooks (learned patterns required) | Composition API (moderate) | Runes — closest to plain JS |
| Single-developer ergonomics | Complex state management | Good | Excellent — minimal boilerplate |
| Ecosystem maturity | Largest | Large | Growing rapidly |

Svelte 5 is recommended for Atlas because: the app is one screen (chat interface), state is simple (threads list, current thread, streaming state), and Svelte's compile-to-vanilla-JS approach produces the smallest output. The developer experience is closest to the existing vanilla JS codebase — migrating from `app.js` to Svelte components is a natural progression rather than a paradigm shift.

React would be the right choice if future staffing required React-familiar developers. Vue 3 is a reasonable alternative if Svelte 5 feels unfamiliar. Either can use the same Flask-served SPA architecture described here.

---

## Component Boundaries

```
App (root Svelte component)
├── Header
│   ├── AppLogo
│   ├── ThemeToggle         (replaces localStorage theme logic from app.js)
│   └── UserInfo + Logout   (receives user from Flask-injected JSON or /api/me)
│
├── Sidebar
│   ├── NewChatButton
│   └── ThreadList
│       └── ThreadItem      (inline rename, delete, active state)
│
└── ChatPane
    ├── MessageList
    │   ├── WelcomeMessage  (example query buttons)
    │   ├── UserMessage
    │   └── AssistantMessage
    │       ├── ThinkingDots
    │       ├── ToolPanel   (collapsible details, JSON highlight)
    │       ├── ProfileCard
    │       ├── SearchResultCards
    │       └── MarkdownRenderer
    │
    └── InputArea
        ├── AutoExpandTextarea
        └── SendButton      (disabled during streaming)
```

**State that crosses component boundaries:**
- `currentThreadId` — owned by App, passed to Sidebar and ChatPane
- `isStreaming` — owned by ChatPane, passed to InputArea
- `user` — fetched once on mount from `/api/me` (new endpoint) or injected via `<script>` tag

---

## Data Flow

```
User types message
    → InputArea emits "submit"
    → ChatPane calls POST /chat/stream
    → Flask chat_bp processes: tool loop → streaming response
    → ChatPane reads ReadableStream (existing SSE protocol unchanged)
    → SSE events dispatched to: ToolPanel, MarkdownRenderer, ThreadList (thread_named)
    → On "done": finalize markdown, refetch /api/threads

User clicks thread
    → ThreadList emits "select"
    → ChatPane calls GET /api/threads/{id}/messages
    → Renders historical messages

User renames thread
    → ThreadItem emits "rename"
    → PATCH /api/threads/{id}
    → ThreadList updates locally

User logs out
    → Header triggers window.location = '/logout'
    → Flask clears session, redirects to splash
```

---

## SSE Streaming Integration

**Key finding:** The existing SSE implementation uses `fetch()` + `ReadableStream.getReader()` — NOT the native `EventSource` API. This is by design because the endpoint is POST (sends `message` and `thread_id` in the JSON body). `EventSource` only supports GET requests.

This means the SSE consumer ports directly to Svelte with zero protocol changes:

```javascript
// Current app.js pattern (works identically in Svelte)
const response = await fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text, thread_id: currentThreadId }),
    signal: abortController.signal
});
const reader = response.body.getReader();
// ... pump loop reads SSE data: lines
```

In Svelte, this lives in a `stream.js` service module. The streaming state (`isStreaming`, abort controller) becomes a Svelte rune or store. The event types (`tool`, `text`, `thread_named`, `done`, `error`) are handled the same way — the only difference is that state mutations trigger reactive UI updates rather than direct DOM manipulation.

**No changes required to `chat.py` or the SSE event protocol.**

---

## Auth Flow Continuity

The MSAL auth code flow is entirely server-side in Flask. The frontend never sees tokens. The SPA simply:

1. On mount, calls `GET /api/me` (new lightweight endpoint) — returns 200 with user JSON or 401
2. If 401 → redirect to `/login` (window.location, not client-side routing)
3. Flask `/login` → Azure AD → `/auth/callback` → sets session cookie → redirects to `/` (which loads SPA)
4. SPA loads, calls `/api/me`, gets user data, renders authenticated UI

**New endpoint needed:** `GET /api/me` — returns `session["user"]` as JSON (name, preferred_username, oid). This is a 5-line Flask route. Replaces Jinja2 template variable injection.

**Session cookie behavior:**
- Existing config: `SESSION_TYPE=filesystem`, `SESSION_USE_SIGNER=True`
- Cookie attributes: Flask default is `SameSite=Lax`, `HttpOnly=True`
- Since SPA is served from the same origin as Flask, `SameSite=Lax` is correct and does not need to change
- `SESSION_COOKIE_SECURE=True` is already correct for the HTTPS on-prem deployment
- No CORS configuration required

**MSAL redirect URI:** The `/auth/callback` route remains unchanged. The callback URL registered in Azure AD Entra (`https://<server>/auth/callback`) does not change.

**Splash page:** The `splash.html` with the "Sign in with Microsoft" button can remain a Jinja2 template served at `/` for unauthenticated users (simplest path), OR it can be replaced by the SPA rendering the login screen conditionally. The simplest migration keeps Flask serving the splash for unauthenticated requests and the SPA for authenticated ones — but a cleaner SPA approach has the SPA always serve the root, with `/api/me` determining render state.

**Recommendation:** Replace splash with SPA-rendered login screen. Avoids the split-template complexity and makes the entire UI consistent.

---

## Build and Serve Strategy

### Directory Structure

```
xmcp/
├── chat_app/             # Flask app (unchanged)
│   ├── static/           # Legacy static (removed after migration)
│   ├── templates/        # Legacy Jinja2 (removed after migration)
│   ├── app.py
│   ├── auth.py
│   ├── chat.py
│   └── ...
│
└── frontend/             # New Svelte/Vite project
    ├── src/
    │   ├── App.svelte
    │   ├── lib/
    │   │   ├── components/
    │   │   └── services/
    │   │       ├── api.js      # /api/threads CRUD
    │   │       └── stream.js   # /chat/stream SSE consumer
    │   └── main.js
    ├── dist/             # Vite build output (gitignored)
    ├── package.json
    └── vite.config.js
```

### Vite Configuration (Development)

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
    plugins: [svelte()],
    server: {
        proxy: {
            '/api': { target: 'http://localhost:5000', changeOrigin: true },
            '/chat': { target: 'http://localhost:5000', changeOrigin: true },
            '/login': { target: 'http://localhost:5000', changeOrigin: true },
            '/auth': { target: 'http://localhost:5000', changeOrigin: true },
            '/logout': { target: 'http://localhost:5000', changeOrigin: true },
            '/static': { target: 'http://localhost:5000', changeOrigin: true },
        }
    },
    build: {
        outDir: '../chat_app/frontend_dist',  // Build directly into Flask static tree
    }
});
```

### Flask Changes for SPA (Production)

```python
# app.py additions — approximately 15 lines

# 1. New /api/me endpoint
@app.route("/api/me")
@login_required
def me():
    return jsonify(session.get("user"))

# 2. Serve SPA static assets
app = Flask(
    __name__,
    static_folder="../frontend_dist/assets",
    static_url_path="/assets",
)

# 3. Catch-all route returns SPA index.html
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa_index(path):
    # Let Flask handle its own routes first; this catch-all is lowest priority
    # because specific routes are registered before it.
    return send_from_directory("../frontend_dist", "index.html")
```

Note: The catch-all must be registered AFTER all blueprints and specific routes, so Flask's URL matching resolves `/api/*`, `/chat/*`, `/login`, `/auth/*`, and `/logout` first.

### Build Integration

```bash
# Development workflow
cd frontend && npm run dev   # Vite dev server on :5173 with Flask proxy
cd chat_app && python -m flask run  # Flask on :5000

# Production build
cd frontend && npm run build  # Outputs to chat_app/frontend_dist/
# Flask/Waitress serves everything from one process as before
```

---

## Migration Strategy

### Phase 1: Parallel Infrastructure (No Visible Change)

1. Scaffold `frontend/` with Vite + Svelte 5
2. Configure Vite proxy to Flask
3. Implement `GET /api/me` in Flask (5-line addition)
4. Create a bare-bones `App.svelte` that calls `/api/me` and renders "authenticated" or "login"
5. Wire the build output into Flask catch-all route (behind a feature flag or config toggle)
6. Verify: cookies work, SSE works, auth round-trip works

**Risk at this phase:** Zero. Original Jinja2 templates still serve in production. The SPA build is only active when explicitly enabled.

### Phase 2: Core Chat Functionality

Migrate in this order (each self-contained, testable before next):

1. **Stream service** (`stream.js`) — port existing `readSSEStream()` and `doSend()` from app.js. Test against live `/chat/stream`. This is the highest-risk piece; isolate it first.
2. **Thread management** — port `fetchThreads()`, `renderThreadList()`, `switchThread()`, `createNewThread()`, `deleteThread()`, `makeRenameHandler()` to ThreadList + ThreadItem components
3. **Message rendering** — port `createMessageEl()`, `appendUserMessage()`, `createAssistantMessage()`, `renderMarkdown()`, tool panel builder, profile card builder, search result cards
4. **Welcome message** — example query buttons
5. **Input area** — auto-expanding textarea, form submit, keyboard shortcuts (Ctrl+Enter, Escape to cancel)
6. **Header** — user info, logout link, theme toggle

**Migrate splash last** (or keep as Jinja2 — it has no dynamic JS, just a link to `/login`).

### Phase 3: UI Polish (The Actual Redesign)

Once the Svelte port is feature-complete and verified against the existing UI behavior, apply the design system changes: layout, typography, colour system, animations, component polish. By this point the component boundaries are established and styling is scoped.

This sequencing is critical: **don't redesign and migrate simultaneously**. Separating the "structural port" from the "visual redesign" phases makes each individually verifiable and reduces rollback scope.

### Rollback Strategy

During Phase 2, Flask can be configured to conditionally serve either the Jinja2 templates or the SPA index.html based on an environment variable. If the SPA has a critical regression, flip the flag. Remove this dual-serving capability after Phase 3 is complete and validated.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: CORS Configuration for Same-Server Deployment

Adding `flask-cors` and configuring cross-origin headers is unnecessary when Flask serves the SPA from the same origin. Adding it anyway introduces security surface and is a signal the architecture is wrong.

### Anti-Pattern 2: JWT/Token Auth for the SPA

Some Flask+SPA tutorials replace session cookies with JWTs because "SPAs need stateless auth." For Atlas, session cookies are correct — the MSAL token is already server-side, the session is short-lived, and the deployment is internal (not a public API). Introducing JWTs would require storing them (localStorage = XSS risk, memory = lost on refresh) and adds significant complexity for no benefit.

### Anti-Pattern 3: Using EventSource for the SSE Endpoint

The existing `/chat/stream` endpoint is POST (because it needs a JSON body with `message` and `thread_id`). `EventSource` only handles GET. The current `fetch()` + `ReadableStream` approach is correct and must be preserved. Do not refactor to GET+EventSource.

### Anti-Pattern 4: Big-Bang Rewrite

Rewriting all Jinja2 templates and all of `app.js` simultaneously before testing any of it against the live Flask backend is how frontend migrations fail. The phased approach (infrastructure → core → polish) limits the blast radius of any given phase.

### Anti-Pattern 5: SvelteKit Instead of Svelte

SvelteKit is a full-stack framework with its own routing, SSR, and server endpoints. For Atlas, Flask IS the server. Using SvelteKit would create a Node.js server layer in front of Flask, complicating auth (two session layers), SSE (SvelteKit's SSE requires its own endpoint patterns), and deployment (two processes). Use plain Svelte 5 with Vite, not SvelteKit.

---

## Scalability Considerations

| Concern | Current (Jinja2 + vanilla JS) | After SPA Migration |
|---------|-------------------------------|---------------------|
| Auth | Unchanged | Unchanged |
| SSE streaming | Unchanged | Unchanged |
| API surface | Unchanged | +1 endpoint (/api/me) |
| Static file serving | Flask serves .js + .css | Flask serves hashed bundles |
| Build complexity | None | npm + Vite build step |
| Deployment | python -m waitress | npm run build then python -m waitress |
| Bundle caching | Manual (filenames static) | Automatic (Vite content hash) |

The largest operational change is adding `npm run build` to the deployment process. This is well-understood and can be scripted in the existing `scripts/` directory.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Flask-served SPA pattern | HIGH | Flask official SPA docs, confirmed working pattern |
| Vite proxy for dev | HIGH | Vite official docs, widely used pattern |
| Session cookie preservation | HIGH | Same-origin = no cookie changes needed |
| SSE via fetch/ReadableStream in Svelte | HIGH | Standard fetch API, framework-agnostic |
| MSAL auth flow unchanged | HIGH | Flask handles all auth; frontend only calls /api/me |
| Svelte 5 with Vite | MEDIUM | Svelte 5 is stable (released Oct 2024); specific Flask+Svelte5 template exists but is not official |
| Migration phasing | MEDIUM | Based on general strangler-fig patterns; Atlas-specific ordering is reasoned but not empirically validated |

---

## Sources

- [Flask Single-Page Applications (official docs)](https://flask.palletsprojects.com/en/stable/patterns/singlepageapplications/)
- [Session-based Auth with Flask for Single Page Apps — TestDriven.io](https://testdriven.io/blog/flask-spa-auth/)
- [Flask + Svelte integration — Medium (Alex Cabrera)](https://cabreraalex.medium.com/svelte-js-flask-combining-svelte-with-a-simple-backend-server-d1bc46190ab9)
- [Flask-Svelte-Template (Svelte 5 + Vite)](https://github.com/martinm07/flask-svelte-template)
- [SvelteKit static adapter + Flask](https://github.com/saas-templates/flask-sveltekit-static)
- [Vite Server Options (proxy configuration)](https://vite.dev/config/server-options)
- [Unbreaking Cookies in Local Dev with Vite Proxy (2025)](https://mattslifebytes.com/2025/03/30/unbreaking-cookies-in-local-dev-with-vite-proxy/)
- [SSE POST fetch ReadableStream vs EventSource — Medium](https://medium.com/@david.richards.tech/sse-server-sent-events-using-a-post-request-without-eventsource-1c0bd6f14425)
- [React vs Vue vs Svelte 2025 comparison — merge.rocks](https://merge.rocks/blog/comparing-front-end-frameworks-for-startups-in-2025-svelte-vs-react-vs-vue)
- [Frontend migration guide — Frontend Mastery](https://frontendmastery.com/posts/frontend-migration-guide/)
- [Cookie Security for Flask — Miguel Grinberg](https://blog.miguelgrinberg.com/post/cookie-security-for-flask-applications)
