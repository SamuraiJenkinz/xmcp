# Requirements: Atlas v1.3 — Access Control, Feedback, Search, Export, Animations

**Defined:** 2026-04-01
**Core Value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data

## v1.3 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Access Control

- [ ] **AUTH-01**: App requires Atlas.User App Role — unauthenticated users get 401, authenticated users without role get 403
- [ ] **AUTH-02**: Roles claim extracted from MSAL id_token_claims and stored in session on login
- [ ] **AUTH-03**: New `role_required` decorator replaces `login_required` on all protected routes
- [ ] **AUTH-04**: Access denied React component with Fluent 2 styling, explaining no access and showing contact instructions
- [ ] **AUTH-05**: Admin mailto: link and copy-own-UPN button on access denied page
- [ ] **AUTH-06**: AuthContext and AuthGuard distinguish 403 (not authorized) from 401 (not authenticated) with different UI paths
- [ ] **AUTH-07**: Existing sessions without roles claim handled gracefully at deploy (session flush or fallback)

### Feedback

- [ ] **FEED-01**: Thumbs up/down buttons on each assistant message, visible on hover alongside existing copy button
- [ ] **FEED-02**: Vote persisted to SQLite feedback table with (thread_id, message_index, user_id) composite key
- [ ] **FEED-03**: Toggle behavior — second click on same button retracts vote
- [ ] **FEED-04**: Buttons excluded during streaming — appear only after done SSE event
- [ ] **FEED-05**: Optional freetext comment via Fluent Popover on thumbs-down
- [ ] **FEED-06**: ARIA live region announces "Feedback submitted" to screen readers
- [ ] **FEED-07**: Feedback table schema designed for future admin analytics queries

### Search

- [ ] **SRCH-01**: Search input at top of sidebar thread list with clear button
- [ ] **SRCH-02**: Instant client-side title filter as user types — does not affect active thread
- [ ] **SRCH-03**: Empty state when no threads match filter
- [ ] **SRCH-04**: SQLite FTS5 full-text search across message content via backend endpoint
- [ ] **SRCH-05**: Search results show thread name + message snippet with result count badge
- [ ] **SRCH-06**: Click search result navigates to thread
- [ ] **SRCH-07**: Debounced FTS5 search (300ms, 2-char minimum)
- [ ] **SRCH-08**: Ctrl+K keyboard shortcut to focus search input

### Export

- [ ] **EXPT-01**: Markdown export of current thread with tool panel data included
- [ ] **EXPT-02**: Export button in ChatPane header with Fluent Menu for format selection
- [ ] **EXPT-03**: Filename includes slugified thread name and date
- [ ] **EXPT-04**: Client-side Blob download — no server round-trip for Markdown

### Animations

- [ ] **ANIM-01**: New assistant message entrance animation (fade-in + upward translate, 200ms ease-out)
- [ ] **ANIM-02**: New user message entrance animation (same pattern, 150ms)
- [ ] **ANIM-03**: All animations wrapped in `prefers-reduced-motion: no-preference` media query
- [ ] **ANIM-04**: No animation during SSE streaming — only on message mount
- [ ] **ANIM-05**: Sidebar collapse/expand width transition (200-250ms ease-in-out, pure CSS)
- [ ] **ANIM-06**: Feedback button scale micro-interaction on click (100ms)

## Future Requirements

Deferred to later milestones.

### Feedback

- **FEED-08**: Admin analytics dashboard for feedback data
- **FEED-09**: Feedback export for reporting

### Search

- **SRCH-09**: Highlight matched search term in FTS5 result snippets
- **SRCH-10**: Scroll-to-message within thread after search result click

### Export

- **EXPT-05**: JSON export of current thread (raw structured data)
- **EXPT-06**: Copy full thread to clipboard (paste into Confluence/Jira)
- **EXPT-07**: PDF export (requires server-side rendering)

### Animations

- **ANIM-07**: Tool panel smooth height animation (requires ToolPanel refactor away from native `<details>`)
- **ANIM-08**: Thread rename highlight flash in sidebar

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multiple role tiers (admin vs. read-only) | All current operations are read-only; single Atlas.User role sufficient |
| Group-membership-claim-based gating | Token overage risk with 80K+ users; App Roles chosen instead |
| Stars or multi-level rating | Binary thumbs sufficient for infrastructure tool |
| Mandatory comment before thumbs-down submits | Friction eliminates most feedback |
| Fuzzy or semantic search | Requires embeddings/external index; FTS5 prefix match is correct for v1 |
| Search replacing sidebar thread list | Users need both simultaneously |
| PDF/HTML/Word export | Heavy dependencies for marginal value; Markdown covers the use case |
| Multi-thread batch export | Use case is single-thread for tickets/reports |
| Typewriter per-character animation | Explicitly excluded in PROJECT.md |
| Loading skeleton animations | Thread list loads in ~50ms; skeleton would flash |
| Historical message entrance animations | Animating 20 messages on thread switch is disorienting |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Pending | Pending |
| AUTH-02 | Pending | Pending |
| AUTH-03 | Pending | Pending |
| AUTH-04 | Pending | Pending |
| AUTH-05 | Pending | Pending |
| AUTH-06 | Pending | Pending |
| AUTH-07 | Pending | Pending |
| FEED-01 | Pending | Pending |
| FEED-02 | Pending | Pending |
| FEED-03 | Pending | Pending |
| FEED-04 | Pending | Pending |
| FEED-05 | Pending | Pending |
| FEED-06 | Pending | Pending |
| FEED-07 | Pending | Pending |
| SRCH-01 | Pending | Pending |
| SRCH-02 | Pending | Pending |
| SRCH-03 | Pending | Pending |
| SRCH-04 | Pending | Pending |
| SRCH-05 | Pending | Pending |
| SRCH-06 | Pending | Pending |
| SRCH-07 | Pending | Pending |
| SRCH-08 | Pending | Pending |
| EXPT-01 | Pending | Pending |
| EXPT-02 | Pending | Pending |
| EXPT-03 | Pending | Pending |
| EXPT-04 | Pending | Pending |
| ANIM-01 | Pending | Pending |
| ANIM-02 | Pending | Pending |
| ANIM-03 | Pending | Pending |
| ANIM-04 | Pending | Pending |
| ANIM-05 | Pending | Pending |
| ANIM-06 | Pending | Pending |

**Coverage:**
- v1.3 requirements: 25 total
- Mapped to phases: 0
- Unmapped: 25 ⚠️

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after initial definition*
