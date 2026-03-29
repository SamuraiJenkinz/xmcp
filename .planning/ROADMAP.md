# Roadmap: Exchange Infrastructure MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-9 (shipped 2026-03-22)
- ✅ **v1.1 Colleague Lookup** — Phases 10-12 (shipped 2026-03-25)
- 🚧 **v1.2 UI/UX Redesign** — Phases 13-19 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9) — SHIPPED 2026-03-22</summary>

### Phase 1: Exchange Client Foundation
**Goal**: Working async PowerShell runner that can execute Exchange cmdlets and return structured data
**Plans**: 4 plans (complete)

Plans:
- [x] 01-01: Async subprocess runner with per-call PSSession lifecycle
- [x] 01-02: Exchange Online auth (interactive + CBA) and connection management
- [x] 01-03: Base error handling, stderr discipline, structured return types
- [x] 01-04: -EncodedCommand UTF-16LE encoding to prevent cp1252 corruption

### Phase 2: MCP Server Scaffold
**Goal**: MCP server over stdio with tool registration, dispatch, and LLM-optimized schemas
**Plans**: 3 plans (complete)

Plans:
- [x] 02-01: MCP server skeleton with stdio transport and JSON-RPC
- [x] 02-02: Tool registration framework and dispatch table
- [x] 02-03: Error handling, startup banner, and stderr discipline

### Phase 3: Mailbox Tools
**Goal**: Mailbox governance tools — list, inspect, shared mailbox permissions, quota
**Plans**: 3 plans (complete)

Plans:
- [x] 03-01: get_mailbox_info, list_mailboxes tools
- [x] 03-02: get_mailbox_permissions, get_shared_mailbox_members tools
- [x] 03-03: get_mailbox_statistics (quota, size, item count)

### Phase 4: DAG and Database Tools
**Goal**: DAG health and mailbox database tools for Exchange availability monitoring
**Plans**: 3 plans (complete)

Plans:
- [x] 04-01: get_dag_health, list_dag_members tools
- [x] 04-02: get_database_copies, list_mailbox_databases tools
- [x] 04-03: get_server_health (Exchange server component status)

### Phase 5: Mail Flow and Security Tools
**Goal**: Mail flow tracing, transport rules, and DNS security lookups (DMARC/SPF/DKIM)
**Plans**: 5 plans (complete)

Plans:
- [x] 05-01: trace_message_tracking_log tool
- [x] 05-02: get_transport_rules, get_accepted_domains tools
- [x] 05-03: get_dmarc_record, get_spf_record tools
- [x] 05-04: get_dkim_record tool
- [x] 05-05: ping_exchange tool for connectivity checks

### Phase 6: Hybrid Tools
**Goal**: Hybrid connector and migration endpoint monitoring
**Plans**: 2 plans (complete)

Plans:
- [x] 06-01: get_inbound_connectors, get_outbound_connectors tools
- [x] 06-02: get_migration_endpoints tool (removed get_migration_batches — MMC not using)

### Phase 7: Chat App Core
**Goal**: Flask chat application with Azure AD SSO, Azure OpenAI tool-calling loop, and SSE streaming
**Plans**: 6 plans (complete)

Plans:
- [x] 07-01: Flask app skeleton, Waitress WSGI, HTTPS startup
- [x] 07-02: Azure AD/Entra ID SSO with MSAL auth code flow
- [x] 07-03: MCP client (async subprocess, JSON-RPC over stdio)
- [x] 07-04: Azure OpenAI tool-calling loop with SSE streaming
- [x] 07-05: Chat UI (message rendering, tool panels, keyboard shortcuts)
- [x] 07-06: Tool visibility panels with JSON highlighting and copy-to-clipboard

### Phase 8: Conversation Persistence
**Goal**: SQLite conversation history with multi-thread sidebar and auto-naming
**Plans**: 3 plans (complete)

Plans:
- [x] 08-01: SQLite schema, auto-bootstrap, conversation CRUD
- [x] 08-02: Multi-thread sidebar navigation and thread switching
- [x] 08-03: Auto-naming threads from first user message

