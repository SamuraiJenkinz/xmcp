# Domain Pitfalls — UI/UX Redesign

**Domain:** Enterprise chat app UI redesign (Flask + vanilla JS → Microsoft Copilot aesthetic)
**Project:** Atlas — Marsh McLennan Exchange infrastructure chat
**Milestone:** v1.2 UI/UX overhaul
**Researched:** 2026-03-27
**Confidence:** HIGH — verified against actual codebase, official Flask/MSAL/SSE docs, and deployment specifics

---

## Preface: This Is a Redesign, Not a Rebuild

The single highest-risk posture in a redesign is treating it like a greenfield project. Atlas is in production. Daily users depend on it. Every phase must ship a working app, not a half-migrated one. Pitfalls in this file are specifically scoped to the "existing system that must keep working" constraint.

---

## Critical Pitfalls

Mistakes that cause broken production functionality, authentication failures, or streaming loss.

---

### Pitfall 1: Breaking the SSE Fetch Stream During Frontend Migration

**Severity:** CRITICAL

**What goes wrong:**
The current streaming implementation uses `fetch()` with `ReadableStream` — NOT the `EventSource` API. The JS reads raw SSE text lines manually from the response body (`response.body.getReader()`). If a framework migration wraps the fetch in a component lifecycle that unmounts before the stream completes, or if the abort controller reference is lost, the stream is silently abandoned mid-response. The user sees a truncated message with no error.

**Why it happens:**
React/Vue component unmounting cleans up state. If `currentAbortController` (see `app.js:49`) is stored in local component state and the component re-renders or the route changes, the controller is garbage-collected and the in-flight stream is orphaned. The server continues generating, burning tokens, while the client shows nothing.

Additionally, if a framework introduces its own fetch wrapper or interceptor that buffers the response body before resolving the Promise, SSE breaks entirely — the stream never fires events incrementally.

**Specific risk in this codebase:**
`app.js` manually parses `data: {...}\n\n` lines from a `ReadableStream`. The parser handles: `tool`, `text`, `thread_named`, `done`, and `error` event types. Any new framework abstraction that replaces this reader must re-implement the same 5-type protocol, including the `thread_named` side-effect (updating sidebar thread name without a round-trip).

**Consequences:**
- Streaming appears broken immediately after migration
- Tool panels (Exchange result chips) never render
- Thread auto-naming stops working
- Abort/cancel mid-stream functionality lost
- No error surfaced — just silence

**Prevention:**
- Isolate the SSE read loop in a single module/hook before introducing any framework
- Write an integration test that sends a real `/chat/stream` request and verifies all 5 event types arrive in order
- Do NOT use `EventSource` as a drop-in replacement — `EventSource` is GET-only and does not support POST with a JSON body
- If using React: keep the `AbortController` in a `useRef`, not `useState`, so it survives re-renders without triggering cleanup
- Preserve the `X-Accel-Buffering: no` header requirement — any new proxy layer (Nginx, IIS ARR) must pass this header through

**Warning signs:**
- Chat input submits but no streaming text appears
- Browser DevTools shows the `/chat/stream` response never starts chunking
- `thread_named` events not reflected in sidebar
- Console errors about `ReadableStream` or `body already used`

**Phase that must address it:** Phase 1 of UI milestone — do NOT start framework migration until the SSE reader is isolated and tested in isolation.

---

### Pitfall 2: Flask Session Cookie Breaks Under SPA Navigation Patterns

**Severity:** CRITICAL

**What goes wrong:**
Atlas uses Flask server-side sessions (filesystem via `flask_session`) with a cookie identifying the session. The `@login_required` decorator checks `session.get("user")` on every protected route. The MSAL token cache is stored in the session as a serialized blob (`session["token_cache"]`).

If a frontend framework introduces client-side routing (React Router, Vue Router), the browser navigates without full page reloads. Flask receives no request during navigation, so `session.get("user")` is never re-evaluated. This works fine — until the session expires server-side. Then the user gets a 302 redirect to the splash page, which SPA frameworks handle incorrectly: they may render the Flask HTML response into a `<div>`, causing a broken UI, or silently 302-loop.

**Why it happens:**
SPAs expect APIs to return JSON 401 responses when unauthenticated, not HTML 302 redirects. Flask's `@login_required` currently returns `redirect(url_for("index"))` — an HTML redirect. The SPA's fetch interceptor does not know how to handle this.

