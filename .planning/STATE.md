# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** Phase 3 in progress — plan 01 complete (get_mailbox_stats)

## Current Position

Phase: 3 of 9 (Mailbox Tools) — In progress
Plan: 1 of 3 in phase 3 complete
Status: In progress
Last activity: 2026-03-20 — Completed 03-01-PLAN.md (helpers + get_mailbox_stats handler, 19 tests passing)

Progress: [████░░░░░░] 23% (8/35 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: ~10 min
- Total execution time: ~69 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-exchange-client-foundation | 4/4 | ~50 min | 12 min |
| 02-mcp-server-scaffold | 3/3 | 15 min | 5 min |
| 03-mailbox-tools | 1/3 | ~4 min | 4 min |

**Recent Trend:**
- Last 5 plans: 02-01 (7 min), 02-02 (4 min), 02-03 (4 min), 03-01 (4 min)
- Trend: Well-scoped implementation plans executing very fast

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Flask 3.x + Waitress chosen over FastAPI — run async PowerShell calls in thread pool via run_in_executor
- [Pre-Phase 1]: Per-call PSSession, no pooling — accept 2-4s latency; benchmark before optimizing
- [Pre-Phase 1]: SQLite for conversation persistence — zero ops, correct for <100 concurrent users
- [Pre-Phase 1]: Official mcp SDK (not fastmcp) — stdio transport for v1
- [01-01]: Use -EncodedCommand (Base64 UTF-16LE) not -Command for PowerShell — prevents cp1252 corruption
- [01-01]: Auto-prepend _PS_PREAMBLE inside run_ps() — all callers get UTF-8 stdout by default
- [01-01]: proc.communicate() not proc.wait() — prevents pipe-buffer deadlock
- [01-02]: System default DNS resolver only — no custom nameserver configuration
- [01-02]: Negative-cache NXDOMAIN/NoAnswer for 300s
- [01-03]: Non-retryable patterns checked case-insensitively — raise immediately, no retry
- [01-03]: Empty string from run_ps() returns [] from run_cmdlet()
- [01-04]: Interactive auth (browser popup) as default, CBA as optional fallback — user requested removal of certificate requirement
- [01-04]: Auth mode auto-detected: AZURE_CERT_THUMBPRINT present → CBA, absent → interactive
- [02-01]: anyio.run(main) as entry point — mcp SDK uses anyio internally; asyncio.run works but anyio.run is idiomatic
- [02-01]: Human-readable log format over structured JSON — internal admin tool, terminal readability preferred at this stage
- [02-01]: raise RuntimeError(sanitized) from None in call_tool — SDK's _make_error_result(str(e)) creates isError=True with the clean message
- [02-01]: SIGTERM handler in try/except — Windows may not support SIGTERM registration; wrap for compatibility
- [02-02]: NotImplementedError from stubs re-raised as plain RuntimeError (no _sanitize_error) — stub message already clean
- [02-02]: Startup banner uses len(TOOL_DEFINITIONS) directly — avoids async call, simpler
- [02-02]: TYPE_CHECKING guard on ExchangeClient in tools.py
- [02-03]: Does NOT clause cross-references sibling tool by name — makes disambiguation machine-readable
- [02-03]: Single-quoted example queries in descriptions as LLM trigger phrase convention
- [02-03]: "PowerShell" forbidden in tool descriptions — descriptions are user-facing, not admin-facing — avoids circular import; client passed at call time
- [03-01]: last_logon passed through as-is from Exchange — no date parsing; LLM reads /Date(ms)/ format
- [03-01]: total_size_bytes included alongside human-friendly total_size — LLM needs raw bytes for quota % calculation
- [03-01]: Quota values passed as strings (not parsed) — Exchange returns full natural language strings; no parsing needed
- [03-01]: test_call_tool_not_implemented_raises updated to use search_mailboxes stub — get_mailbox_stats is now real

### Pending Todos

None.

### Blockers/Concerns

- [Phase 1]: Verify Exchange throttling policy for service account before Phase 3 tool testing
- [Phase 7]: Flask vs FastAPI decision is documented as resolved (Flask + thread executor) — confirm before Phase 7
- [General]: MMC Azure OpenAI gateway API version pinned at 2023-05-15 — verify with MMC CTS before upgrade

## Session Continuity

Last session: 2026-03-20
Stopped at: Completed 03-01-PLAN.md — helpers + get_mailbox_stats handler, 75 tests passing (3 pre-existing exchange integration failures)
Resume file: None
