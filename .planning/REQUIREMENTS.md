# Requirements: Exchange Infrastructure MCP Server

**Defined:** 2026-03-27
**Core Value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data

## v1.2 Requirements

Requirements for UI/UX Redesign milestone. Full visual overhaul targeting Microsoft Copilot aesthetic with React + Fluent UI v9 migration.

### Framework Migration

- [x] **FRAME-01**: Scaffold React 19 + Vite + TypeScript within existing Flask app (hybrid SPA pattern — Flask serves shell, React mounts on #app)
- [x] **FRAME-02**: Integrate Fluent UI v9 (@fluentui/react-components) as primary component library
- [x] **FRAME-03**: Integrate Tailwind CSS v4 for utility styling alongside Fluent tokens
- [x] **FRAME-04**: Port SSE streaming logic to React (fetch + ReadableStream, AbortController in useRef)
- [x] **FRAME-05**: Port thread management (CRUD, sidebar, switching) to React components
- [x] **FRAME-06**: Port message rendering and markdown to React components
- [x] **FRAME-07**: Add /api/me endpoint to replace Jinja2 template variable injection
- [x] **FRAME-08**: Achieve functional parity — all existing features work identically before visual changes

### Design System

- [x] **DSGN-01**: Implement Fluent 2 semantic color token system (CSS custom properties with --atlas- namespace)
- [x] **DSGN-02**: Dark mode audit — three-tier surface hierarchy, no ad-hoc grays, WCAG AA contrast
- [x] **DSGN-03**: Light mode aligned with Fluent 2 neutral palette
- [x] **DSGN-04**: Typography system using Fluent 2 type ramp (Segoe UI Variable)

### Chat Experience

- [x] **CHAT-01**: Redesigned message bubbles — clear user vs assistant role differentiation (Copilot style)
- [x] **CHAT-02**: Smooth message entrance animation (fade-in + translate, 150-200ms)
- [x] **CHAT-03**: Stop generation button replaces Send during streaming
- [x] **CHAT-04**: Auto-resize textarea with Send on Enter, Shift+Enter for newline
- [x] **CHAT-05**: Hover actions on messages — copy, per-message timestamp
- [x] **CHAT-06**: Welcome/empty state with Fluent 2 card-style prompt suggestion chips

### Tool Panels

- [x] **TOOL-01**: Redesigned collapsible tool panels — chevron icon, status badge (done/error)
- [x] **TOOL-02**: Tool call elapsed time display ("Ran in 1.2s") — requires backend timestamp addition to SSE tool events
- [x] **TOOL-03**: Syntax-highlighted JSON with Fluent-aligned dark theme
- [x] **TOOL-04**: Per-panel copy button

### Sidebar

- [x] **SIDE-01**: Thread recency grouping — Today / Yesterday / This Week / Older
- [x] **SIDE-02**: Sidebar collapse to icon-only mode (CSS transition, localStorage persistence)
- [x] **SIDE-03**: Visual polish — spacing, active state, hover states, new-chat button (Compose icon)

### Profile Cards

- [x] **PROF-01**: Profile card visual alignment with Fluent 2 card component
- [x] **PROF-02**: Search result cards aligned with Fluent 2 list patterns

### Splash Page

- [x] **SPLA-01**: Redesigned login/splash page — professional landing with Fluent 2 aesthetic

### Accessibility

- [x] **A11Y-01**: Keyboard navigation with visible focus rings (WCAG AA 3:1 contrast)
- [x] **A11Y-02**: Logical tab order across all components

### Tech Debt

- [x] **DEBT-01**: Persist tool events to SQLite so historical messages retain tool panels
- [x] **DEBT-02**: Copy-to-clipboard on historical messages
- [x] **DEBT-03**: Fix 3 test regressions (description phrasing, tool count assertion)
- [x] **DEBT-04**: Remove get_user_photo_bytes() dead code
- [x] **DEBT-05**: Fix get_colleague_profile user_id schema description

## Future Requirements

Deferred to post-v1.2. Tracked but not in current roadmap.

### Feedback & Analytics

- **FEED-01**: Thumbs-up/down feedback on AI responses (needs POST /api/feedback endpoint + storage)
- **FEED-02**: Usage analytics dashboard (admin view — query log aggregation)

### Enhanced Navigation

- **NAV-01**: Thread search (requires search backend or client-side index)
- **NAV-02**: Conversation export as Markdown

### Enhanced Animations

- **ANIM-01**: Motion library (formerly Framer Motion) for complex entrance/exit/layout animations

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Typewriter / per-character animation | Artificial latency, frustrates fast readers — Copilot streams naturally |
| Emoji reactions on messages | Consumer chat pattern — undermines enterprise trust |
| Onboarding wizard / product tour | IT engineers don't want guided tours — let affordances speak |
| Sound effects on send/receive | No modern enterprise chat uses audio |
| Floating chat bubble / widget style | Support bot pattern — full-page layout is professional standard |
| File attachment upload UI | Not applicable to Exchange query domain |
| Model picker dropdown | Confuses enterprise users — single model, single experience |
| Animated mesh gradient background | Consumer AI marketing aesthetic — signals startup, not enterprise |
| Real-time multi-user collaboration | IT engineers investigate solo — adds WebSocket complexity for zero benefit |
| Chat export as PDF/Word | High implementation cost, low usage — copy-to-clipboard covers 95% |
| Mobile responsive layout | Desktop-only tool (1080p-1440p), no mobile requirement |
| "Powered by OpenAI" branding | Signals demo build, not production tool |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FRAME-01 | Phase 13 | Complete |
| FRAME-02 | Phase 13 | Complete |
| FRAME-03 | Phase 13 | Complete |
| FRAME-07 | Phase 13 | Complete |
| FRAME-04 | Phase 14 | Complete |
| FRAME-05 | Phase 14 | Complete |
| FRAME-06 | Phase 14 | Complete |
| FRAME-08 | Phase 14 → Phase 20 (fix) | Gap closure |
| DEBT-01 | Phase 14 | Complete |
| DEBT-02 | Phase 14 | Complete |
| DSGN-01 | Phase 15 | Complete |
| DSGN-02 | Phase 15 | Complete |
| DSGN-03 | Phase 15 | Complete |
| DSGN-04 | Phase 15 | Complete |
| CHAT-01 | Phase 16 | Complete |
| CHAT-02 | Phase 16 | Complete |
| CHAT-03 | Phase 16 → Phase 20 (fix) | Gap closure |
| CHAT-04 | Phase 16 | Complete |
| CHAT-05 | Phase 16 | Complete |
| CHAT-06 | Phase 16 | Complete |
| SIDE-01 | Phase 17 | Complete |
| SIDE-02 | Phase 17 | Complete |
| SIDE-03 | Phase 17 | Complete |
| TOOL-01 | Phase 17 | Complete |
| TOOL-02 | Phase 17 | Complete |
| TOOL-03 | Phase 17 | Complete |
| TOOL-04 | Phase 17 | Complete |
| PROF-01 | Phase 18 | Complete |
| PROF-02 | Phase 18 | Complete |
| SPLA-01 | Phase 18 | Complete |
| DEBT-03 | Phase 18 | Complete |
| DEBT-04 | Phase 18 | Complete |
| DEBT-05 | Phase 18 | Complete |
| A11Y-01 | Phase 19 | Complete |
| A11Y-02 | Phase 19 | Complete |

**Coverage:**
- v1.2 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-30 after Phase 20 gap closure creation*
