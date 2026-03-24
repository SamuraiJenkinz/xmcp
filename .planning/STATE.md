# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-22)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** v1.1 — Colleague Lookup via Microsoft Graph API

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements for v1.1
Last activity: 2026-03-24 — Milestone v1.1 started

Progress: Defining requirements

## Performance Metrics

**Velocity:**
- Total plans completed: 35
- Total execution time: ~4 days (2026-03-19 → 2026-03-22)
- Git commits: 139

**By Phase:**

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

### Pending Todos

None.

### Blockers/Concerns

- [Tech Debt]: Tool events not persisted to SQLite — historical messages lose tool panels
- [Tech Debt]: Copy button not rendered on historical messages

### Post-v1.0 Fixes (2026-03-24)

- Switched powershell.exe → pwsh.exe (PS7) for cleaner error handling
- Fixed env var propagation to child processes (inject CBA creds into PS script directly)
- Fixed MCP subprocess env passing (env=dict(os.environ) in StdioServerParameters)
- Fixed conversation pruning: increased safety buffer to 8K, prune after tool results, atomic tool group removal
- Added start.py for simple HTTPS startup
- Deployed to usdf11v1784.mercer.com:5050 with internal PKI cert + Azure AD SSO
- Created auth-workflow.html documentation

## Session Continuity

Last session: 2026-03-24
Stopped at: Defining v1.1 requirements and roadmap
Resume file: None
