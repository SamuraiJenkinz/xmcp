# Research Summary — Atlas v1.2 UI/UX Redesign

**Project:** Atlas — Exchange Infrastructure Chat App (Marsh McLennan)
**Milestone:** v1.2 UI/UX Overhaul — Microsoft Copilot Aesthetic
**Researched:** 2026-03-27
**Synthesized:** 2026-03-27
**Overall Confidence:** HIGH (backend unchanged and validated; frontend decisions anchored to verifiable facts)

---

## Executive Summary

Atlas v1.2 is a visual and interaction redesign of a working, production internal tool. The backend — Flask, Waitress, SQLite, MSAL, SSE streaming — stays entirely unchanged. The goal is to replace approximately 1,200 lines of vanilla JS and organically-grown CSS with a component-based frontend that looks and behaves like Microsoft Copilot, targeting IT engineers and operations teams on Windows desktop at 1080p–1440p in dark mode.

The central technical decision is framework choice. Two research agents reached opposite conclusions: STACK.md recommends React 19 because Fluent UI v9 (`@fluentui/react-components`) is React-only from Microsoft, and `@fluentui-copilot/react-copilot-chat` exists specifically for this aesthetic. ARCHITECTURE.md recommends Svelte 5 because it compiles to minimal vanilla JS, keeps the codebase closest to the developer's existing knowledge, and the Flask-served SPA integration is simpler. Both are technically defensible. The synthesis resolves this conflict in Section 3 below with a clear decision.

The migration must be executed in three phases: infrastructure first, feature parity second, visual polish third. The four most dangerous failure modes — SSE stream loss during framework migration, Flask session cookies breaking under SPA patterns, IIS ARR buffering killing streaming in production, and CSS variable namespace collisions — are all fully preventable with specific measures documented in PITFALLS.md and must be addressed before any user-facing change ships.

---

## Key Findings

### From STACK.md

The existing backend stack (Python 3.12, Flask 3.x, Waitress 3.x, SQLite WAL, MSAL 1.35.1) is validated, production-confirmed, and unchanged in this milestone. The frontend question is new.

STACK.md recommends a **hybrid SPA** pattern: keep Flask/Jinja2 for the auth shell and page routing; mount a React 19 component tree inside the Jinja2-rendered `chat.html` via a Vite-built bundle. This preserves the MSAL auth code flow on the server, avoids CORS and cookie reconfiguration, and passes user data as data attributes from Jinja2 into React props.

**Core frontend technologies recommended by STACK.md:**
- `react` ^19.2 + `react-dom` — UI runtime; chosen because Fluent UI v9 is React-only from Microsoft
- `@fluentui/react-components` ^9.73.5 — Microsoft's official Fluent UI v9 (daily publishes, React-only, verified on npm)
- `@fluentui-copilot/react-copilot-chat` v0.13.x — Microsoft's own Copilot chat message components (actively published March 2026)
- `tailwindcss` ^4.0 — utility CSS layer, integrates natively with CSS custom properties via `@theme` directive
- `vite` ^6.x + `@vitejs/plugin-react-swc` — build tooling and dev server with Flask proxy
- `motion` ^12.x (formerly framer-motion) — declarative animations for streaming cursor, message entrances, collapsible panels
- `typescript` ^5.5 — type safety across the component tree

### From FEATURES.md

Domain 5 (UI/UX Overhaul) categorizes features into must-ship, should-ship, and defer. All existing backend-facing features (streaming, tool panels, thread management, profile cards) are already built; this milestone is exclusively about how they look and feel.