**Specific risk in this codebase:**
`auth.py` line 97: `return redirect(url_for("index"))` — this is an HTML redirect, not a JSON 401. The `/chat/stream` endpoint inherits `@login_required`. If the session expires mid-stream, the SSE response body will contain an HTML redirect page, not SSE events. The stream parser will receive malformed data.

**Consequences:**
- Session expiry causes a white screen or broken render in SPA mode
- `/chat/stream` returns HTML 302 instead of SSE on expired session
- Users are silently logged out with no error message
- MSAL token refresh stops working (cache is session-bound)

**Prevention:**
- Keep Flask as the authoritative renderer for the initial page load — do NOT make it a pure API yet
- If introducing any SPA routing, add a `/api/me` endpoint that returns `{"authenticated": true, "user": {...}}` or JSON 401, and poll it on navigation
- Modify `@login_required` to return JSON 401 when the request has `Accept: application/json` (for API calls) vs HTML redirect (for page loads)
- Test session expiry explicitly: set `SESSION_PERMANENT = False` and `PERMANENT_SESSION_LIFETIME = timedelta(seconds=30)` in a dev environment, then verify behavior

**Warning signs:**
- After 30+ minutes of idle, users get a blank white page
- Browser DevTools shows `/chat/stream` returning HTTP 302 with `Content-Type: text/html`
- Console errors about parsing HTML as JSON

**Phase that must address it:** Before any SPA routing is introduced. May be deferred if framework migration is kept shallow (no client-side routing).

---

### Pitfall 3: Waitress + IIS ARR Response Buffering Silently Breaks Streaming

**Severity:** CRITICAL

**What goes wrong:**
Waitress is the WSGI server. On Windows Server with IIS as reverse proxy (common enterprise deployment), IIS Application Request Routing (ARR) buffers responses by default. Buffered responses mean SSE events are held until the buffer fills or the connection closes — users receive no streaming output until the entire response completes, defeating the purpose.

The current code already sets `X-Accel-Buffering: no` (designed for Nginx). This header is ignored by IIS ARR.

**Why it happens:**
IIS ARR's proxy buffering is controlled by `responseBufferLimit` in `applicationRequestRouting` and by the `ARR_DISABLE_SESSION_AFFINITY` and response buffer settings. They default to buffered.

**Specific risk in this codebase:**
If the redesign introduces a build step (Vite, webpack) and static asset serving via IIS directly, the IIS configuration may be modified in a way that accidentally enables ARR buffering for the Flask origin as well.

**Consequences:**
- Streaming appears to work in development (direct Waitress, no proxy) but breaks in production
- Users see blank chat area until the full response is ready, then the entire message appears at once
- Tool panel chips appear all at once at the end, not incrementally

**Prevention:**
- Verify current SSE behavior in the actual deployment environment before starting any redesign phase
- If using IIS ARR: set `<applicationRequestRouting>` with `responseBufferLimit="0"` and `enableDiskCache="false"` for the Flask upstream
- Add an explicit SSE smoke test to the deployment checklist: send a multi-token message and verify first `text` event arrives within 2 seconds
- Document the `X-Accel-Buffering: no` header is for Nginx — add equivalent IIS configuration to deployment docs

**Warning signs:**
- Streaming works in local dev but not on the server
- All tool chips appear simultaneously at the end of a response
- Response arrives as one chunk in browser DevTools Network tab

**Phase that must address it:** Deployment validation in every phase that touches the serving layer.

---

## High Severity Pitfalls

Mistakes that cause visual regressions, auth edge cases, or significant technical debt.

---

### Pitfall 4: CSS Variable Namespace Collision When Introducing a Design System

**Severity:** HIGH

**What goes wrong:**
Atlas currently uses a custom `data-theme` attribute on `<html>` with CSS custom properties for dark/light mode. If Fluent UI, Tailwind, or another design system is layered on top, their CSS variables may share names with existing Atlas variables (e.g., both might define `--color-background`, `--text-primary`, `--border-color`).

The result is partial theming: some components pick up the design system tokens, others pick up Atlas tokens, and dark mode breaks for a subset of elements — often the custom ones like tool panels and streaming cursors.

