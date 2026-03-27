# Technology Stack

**Project:** Exchange Infrastructure MCP Server — Marsh McLennan Companies
**Researched:** 2026-03-19 (original) | Updated: 2026-03-24 (Graph milestone) | Updated: 2026-03-27 (UI/UX milestone — frontend redesign)
**Researcher:** GSD Project Researcher

---

## Research Method & Confidence Note

The 2026-03-27 update was scoped to the frontend redesign milestone only. The existing validated
backend stack (Python/Flask/Waitress/SQLite/MSAL) is unchanged and not re-researched here.

Research sources for this update:
1. Existing codebase inspection (`app.js`, `style.css`, `chat.py`, `app.py`, templates) — HIGH confidence for current implementation.
2. Design brief (`designux.md`) — HIGH confidence for component inventory and token system.
3. WebSearch (with 2026 year qualifier) — MEDIUM confidence, cross-verified where possible.
4. Official npm registry results (via WebSearch) — MEDIUM-HIGH for current versions.
5. Training data (cutoff August 2025) — flagged where used without external verification.

---

## Sections in This File

The original sections (Layers 1–4) covering MCP server, Flask, MSAL, Graph, and AI are
preserved below unchanged. **New Section 5 covers the frontend stack for the UI/UX milestone.**

---

## Recommended Stack

### Layer 1: MCP Server (Python)

| Technology | Min Version | Recommended Pin | Purpose | Why |
|------------|-------------|-----------------|---------|-----|
| Python | 3.11 | 3.12 | Runtime | 3.11 mandated by project; 3.12 offers free-threaded perf improvements and `asyncio` refinements. Do not use 3.13 yet — `pywinpty` and some WinRM libs lag. |
| `mcp` (Anthropic SDK) | 1.0.0 | ≥1.9.x | MCP protocol: tool registration, stdio transport, schema serialization | The `mcp` package is the official Anthropic Python SDK. 1.0.0 stable released late 2024; the architecture doc pins `>=1.0.0`. Verify current release at `https://pypi.org/project/mcp/` before pinning. |
| `anyio` | 4.x | ≥4.3.0 | Async runtime compatibility layer required by `mcp` | `mcp` SDK depends on `anyio`; pinning explicitly prevents transitive version drift on Windows. |
| `pydantic` | v2 | ≥2.5.0 | Data validation for tool input schemas | `mcp` SDK v1.x uses Pydantic v2 internally. Explicitly pinning avoids install-time resolution conflicts. Do NOT use Pydantic v1 — it is EOL. |

**Confidence:** MEDIUM. The `mcp>=1.0.0` floor is HIGH (project-authored). The recommendation
to verify current patch level before pinning is correct discipline — the package moves fast.

**What NOT to use:**
- `fastmcp` (third-party wrapper) — adds abstraction over the official SDK with no benefit for
  15 well-defined tools. The official `mcp` SDK is now mature enough that wrappers are unnecessary.
- `mcp` SDK versions below 1.0.0 — pre-1.0 had breaking protocol changes.

---

### Layer 2: Web Framework (Chat Application)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Flask** | ≥3.0 | HTTP server, routing, session management, Jinja2 templating | Project constraint specifies Flask/FastAPI + Jinja2. Flask is the correct choice here (see rationale below). |
| **Jinja2** | ≥3.1 | Server-side HTML templating | Bundled with Flask 3.x. No separate pin needed unless you need a Jinja2-only feature. |
| **Flask-Session** | ≥0.8 | Server-side session storage (filesystem or Redis) | Browser cookies cannot hold conversation history. Flask-Session stores it server-side. Required for multi-thread conversation history. |
| **Werkzeug** | ≥3.0 | WSGI utilities — ships with Flask 3.x | No separate pin. Locked to Flask version. |
| **Waitress** | ≥3.0 | WSGI production server for Windows | Gunicorn does NOT run on Windows. Waitress is the production WSGI server for Windows deployments. This is non-negotiable given the on-prem Windows constraint. |

**Flask vs FastAPI decision rationale:**

Choose **Flask** because:

1. **Jinja2 server-side rendering is idiomatic Flask.** FastAPI was designed for JSON API services.
   Using FastAPI with Jinja2/HTML responses (via `Jinja2Templates`) works but is non-standard
   and produces a mismatched mental model. The project is NOT building a React SPA — it's building
   an internal tool with HTML pages rendered server-side. Flask is the correct fit.