### Phase 9: UI Polish
**Goal**: Dark mode, loading indicators, copy-to-clipboard on all responses, and production deployment
**Plans**: 4 plans (complete)

Plans:
- [x] 09-01: Dark mode toggle with CSS variables
- [x] 09-02: Loading indicators and streaming feedback
- [x] 09-03: Copy-to-clipboard on AI responses
- [x] 09-04: Production hardening, start.py HTTPS startup, deployment to usdf11v1784

</details>

<details>
<summary>✅ v1.1 Colleague Lookup (Phases 10-12) — SHIPPED 2026-03-25</summary>

- [x] Phase 10: Graph Client Foundation (4/4 plans) — completed 2026-03-24
- [x] Phase 11: MCP Tools + Photo Proxy (3/3 plans) — completed 2026-03-24
- [x] Phase 12: Profile Card Frontend + System Prompt (2/2 plans) — completed 2026-03-25

</details>

### 🚧 v1.2 UI/UX Redesign (In Progress)

**Milestone Goal:** Replace vanilla JS with a React 19 + Fluent UI v9 + Tailwind v4 frontend delivering a Microsoft Copilot aesthetic — enterprise-ready appearance, consistent dark mode, and polished chat interactions — without changing the Flask backend.

#### Phase 13: Infrastructure Scaffold
**Goal**: React + Vite + Fluent UI v9 + Tailwind v4 scaffold wired into Flask — auth and SSE verified through the new integration layer; zero user-visible change
**Depends on**: Phase 12
**Requirements**: FRAME-01, FRAME-02, FRAME-03, FRAME-07
**Success Criteria** (what must be TRUE):
  1. Running `npm run dev` in `frontend/` starts Vite on :5173 and proxies API requests to Flask on :5000 without CORS errors
  2. Navigating to the app in dev mode shows a React-rendered page; the user is authenticated via the existing MSAL session cookie
  3. `GET /api/me` returns the current user's display name and email as JSON (200) or redirects/401 if unauthenticated
  4. `@fluentui/react-components` FluentProvider renders without errors and applies webDarkTheme to the page shell
  5. `npm run build` produces a bundle in `frontend_dist/` that Flask serves correctly with the catch-all route
**Plans**: 2 plans

Plans:
- [x] 13-01-PLAN.md — Vite + React 19 + TypeScript scaffold with Fluent UI v9 and Tailwind v4
- [x] 13-02-PLAN.md — Flask integration: /api/me endpoint, catch-all route, ATLAS_UI feature flag

#### Phase 14: Functional Port
**Goal**: All existing chat features run in React components with identical behavior — SSE streaming, thread management, message rendering, tool panels, profile cards, input area — plus DEBT-01 and DEBT-02 fixed during the port
**Depends on**: Phase 13
**Requirements**: FRAME-04, FRAME-05, FRAME-06, FRAME-08, DEBT-01, DEBT-02
**Success Criteria** (what must be TRUE):
  1. Sending a message streams tokens in real-time; first text token arrives within 3 seconds; pressing Escape mid-stream cancels and shows "[response cancelled]"
  2. Thread create, rename, delete, and auto-naming from first message all work; switching threads renders the correct conversation history including tool panels for historical messages (DEBT-01 fix)
  3. Copy-to-clipboard works on both new and historical messages (DEBT-02 fix)
  4. Tool panels expand and collapse; profile cards render with photo or initials placeholder
  5. All 7 regression smoke tests pass before this phase is marked complete
**Plans**: 5 plans

Plans:
- [x] 14-01-PLAN.md — Types, API clients, and Context providers (auth, threads, chat state)
- [x] 14-02-PLAN.md — useStreamingMessage hook with SSE parsing + parseHistoricalMessages utility (DEBT-01 frontend fix)
- [x] 14-03-PLAN.md — ThreadList and ThreadItem sidebar components (CRUD, rename, switch with stream abort)
- [x] 14-04-PLAN.md — Message rendering: UserMessage, AssistantMessage, MarkdownRenderer, ToolPanel, ProfileCard, SearchResultCard, CopyButton (DEBT-02 fix)
- [x] 14-05-PLAN.md — InputArea, Header, AppLayout wiring, App.tsx integration + human verification

