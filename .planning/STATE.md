# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data
**Current focus:** Phase 7 Chat App Core — In progress (1/6 plans complete)

## Current Position

Phase: 7 of 9 (Chat App Core) — In progress
Plan: 1 of 6 in phase 7 complete
Status: In progress
Last activity: 2026-03-21 — Completed 07-01-PLAN.md: Flask scaffold with sessions, secrets, templates, static files

Progress: [█████░░░░░] 60% (21/35 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 18
- Average duration: ~6 min
- Total execution time: ~80 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-exchange-client-foundation | 4/4 | ~50 min | 12 min |
| 02-mcp-server-scaffold | 3/3 | 15 min | 5 min |
| 03-mailbox-tools | 3/3 | ~11 min | 4 min |
| 04-dag-and-database-tools | 3/3 | ~14 min | 5 min |
| 05-mail-flow-and-security-tools | 5/5 | 16 min | 3 min |
| 06-hybrid-tools | 2/2 | 50 min | 25 min |
| 07-chat-app-core | 1/6 | 4 min | 4 min |

**Recent Trend:**
- Last 5 plans: 04-03 (6 min), 05-01 (3 min), 06-01 (25 min), 06-02 (25 min), 07-01 (4 min)
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
- [05-02]: Return ALL queues — over_threshold boolean flags backlogs, not a filter; LLM needs full queue context
- [05-02]: Two-step query: Get-TransportService discovery then per-server Get-Queue -Server (no all-server mode in Get-Queue)
- [05-02]: server_name shortcut skips Get-TransportService when caller targets specific server
- [05-02]: test_call_tool_not_implemented_raises updated to get_smtp_connectors — get_transport_queues is now real
- [05-03]: connector_type defaults to "all" — returns both send and receive, most informative for LLM
- [05-03]: Invalid connector_type raises RuntimeError immediately before any Exchange call — fail fast
- [05-03]: MaxMessageSize serialized as str(val) if val else None — ByteQuantifiedSize renders as "25 MB (26,214,400 bytes)"
- [05-03]: Multi-valued Bindings/RemoteIPRanges use ForEach-Object { $_.ToString() } — same lesson as Phase 4 ActivationPreference
- [05-03]: test_call_tool_not_implemented_raises updated to use get_dkim_config stub — get_smtp_connectors is now real
- [05-04]: CNAME cache key prefix "CNAME:{name}" prevents collision with TXT cache entries in shared _cache dict
- [05-04]: Sentinel object() per-call to distinguish DNS error (match=null) from NXDOMAIN/not-published (match=false)
- [05-04]: Three-state DNS match: True (published==expected), False (mismatch or expected-but-missing), None (DNS error)
- [05-04]: Expected-but-NXDOMAIN = False (definite failure); DNS LookupError = None (unknown — don't claim failure)
- [05-04]: dns_utils imported at module level in tools.py to enable patch('exchange_mcp.tools.dns_utils.get_cname_record') in tests
- [05-04]: test_call_tool_not_implemented_raises updated to use get_dmarc_status stub — get_dkim_config is now real
- [05-05]: get_dmarc_status does NOT check client is None — pure DNS tool works without Exchange connection
- [05-05]: get_dmarc_status raises RuntimeError on LookupError — DNS errors surface as user-readable errors
- [05-05]: check_mobile_devices returns ALL devices including stale partnerships — LLM/user decides relevance
- [05-05]: Empty device list is valid result (not an error) — user simply has no mobile partnerships
- [05-05]: test_call_tool_not_implemented_raises updated to get_hybrid_config (Phase 6 stub)
- [06-01]: get_migration_batches removed — out of MMC scope; tool count now 15 (14 Exchange + ping)
- [06-01]: get_hybrid_config composite handler: 5 sequential cmdlets (org rel, fed trust, intra-org, avail addr, hybrid send)
- [06-01]: Per-section independent error handling — partial Exchange failure yields {"error": "..."} for that section only
- [06-01]: FederationTrust X509Certificate2 projected to scalar strings in PowerShell (Thumbprint, Subject, NotAfter ISO-8601)
- [06-01]: MultiValuedProperty fields projected with ForEach-Object ToString() — same pattern as Phase 4/5
- [06-01]: test_call_tool_not_implemented_raises updated to get_connector_status (last remaining stub)
- [06-02]: get_connector_status identifies hybrid send connectors by CloudServicesMailEnabled eq true
- [06-02]: get_connector_status identifies hybrid receive connectors by TlsCertificateName non-empty
- [06-02]: Per-connector TLS cert lookup via Get-ExchangeCertificate -DomainName returns None gracefully if cmdlet unavailable (Exchange Online)
- [06-02]: None cert treated as healthy — cannot fully verify but connector is still TLS-configured
- [06-02]: all_healthy=True for empty connector list — no connectors is not an unhealthy state
- [06-02]: test_call_tool_not_implemented_raises updated to use nonexistent_tool — zero stubs remain in TOOL_DISPATCH
- [07-01]: Stub login/logout routes in app.py prevent url_for BuildError before MSAL auth is wired in 07-02
- [07-01]: fetch-based SSE (not native EventSource) — /chat/stream requires POST body with user message payload
- [07-01]: SESSION_FILE_DIR defaults to /tmp/flask-sessions; created with os.makedirs(exist_ok=True) at startup
- [07-01]: Static Config class with update_from_secrets classmethod — simpler than dataclass for this startup pattern

### Pending Todos

None.

### Blockers/Concerns

- [Phase 1]: Verify Exchange throttling policy for service account before Phase 3 tool testing
- [Phase 7]: Flask vs FastAPI resolved as Flask — scaffold is live and working
- [Phase 7]: API_VERSION=2023-05-15 may not support `tools` parameter — verify in 07-03 before tool-call loop
- [General]: MMC Azure OpenAI gateway API version pinned at 2023-05-15 — verify with MMC CTS before upgrade

## Session Continuity

Last session: 2026-03-21T19:00:06Z
Stopped at: Completed 07-01-PLAN.md — Flask scaffold with filesystem sessions, AWS Secrets Manager loader, Atlas chat UI templates and static files
Resume file: None
