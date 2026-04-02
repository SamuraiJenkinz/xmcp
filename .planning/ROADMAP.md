# Roadmap: Exchange Infrastructure MCP Server (Atlas)

## Milestones

- ✅ **v1.0 MVP** - Phases 1-9 (shipped 2026-03-22)
- ✅ **v1.1 Colleague Lookup** - Phases 10-12 (shipped 2026-03-25)
- ✅ **v1.2 UI/UX Redesign** - Phases 13-20 (shipped 2026-03-30)
- 🚧 **v1.3 Access Control, Feedback, Search, Export, Animations** - Phases 21-25 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9) - SHIPPED 2026-03-22</summary>

Delivered complete Exchange management system: 15-tool MCP server, Flask chat app with Azure AD SSO, SQLite conversation persistence, polished UI with tool panels and dark mode.

35 plans across 9 phases. See MILESTONES.md for full detail.

</details>

<details>
<summary>✅ v1.1 Colleague Lookup (Phases 10-12) - SHIPPED 2026-03-25</summary>

Delivered Microsoft Graph API integration, two new MCP tools (search_colleagues, get_colleague_profile), secure photo proxy, and inline profile cards.

9 plans across 3 phases. See MILESTONES.md for full detail.

</details>

<details>
<summary>✅ v1.2 UI/UX Redesign (Phases 13-20) - SHIPPED 2026-03-30</summary>

Delivered full frontend rewrite to React 19 + Fluent UI v9 + Tailwind v4 with Microsoft Copilot aesthetic, 62 --atlas- design tokens, WCAG AA accessibility, dark/light mode, and polished chat interactions.

22 plans across 8 phases. See MILESTONES.md for full detail.

</details>

---

### 🚧 v1.3 Access Control, Feedback, Search, Export, Animations (In Progress)

**Milestone Goal:** Gate access to authorized IT engineers via Azure AD App Roles, add per-message thumbs up/down feedback, thread search in the sidebar, Markdown export for tickets, and motion entrance animations consistent with the Copilot aesthetic established in v1.2.

**Phase numbering:** Continues from v1.2 (phases 1-20 complete). New phases start at 21.

#### Phase 21: App Role Access Control

**Goal**: Only authorized IT engineers (holding the Atlas.User App Role) can access the application — all other authenticated users see a Fluent 2 access denied experience instead of the chat interface.

**Depends on**: Phase 20 (v1.2 shipped React app and AuthContext)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
1. A user authenticated to Azure AD but not assigned the Atlas.User role receives a 403 from /api/me and sees the AccessDenied component — not a loading spinner, not a white screen
2. A user with no session at all receives a 401 and is redirected to /login — the 403/401 paths are distinct in AuthContext and the React routing layer
3. The /chat/stream SSE endpoint and all /api/conversations routes return 403 (not 401) for an authenticated session that lacks the roles claim — no AI access through direct endpoint calls
4. An IT engineer who is correctly assigned Atlas.User sees no change in behavior — the app loads and functions identically to v1.2
5. The access denied page shows the user's own UPN with a one-click copy button and a mailto: link to the admin, so users know exactly who to contact and what identity to reference
**Plans:** 2 plans

Plans:
- [x] 21-01-PLAN.md — role_required decorator, session roles extraction, 403/401 response paths (backend)
- [x] 21-02-PLAN.md — AuthContext 403 state, AccessDenied component, AuthGuard routing (frontend)

---

#### Phase 22: Per-Message Feedback

**Goal**: IT engineers can vote thumbs up or down on any assistant message after it finishes streaming, and votes persist to SQLite against the user's identity for future analytics.

**Depends on**: Phase 21 (role_required must be applied to feedback endpoints)
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04, FEED-05, FEED-06, FEED-07
**Success Criteria** (what must be TRUE):
1. Thumbs up and thumbs down buttons appear on hover next to the copy button on every completed assistant message — buttons are absent while the SSE stream is active
2. Clicking a thumb button fills the icon (ThumbLikeFilled / ThumbDislikeFilled) immediately as optimistic UI, and the vote is persisted to SQLite on the server
3. Clicking the same button a second time retracts the vote — the icon returns to the unfilled variant and the record is removed from the database
4. A thumbs-down click opens a Fluent Popover with an optional freetext comment field — submitting the popover persists the comment alongside the vote
5. Screen readers hear "Feedback submitted" announced via an ARIA live region after any vote action
**Plans**: TBD