2. **Session management is simpler in Flask.** `flask.session` and `Flask-Session` are
   first-class. FastAPI requires `starlette` session middleware that is less battle-tested
   for this pattern.

3. **SSO / MSAL integration libraries are more mature for Flask.** `msal` + `Flask` has
   established patterns (`flask-dance`, direct MSAL usage) that are well-documented.
   FastAPI MSAL integration requires more manual wiring.

4. **Windows deployment.** Both run under Waitress (WSGI) on Windows, but Flask's synchronous
   model is simpler to reason about on a domain-joined Windows server. FastAPI's async model
   provides benefits primarily when you have many concurrent I/O-bound requests — this
   internal tool will not be under that load.

**What NOT to use:**
- **Gunicorn** — Unix-only, will not run on Windows without WSL. Use Waitress.
- **uvicorn** — async ASGI server for FastAPI/Starlette. Not appropriate for Flask unless
  you add the `asgiref` shim, which adds unnecessary complexity.
- **Django** — wildly over-engineered for an internal single-purpose tool. No ORM needed.
  No admin interface needed. Adds 40+ packages of surface area.

**Confidence:** HIGH. Windows-specific WSGI constraint eliminates Gunicorn. Flask + Jinja2 +
Waitress is the correct triad for this deployment model.

---

### Layer 3: Azure AD / Entra ID SSO

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **msal** (Microsoft Authentication Library) | ≥1.35.1 | Azure AD / Entra ID OAuth 2.0 / OIDC token acquisition | Official Microsoft Python library. The only supported, Microsoft-maintained path for Entra ID SSO from Python. Current stable: 1.35.1 (released 2026-03-04, verified on PyPI). |
| **Flask-Login** | ≥0.6.3 | Session-based login state management after MSAL token validation | Separates "who is authenticated" from "how they authenticated." Integrates cleanly with MSAL for post-callback session establishment. |

**SSO flow for this deployment:**

```
Browser → Flask app → Redirect to Azure AD /authorize
         → User authenticates with MMC Entra ID (MFA, existing SSO session)
         → Azure AD redirects back with auth code
         → Flask app calls MSAL /token endpoint (auth code exchange)
         → MSAL returns access token + ID token
         → Flask-Login establishes session
         → Subsequent requests: validate session, no re-auth
```

**Key MSAL configuration for MMC:**
- Flow: Authorization Code Flow (NOT Client Credentials — requires user identity for
  Kerberos delegation chain to work)
- Scopes: `openid`, `profile`, `email`, plus `User.Read` from Microsoft Graph for
  display name and UPN
- Token cache: in-memory per session (Flask-Session stores the MSAL token cache
  alongside conversation history)
- Tenant: MMC's Entra ID tenant — `AZURE_TENANT_ID` env var
- Client: Registered app in MMC Entra ID — `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET`

**What NOT to use:**
- `flask-azure-ad` — third-party, unmaintained, do not use.
- `authlib` — capable library but adds a dependency layer over MSAL with no benefit
  when MSAL itself is straightforward and Microsoft-maintained.
- `python-jose` for manual JWT validation — unnecessary when MSAL handles token
  validation internally.

**Confidence:** HIGH for MSAL as the correct library. Current pinned version is 1.35.1
(verified against PyPI 2026-03-24).

---

### Layer 3a: Microsoft Graph API Client (Graph Milestone)

**Decision: Use `msal` + `requests` directly. Do NOT add `msgraph-sdk`.**

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **msal** | ≥1.35.1 (already pinned) | Token acquisition via client credentials flow | `ConfidentialClientApplication.acquire_token_for_client()` is the correct pattern for application-identity Graph calls. No new package needed. |
| **requests** | ≥2.32 (transitive via msal) | HTTP client for Graph REST calls | `requests` is already installed as a transitive dependency of `msal` (verified in the project lockfile: msal 1.35.1 pulls requests 2.32.5). Zero new install cost. |

**Rationale for NOT using `msgraph-sdk`:**

The official Microsoft Graph Python SDK (`msgraph-sdk`, current v1.55.0 as of 2026-02-20) is a
large package. It introduces these dependencies that are not otherwise in this project:

- `azure-identity` — Microsoft's Azure credential library (duplicates MSAL's role)
- `microsoft-kiota-abstractions`, `microsoft-kiota-authentication-azure`,
  `microsoft-kiota-http`, `microsoft-kiota-serialization-json`,
  `microsoft-kiota-serialization-text` — five Kiota packages for the generated client
