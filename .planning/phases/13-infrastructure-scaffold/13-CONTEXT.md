# Phase 13: Infrastructure Scaffold - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

React 19 + Vite + Fluent UI v9 + Tailwind v4 scaffold wired into Flask with auth and SSE verified through the new integration layer. Zero user-visible change — the classic Jinja2 UI remains the default. This phase creates the foundation all subsequent v1.2 phases build on.

</domain>

<decisions>
## Implementation Decisions

### Frontend folder structure
- `frontend/` directory at project root as a standard Vite project
- `src/` contains: `components/`, `hooks/`, `api/`, `App.tsx`, `main.tsx`
- Production build outputs to `frontend_dist/` which Flask serves via catch-all route
- Direct imports throughout — no barrel files
- Components directory stays flat until Phase 14 populates it

### Dev workflow and proxy config
- `npm run dev` starts Vite on :5173 with proxy config routing `/api/*`, `/login`, `/logout`, `/auth/*` to Flask on :5000
- Developers run Flask and Vite in separate terminals during development
- No SSL in dev mode — Flask dev mode on :5000 plain HTTP, Vite proxies to it
- Production path: `npm run build` produces `frontend_dist/`, Flask serves it via catch-all

### Feature flag and cutover strategy
- Env var `ATLAS_UI=react` (default `classic`) controls which UI is served
- Flask catch-all: if `ATLAS_UI=react`, serve `frontend_dist/index.html`; otherwise serve Jinja2 templates as today
- Both UIs hit the same `/api/*` endpoints — no backend branching needed
- Classic UI stays fully functional until Phase 14 completes and the flag is flipped

### Fluent UI and Tailwind coexistence
- Fluent UI v9 for interactive components (buttons, inputs, menus, cards) — built-in a11y and dark mode
- Tailwind v4 for layout utilities only (flex, grid, spacing, responsive) — not for colors or typography
- Tailwind prefix `tw-` to prevent class name collisions with Fluent
- All colors and typography sourced from Fluent's `webDarkTheme` / `webLightTheme` tokens exclusively

### Claude's Discretion
- Exact Vite config details (chunk splitting, aliases)
- TypeScript strictness level and tsconfig options
- Package manager choice (npm vs pnpm)
- Dev script naming conventions
- ESLint/Prettier configuration

</decisions>

<specifics>
## Specific Ideas

- The existing `chat_app/static/app.js` is a single ~600-line IIFE — Phase 14 will decompose it into React components, not this phase
- Flask currently uses Waitress in production and `start.py` with SSL certs for dev — the Vite proxy only applies during frontend development
- The `/api/me` endpoint (new in this phase) returns display name and email from the existing MSAL session — no new auth flow needed
- IIS ARR may be in the production serving path — if present, `responseBufferLimit="0"` must be configured for SSE (blocker from STATE.md)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-infrastructure-scaffold*
*Context gathered: 2026-03-27*