**Why it happens:**
Developers add a design system's CSS bundle globally, assume dark mode "just works" via the system's theme provider, and don't audit the existing variable namespace. The existing `style.css` has grown organically and uses shorthand variable names without a namespace prefix.

**Specific risk in this codebase:**
`style.css` uses unprefixed variables like `--bg`, `--text`, `--border`. Fluent UI uses `--colorNeutralBackground1`, `--colorNeutralForeground1` — these do not collide. BUT if adopting Tailwind, its CSS reset will override baseline body/html styles that Atlas's dark mode depends on.

**Consequences:**
- Dark mode partially breaks: sidebar stays dark, message area reverts to light
- Tool panel JSON syntax highlighting loses color in dark mode
- Streaming cursor disappears in one theme
- Inconsistent theming frustrates IT engineers who use the app for hours

**Prevention:**
- Namespace all existing CSS variables before adopting any design system: rename `--bg` → `--atlas-bg`, `--text` → `--atlas-text`, etc.
- Run a CSS variable audit: `grep -r "var(--" static/style.css` to enumerate all current variables
- When adding Fluent/Tailwind: use it for new components only; do not replace Atlas variables globally until all components are migrated
- Verify dark mode toggle works end-to-end after every CSS change: toggle 5 times, check tool panels, streaming cursor, sidebar, message bubbles, JSON highlighting

**Warning signs:**
- Dark mode toggle works for some elements but not others
- `data-theme="dark"` on `<html>` but some elements render in light colors
- Browser DevTools computed styles show two conflicting variable definitions for the same property

**Phase that must address it:** Before introducing any design system. Namespace migration should be a standalone PR.

---

### Pitfall 5: Framework Migration Breaks the Inline Profile Card / Photo Proxy

**Severity:** HIGH

**What goes wrong:**
The photo proxy endpoint (`/api/photo/<user_id>`) returns either JPEG bytes or an SVG placeholder with HTTP 200. The current implementation uses `<img src="/api/photo/...">` tags rendered inline. In a framework migration, if components render before the session is established (server-side rendering, or component mounting before auth state is confirmed), the `<img>` request fires before the Flask session cookie is set, returning a 302 redirect to the login page. The browser follows the redirect and renders the login HTML as an image — typically a broken image icon.

**Why it happens:**
Flask's `@login_required` on `photo_proxy` returns a redirect (HTML) when unauthenticated. `<img>` tags do not follow redirect restrictions — they will load whatever URL they are pointed at. If the component mounts optimistically before auth is confirmed, photo requests land on the login page.

**Consequences:**
- Profile cards show broken image icons on first load
- SVG placeholders with user initials stop rendering (regression from current behavior)
- Hard to reproduce in development where sessions are long-lived

**Prevention:**
- Wrap all photo `<img>` renders in an auth guard — do not render profile images until `session.get("user")` is confirmed
- Consider returning HTTP 401 (not 302) from `photo_proxy` when unauthenticated, so `<img>` gets an error it can handle gracefully
- Test photo rendering after a fresh login specifically, not just during an active session

**Warning signs:**
- Broken image icons on colleague mention cards
- Network tab shows photo requests returning 302 to the login page

**Phase that must address it:** Any phase that introduces component-based rendering of user data.

---

### Pitfall 6: Thread List State Drift Between Server and Client

**Severity:** HIGH

**What goes wrong:**
The thread sidebar is populated by a `GET /api/threads` call on page load and then mutated client-side (new thread creates, renames, deletes). The `thread_named` SSE event updates the sidebar title in-place by mutating DOM directly. In a framework migration, if the thread list becomes component state managed by React/Vue, the SSE `thread_named` event must be wired into the state update mechanism — not DOM mutation. If this is missed, sidebar titles never update after auto-naming, leaving "New Chat" as the title forever.

**Why it happens:**
The SSE event handler in `app.js` calls DOM APIs directly. When the DOM is owned by a framework, direct DOM mutation bypasses the virtual DOM diffing and causes state inconsistency: the framework's next render cycle will overwrite the manual DOM change.

**Consequences:**
- Sidebar thread titles never auto-update after the first message
- Users see "New Chat" instead of the auto-generated title
- Thread rename UI may show stale names

**Prevention:**
- Before migrating the sidebar to a component, document every place in `app.js` that mutates the thread list DOM: new thread creation, thread switching, thread deletion, and `thread_named` SSE handling
- Migrate all four mutation paths to state updates in one atomic commit — not one at a time
- Add a test: send a first message to a new thread, verify sidebar title updates within 3 seconds