- `httpx` — a second HTTP client (the project already has the requests-based MSAL path)

For **two Graph endpoints** (`GET /users?$search=...` and `GET /users/{id}/photo/$value`),
the `msgraph-sdk` dependency tree is engineering overhead with no benefit. The Graph API is
a straightforward JSON REST API. Raw `requests` calls are clearer, simpler to debug, and
require no additional packages.

---

### Layer 4: AI / LLM Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **openai** (Python SDK) | ≥1.60 | Azure OpenAI gpt-4o-mini-128k API client | Project constraint. Azure OpenAI endpoint requires the official `openai` Python SDK with `AzureOpenAI` client class. |

**Confidence:** HIGH. Project constraint.

---

### Layer 5: Frontend Stack (UI/UX Redesign Milestone — NEW)

This section covers the frontend-only question: what framework, CSS approach, build tooling,
and animation library to use when redesigning the UI to achieve a Microsoft Copilot-style
aesthetic.

---

#### 5a. Architecture Decision: Hybrid SPA, Not Full SPA

**Decision: Keep Flask/Jinja2 for page routing and authentication. Build chat UI as a
component-isolated React app mounted inside a Flask-rendered shell.**

**Do NOT do a full SPA migration.** Reasons:

1. **Auth is Jinja2-native.** The splash page (`splash.html`), Azure AD redirect, and the
   session-gated `/chat` route are already correct and working. A full SPA would require
   re-implementing MSAL's auth code flow in JavaScript with `@azure/msal-browser` — an
   entirely separate integration surface. This gains nothing for an on-prem internal tool.

2. **The chat page is a single route.** There is one protected page (`/chat`) and one
   unprotected page (`/` splash). React Router is not needed. Serving the SPA shell from
   Flask's `render_template("chat.html", ...)` passes server-side data (user display name,
   last thread ID) down as props — a clean, proven pattern with zero additional complexity.

3. **Photo proxy is server-side.** The `/user-photo/<user_id>` route proxies Graph API
   images through Flask with in-memory TTL caching. This stays unchanged. The React
   frontend calls it as a normal image `src` URL.

4. **SSE streaming stays as-is on the server.** The `POST /chat/stream` endpoint with
   `text/event-stream` response is already implemented and working. React consumes it
   identically to how current vanilla JS does — via the Fetch API with a `ReadableStream`
   reader. No changes to `chat.py` are required.

**Integration pattern:**

```
Flask renders chat.html (Jinja2)
  └─ Injects: user display name, last_thread_id as data attributes on #app div
  └─ Loads: /static/dist/bundle.js (Vite-built React)

React mounts on #app div
  └─ Reads user/thread props from data attributes
  └─ All API calls: /api/threads/*, /chat/stream, /user-photo/*
  └─ All routes: Flask handles, React never uses React Router
```

---

#### 5b. Frontend Framework: React 19

**Recommendation: React 19 (current: 19.2)**

**Do NOT use Vue 3, Svelte 5, or enhanced vanilla JS for this milestone.**

**Why React wins for this project:**

1. **Fluent UI v9 is React-only from Microsoft.** The `@fluentui/react-components` package
   (current: v9.73.5, published daily as of March 2026) is the official Microsoft Fluent UI
   v9 component library. It is React-only. There is no official Fluent UI v9 for Vue or
   Svelte. This single fact makes React the only framework where you get Microsoft-authentic
   Copilot-style UI components without building them yourself.

2. **Microsoft ships a Copilot chat package for React.** `@fluentui-copilot/react-copilot-chat`
   (v0.13.x, published within the last 30 days as of March 2026) is Microsoft's own React
   package for building Copilot-style chat experiences. It is built on Fluent UI v9 and
   provides message bubbles, chat containers, and loading states that match the Copilot
   aesthetic out of the box. This directly addresses the design brief.

3. **shadcn/ui chat components.** Microsoft's `@fluentui-copilot` packages may be too
   opinionated for Atlas's custom tool panels and profile cards. shadcn/ui (the dominant
   React copy-paste component ecosystem in 2026) has AI-native chat components that work
   with Tailwind and can be combined with Fluent tokens. This provides a fallback if
   Fluent's chat package doesn't fit the exact Atlas component model.

