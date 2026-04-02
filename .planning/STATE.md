# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-01)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** v1.3 — Phase 23 complete, Thread Search fully shipped (FTS5 backend + frontend search UI)

## Current Position

Phase: 23 of 25 complete (Thread Search)
Plan: 23-02 of 2 complete — Phase 23 done
Status: Phase complete
Last activity: 2026-04-02 — Completed 23-02-PLAN.md (frontend search: useDebounce, searchThreads, SearchInput, ThreadList wired)

Progress: [█████░░░░░░░░░░░░░░] 25% (v1.3 — 7/~10 plans)

## Performance Metrics

**Velocity:**
- v1.0: 35 plans in 4 days (2026-03-19 → 2026-03-22)
- v1.1: 9 plans in 3 days (2026-03-23 → 2026-03-25)
- v1.2: 22 plans in 4 days (2026-03-27 → 2026-03-30)
- v1.3: 7 plans in 1 day (2026-04-02, Phases 21-23 complete)
- Total shipped: 73 plans, 23 complete phases, 3 milestones

## Accumulated Context

### Decisions

(Full decision log in PROJECT.md Key Decisions table)

- App Roles chosen over groupMembershipClaims for access gating (no overage, no raw GUIDs)
- Feedback key: (thread_id, message_idx) — append-only assumption, document in code
- Feedback vote field: TEXT ('up'/'down'/null) over INTEGER — more readable in analytics queries
- Export: Markdown client-side Blob, JSON server-side Response (hybrid per research resolution)
- FTS5 tokenizer: unicode61 only — porter over-stems Exchange technical terms (DAGHealth, etc.)
- Animation: LazyMotion + domAnimation from the start; no framer-motion package; MotionConfig reducedMotion="user" required before any animation ships
- role_required is the canonical route decorator (login_required retained but unused on routes) — 21-01
- 403 JSON includes upn field so frontend can display the blocked user identity — 21-01
- /api/me returns roles array for authorized users, enabling frontend role introspection — 21-01
- AuthStatus discriminated union replaces loading boolean — compiler enforces all branches are handled — 21-02
- migrate_db() runs on every startup in app context — idempotent DDL, existing DBs gain feedback table on next restart — 22-01
- POST vote=null retracts (same DELETE path) — one POST endpoint for both set and clear — 22-01
- Comment truncated 500 chars at API layer, None if empty — DB column unconstrained — 22-01
- ThumbLike16* icons not available from main @fluentui/react-icons entry; bundleIcon uses standard-sized Filled/Regular variants — 22-02
- handleCommentDismiss persists thumbs-down without comment on Popover close — avoids silent vote loss — 22-02
- error status on /api/me redirects to /login (network failure indistinguishable from session expiry) — 21-02
- AccessDenied renders before ThreadProvider/ChatProvider to prevent cascading 403s — 21-02
- SSE 401/403 triggers window.location.reload() so AuthGuard re-evaluates rather than surfacing error toast — 21-02
- INSERT OR IGNORE backfill (not DELETE+INSERT) for FTS idempotency — prevents clearing existing rows on restart — 23-01
- DELETE+INSERT in sync triggers (not FTS content table) — simpler with group_concat, correct for single-row-per-thread — 23-01
- try/except on FTS MATCH execute — malformed input returns [] not 500, consistent UX — 23-01
- _build_fts5_query quotes each token individually — neutralises bare AND/OR/NOT operators — 23-01
- SearchBox ref forwarded to underlying input directly — confirmed ForwardRefComponent<SearchBoxProps> — 23-02
- Client-side filter feeds groupThreadsByRecency (active thread not pinned, disappears if no match) — 23-02
- Ctrl+K uses setTimeout(0) deferred focus when expanding sidebar — ensures DOM update before focus — 23-02
- Cancelled flag for FTS fetch cleanup (not AbortController) — simpler for single non-streaming GET — 23-02

### Pending Todos

None.

### Blockers/Concerns

- Phase 21 human testing blocked on admin: Atlas.User App Role must be created in Entra admin center and IT engineers group assigned
- Phase 25 (animations): motion + React 19 compat is MEDIUM confidence — spike npm install motion and a basic m.div render before committing to full animation scope
- CHATGPT_ENDPOINT not in AWS Secrets Manager pipeline (manually set as env var) — carried from v1.2

## Session Continuity

Last session: 2026-04-02
Stopped at: Completed 23-02-PLAN.md — Thread Search phase fully complete
Resume file: None
