# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** Phase 5 in progress — check_mail_flow handler complete; 4 more mail flow + security tools remain

## Current Position

Phase: 5 of 9 (Mail Flow and Security Tools) — In progress
Plan: 1 of 5 in phase 5 complete
Status: In progress
Last activity: 2026-03-20 — Completed 05-01-PLAN.md — check_mail_flow handler, 10 new tests, 138 passing (3 pre-existing integration failures)

Progress: [████░░░░░░] 40% (14/35 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: ~6 min
- Total execution time: ~80 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-exchange-client-foundation | 4/4 | ~50 min | 12 min |
| 02-mcp-server-scaffold | 3/3 | 15 min | 5 min |
| 03-mailbox-tools | 3/3 | ~11 min | 4 min |
| 04-dag-and-database-tools | 3/3 | ~14 min | 5 min |
| 05-mail-flow-and-security-tools | 1/5 | 3 min | 3 min |

**Recent Trend:**
- Last 5 plans: 04-01 (3 min), 04-02 (5 min), 04-03 (6 min), 05-01 (3 min)
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
- [03-02]: ANR trailing wildcard stripped before passing to -Anr — implicit prefix matching
- [03-02]: Database not-found returns empty result (not error) — search finding nothing is valid
- [03-02]: RecipientTypeDetails passed unquoted — it is a PowerShell enum parameter
- [03-02]: test_call_tool_not_implemented_raises updated to use list_dag_members stub — search_mailboxes is now real
- [03-03]: System account filtering in PowerShell Where-Object, not Python — reduces data transferred
- [03-03]: via_group always null — Get-MailboxPermission shows IsInherited but not which group caused it
- [03-03]: SendAs display_name always null — Get-RecipientPermission has no display name field
- [03-03]: GrantSendOnBehalfTo identity returned as-is (DN/UPN) — resolving would require N extra Get-Recipient calls
- [04-01]: dag_name functionally required despite schema required:[] — raise RuntimeError before any Exchange call
- [04-01]: Unreachable servers produce error entry with null fields — partial results pattern, not tool failure
- [04-01]: @() wrapper on ForEach-Object projection forces array output for single-member DAGs
- [04-01]: .ToString() on ADObjectId/ADSite/ServerVersion objects for plain string representation
- [04-01]: Active DB count = Status=="Mounted"; everything else is passive
- [04-01]: test_call_tool_not_implemented_raises updated to get_dag_health — list_dag_members is now real
- [04-02]: No -Status flag on Get-DatabaseAvailabilityGroup in get_dag_health — only need member names, saves Exchange round-trip
- [04-02]: is_mounted derived from Status == "Mounted" in handler — cleaner API, no raw status string interpretation needed by LLM
- [04-02]: Queue lengths as raw integers, no threshold interpretation — context-dependent meaning, LLM interprets
- [04-02]: Content index state passed as-is (Healthy/Crawling/Failed/etc.) — all values meaningful as strings
- [04-02]: test_call_tool_not_implemented_raises updated to use get_database_copies — get_dag_health is now real
- [04-03]: Activation preference from Get-MailboxDatabase (authoritative), not Get-MailboxDatabaseCopyStatus (known bug)
- [04-03]: Both dict and list ActivationPreference serialization formats handled (Exchange version-dependent)
- [04-03]: Zero copies raises RuntimeError (abnormal database state, not valid empty result)
- [04-03]: test_call_tool_not_implemented_raises updated to use check_mail_flow — get_database_copies is now real
- [05-01]: check_mail_flow is config-based route analysis only — no test messages sent, safe for production use
- [05-01]: Internal routing check uses accepted domains set membership; wildcard/subdomain connectors not checked for internal
- [05-01]: AddressSpace parsing: strip "SMTP:" prefix and ";cost" suffix before domain comparison
- [05-01]: Enabled-only connector filtering before domain matching — Enabled:False connectors skipped
- [05-01]: routing_type=internal takes precedence over connector matching when recipient domain is accepted
- [05-01]: test_call_tool_not_implemented_raises updated to get_transport_queues — check_mail_flow is now real

### Pending Todos

None.

### Blockers/Concerns

- [Phase 1]: Verify Exchange throttling policy for service account before Phase 3 tool testing
- [Phase 7]: Flask vs FastAPI decision is documented as resolved (Flask + thread executor) — confirm before Phase 7
- [General]: MMC Azure OpenAI gateway API version pinned at 2023-05-15 — verify with MMC CTS before upgrade

## Session Continuity

Last session: 2026-03-20T17:49:22Z
Stopped at: Completed 05-01-PLAN.md — check_mail_flow handler, 10 new tests, 138 passing (3 pre-existing exchange integration failures)
Resume file: None
