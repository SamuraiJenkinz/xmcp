# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** v1.1 — Phase 10: Graph Client Foundation

## Current Position

Phase: 10 of 12 (Graph Client Foundation)
Plan: 1 of 3 in current phase (complete)
Status: In progress — Plan 01 complete, ready for Plan 02
Last activity: 2026-03-24 — Completed 10-01-PLAN.md (admin consent confirmed, all tasks done)

Progress: [█████████░░░] v1.0 complete, v1.1 starting Phase 10

## Performance Metrics

**Velocity:**
- Total plans completed: 35 (v1.0)
- Total execution time: ~4 days (2026-03-19 → 2026-03-22)
- Git commits: 139

**By Phase (v1.0):**

| Phase | Plans | Completed |
|-------|-------|-----------|
| 01-exchange-client-foundation | 4/4 | 2026-03-19 |
| 02-mcp-server-scaffold | 3/3 | 2026-03-19 |
| 03-mailbox-tools | 3/3 | 2026-03-20 |
| 04-dag-and-database-tools | 3/3 | 2026-03-20 |
| 05-mail-flow-and-security-tools | 5/5 | 2026-03-20 |
| 06-hybrid-tools | 2/2 | 2026-03-20 |
| 07-chat-app-core | 6/6 | 2026-03-21 |
| 08-conversation-persistence | 3/3 | 2026-03-22 |
| 09-ui-polish | 4/4 | 2026-03-22 |

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table with outcomes.

Key v1.1 decision: Use `msal` + `requests` directly — `msgraph-sdk` rejected (7 new transitive packages for two REST endpoints, already have both deps).

### Pending Todos

None.

### Blockers/Concerns

- [RESOLVED — 2026-03-24]: Admin consent for User.Read.All and ProfilePhoto.Read.All granted. 10-01 complete.
- [Tech Debt — v1.0]: Tool events not persisted to SQLite — historical messages lose tool panels
- [Tech Debt — v1.0]: Copy button not rendered on historical messages

### Post-v1.0 Fixes (2026-03-24)

- Switched powershell.exe → pwsh.exe (PS7)
- Fixed env var propagation to child processes
- Fixed MCP subprocess env passing
- Fixed conversation pruning (8K buffer, prune after tool results, atomic group removal)
- Added start.py, deployed to usdf11v1784.mercer.com:5050

## Session Continuity

Last session: 2026-03-24
Stopped at: 10-01-PLAN.md complete — all tasks done, admin consent confirmed
Resume file: None
