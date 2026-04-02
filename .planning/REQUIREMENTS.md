# Requirements: Atlas v1.3 — Access Control, Feedback, Search, Export, Animations

**Defined:** 2026-04-01
**Core Value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data

## v1.3 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Access Control

- [x] **AUTH-01**: App requires Atlas.User App Role — unauthenticated users get 401, authenticated users without role get 403
- [x] **AUTH-02**: Roles claim extracted from MSAL id_token_claims and stored in session on login
- [x] **AUTH-03**: New `role_required` decorator replaces `login_required` on all protected routes
- [x] **AUTH-04**: Access denied React component with Fluent 2 styling, explaining no access and showing contact instructions
- [x] **AUTH-05**: Admin mailto: link and copy-own-UPN button on access denied page
- [x] **AUTH-06**: AuthContext and AuthGuard distinguish 403 (not authorized) from 401 (not authenticated) with different UI paths
- [x] **AUTH-07**: Existing sessions without roles claim handled gracefully at deploy (session flush or fallback)

### Feedback

- [x] **FEED-01**: Thumbs up/down buttons on each assistant message, visible on hover alongside existing copy button
- [x] **FEED-02**: Vote persisted to SQLite feedback table with (thread_id, message_index, user_id) composite key
- [x] **FEED-03**: Toggle behavior — second click on same button retracts vote
- [x] **FEED-04**: Buttons excluded during streaming — appear only after done SSE event
- [x] **FEED-05**: Optional freetext comment via Fluent Popover on thumbs-down
- [x] **FEED-06**: ARIA live region announces "Feedback submitted" to screen readers
- [x] **FEED-07**: Feedback table schema designed for future admin analytics queries

### Search

- [x] **SRCH-01**: Search input at top of sidebar thread list with clear button
- [x] **SRCH-02**: Instant client-side title filter as user types — does not affect active thread
- [x] **SRCH-03**: Empty state when no threads match filter
- [x] **SRCH-04**: SQLite FTS5 full-text search across message content via backend endpoint
- [x] **SRCH-05**: Search results show thread name + message snippet with result count badge
- [x] **SRCH-06**: Click search result navigates to thread
- [x] **SRCH-07**: Debounced FTS5 search (300ms, 2-char minimum)
- [x] **SRCH-08**: Ctrl+K keyboard shortcut to focus search input

### Export

- [x] **EXPT-01**: Markdown export of current thread with tool panel data included
- [x] **EXPT-02**: Export button in ChatPane header with Fluent Menu for format selection
- [x] **EXPT-03**: Filename includes slugified thread name and date
- [x] **EXPT-04**: Client-side Blob download — no server round-trip for Markdown

### Animations

- [x] **ANIM-01**: New assistant message entrance animation (fade-in + upward translate, 200ms ease-out)
- [x] **ANIM-02**: New user message entrance animation (same pattern, 150ms)
- [x] **ANIM-03**: All animations wrapped in `prefers-reduced-motion: no-preference` media query
- [x] **ANIM-04**: No animation during SSE streaming — only on message mount
- [x] **ANIM-05**: Sidebar collapse/expand width transition (200-250ms ease-in-out, pure CSS)
- [x] **ANIM-06**: Feedback button scale micro-interaction on click (100ms)

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
| AUTH-01 | Phase 21 | Complete |
| AUTH-02 | Phase 21 | Complete |
| AUTH-03 | Phase 21 | Complete |
| AUTH-04 | Phase 21 | Complete |
| AUTH-05 | Phase 21 | Complete |
| AUTH-06 | Phase 21 | Complete |
| AUTH-07 | Phase 21 | Complete |
| FEED-01 | Phase 22 | Complete |
| FEED-02 | Phase 22 | Complete |
| FEED-03 | Phase 22 | Complete |
| FEED-04 | Phase 22 | Complete |
| FEED-05 | Phase 22 | Complete |
| FEED-06 | Phase 22 | Complete |
| FEED-07 | Phase 22 | Complete |
| SRCH-01 | Phase 23 | Complete |
| SRCH-02 | Phase 23 | Complete |
| SRCH-03 | Phase 23 | Complete |
| SRCH-04 | Phase 23 | Complete |
| SRCH-05 | Phase 23 | Complete |
| SRCH-06 | Phase 23 | Complete |
| SRCH-07 | Phase 23 | Complete |
| SRCH-08 | Phase 23 | Complete |
| EXPT-01 | Phase 24 | Complete |
| EXPT-02 | Phase 24 | Complete |
| EXPT-03 | Phase 24 | Complete |
| EXPT-04 | Phase 24 | Complete |
| ANIM-01 | Phase 25 | Complete |
| ANIM-02 | Phase 25 | Complete |
| ANIM-03 | Phase 25 | Complete |
| ANIM-04 | Phase 25 | Complete |
| ANIM-05 | Phase 25 | Complete |
| ANIM-06 | Phase 25 | Complete |

**Coverage:**
- v1.3 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after roadmap creation — all 25 requirements mapped*