#### Phase 15: Design System
**Goal**: Fluent 2 semantic color token system applied globally — dark mode surface hierarchy correct, light mode aligned, Segoe UI Variable typography in place — enabling all subsequent visual work
**Depends on**: Phase 14
**Requirements**: DSGN-01, DSGN-02, DSGN-03, DSGN-04
**Success Criteria** (what must be TRUE):
  1. All CSS variables use the `--atlas-` prefix with no ad-hoc grays or hardcoded color values anywhere in the codebase
  2. Dark mode shows a three-tier surface hierarchy (background / surface / elevated surface) that matches Fluent 2 webDarkTheme — verified by toggling dark mode and inspecting computed styles
  3. Light mode uses the Fluent 2 neutral palette with no dark-mode bleed; switching modes changes all surfaces correctly
  4. Body text, headings, and code blocks use Segoe UI Variable at Fluent 2 type ramp sizes
**Plans**: 2 plans

Plans:
- [x] 15-01-PLAN.md — --atlas- token definitions, Tailwind @theme inline bridge, @layer base typography
- [x] 15-02-PLAN.md — Component CSS rules using --atlas- tokens, surface hierarchy, human verification

#### Phase 16: Chat Experience Redesign
**Goal**: Message bubbles, input area, streaming states, and welcome screen look and feel like Microsoft Copilot — clear role differentiation, smooth animations, stop-generation button, prompt chips
**Depends on**: Phase 15
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06
**Success Criteria** (what must be TRUE):
  1. User and assistant messages are visually unambiguous — distinct bubble geometry, color, and alignment matching Copilot style
  2. New messages entrance with a fade-in + upward translate animation (150-200ms) without layout thrash
  3. During streaming, the Send button is replaced by a Stop button; pressing it cancels the stream and the button reverts to Send
  4. The textarea expands as text is typed (up to ~5 lines), submits on Enter, and inserts a newline on Shift+Enter
  5. Hovering a message reveals a copy button and a per-message timestamp
  6. An empty thread shows a welcome state with Fluent 2 card-style prompt suggestion chips
**Plans**: 3 plans (complete)

Plans:
- [x] 16-01: Message bubble components — UserMessage, AssistantMessage Copilot style; message entrance animations
- [x] 16-02: InputArea redesign — auto-resize, send/stop toggle, keyboard shortcuts, welcome state with prompt chips
- [x] 16-03: Hover actions — per-message copy button and timestamp overlay

#### Phase 17: Sidebar and Tool Panels
**Goal**: Thread sidebar has recency grouping, collapse mode, and polished states; tool panels have chevron expand, status badges, elapsed time, and syntax-highlighted JSON
**Depends on**: Phase 15
**Requirements**: SIDE-01, SIDE-02, SIDE-03, TOOL-01, TOOL-02, TOOL-03, TOOL-04
**Success Criteria** (what must be TRUE):
  1. Sidebar threads are grouped under Today / Yesterday / This Week / Older headings with correct date bucketing
  2. Clicking the collapse icon shrinks the sidebar to icon-only mode with a CSS transition; the collapsed state persists across hard reloads (localStorage)
  3. Tool panels show a chevron toggle, a status badge (running / done / error), and elapsed time ("Ran in 1.2s") when expanded
  4. JSON inside tool panels is syntax-highlighted with a Fluent-aligned dark theme and has a per-panel copy button
  5. Backend SSE tool events carry start/end timestamps enabling elapsed time calculation (tracked backend PR separate from UI work)
**Plans**: TBD

Plans:
- [ ] 17-01: Backend — add tool_start_time / tool_end_time to SSE tool events
- [ ] 17-02: Sidebar redesign — recency grouping, collapse mode, spacing, active/hover states, pencil-plus new-chat button
- [ ] 17-03: Tool panel redesign — chevron, status badge, elapsed time, syntax-highlighted JSON, per-panel copy