**Warning signs:**
- Thread titles show "New Chat" permanently after migration
- Creating a new thread in one browser tab doesn't reflect in sidebar state

**Phase that must address it:** Any phase that converts the sidebar to a framework component.

---

### Pitfall 7: Copilot Aesthetic Requires Markdown Rendering — Adds XSS Risk

**Severity:** HIGH

**What goes wrong:**
The current app renders assistant text as plain text nodes (`textNode.textContent += chunk`). Copilot renders responses as rich Markdown (headers, bold, code blocks, bullet lists). Adding a Markdown renderer (marked.js, markdown-it, react-markdown) that uses `innerHTML` instead of `textContent` opens an XSS vector: if the AI generates a response containing `<script>` or malicious HTML, it renders directly.

This matters particularly for Atlas because the LLM sometimes echoes back Exchange data containing angle brackets (e.g., email addresses like `<user@domain.com>` in cmdlet output).

**Why it happens:**
Markdown renderers produce HTML strings. Developers set `innerHTML = renderedMarkdown` without sanitizing. Exchange cmdlet results contain characters that are safe in `textContent` but meaningful in HTML (`<`, `>`, `&`).

**Consequences:**
- Stored XSS if malicious content reaches the Exchange tools and is echoed back
- Exchange cmdlet results with `<user@domain.com>` render as broken HTML tags
- Security audit failure for a financial services enterprise tool

**Prevention:**
- Use a Markdown renderer with built-in HTML sanitization: `marked` + `DOMPurify`, or `react-markdown` with no `dangerouslySetInnerHTML`
- Sanitize the rendered output before inserting: `DOMPurify.sanitize(marked.parse(chunk))`
- For tool panel JSON (Exchange results), continue using `textContent` + the existing `highlightJson()` regex — do NOT run Markdown rendering on raw Exchange JSON
- Add a test case: send a message that returns `<script>alert(1)</script>` from a mock tool and verify it renders safely

**Warning signs:**
- `innerHTML` used without `DOMPurify`
- Email addresses in tool results render as HTML tags (e.g., `@domain.com>` visible but `<user` missing)

**Phase that must address it:** The phase that introduces Markdown rendering. Must be completed in the same phase, not deferred.

---

## Medium Severity Pitfalls

Mistakes that cause technical debt, developer friction, or user annoyance.

---

### Pitfall 8: Single Developer Scope Creep — "While I'm In There" Syndrome

**Severity:** MEDIUM

**What goes wrong:**
A UI redesign naturally surfaces things that could be "improved while touching this area." For a single developer on a production tool, each addition extends the redesign timeline and increases the regression surface. Common additions that derail UI redesigns: adding new features to the chat API, rewriting the auth flow, migrating the database, or adding real-time notifications. Each of these is independently valuable but wrong to bundle with a visual redesign.

**Why it happens:**
The redesign opens every file. Seeing imperfections triggers the fix impulse. There is no second developer to say "that's out of scope."

**Specific risk for Atlas:**
- "While I'm redesigning the sidebar, I'll add thread search" — doubles the sidebar work
- "While I'm styling the chat input, I'll add file attachment" — requires backend changes
- "While I'm adding Tailwind, I'll migrate the auth to JWT" — breaks the entire auth chain
- "While I'm doing dark mode properly, I'll support system preference" — adds complexity to theme persistence

**Consequences:**
- Redesign takes 3x longer than planned
- Multiple half-finished features shipped together
- If something breaks in production, impossible to identify which change caused it
- Momentum lost, redesign abandoned mid-way

**Prevention:**
- Write a "not in this milestone" list before starting and review it weekly
- Each phase PR must touch only CSS/template/JS files unless explicitly scoped otherwise — backend changes require a separate PR
- Use a `.planning/phases/XX-ui-polish/SCOPE-LOCK.md` to document explicit exclusions
- When an improvement idea surfaces during the redesign, log it as a future issue rather than implementing it

**Warning signs:**
- A single PR modifies both Python backend files and CSS/template files
- Sprint scope expands after work begins
- "Just one more thing" appears in PR descriptions

**Phase that must address it:** All phases. Establish the pattern in Phase 1 and hold to it.

---

### Pitfall 9: Dark Mode localStorage Key Conflict After Rename

