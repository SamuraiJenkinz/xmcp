# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** Phase 1 — Exchange Client Foundation

## Current Position

Phase: 1 of 9 (Exchange Client Foundation)
Plan: 0 of 5 in current phase
Status: Ready to plan
Last activity: 2026-03-19 — Roadmap created (9 phases, 35 requirements mapped)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Flask 3.x + Waitress chosen over FastAPI — run async PowerShell calls in thread pool via run_in_executor (see SUMMARY.md Conflicts)
- [Pre-Phase 1]: Basic Auth service account for v1 — Kerberos Constrained Delegation deferred to v2 (requires MMC AD team engagement)
- [Pre-Phase 1]: Per-call PSSession, no pooling — accept 2-4s latency; benchmark before optimizing
- [Pre-Phase 1]: SQLite for conversation persistence — zero ops, correct for <100 concurrent users
- [Pre-Phase 1]: Official mcp SDK (not fastmcp) — stdio transport for v1

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1]: Kerberos/RBCD AD configuration requires hands-on validation with MMC Active Directory team — cannot be resolved from code. Use Basic Auth fallback for v1 demo. Start KCD engagement early for v2.
- [Phase 1]: Verify Exchange throttling policy for service account before Phase 3 tool testing (run Get-ThrottlingPolicyAssociation). An overly restrictive policy produces intermittent failures that look like code bugs.
- [Phase 7]: Flask vs FastAPI decision is documented as resolved (Flask + thread executor) — confirm before Phase 7 planning begins.
- [General]: MMC Azure OpenAI gateway API version pinned at 2023-05-15 — verify with MMC CTS before attempting any upgrade.

## Session Continuity

Last session: 2026-03-19
Stopped at: Roadmap created — 9 phases, 35/35 v1 requirements mapped
Resume file: None
