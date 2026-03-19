# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** Phase 1 — Exchange Client Foundation

## Current Position

Phase: 1 of 9 (Exchange Client Foundation)
Plan: 1 of 5 in current phase
Status: In progress
Last activity: 2026-03-19 — Completed 01-01-PLAN.md (project scaffold + async PowerShell runner)

Progress: [█░░░░░░░░░] 3% (1/35 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 37 min
- Total execution time: 0.6 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-exchange-client-foundation | 1/5 | 37 min | 37 min |

**Recent Trend:**
- Last 5 plans: 01-01 (37 min)
- Trend: baseline

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
- [01-01]: Use -EncodedCommand (Base64 UTF-16LE) not -Command for PowerShell — prevents cp1252 corruption of non-ASCII script args on Windows
- [01-01]: Auto-prepend _PS_PREAMBLE inside run_ps() so all callers get UTF-8 stdout by default — callers must not skip this preamble
- [01-01]: proc.communicate() not proc.wait() everywhere — prevents pipe-buffer deadlock on large output
- [01-01]: uv binary at C:\Users\taylo\uv_install\uv.exe — not in system PATH; run via full path or add to PATH

### Pending Todos

None.

### Blockers/Concerns

- [Phase 1]: Kerberos/RBCD AD configuration requires hands-on validation with MMC Active Directory team — cannot be resolved from code. Use Basic Auth fallback for v1 demo. Start KCD engagement early for v2.
- [Phase 1]: Verify Exchange throttling policy for service account before Phase 3 tool testing (run Get-ThrottlingPolicyAssociation). An overly restrictive policy produces intermittent failures that look like code bugs.
- [Phase 7]: Flask vs FastAPI decision is documented as resolved (Flask + thread executor) — confirm before Phase 7 planning begins.
- [General]: MMC Azure OpenAI gateway API version pinned at 2023-05-15 — verify with MMC CTS before attempting any upgrade.
- [Env]: uv not in system PATH; currently installed at C:\Users\taylo\uv_install\uv.exe — consider adding to PATH before Plan 02 to simplify dev workflow.

## Session Continuity

Last session: 2026-03-19T20:04:24Z
Stopped at: Completed 01-01-PLAN.md — project scaffold and async PowerShell runner
Resume file: None