**Severity:** MEDIUM

**What goes wrong:**
The current theme is persisted to `localStorage` under the key `atlas-theme` (see `app.js:34`). If the redesign renames or replaces the theme storage mechanism (e.g., a design system's theme provider uses a different key), existing users' preferences are lost on first load after deployment. All users revert to the default theme — visible as a flash of the wrong theme on every page load.

**Why it happens:**
Design systems (Fluent UI, Tailwind dark mode) often use their own localStorage keys (`theme`, `color-scheme`, `fluent-theme`). Developers integrate the new system without migrating the old key.

**Consequences:**
- All ~20 production users lose their dark mode preference after deployment
- Flash of unstyled content (FOUC) on page load for users whose preference doesn't match the new default
- User confusion and support requests

**Prevention:**
- Keep `atlas-theme` as the canonical key, or add a one-time migration: `if (localStorage.getItem('atlas-theme')) { migrateToNewKey() }`
- The theme application script must run before the first render — keep it in a `<script>` tag in `base.html` `<head>`, not in a JS bundle
- Test theme persistence explicitly: set dark mode, hard-reload, verify it persists

**Warning signs:**
- After redesign deployment, users report "it switched to light mode"
- FOUC (flash of wrong theme) on page load in production

**Phase that must address it:** Any phase that changes the theme system.

---

### Pitfall 10: Build Tooling (Vite/webpack) Breaks Flask's Static Asset URL Generation

**Severity:** MEDIUM

**What goes wrong:**
Flask uses `url_for('static', filename='app.js')` to generate versioned or fingerprinted static asset URLs. If a build tool outputs assets with content-hash suffixes (`app.a1b2c3d4.js`), Flask's static file serving won't find them unless the manifest is integrated. Conversely, if the build tool outputs `app.js` directly to `static/`, Flask serves it correctly but without cache-busting.

**Why it happens:**
Developers add Vite or webpack for bundling and point the output to `chat_app/static/`. The build works, but either:
- Cache-busted filenames break Flask's `url_for` references in Jinja templates
- Browser caches the old `app.js` after deployment because the filename didn't change

**Specific risk in this codebase:**
`base.html` currently has `<script src="{{ url_for('static', filename='app.js') }}">`. If the build renames the output, this reference 404s silently — the page loads but JS is absent.

**Consequences:**
- After deployment, chat form does nothing (JS absent)
- SSE streaming silently broken
- Hard to notice in testing if the browser serves the cached old bundle

**Prevention:**
- If adding a build tool: configure it to output fixed filenames (`app.js`, `style.css`) without hashing, and use Flask's `SEND_FILE_MAX_AGE_DEFAULT = 0` in development
- OR: integrate the build manifest with Flask using `flask-vite` or a custom Jinja global
- Add a deployment smoke test: hard-reload the page (Ctrl+Shift+R), verify the JS bundle loads with a 200

**Warning signs:**
- Browser DevTools shows `app.js` returning 404
- Chat input submits but nothing happens after deployment
- Console error: `ReferenceError` for functions defined in `app.js`

**Phase that must address it:** The phase that introduces any build tooling.

---

### Pitfall 11: Tailwind Preflight Resets `<details>` and `<summary>` Styling for Tool Panels

**Severity:** MEDIUM

**What goes wrong:**
Tool panel chips use native `<details>` / `<summary>` elements for the collapsible Exchange result panels. Tailwind's Preflight (CSS reset) removes the default disclosure triangle from `<summary>` and resets `<details>` display behavior. After adding Tailwind, all tool panels appear as flat non-collapsible divs — the expand/collapse interaction is gone.

**Why it happens:**
Tailwind Preflight sets `summary { display: list-item }` is removed, and the `::marker` pseudo-element is unstyled. Developers notice the chat works but don't test tool-heavy queries.

**Consequences:**
- Tool panel disclosure triangles disappear
- Exchange JSON results cannot be expanded/collapsed
- IT engineers cannot inspect the raw Exchange data that Atlas fetched

**Prevention:**
- Test with a query that triggers at least 2 tool calls before declaring the Tailwind integration complete
- Explicitly restyle `details` and `summary` elements in the Atlas component layer after Preflight
- Add `list-style: disclosure-closed` to `summary` in the project's Tailwind config or base layer

**Warning signs:**
- Tool chips render as flat text with no expand triangle
- `<details>` elements all appear permanently open or closed

**Phase that must address it:** Any phase that introduces Tailwind or a CSS reset.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| CSS design tokens / variables | Namespace collision with existing `--bg`, `--text` vars (Pitfall 4) | Namespace audit before touching CSS |
| Framework introduction (React/Vue) | SSE stream abandoned on component unmount (Pitfall 1) | Isolate SSE reader as standalone module first |
| SPA client-side routing | Auth session expiry returns HTML redirect into fetch (Pitfall 2) | Add JSON 401 path to `@login_required` |
| Markdown rendering | XSS via Exchange cmdlet output containing angle brackets (Pitfall 7) | Pair renderer with DOMPurify in same PR |
| Build tooling (Vite/webpack) | Flask `url_for` references break on hashed filenames (Pitfall 10) | Fixed output filenames or manifest integration |
| Tailwind adoption | Preflight breaks `<details>`/`<summary>` tool panels (Pitfall 11) | Post-Preflight restyle in same PR |
| Sidebar → component | Thread state drift, `thread_named` SSE no longer updates DOM (Pitfall 6) | Migrate all 4 thread mutation paths atomically |
| Deployment of any phase | IIS ARR response buffering kills SSE in production (Pitfall 3) | Smoke test streaming in actual deployment target |
| Any phase | Scope creep from "while I'm in there" additions (Pitfall 8) | SCOPE-LOCK.md, backend-only PRs stay separate |
| Theme system change | `atlas-theme` localStorage key orphaned, users lose preference (Pitfall 9) | Key migration script in `base.html` head |
| Profile photo rendering | Framework mounts before session confirmed, photo request hits 302 (Pitfall 5) | Auth guard before any photo `<img>` render |

---

## Summary: What to Protect at All Costs

The following are the Atlas features most likely to silently break during a redesign. Treat these as a regression test suite that must pass before any phase ships:

1. **SSE streaming** — send a message, verify first text token appears within 3 seconds
2. **Tool panels** — send "check DAG health", verify chips render with expand/collapse
3. **Thread auto-naming** — send first message to new thread, verify sidebar title updates
4. **Dark mode persistence** — set dark mode, hard-reload, verify it stays dark
5. **Auth redirect** — visit `/chat` without a session, verify you land on splash (not a broken page)
6. **Photo proxy** — verify colleague profile images render (or show initials placeholder, not broken img)
7. **Message cancel** — start a long response, press Escape or Cancel, verify `[response cancelled]` marker appears

---

## Sources

- Flask `stream_with_context` and SSE: reviewed `chat_app/chat.py` directly
- Auth flow: reviewed `chat_app/auth.py` and `flask_session` integration in `chat_app/app.py`
- IIS ARR buffering with SSE: [Microsoft Q&A — SSE on Azure App Service](https://learn.microsoft.com/en-us/answers/questions/5573038/issues-with-sse-(server-side-events)-on-azure-app), [.NET 10 SSE proxy buffering](https://medium.com/codetodeploy/net-10-sse-in-production-the-3-reverse-proxy-defaults-that-make-real-time-not-real-time-9c1a6d1c5622)
- Flask SPA auth patterns: [Session-based Auth with Flask for SPAs](https://testdriven.io/blog/flask-spa-auth/), [Transitioning Flask Jinja2 to React](https://dev.to/usooldatascience/transitioning-from-flask-with-jinja2-to-react-understanding-authentication-and-data-flow-for-4214)
- Fluent UI dark mode tokens: [Fluent UI Web Components design tokens](https://learn.microsoft.com/en-us/fluent-ui/web-components/design-system/design-tokens), [Fluent 2 Design Tokens](https://fluent2.microsoft.design/design-tokens)
- SSE with React/Vue lifecycle: [SSE in React — OneUptime](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view), [useEventSource — VueUse](https://vueuse.org/core/useeventsource/)
- Vanilla JS to React migration: [Migrating to React — Brainhub](https://brainhub.eu/library/migrating-to-react), [From VanillaJS to React](https://www.abelmbula.com/blog/vanillajs-react/)
- Scope creep prevention: [Scope Creep in Design Projects 2026](https://dardesign.io/blog/scope-creep-design-projects-2026)
- Waitress streaming limitations: verified from Waitress GitHub issue and Flask docs
