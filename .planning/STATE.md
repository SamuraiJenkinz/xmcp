# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-01)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** v1.3 — Phase 21: App Role Access Control

## Current Position

Phase: 21 of 25 (App Role Access Control)
Plan: 1 of 2 complete
Status: In progress
Last activity: 2026-04-02 — Completed 21-01-PLAN.md (role_required decorator + route migration)

Progress: [█░░░░░░░░░░░░░░░░░░] 5% (v1.3 — 1/~20 plans)

## Performance Metrics

**Velocity:**
- v1.0: 35 plans in 4 days (2026-03-19 → 2026-03-22)
- v1.1: 9 plans in 3 days (2026-03-23 → 2026-03-25)
- v1.2: 22 plans in 4 days (2026-03-27 → 2026-03-30)
- Total shipped: 66 plans, 20 phases, 3 milestones

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

### Pending Todos

None.

### Blockers/Concerns

- Phase 21 has an admin-dependency blocker: Atlas.User App Role must be created in Entra admin center and IT engineers group assigned before end-to-end testing is possible
- Phase 25 (animations): motion + React 19 compat is MEDIUM confidence — spike npm install motion and a basic m.div render before committing to full animation scope
- CHATGPT_ENDPOINT not in AWS Secrets Manager pipeline (manually set as env var) — carried from v1.2

## Session Continuity

Last session: 2026-04-02
Stopped at: Completed 21-01-PLAN.md — role_required decorator and route migration complete
Resume file: None