**Must ship (table stakes — all exist today, need polish or correctness fixes):**
- Full-bleed consistent dark mode — surface hierarchy audit, fix light-mode bleed
- Unambiguous user vs. assistant message differentiation
- Proper markdown rendering during SSE streaming (audit for partial-tag edge cases)
- Syntax-highlighted code blocks with per-block copy buttons
- Auto-resize textarea (max ~5 lines before scroll)
- Send on Enter / newline on Shift+Enter (verify current behavior matches standard)
- Streaming cursor / active generation indicator
- Stop generation button (replaces send button during SSE streaming)
- Sidebar thread list polish — spacing, active states, hover states
- Thread rename and delete affordances (discoverable on hover)
- Welcome / empty state with prompt suggestion chips
- Loading/thinking state before first token arrives
- Keyboard navigation and WCAG AA focus rings

**Should ship (differentiators, low-to-medium complexity):**
- Tool call panel upgrade — chevron icon, status badge (running/done/error), elapsed time display
- Hover actions on messages — copy button, per-message timestamp, thumbs-up/down feedback
- Thread recency grouping in sidebar (Today / Yesterday / This Week / Older)
- Sidebar collapse to icon-only mode with CSS transition
- Inline profile card visual alignment with Fluent 2 specification

**Defer to v1.3+:**
- Thread search (requires search backend or client-side index)
- Full design token system migration as a standalone milestone
- Export as PDF or Word document
- Response word count or token indicator

**Hard anti-features — do not build:**
- Typewriter animation (use natural SSE streaming speed)
- Emoji reaction palette (thumbs-up/down only)
- Onboarding wizard or product tour overlay
- Sound effects on send/receive
- Floating chat bubble or widget layout
- Model picker dropdown in the chat UI
- Animated mesh gradient or particle background
- File attachment upload UI
- Real-time multi-user collaboration

### From ARCHITECTURE.md

ARCHITECTURE.md recommends the **Flask-served SPA** pattern: Svelte 5 compiled via Vite to a static bundle, served by Flask from `chat_app/frontend_dist/`, with a catch-all route returning `index.html` for non-API paths. Flask stays on one origin, cookies require zero reconfiguration, and CORS is never introduced.

The key insight from ARCHITECTURE.md: the existing SSE implementation uses `fetch()` + `ReadableStream.getReader()` — not `EventSource` — because the endpoint is POST. This implementation is framework-agnostic and ports directly to any framework without protocol changes.

**Component boundary map (framework-agnostic — applies regardless of React or Svelte):**
- `App` — root component, owns `currentThreadId`
- `Header` — user info, logout link, theme toggle
- `Sidebar` — `ThreadList` + `ThreadItem` (inline rename, delete, active state)
- `ChatPane` — owns streaming state (`isStreaming`, `AbortController`); contains `MessageList` + `InputArea`
- `MessageList` — `WelcomeMessage`, `UserMessage`, `AssistantMessage` (with `ThinkingDots`, `ToolPanel`, `ProfileCard`, `SearchResultCards`, `MarkdownRenderer`)
- `InputArea` — auto-expanding textarea, send/stop button

**Migration sequence (critical — do not skip or reorder):**
1. Infrastructure: scaffold frontend project, configure Vite proxy, add `GET /api/me` to Flask, verify auth round-trip and SSE through the new layer
2. Port SSE stream service first (highest risk; isolate and test before anything else)
3. Port thread management, message rendering, input area, header
4. Apply visual redesign after port is feature-complete and regression suite passes

ARCHITECTURE.md explicitly warns against SvelteKit (creates a Node.js layer in front of Flask) and against a separate frontend server (SameSite=Lax cookies break cross-origin).

### From PITFALLS.md

Eleven pitfalls documented: three critical (production-breaking), four high (significant regressions), four medium (technical debt or user friction).

**Regression test suite — must pass before any phase ships:**
1. SSE streaming: send message, first text token arrives within 3 seconds
2. Tool panels: trigger 2 tool calls, verify chips render with expand/collapse
3. Thread auto-naming: send first message to new thread, verify sidebar title updates
4. Dark mode persistence: set dark, hard-reload, verify it stays dark
5. Auth redirect: visit `/chat` without session, verify splash appears (not a broken page)
6. Photo proxy: colleague cards show photo or initials placeholder (not broken img icon)
7. Message cancel: press Escape or Cancel mid-stream, verify `[response cancelled]` marker appears