4. **SSE streaming is fully compatible.** React consumes SSE the same way vanilla JS does:
   `fetch('/chat/stream', { method: 'POST', body: ... })` + `ReadableStream` reader.
   No framework-level SSE complications. The existing `readSSEStream` function logic
   migrates directly into a React hook.

5. **Ecosystem depth for single developer.** React has the largest ecosystem of any frontend
   framework. For a single developer, this means: more StackOverflow answers, more library
   choices, more shadcn/ui components to copy-paste, and more AI coding assistant training
   data. Vue and Svelte are excellent but the depth asymmetry is real at 1-developer scale.

**Why NOT Vue 3:**
- No official Microsoft Fluent UI v9 for Vue. Vue-specific Fluent libraries (`VFluent3`,
  `Vuent`) are community projects with limited component sets and no connection to the
  official Microsoft design token system. Building a "Microsoft Copilot style" UI without
  official Fluent components means doing all token/component work manually.
- The `@fluentui/web-components` package (Microsoft's Web Components version) works in
  Vue but is designed for simpler integrations and has fewer chat-specific components.
- VueUse provides `useEventSource` composable for SSE — SSE is not a blocker for Vue,
  but the Fluent gap is significant.

**Why NOT Svelte 5:**
- `fluent-svelte` and `svelte-fui` are the only Svelte Fluent options. Both are community
  projects with partial component coverage. `fluent-svelte` targets WinUI/desktop aesthetics,
  not the modern web Copilot look. Neither is maintained by Microsoft.
- Svelte 5's Runes system is a paradigm shift from Svelte 4. While the framework is
  production-ready (used at NYT, IKEA), enterprise teams adopting it in 2026 are primarily
  doing so for new greenfield apps. Migrating to Svelte while simultaneously redesigning
  complex UI is doubled cognitive load for one developer.
- Job market and AI coding assistant training data are significantly thinner for Svelte.
  Practical productivity impact for one developer matters here.

**Why NOT enhanced vanilla JS:**
- The current app is already 1,012 lines of vanilla JS managing stateful UI: thread
  selection, streaming cursor, tool panel expansion, inline profile cards, copy buttons.
  This code works but is already showing signs of complexity that belong in a component
  model (duplicated DOM manipulation logic, manual event delegation patterns).
- A "Copilot aesthetic" means rich micro-animations, hover states, transitions, and
  multi-state loading indicators. Building these in vanilla JS without a component model
  creates unmaintainable CSS/JS coupling.
- The key failure mode: vanilla JS scales poorly when new features are added. The
  upcoming UI phase will add new component types. Each new feature in vanilla JS
  means more global state, more event listener management, more DOM bookkeeping.

**React version choice: React 19.2**

React 19.2 is current (October 2025). Use React 19 for:
- New `use()` hook and Actions API (simplifies async state for streaming)
- Automatic memoization (React Compiler, opt-in)
- Better TypeScript inference

Do NOT use React Server Components (RSC) or Next.js — this is not a Node.js server.
Flask is the server. React runs client-side only.

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^19.2.0 | UI runtime |
| `react-dom` | ^19.2.0 | DOM renderer |
| `typescript` | ^5.5.x | Type safety |
| `@types/react` | ^19.x | React TypeScript types |
| `@types/react-dom` | ^19.x | DOM types |

**Confidence:** HIGH for React over Vue/Svelte (Fluent UI v9 is React-only from Microsoft —
verified via WebSearch against npm registry). MEDIUM for specific React 19 sub-version
(19.2 is current as of October 2025 per WebSearch; patch version may have advanced).

---

#### 5c. UI Component Library: Fluent UI v9 + shadcn/ui (hybrid)

**Recommendation: Use Fluent UI v9 for design tokens and structural components.
Use shadcn/ui for chat-specific and complex interactive components.**

**Rationale for the hybrid:**

Fluent UI v9 (`@fluentui/react-components`, v9.73.5) provides:
- Microsoft-authentic design tokens (colors, typography, spacing, shadows)
- `FluentProvider` + `webLightTheme`/`webDarkTheme` for theme switching
- Core UI primitives: Button, Input, Tooltip, Badge, Avatar, Spinner, Toast, Divider, Card
- The `makeStyles` / `mergeStyles` API for consuming Fluent tokens in custom components

shadcn/ui provides:
- Chat-specific layout components not in Fluent v9 (message lists, chat bubbles, streaming states)
- AI-native components tuned to match ChatGPT/Copilot UX patterns
- Copy-paste philosophy — no runtime library, no version lock-in
- Works with Tailwind CSS v4 tokens that can be mapped to Fluent design values

**The `@fluentui-copilot/react-copilot-chat` option:**
Microsoft publishes `@fluentui-copilot/react-copilot-chat` (v0.13.x) which provides
Copilot-style message bubbles and chat containers. This package is actively maintained
(published within 30 days as of March 2026). However, it is designed for Microsoft's own
Copilot products and may be opinionated about message structure and theming in ways that
conflict with Atlas's tool panels and profile cards.

**Recommendation:** Evaluate `@fluentui-copilot/react-copilot-chat` first during the
initial implementation phase. If it does not accommodate the tool panel / profile card
component model cleanly, fall back to shadcn/ui chat components styled with Fluent tokens.
Do not try to use both simultaneously — pick one for the chat container.

| Package | Version | Purpose |
|---------|---------|---------|
| `@fluentui/react-components` | ^9.73.5 | Fluent UI v9 core components + theming |
| `@fluentui/react-icons` | ^2.x | Microsoft Fluent icons (Copilot, chat, UI icons) |
| shadcn/ui components (copy-paste) | n/a | Chat bubbles, sidebar, command palette |

**What NOT to add:**
- `@fluentui/react` (v8) — this is the legacy Fluent v8 library. Do not mix v8 and v9.
  v8 uses a completely different token system. v9 is the current standard.
- `@fluentui/react-northstar` — EOL as of July 2025. Do not use.
- `fluent-react` (any third-party) — check package provenance; unofficial Fluent packages
  exist and some are abandoned.

**Confidence:** HIGH for `@fluentui/react-components` v9 as the correct package (verified
via npm WebSearch, version 9.73.5 published daily). MEDIUM for Copilot-specific packages
(actively maintained but intended for Microsoft's own products — fitness for Atlas
requires hands-on evaluation).

---

#### 5d. CSS Approach: Tailwind CSS v4 + CSS Custom Properties (design tokens)

**Recommendation: Tailwind CSS v4 as the utility layer. CSS custom properties for
Atlas-specific design tokens. Do NOT use styled-components or CSS Modules.**

**Rationale:**

The Atlas design brief in `designux.md` already defines a complete token system
(30+ CSS custom properties covering colors, typography, spacing, shadows). This token
system is the single source of truth for dark/light mode switching. The migration must
preserve and extend this system, not replace it.

Tailwind CSS v4 (released January 2026, verified via WebSearch) integrates with CSS custom
properties natively via the `@theme` directive. You define tokens once in CSS, Tailwind
generates utility classes from them, and they are available at runtime for dark mode
switching. This eliminates the mismatch between Tailwind's `dark:` utilities and a
token-based dark mode system.

Tailwind v4 changes that matter:
- No `tailwind.config.js` — configuration is CSS-first via `@import "tailwindcss"` + `@theme`
- `dark:` variant defaults to `prefers-color-scheme` (OS preference)
- Manual dark mode toggle uses `@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *))`
- 5x faster full builds, 100x faster incremental — development experience improvement

**CSS approach for Atlas:**

```css
/* tokens.css — preserve existing designux.md tokens */
@import "tailwindcss";

@theme {
  --color-brand: #2563eb;
  --color-surface: #ffffff;
  /* ... all Atlas tokens */
}

@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *)) {
  --color-brand: #3b82f6;
  --color-surface: #1a1d27;
  /* ... dark mode overrides */
}
```

This preserves every existing design decision from `designux.md` while making them
Tailwind-aware.

**Why NOT styled-components:**
- Zero-runtime CSS-in-JS is the 2026 direction (Panda CSS, Vanilla Extract, Tailwind).
  styled-components has runtime overhead: CSS is injected via JavaScript at render time.
  For a streaming chat app with frequent DOM updates, this matters.
- styled-components v6 dropped React 18 compatibility changes and requires explicit
  migration. With React 19, compatibility is unverified at HIGH confidence.
- For one developer, Tailwind utility classes are faster to write and easier to audit
  than styled-components template literals.

**Why NOT CSS Modules:**
- CSS Modules are an excellent choice for large teams preventing class name collisions.
  For a single developer on a focused internal tool, the file-per-component overhead
  adds friction without solving a real problem.
- CSS Modules cannot consume Fluent UI v9's `makeStyles` token system without extra wiring.
  The Tailwind + CSS custom properties approach is simpler to integrate with Fluent.

**Why NOT vanilla CSS (only):**
- Maintaining a 1,179-line CSS file with manual utility classes is already approaching
  the complexity ceiling. The redesign will add more components. Tailwind's utility model
  prevents that file from growing further.
- Responsive utilities (`md:`, `lg:`) and state variants (`hover:`, `focus:`, `group-hover:`)
  in Tailwind replace dozens of hand-crafted CSS rules.

| Package | Version | Purpose |
|---------|---------|---------|
| `tailwindcss` | ^4.0.x | Utility CSS layer |
| `@tailwindcss/vite` | ^4.0.x | Vite plugin for Tailwind v4 |

**Confidence:** HIGH for Tailwind v4 as the correct approach (released and stable as of
January 2026, verified via WebSearch). MEDIUM for exact version numbers — verify against
npm before pinning.

---

#### 5e. Build Tooling: Vite 6

**Recommendation: Vite 6 (current as of March 2026). Use the `@vitejs/plugin-react-swc`
plugin for SWC-based transformation (faster than Babel).**

**Why Vite:**
- Vite is the de facto standard for React development in 2026. Create React App is
  unmaintained. Webpack is an option only if the team has existing webpack expertise or
  complex multi-entry requirements — neither applies here.
- Vite's Rollup-based production build produces smaller bundles than webpack for this
  use case.
- Vite development server starts in milliseconds (compared to webpack's seconds). For
  daily development, this matters more than theoretical bundle differences.
- Flask + Vite integration is well-documented (multiple tutorials, `flask-vite` PyPI
  package, direct manifest-based approach). The proxy pattern — Vite dev server proxies
  API calls to Flask during development — is the standard approach.

**Flask + Vite integration pattern:**

Development (Vite dev server + Flask API server running in parallel):
```javascript
// vite.config.ts
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/chat': 'http://localhost:5000',
      '/login': 'http://localhost:5000',
      '/user-photo': 'http://localhost:5000',
    }
  }
}
```

Production (Flask serves Vite's built output):
```python
# app.py — Flask serves /static/dist/* built by Vite
# chat.html template loads /static/dist/assets/index-[hash].js
# A catch-all route is NOT needed — Atlas has a single /chat route, not a multi-route SPA
```

The simplest production pattern: Vite builds to `chat_app/static/dist/`. Flask's
existing static file serving handles it. The `chat.html` Jinja2 template references
the built asset via a manifest lookup or a fixed output filename.

**esbuild vs Vite:**
esbuild alone is faster but lacks Vite's plugin ecosystem, HMR, and React Fast Refresh.
For a component-heavy React app, Vite's DX advantages outweigh esbuild's marginal build
speed improvements. esbuild is Vite's underlying transformer — you get its speed inside Vite.

| Package | Version | Purpose |
|---------|---------|---------|
| `vite` | ^6.x | Build tool + dev server |
| `@vitejs/plugin-react-swc` | ^3.x | React/JSX transform via SWC (faster than Babel) |

**Confidence:** MEDIUM-HIGH. Vite 6 current status verified via WebSearch (tutorials and
documentation reference Vite 6 in early 2026). Exact version requires npm verification.

---

#### 5f. Animation Library: Motion (formerly Framer Motion)

**Recommendation: `motion` package (formerly `framer-motion`, rebranded in 2025),
version ^12.x. Import from `motion/react`.**

**Why Motion:**
- The Atlas design brief specifies micro-animations: thinking dots (bouncing), streaming
  cursor (blinking), tool spinner (spinning border), collapsible panel transitions,
  message appearance. These are exactly the animations Motion handles with declarative APIs.
- Motion (formerly Framer Motion) rebranded in 2025 to become framework-agnostic.
  The package name changed from `framer-motion` to `motion`. Import path changed from
  `framer-motion` to `motion/react`. The API is identical.
- Current version: 12.37.0 (verified via WebSearch, March 2026). Over 30M monthly npm downloads.
- `AnimatePresence` handles enter/exit animations for message appearance — critical for
  the streaming effect where new messages appear.
- `layout` prop handles sidebar resize animations with zero manual positioning code.
- `motion.div` with `variants` replaces the current CSS keyframe animations for
  thinking dots and tool spinner.

**Why NOT GSAP:**
- GSAP requires imperative `ref`-based API in React. For a component-driven UI, Motion's
  declarative approach is significantly simpler.
- GSAP's license for commercial use requires a paid license for for-profit products.
  Marsh McLennan is a commercial entity. Motion is MIT-licensed.

**Why NOT CSS-only animations:**
- CSS animations handle simple looping effects (thinking dots, streaming cursor) well,
  but enter/exit animations for dynamically mounted React components require JavaScript
  coordination. AnimatePresence handles this; CSS cannot.
- Smooth layout transitions when the sidebar collapses or thread list grows require
  JavaScript measurement. Motion's layout animations handle this automatically.

**AutoAnimate consideration:**
`@formkit/auto-animate` adds enter/exit animations to DOM changes with zero config.
It is worth evaluating for the thread list sidebar where items are added/removed. However,
it does not handle the streaming cursor, thinking dots, or custom micro-animations.
Motion is required anyway — avoid adding a second animation library.

| Package | Version | Purpose |
|---------|---------|---------|
| `motion` | ^12.x | Animation library (formerly framer-motion) |

Import: `import { motion, AnimatePresence } from 'motion/react'`

**Confidence:** HIGH for `motion` as the correct package (rebranding verified via WebSearch,
version 12.37.0 confirmed). MEDIUM for version pin — verify on npm before pinning.

---

#### 5g. Syntax Highlighting: Prism.js

**Recommendation: Prism.js for JSON syntax highlighting in tool panels.**

The Atlas tool panels display JSON (parameters sent to Exchange tools, raw Exchange results).
The current implementation uses custom CSS for Catppuccin-palette highlighting. The redesign
should use a maintained library.

**Why Prism.js over highlight.js:**
- Prism's ~2KB core + language-specific modules means you load only the JSON grammar.
  highlight.js loads more code by default.
- Prism's theming system maps to CSS custom properties cleanly — the Catppuccin palette
  can be expressed as a Prism theme that inherits from Atlas's token system.
- Prism renders 30% more tokens than highlight.js for the same input, but JSON output
  from Exchange APIs is typically <5KB per panel — the difference is imperceptible.

**Alternative: Shiki** (MEDIUM confidence recommendation)
Shiki is a newer syntax highlighter (used by Vitepress, Astro) that uses TextMate grammars
for higher fidelity highlighting. It is server-rendered or generates static HTML. For
React client-side use, Shiki works but adds complexity (async grammar loading, WASM).
For this use case (small JSON blobs, custom Catppuccin theme), Prism is simpler.

| Package | Version | Purpose |
|---------|---------|---------|
| `prismjs` | ^1.29.x | JSON syntax highlighting in tool panels |
| `@types/prismjs` | ^1.26.x | TypeScript types |

**Confidence:** MEDIUM. Prism.js is the pragmatic choice for this use case. Shiki is a
viable alternative worth evaluating during implementation.

---

#### 5h. Supporting Utilities

Small libraries that address specific Atlas requirements:

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `lucide-react` | ^0.400.x | Icon library | Fluent Icons via `@fluentui/react-icons` covers Microsoft-specific icons. Lucide covers generic UI icons (copy, trash, chevron, etc.) with consistent stroke style. Both libraries coexist cleanly. |
| `clsx` | ^2.x | Conditional className utility | Replaces manual string concatenation for conditional CSS classes. 300 bytes. Used pervasively in shadcn/ui components. |
| `tailwind-merge` | ^2.x | Merge Tailwind classes without conflicts | Prevents Tailwind class conflicts when combining base + variant classes. Required for shadcn/ui components. |

**What NOT to add:**
- **React Query / TanStack Query** — The app's API surface is small: thread CRUD
  (`/api/threads/*`) and the SSE stream. React's `useEffect` + `fetch` is sufficient.
  Adding React Query for 4 API endpoints is over-engineering.
- **Zustand / Redux** — State is localized: thread list, active thread, streaming state.
  React's `useState` + `useReducer` + Context API handles this without a state management
  library.
- **React Router** — Not needed. Flask handles all routing. Atlas is a single-page chat
  view, not a multi-route SPA.
- **Axios** — `fetch` is sufficient and built into the browser. No additional HTTP client
  is needed.
- **date-fns / dayjs** — Thread timestamps are displayed as relative time ("2 hours ago").
  JavaScript's `Intl.RelativeTimeFormat` handles this natively in modern browsers with
  no library required.

**Confidence:** HIGH for the "what not to add" list (based on direct app surface analysis).
MEDIUM for lucide-react version (verify on npm).

---

## Full Installation Reference (UI/UX Milestone)

### npm packages to install (production dependencies)

```bash
npm install react@^19.2.0 react-dom@^19.2.0 \
  @fluentui/react-components@^9 \
  @fluentui/react-icons@^2 \
  motion@^12 \
  prismjs@^1.29 \
  clsx@^2 \
  tailwind-merge@^2 \
  lucide-react@^0.400
```

### npm packages to install (dev dependencies)

```bash
npm install -D \
  typescript@^5.5 \
  @types/react@^19 \
  @types/react-dom@^19 \
  @types/prismjs@^1.26 \
  vite@^6 \
  @vitejs/plugin-react-swc@^3 \
  @tailwindcss/vite@^4 \
  tailwindcss@^4
```

### Total dependency footprint assessment

Estimated gzipped bundle for Atlas chat app:
- React 19 runtime: ~45KB gz
- Fluent UI v9 (tree-shaken to used components): ~80-120KB gz
- Motion (react subset): ~35KB gz
- Tailwind (purged): ~10-20KB gz
- App code + Prism + utilities: ~30-50KB gz

**Estimated total: ~200-270KB gz.** This is well within acceptable range for an internal
desktop-only enterprise tool (no mobile requirement, corporate network, 1080p-1440p target).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Framework | React 19 | Vue 3 | No official Fluent UI v9 for Vue; community Vue Fluent libraries are partial and unmaintained |
| Framework | React 19 | Svelte 5 | No official Fluent UI v9 for Svelte; Svelte Fluent libraries are community, WinUI-focused, not web Copilot |
| Framework | React 19 | Enhanced vanilla JS | Current 1,012-line JS is already at complexity ceiling; no component model means escalating DOM bookkeeping for new features |
| UI library | Fluent UI v9 | Fluent UI v8 (@fluentui/react) | v8 is legacy; different token system; v9 is the current standard |
| UI library | Fluent UI v9 + shadcn/ui | MUI (Material UI) | Material Design != Microsoft Fluent Design; wrong aesthetic for Copilot style |
| CSS approach | Tailwind v4 + CSS props | styled-components | Runtime CSS-in-JS overhead; React 19 compatibility unverified at high confidence |
| CSS approach | Tailwind v4 + CSS props | CSS Modules | Unnecessary per-file overhead for a single developer; poor integration with Fluent token system |
| Build tool | Vite 6 | webpack 5 | Slower DX (seconds vs milliseconds for dev server start); no advantage for this project |
| Build tool | Vite 6 | esbuild standalone | No HMR, no React Fast Refresh, no plugin ecosystem |
| Animation | motion (^12) | GSAP | Imperative React API; commercial license concern for MMC |
| Animation | motion (^12) | CSS keyframes only | Cannot handle AnimatePresence (enter/exit for mounted components) |
| Syntax highlight | Prism.js | Shiki | Async WASM loading adds complexity; unnecessary for <5KB JSON blobs |
| State management | useState/Context | Zustand/Redux | Overengineered for 4 API endpoints and localized UI state |

---

## Sources

- React versions: https://react.dev/versions (React 19.2, October 2025)
- Fluent UI React v9: https://react.fluentui.dev/ (v9.73.5, verified March 2026 via npm search)
- Fluent UI v9 npm: https://www.npmjs.com/package/@fluentui/react-components
- Fluent Copilot chat: https://www.npmjs.com/package/@fluentui-copilot/react-copilot-chat
- Fluent 2 Design System: https://fluent2.microsoft.design/get-started/develop
- Tailwind CSS v4: https://tailwindcss.com/blog/tailwindcss-v4
- Motion (formerly Framer Motion): https://motion.dev/ (v12.37.0)
- Motion rebranding: https://fireup.pro/news/framer-motion-becomes-independent-introducing-motion
- Flask + React integration (Miguel Grinberg): https://blog.miguelgrinberg.com/post/create-a-react-flask-project-in-2025
- Flask SPA patterns: https://flask.palletsprojects.com/en/stable/patterns/singlepageapplications/
- Svelte production readiness: https://codifysol.com/svelte-in-2025-is-it-ready-for-production/
- Prism vs highlight.js: https://www.peterbe.com/plog/benchmark-compare-highlight.js-vs-prism
- Shadcn AI chat: https://www.shadcn.io/ai