Plans:
- [x] 22-01-PLAN.md — feedback SQLite table schema, feedback Blueprint (POST/DELETE endpoints)
- [x] 22-02-PLAN.md — AssistantMessage feedback buttons, optimistic state, ARIA live region, Popover for comment

---

#### Phase 23: Thread Search

**Goal**: Users can find threads instantly by typing in the sidebar search box, and can perform full-text search across message content when a thread name alone is not enough.

**Depends on**: Phase 21 (search endpoint must be protected by role_required)
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-08
**Success Criteria** (what must be TRUE):
1. A search input with a clear button is visible at the top of the sidebar thread list; pressing Ctrl+K from anywhere in the app focuses it
2. Typing in the search box instantly filters the displayed thread list to titles that match — no network request, no delay, active thread not affected
3. When no threads match the typed filter, an empty state message is displayed rather than a blank list
4. Typing at least 2 characters and pausing 300ms triggers a backend FTS5 search across message content, returning matching threads with a snippet and a result count badge
5. Clicking any search result navigates to that thread
**Plans:** 2 plans

Plans:
- [x] 23-01-PLAN.md — FTS5 virtual table, sync triggers, backfill, search endpoint with user scoping
- [x] 23-02-PLAN.md — SearchInput component, client-side title filter, FTS5 results display, Ctrl+K shortcut

---

#### Phase 24: Conversation Export

**Goal**: IT engineers can download the active thread as a Markdown file for pasting into Jira/incident reports, with all tool call data included.

**Depends on**: Phase 21 (export endpoint must verify thread ownership and require role)
**Requirements**: EXPT-01, EXPT-02, EXPT-03, EXPT-04
**Success Criteria** (what must be TRUE):
1. An export button in the ChatPane header opens a Fluent Menu offering Markdown as a format choice
2. Clicking Markdown triggers a client-side download of a .md file containing the full conversation — user and assistant turns, plus tool panel data for Exchange queries
3. The downloaded filename includes the slugified thread name and the current date (e.g., dag-health-check-2026-04-01.md)
4. Attempting to export a thread belonging to another user returns 404 — thread ID enumeration does not expose other users' conversations
**Plans**: TBD

Plans:
- [ ] 24-01: export Blueprint, Markdown renderer, ownership check, Content-Disposition response
- [ ] 24-02: ChatPane export button, Fluent Menu, client-side Blob download trigger

---

#### Phase 25: Motion Animations

**Goal**: New messages and UI transitions have fluid entrance animations consistent with the Microsoft Copilot aesthetic, with full prefers-reduced-motion compliance.

**Depends on**: Phases 22, 23, 24 (component structure must be settled before applying motion wrappers; feedback button micro-interaction requires FEED to be complete)
**Requirements**: ANIM-01, ANIM-02, ANIM-03, ANIM-04, ANIM-05, ANIM-06
**Success Criteria** (what must be TRUE):
1. New assistant messages fade in and slide up over 200ms ease-out; new user messages do the same over 150ms — neither animates during active SSE streaming
2. The sidebar collapse/expand transition is a smooth CSS width change over 200-250ms ease-in-out rather than an instant snap
3. Clicking a feedback thumb button has a brief 100ms scale micro-interaction that communicates interactivity
4. All motion animations are absent for users with prefers-reduced-motion or OS-level "Reduce animations" enabled — the MotionConfig reducedMotion="user" wrapper handles this globally
**Plans**: TBD

Plans:
- [ ] 25-01: motion package install, LazyMotion + domAnimation setup, MotionConfig reducedMotion wrapper
- [ ] 25-02: message entrance animations, sidebar collapse transition, feedback button micro-interaction

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-9. MVP | v1.0 | 35/35 | Complete | 2026-03-22 |
| 10-12. Colleague Lookup | v1.1 | 9/9 | Complete | 2026-03-25 |
| 13-20. UI/UX Redesign | v1.2 | 22/22 | Complete | 2026-03-30 |
| 21. App Role Access Control | v1.3 | 2/2 | Complete | 2026-04-02 |
| 22. Per-Message Feedback | v1.3 | 2/2 | Complete | 2026-04-02 |
| 23. Thread Search | v1.3 | 2/2 | Complete | 2026-04-02 |
| 24. Conversation Export | v1.3 | 0/TBD | Not started | - |
| 25. Motion Animations | v1.3 | 0/TBD | Not started | - |