---

## The Framework Decision

This is the primary conflict between STACK.md (React 19) and ARCHITECTURE.md (Svelte 5). Both are correct within their own reasoning. The synthesis picks one.

### The Case for React (STACK.md argument)

The goal is a Microsoft Copilot aesthetic. Microsoft publishes the tools for this:
- `@fluentui/react-components` v9 is React-only. There is no official Fluent UI v9 for Svelte.
- `@fluentui-copilot/react-copilot-chat` is a React package shipping Copilot-style message bubbles and chat containers out of the box — actively maintained as of March 2026.
- Community Svelte Fluent options (`fluent-svelte`, `svelte-fui`) are partial, community-maintained, and do not target the modern web Copilot aesthetic.

Without official Fluent components, achieving a credible Copilot aesthetic in Svelte means building every token, color, and component from scratch against the Fluent 2 design spec — substantially more work than using the official packages. React 19 also has the largest ecosystem; for one developer, more StackOverflow answers, more shadcn/ui components to copy-paste, and more AI coding assistant training data have real, daily productivity impact.

### The Case for Svelte (ARCHITECTURE.md argument)

Svelte 5 compiles to vanilla JS (~1.6KB runtime vs React's ~42KB). The existing codebase is vanilla JS; Svelte's reactivity model is closer to plain JS than React Hooks. For a single developer migrating an existing app, learning React Hooks, the React component model, and TypeScript simultaneously is real cognitive overhead. ARCHITECTURE.md notes: "Migrating to Svelte while simultaneously redesigning complex UI is doubled cognitive load for one developer" — the same argument applies symmetrically to React.

The Flask-served SPA integration pattern works identically for both frameworks. Svelte 5 is production-stable (released October 2024, used at IKEA, The New York Times). The SSE streaming pattern is framework-agnostic.

### Recommendation: React 19

**Use React 19 with the hybrid SPA integration pattern from STACK.md.**

The deciding factor is the primary goal: Microsoft Copilot aesthetic. `@fluentui/react-components` v9 and `@fluentui-copilot/react-copilot-chat` are official, actively-maintained Microsoft packages that are React-only. This is a concrete, verifiable fact — not a preference. Building a credible Copilot aesthetic without official Fluent UI components would require reverse-engineering the token system, component geometry, and interaction patterns manually, which is a larger effort than the framework migration itself.

The single-developer ergonomics concern from ARCHITECTURE.md is real but addressable: use the hybrid SPA pattern (not a full SPA migration), keep Flask handling auth, and evaluate `@fluentui-copilot/react-copilot-chat` first — falling back to shadcn/ui components styled with Fluent tokens if the package does not accommodate Atlas's tool panels.

**What this decision means operationally:**
- Flask renders `chat.html` (Jinja2 shell); Vite builds React to `static/dist/`; React mounts on `#app` div; user and thread data passed as HTML data attributes
- No React Router needed (one protected route: `/chat`)
- No RSC, no Next.js — Flask is the server; React runs client-side only
- `@login_required` on Flask routes stays unchanged
- The existing `readSSEStream` logic moves into a `useStreamingMessage` custom hook; `AbortController` must live in `useRef` (not `useState`) to survive re-renders without triggering cleanup
- `GET /api/me` replaces Jinja2 template variable injection for user data

**Decision point at end of Phase 1:** If React proves wrong for this developer and codebase, the Flask-served SPA architecture is identical for Svelte. Switching at infrastructure phase costs one sprint of re-scaffolding. After Phase 2 (feature port), switching is expensive. Commit by end of Phase 1.

---

## Architecture Approach

The integration pattern agreed between both research files: Flask-served SPA, single origin, Vite proxy during development, catch-all route for non-API paths in production.

**New Flask additions (approximately 15–20 lines total):**
- `GET /api/me` — returns `session["user"]` as JSON (200) or 401; replaces Jinja2 template variable injection
- `static_folder` pointing to `frontend_dist/assets/` for hashed bundles
- Catch-all route returning `frontend_dist/index.html` (registered after all blueprints so `/api/*`, `/chat/*`, `/login`, `/auth/*`, `/logout` resolve first)

**Directory structure:**
```
xmcp/
├── chat_app/               # Flask — unchanged except app.py additions
│   └── frontend_dist/      # Vite build output (gitignored, rebuilt on deploy)
└── frontend/               # React + Vite project
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   └── services/
    │       ├── api.ts      # /api/threads CRUD
    │       └── stream.ts   # /chat/stream SSE consumer hook
    └── vite.config.ts
```

**Build pipeline:**
- Dev: `cd frontend && npm run dev` (Vite on :5173 proxying API calls to Flask on :5000)
- Prod: `cd frontend && npm run build` then `python -m waitress` (Waitress serving unchanged)

**Rollback capability:** Flask can be configured with an env var to serve either the Jinja2 templates or the SPA index.html throughout Phase 2. Remove dual-serving after Phase 3 validation.

---

## Critical Pitfalls

The five most dangerous pitfalls for this milestone, with prevention required before or during the phase that introduces the risk:

**1. SSE stream abandoned on React component unmount (CRITICAL)**
The `AbortController` for the fetch stream must live in `useRef`, not `useState`. Port the SSE read loop into an isolated `stream.ts` service module and integration-test it against live `/chat/stream` — verifying all five event types (`tool`, `text`, `thread_named`, `done`, `error`) — before building any other component. Do not use `EventSource` as a replacement; the endpoint is POST and EventSource is GET-only.

**2. Flask session cookie breaks under SPA navigation (CRITICAL)**
Session expiry causes a white screen; `/chat/stream` returns HTML 302 instead of SSE data. Add a JSON 401 response path to `@login_required` (return JSON when `Accept: application/json` is present, HTML redirect otherwise). Test session expiry explicitly in the dev environment (set `PERMANENT_SESSION_LIFETIME = timedelta(seconds=30)`) before shipping Phase 1.

**3. IIS ARR response buffering kills streaming in production (CRITICAL)**
Streaming works on localhost but the actual deployment target may buffer SSE responses. Every phase touching the serving layer must include a streaming smoke test on the production server, not just localhost. If IIS ARR is in the path, configure `responseBufferLimit="0"` for the Flask upstream.

**4. CSS variable namespace collision when introducing design system (HIGH)**
Before introducing Fluent UI or Tailwind, run an audit of existing CSS variables and rename all to `--atlas-` prefix (e.g., `--bg` → `--atlas-bg`). Apply Fluent tokens to new components only; do not replace Atlas variables globally until all components are migrated. Verify dark mode toggle end-to-end after every CSS change.

**5. Markdown rendering introduces XSS via Exchange cmdlet output (HIGH)**
Exchange cmdlet results contain `<user@domain.com>` angle brackets that become HTML. Use `marked` + `DOMPurify.sanitize()` or `react-markdown` without `dangerouslySetInnerHTML`. DOMPurify must be added in the same PR as the Markdown renderer — it cannot be deferred to a follow-up.

---

## Implications for Roadmap

Three phases, each independently shippable and verifiable.

### Phase 1: Infrastructure Foundation
**Rationale:** Zero user-visible change; establishes the build pipeline, proves auth and SSE work through the new integration layer, and creates the rollback capability. Must complete — and pass the regression suite — before any UI work begins.
**Delivers:** React + Vite scaffold; Vite dev proxy to Flask; `GET /api/me` endpoint; bare-bones React app that authenticates and renders correctly; build output wired into Flask catch-all with env-var feature flag; `stream.ts` isolated and integration-tested.
**Features addressed:** None user-facing. Unblocks all subsequent phases.
**Pitfalls to prevent:** SSE stream loss (Pitfall 1 — isolate `stream.ts` and test all five event types before proceeding); session cookie under SPA (Pitfall 2 — add JSON 401 path and test session expiry).
**Research flag:** STANDARD PATTERN — well-documented Flask + Vite + React integration. No additional research needed before planning.

### Phase 2: Feature Parity Port
**Rationale:** Migrate all functionality from vanilla JS to React components before applying any visual changes. Each component can be tested against existing behavior. Regression suite runs at the end of this phase and must pass completely before Phase 3 begins.
**Delivers:** Complete React implementation of all existing features — SSE streaming, thread management, message rendering (markdown, tool panels, profile cards), input area, header, welcome state. Behavior is identical to current production; visuals may still be dated.
**Migrate in this order (dependency-driven):**
1. `stream.ts` — SSE consumer hook (highest risk, verify first)
2. Thread management — `ThreadList`, `ThreadItem`, all four mutation paths in one atomic commit (new thread, rename, delete, `thread_named` SSE update)
3. Message rendering — `UserMessage`, `AssistantMessage`, `ToolPanel`, `ProfileCard`, `MarkdownRenderer` + DOMPurify in the same commit
4. `InputArea` — auto-resize textarea, send/stop button, keyboard shortcuts
5. `Header` — user info, logout, theme toggle
**Pitfalls to prevent:** Thread state drift (Pitfall 6 — migrate all four mutation paths atomically); XSS via markdown (Pitfall 7 — DOMPurify in same PR as renderer); profile photo before auth confirmed (Pitfall 5 — auth guard before any photo `<img>` renders); CSS variable namespace audit before adding any design system tokens (Pitfall 4).
**Research flag:** STANDARD PATTERN for React hooks and component model. No additional research needed.

### Phase 3: Visual Redesign — Copilot Aesthetic
**Rationale:** Once components exist with clear boundaries and verified behavior, visual redesign is safe. Regressions are isolated to CSS and component props, not data flow. Attempting visual polish before feature parity is the primary failure mode of UI migrations.
**Delivers:** Fluent UI v9 token system and `FluentProvider` with `webDarkTheme`; dark mode surface hierarchy audit; user vs. assistant differentiation; tool call panel visual upgrade (chevron, status badge, elapsed time); hover actions on messages; thread recency grouping; sidebar collapse; message entrance animations; WCAG AA focus rings. Achieves the Microsoft Copilot aesthetic.
**Stack used:** `@fluentui/react-components` v9, `@fluentui-copilot/react-copilot-chat` (evaluate first; fall back to shadcn/ui), `tailwindcss` v4 with `@theme` directive, `motion` v12 for `AnimatePresence` and layout animations.
**The only backend change in this milestone:** Add tool call `start_time` and `end_time` timestamps to SSE events (for elapsed time display on tool panels). This is a tracked backend PR, separate from CSS/component work, to enforce scope discipline.
**Pitfalls to prevent:** IIS ARR buffering smoke test on every deploy (Pitfall 3); Tailwind Preflight resets `<details>/<summary>` — restyle explicitly in the same PR as Tailwind introduction (Pitfall 11); `atlas-theme` localStorage key migration script before theme system changes (Pitfall 9); per-phase SCOPE-LOCK.md to prevent scope creep (Pitfall 8).
**Research flag:** EVALUATE FIRST — `@fluentui-copilot/react-copilot-chat` fitness for Atlas's tool panel and profile card model requires a hands-on spike (2–4 hours) at the start of Phase 3. Document as a go/no-go before committing Phase 3 scope.

### Phase Ordering Rationale

- Infrastructure before feature port: auth and SSE correctness must be verified in the new integration layer before building on top of it. A broken stream discovered in Phase 2 is much harder to diagnose when mixed with component logic.
- Feature parity before visual redesign: separating structural migration (verifiable against existing behavior) from visual redesign (no ground truth to compare against) means either phase failing does not contaminate the other. This is the most important sequencing decision.
- Backend timestamp change belongs in Phase 3: the only backend touch in the milestone (tool call timestamps for elapsed time display) belongs alongside the tool panel visual upgrade — not Phase 1 or 2. Backend-only PRs stay separate from CSS/component PRs within Phase 3.

---

## Conflicts and Agreements Between Research Files

### Conflicts

| Topic | STACK.md | ARCHITECTURE.md | Resolution |
|-------|----------|-----------------|------------|
| Framework | React 19 — Fluent UI v9 is React-only from Microsoft | Svelte 5 — simpler for single developer, closest to existing vanilla JS | **React 19.** Primary goal is Microsoft Copilot aesthetic; official Fluent UI v9 is React-only. This is a verifiable constraint, not a preference. |
| SPA scope | Hybrid SPA: Jinja2 shell preserved, React mounted inside `chat.html` | Full SPA: Jinja2 removed, Flask catch-all returns `index.html`, `/api/me` replaces template injection | **Hybrid for Phase 1, evaluate full SPA in Phase 2.** Both patterns use same-origin Flask-served SPA and are compatible with session cookies. Hybrid is lower risk for the initial port. |
| Vite output target | `chat_app/static/dist/` (Flask serves directly, no catch-all needed) | `chat_app/frontend_dist/` (Flask catch-all returns `index.html`) | **Minor difference.** Use `frontend_dist/` with catch-all for the cleaner full-SPA path. Both are functionally equivalent. |

### Agreements

Both research files agree on every other significant decision:
- Flask, Waitress, SQLite, MSAL: unchanged, not under consideration
- Vite 6 as the build tool
- SSE via `fetch()` + `ReadableStream` is framework-agnostic; ports without protocol changes
- Flask-served SPA on same origin; CORS is unnecessary and must not be introduced
- `SameSite=Lax` session cookies require no reconfiguration in same-origin SPA
- Phased migration: infrastructure first, port second, polish third
- No SvelteKit, no Next.js; React must run client-side with Flask as the server
- `GET /api/me` is needed regardless of framework choice
- The component boundary map is correct regardless of framework
- The regression test suite (seven items) is the definition of "phase complete"
- PITFALLS.md SSE, session cookie, and IIS ARR risks are confirmed by ARCHITECTURE.md as well

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Backend stack (unchanged) | HIGH | Production-validated; not under review in this milestone |
| React as framework choice | HIGH | Fluent UI v9 React-only constraint verified against npm registry — a documented fact |
| Flask-served SPA integration pattern | HIGH | Official Flask SPA docs; Vite proxy behavior is standard and well-documented |
| SSE streaming portability to React | HIGH | `fetch()` + `ReadableStream` is browser-native; framework-agnostic by design |
| Session cookie behavior under same-origin SPA | HIGH | SameSite=Lax with same-origin deployment; reviewed against Flask session docs |
| `@fluentui-copilot/react-copilot-chat` fitness for Atlas | MEDIUM | Package exists and is actively maintained (verified March 2026); whether it accommodates tool panels and profile cards requires hands-on evaluation |
| Tailwind v4 + Fluent v9 `makeStyles` token integration | MEDIUM | Both are released and stable; CSS `@theme` + Fluent token combination is plausible but not validated as a combined system |
| IIS ARR buffering in actual production deployment | MEDIUM | Pattern is documented; actual server configuration is unknown from research alone |
| Motion v12 specific animation timing values | MEDIUM | Package and API verified; exact timing values (150–200ms, 8px translate) from design brief are LOW confidence |

**Overall confidence:** HIGH for architecture and integration patterns. MEDIUM for specific package fitness and combined framework integrations that require hands-on validation.

### Gaps to Address During Planning

- **`@fluentui-copilot/react-copilot-chat` evaluation spike:** Required at the start of Phase 3. If the package does not accommodate tool panels and profile cards, the fallback is shadcn/ui chat components styled with Fluent tokens. Budget 2–4 hours before committing Phase 3 scope.
- **IIS ARR verification:** Confirm whether IIS ARR is in the actual production serving path before Phase 1 ships. If present, add `responseBufferLimit="0"` to the deployment runbook before Phase 1 is marked complete.
- **Thread `created_at` column existence:** Sidebar recency grouping (Today / Yesterday / This Week) requires `created_at` on thread records. Verify this column exists in the current SQLite schema before scheduling this feature in Phase 3.
- **Tool call timestamp SSE changes:** The only backend change in this milestone (adding `tool_start_time` and `tool_end_time` to SSE events) must be scoped explicitly in Phase 3 as a tracked backend PR separate from CSS/component work.

---

## Sources

### Primary (HIGH confidence — verified against official sources)

- [Flask Single-Page Applications (official docs)](https://flask.palletsprojects.com/en/stable/patterns/singlepageapplications/) — SPA pattern, catch-all route
- [@fluentui/react-components on npm](https://www.npmjs.com/package/@fluentui/react-components) — v9.73.5, React-only, daily publishes verified March 2026
- [@fluentui-copilot/react-copilot-chat on npm](https://www.npmjs.com/package/@fluentui-copilot/react-copilot-chat) — v0.13.x, active maintenance verified March 2026
- [Fluent 2 Design System — Color and tokens](https://fluent2.microsoft.design/color)
- [Vite Server Options — proxy configuration](https://vite.dev/config/server-options)
- [Session-based Auth with Flask for Single Page Apps — TestDriven.io](https://testdriven.io/blog/flask-spa-auth/)
- [Microsoft SSE on Azure App Service — IIS ARR buffering](https://learn.microsoft.com/en-us/answers/questions/5573038/issues-with-sse-(server-side-events)-on-azure-app)
- Actual codebase inspection: `app.js`, `style.css`, `chat.py`, `app.py`, `auth.py`, `chat.html`, `base.html` — HIGH confidence for all current implementation details

### Secondary (MEDIUM confidence — community sources, multiple agreement)

- [React vs Vue vs Svelte 2025 comparison — merge.rocks](https://merge.rocks/blog/comparing-front-end-frameworks-for-startups-in-2025-svelte-vs-react-vs-vue)
- [Design Patterns For AI Interfaces — Smashing Magazine](https://www.smashingmagazine.com/2025/07/design-patterns-ai-interfaces/)
- [AI Copilot UX 2025–26: Best Practices — Groto](https://www.letsgroto.com/blog/mastering-ai-copilot-design)
- [Unbreaking Cookies in Local Dev with Vite Proxy (2025)](https://mattslifebytes.com/2025/03/30/unbreaking-cookies-in-local-dev-with-vite-proxy/)
- [The new UI for enterprise AI — Microsoft Design](https://microsoft.design/articles/the-new-ui-for-enterprise-ai/)
- [Tailwind CSS v4 — CSS-first configuration and @theme directive](https://tailwindcss.com/blog/tailwindcss-v4)
- [Flask-Svelte-Template (Svelte 5 + Vite)](https://github.com/martinm07/flask-svelte-template) — integration pattern reference
- [SSE POST fetch ReadableStream vs EventSource — Medium](https://medium.com/@david.richards.tech/sse-server-sent-events-using-a-post-request-without-eventsource-1c0bd6f14425)

### Tertiary (LOW confidence — inferred or single-source, needs validation)

- Tailwind v4 + Fluent UI v9 `makeStyles` as a combined system — plausible from individual docs, not validated together
- `responseBufferLimit="0"` as the correct IIS ARR configuration key — requires validation against the actual server
- Motion v12 animation timing values (150–200ms, 8px translate) from design brief — not externally validated

---

*Research completed: 2026-03-27*
*Supersedes: SUMMARY.md from v1.1 Colleague Lookup milestone (2026-03-24)*
*Ready for roadmap: yes*