#### Phase 18: Profile Cards, Splash Page, and Cleanup
**Goal**: Profile and search result cards aligned with Fluent 2; professional splash/login page; three test regressions and two schema issues resolved
**Depends on**: Phase 15
**Requirements**: PROF-01, PROF-02, SPLA-01, DEBT-03, DEBT-04, DEBT-05
**Success Criteria** (what must be TRUE):
  1. Inline profile cards match Fluent 2 Card component geometry — photo, name, title, department, and email laid out consistently with surrounding chat content
  2. Colleague search result cards follow Fluent 2 list patterns and are visually consistent with profile cards
  3. The login/splash page has a professional landing appearance using Fluent 2 aesthetics — not a bare form
  4. All 3 test regressions pass (description phrasing, tool count assertion); get_user_photo_bytes() dead code removed; get_colleague_profile user_id schema description corrected
**Plans**: TBD

Plans:
- [ ] 18-01: Profile card and search result card Fluent 2 alignment
- [ ] 18-02: Splash/login page redesign
- [ ] 18-03: Tech debt cleanup — fix 3 test regressions (DEBT-03), remove dead code (DEBT-04), fix schema description (DEBT-05)

#### Phase 19: Accessibility Sweep
**Goal**: Keyboard navigation and WCAG AA focus rings verified across all redesigned components — the full UI is operable without a mouse
**Depends on**: Phases 16, 17, 18
**Requirements**: A11Y-01, A11Y-02
**Success Criteria** (what must be TRUE):
  1. Every interactive element (buttons, links, thread items, tool panels, textarea, chips) is reachable and activatable via keyboard Tab and Enter/Space
  2. Focus rings are visible on all focused elements with at least 3:1 contrast ratio against adjacent backgrounds (WCAG AA)
  3. Tab order follows a logical reading order — sidebar threads before chat pane, chat pane top-to-bottom, input area last
**Plans**: TBD

Plans:
- [ ] 19-01: Keyboard navigation audit and focus ring implementation across all v1.2 components

## Progress

**Execution Order:**
v1.2 phases execute in order: 13 → 14 → 15 → 16 → 17 → 18 → 19
Note: Phases 16, 17, and 18 all depend on Phase 15 and may be partially parallelized; Phase 19 requires all three complete.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Exchange Client Foundation | v1.0 | 4/4 | Complete | 2026-03-19 |
| 2. MCP Server Scaffold | v1.0 | 3/3 | Complete | 2026-03-19 |
| 3. Mailbox Tools | v1.0 | 3/3 | Complete | 2026-03-20 |
| 4. DAG and Database Tools | v1.0 | 3/3 | Complete | 2026-03-20 |
| 5. Mail Flow and Security Tools | v1.0 | 5/5 | Complete | 2026-03-20 |
| 6. Hybrid Tools | v1.0 | 2/2 | Complete | 2026-03-20 |
| 7. Chat App Core | v1.0 | 6/6 | Complete | 2026-03-21 |
| 8. Conversation Persistence | v1.0 | 3/3 | Complete | 2026-03-22 |
| 9. UI Polish | v1.0 | 4/4 | Complete | 2026-03-22 |
| 10. Graph Client Foundation | v1.1 | 4/4 | Complete | 2026-03-24 |
| 11. MCP Tools + Photo Proxy | v1.1 | 3/3 | Complete | 2026-03-24 |
| 12. Profile Card Frontend + System Prompt | v1.1 | 2/2 | Complete | 2026-03-25 |
| 13. Infrastructure Scaffold | v1.2 | 2/2 | Complete | 2026-03-27 |
| 14. Functional Port | v1.2 | 5/5 | Complete | 2026-03-29 |
| 15. Design System | v1.2 | 2/2 | Complete | 2026-03-29 |
| 16. Chat Experience Redesign | v1.2 | 3/3 | Complete | 2026-03-29 |
| 17. Sidebar and Tool Panels | v1.2 | 0/3 | Not started | - |
| 18. Profile Cards, Splash, Cleanup | v1.2 | 0/3 | Not started | - |
| 19. Accessibility Sweep | v1.2 | 0/1 | Not started | - |
