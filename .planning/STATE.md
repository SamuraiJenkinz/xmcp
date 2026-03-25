# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** v1.1 — Phase 11 complete, ready for Phase 12: Profile Card Frontend + System Prompt

## Current Position

Phase: 11 of 12 (MCP Tools + Photo Proxy)
Plan: 3 of 3 in current phase
Status: Phase 11 verified ✓ — ready for Phase 12 (Profile Card Frontend + System Prompt)
Last activity: 2026-03-24 — Completed Phase 11 (MCP Tools + Photo Proxy)

Progress: [███████████░] v1.0 complete, v1.1 Phases 10-11 done

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
- [RESOLVED — 2026-03-24]: Token layer (_get_token, _make_headers, _graph_request_with_retry) implemented. 10-02 complete.
- [RESOLVED — 2026-03-24]: search_users() and get_user_photo_bytes() implemented. 10-03 complete. Phase 10 done.
- [RESOLVED — 2026-03-24]: Phase 10 verification gap closed. 10 unit tests added for graph_client core ops. 10-04 complete.
- [RESOLVED — 2026-03-25]: get_user_profile() and get_user_photo_96() added to graph_client. search_colleagues and get_colleague_profile schemas in TOOL_DEFINITIONS. 11-01 complete.
- [RESOLVED — 2026-03-25]: _search_colleagues_handler and _get_colleague_profile_handler implemented in TOOL_DISPATCH (17 entries). asyncio.to_thread + lazy imports. 11-02 complete.
- [RESOLVED — 2026-03-25]: Flask /api/photo/<user_id> proxy route with TTL cache and SVG placeholder. @login_required protection. 11-03 complete. Phase 11 done.
- [Tech Debt — v1.0]: Tool events not persisted to SQLite — historical messages lose tool panels
- [Tech Debt — v1.0]: Copy button not rendered on historical messages

### Post-v1.0 Fixes (2026-03-24)

- Switched powershell.exe → pwsh.exe (PS7)
- Fixed env var propagation to child processes
- Fixed MCP subprocess env passing
- Fixed conversation pruning (8K buffer, prune after tool results, atomic group removal)
- Added start.py, deployed to usdf11v1784.mercer.com:5050

## Session Continuity

Last session: 2026-03-24T22:30Z
Stopped at: Phase 11 complete and verified — ready for Phase 12
Resume file: None
