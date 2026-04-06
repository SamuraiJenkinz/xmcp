# Project Research Summary

**Project:** Atlas v1.4 -- Message Trace & Feedback Analytics
**Domain:** Enterprise Exchange infrastructure chat (MCP tool extension)
**Researched:** 2026-04-02
**Synthesized:** 2026-04-02
**Confidence:** HIGH
**Replaces:** SUMMARY.md for v1.3 (App Role Access Control, Feedback, Search, Export, Animations)

## Executive Summary

Atlas v1.4 adds two independent feature clusters to the existing Exchange MCP chat application: (1) a Message Trace tool backed by `Get-MessageTraceV2` for email delivery tracking, and (2) three feedback analytics tools that query the existing SQLite `feedback` table directly from the MCP server process. This is a low-risk milestone because both clusters build entirely on existing infrastructure -- zero new Python packages, zero new npm packages, zero schema changes. The message trace tool follows the exact pattern used by the 14 existing Exchange tools (PowerShell cmdlet via `ExchangeClient.run_cmdlet_with_retry()`), and the analytics tools introduce one controlled architectural change: read-only SQLite access from the MCP subprocess.

The recommended approach is a three-phase build: (Phase 0) verify RBAC permissions for `Get-MessageTraceV2`, (Phase 1) implement the message trace tool with system prompt disambiguation against `check_mail_flow`, (Phase 2) implement the feedback analytics foundation with `get_feedback_summary`, then layer on `get_feedback_by_tool` and `get_low_rated_responses`. Phase ordering is driven by risk: Phase 1 has zero architectural novelty, while Phase 2 validates the new cross-process SQLite read pattern before building the complex tool-correlation logic on top of it.

The critical risks are: using the deprecated `Get-MessageTrace` instead of V2 (the legacy cmdlet was deprecated September 2025 and the Reporting Webservice removal is scheduled April 8, 2026), unbounded result sets causing PowerShell timeout on broad queries, and accidental write access from the MCP process to SQLite. All three are preventable with straightforward implementation constraints documented in the research. A secondary risk is PII leakage from Subject lines in message trace results, which must be stripped or gated at the handler level.

---

## Key Findings

### From STACK-v1.4.md

No new dependencies. Both features use existing infrastructure exclusively. The tool count goes from 17 to 21 (1 Exchange tool + 3 SQLite analytics tools).

**Core technologies (all existing):**
- **Get-MessageTraceV2 via ExchangeClient** -- Exchange Online message trace cmdlet, replacing the deprecated Get-MessageTrace. Supports 90-day history (10 days per query), subject filtering via SubjectFilterType, and 5000-result cap.
- **SQLite `json_each()` / `json_extract()`** -- JSON1 extension functions already proven in the project's FTS5 triggers. Used for correlating feedback with tool calls embedded in `messages_json`.
- **`asyncio.to_thread()` for sync SQLite** -- existing pattern from `_search_colleagues_handler` (tools.py:1897). Wraps synchronous sqlite3 calls in the async MCP handler.

**Critical version/config requirements:**
- Get-MessageTraceV2 requires Exchange Online PowerShell V3 module 3.7.0+
- The Atlas service principal must have the "Message Tracking" RBAC role -- verify before implementation
- SQLite opened with `?mode=ro` URI parameter to enforce read-only from MCP process

### From FEATURES.md

**Must have (table stakes):**
- Message trace by sender/recipient address with date range (the core "did my email arrive?" use case)
- Delivery status display (Delivered, Failed, Pending, Quarantined, FilteredAsSpam)
- Timestamps, no-results handling, too-many-results summarization
- Feedback vote counts (up/down) with date filtering and satisfaction rate percentage
- Thumbs-down entries with comments for admin review

**Should have (differentiators):**
- Subject line search via SubjectFilterType (Contains/StartsWith/EndsWith)
- Tool-to-feedback correlation: "which Exchange tools get the most negative feedback?"
- Contrastive system prompt guidance for trace vs check_mail_flow
- Trend analysis (satisfaction over time) and per-tool satisfaction ranking

**Defer (post-v1.4):**
- Get-MessageTraceDetailV2 drill-down (routing hops, transport rule actions)
- Pagination for >1000 trace results (cursor-based, complex)
- IP-based trace filtering (FromIP/ToIP)
- Feedback rate metric (requires counting all assistant messages, expensive)
- Most-rated threads/topics analysis

### From ARCHITECTURE.md

The architecture introduces one controlled change: the MCP subprocess gains read-only SQLite access for feedback analytics, while message trace follows the identical pattern to all existing Exchange tools. All research files converge on Option A (direct SQLite read from MCP) as the correct approach, rejecting Flask API callbacks (circular dependency), Flask-only endpoints (breaks conversational model), and dispatch interception (fractures tool model). A new file `exchange_mcp/feedback_analytics.py` encapsulates analytics handlers, keeping `tools.py` focused on Exchange tools.

**Major components:**
1. **`get_message_trace` tool handler** (tools.py) -- builds Get-MessageTraceV2 cmdlet string, dispatches via ExchangeClient, normalizes results
2. **`exchange_mcp/feedback_analytics.py`** (new file) -- 3 analytics handlers + `_get_analytics_db()` read-only connection + tool correlation utility
3. **System prompt updates** (openai_client.py) -- message trace vs check_mail_flow disambiguation, feedback analytics tool routing guidance
4. **Tool definitions + dispatch entries** (tools.py) -- 4 new entries in TOOL_DEFINITIONS and TOOL_DISPATCH

### From PITFALLS.md

16 pitfalls identified: 3 CRITICAL, 5 HIGH, 6 MEDIUM, 2 LOW. Top five:

1. **Get-MessageTrace is DEPRECATED (CRITICAL)** -- must use Get-MessageTraceV2 from day one. The legacy cmdlet was deprecated Sept 2025; the Reporting Webservice removal is scheduled April 8, 2026. Detection: check for "Get-MessageTrace" without "V2" suffix in tools.py.
2. **Unbounded result sets causing timeout (CRITICAL)** -- hard cap ResultSize to 50-100, require at least one of sender_address or recipient_address. Broad queries on large tenants can hang the PowerShell subprocess and stall the SSE stream.
3. **SQLite write contention if MCP writes (CRITICAL)** -- prevented entirely by opening the database with `?mode=ro` URI parameter. MCP analytics tools must be read-only; all writes go through Flask.
4. **PII exposure in Subject lines (HIGH)** -- message trace returns subjects that may contain confidential information. Strip or truncate subjects in the handler before returning to the AI.
5. **Tool confusion: check_mail_flow vs get_message_trace (HIGH)** -- semantic overlap in "mail flow" domain. Mitigate with contrastive descriptions in both tool definitions and a dedicated system prompt section.

---

## Conflicts and Agreements Between Research Files

### Naming Inconsistency (Resolved)

| File | Tool name used | Env var name |
|------|---------------|--------------|
| STACK-v1.4.md | `get_message_trace` | `ATLAS_DB_PATH` |
| ARCHITECTURE.md | `trace_messages` | `CHAT_DB_PATH` |
| FEATURES.md | `message_trace` | (not mentioned) |
| PITFALLS.md | references both | (not mentioned) |

**Resolution:** The tool name should be `get_message_trace` (matches the `get_` prefix convention used by all existing tools like `get_mailbox_stats`, `get_dag_health`). The environment variable should be `ATLAS_DB_PATH` (matches the project name). These are naming drafts that must be unified during implementation.

### 10-Day vs 90-Day Lookback (Clarified)

STACK-v1.4.md correctly documents both the 90-day total history and 10-day per-query window for V2. ARCHITECTURE.md references only "10-day max lookback" without the 90-day context, appearing to describe the legacy cmdlet behavior.

**Resolution:** The correct information is: **90-day history available via Get-MessageTraceV2, but each query covers at most 10 days.** For v1.4, accept the 10-day single-query limit without multi-query stitching. The tool description should say "last 10 days" for simplicity, and explain the limitation if users ask about older messages.

### Analytics Tool Names (Aligned)

STACK-v1.4.md uses `get_feedback_stats` / `get_negative_feedback` / `get_feedback_by_tool`. ARCHITECTURE.md uses `get_feedback_summary` / `get_feedback_by_tool` / `get_low_rated_responses`.

**Resolution:** Use the ARCHITECTURE.md naming (`get_feedback_summary`, `get_feedback_by_tool`, `get_low_rated_responses`) as it better describes the tool purpose and avoids the ambiguous "stats" and "negative" terms. The AI responds better to descriptive tool names.

### Agreement: MCP Reads SQLite Directly (All Files Converge)

All four research files agree: the MCP server should query SQLite directly with a read-only connection. ARCHITECTURE.md provides the most detailed option analysis (4 options evaluated, 3 rejected). STACK-v1.4.md provides the implementation pattern. PITFALLS.md provides the safety constraints (read-only mode, per-call connections, no persistent handles). No conflict.

### Agreement: No New Packages

All four files confirm zero new Python and zero new npm packages needed. STACK-v1.4.md explicitly lists temptations to avoid (pandas, sqlalchemy, plotly, recharts) with reasons.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 0: RBAC Verification (Pre-Implementation Gate)

**Rationale:** The Message Tracking management role must be confirmed before writing any code. Enterprise RBAC changes can take days/weeks through change management. This is a blocking dependency identified in both STACK-v1.4.md and PITFALLS.md (#14).
**Delivers:** Confirmed permission for Get-MessageTraceV2 on the Atlas service principal.
**Addresses:** Pitfall #14 (RBAC permissions)
**Effort:** 1 manual PowerShell test + potentially a change request
**Risk if skipped:** All Phase 1 work is wasted if permissions are denied

### Phase 1: Message Trace Tool

**Rationale:** Zero architectural risk -- identical pattern to 14 existing Exchange tools. Validates the Get-MessageTraceV2 cmdlet integration and system prompt changes independently of feedback analytics. Delivers the #1 IT helpdesk feature ("where is my email?").
**Delivers:** `get_message_trace` MCP tool with sender/recipient/date/status/subject filters. Updated system prompt with trace vs check_mail_flow disambiguation. Updated check_mail_flow description with contrastive language.
**Addresses features:** Sender/recipient search, date range, status display, subject search, no-results handling, result capping
**Avoids pitfalls:** #1 (deprecated cmdlet), #2 (unbounded results), #4 (date format), #5 (tool confusion), #6 (PII in subjects), #7 (prompt bloat), #9 (10-day limit comms)
**Key decisions:**
- Hard cap ResultSize at 100
- Require at least one of sender_address or recipient_address
- Compute UTC dates in Python, pass to PowerShell
- Strip or truncate Subject lines for PII safety
- Contrastive descriptions in both tool definitions

### Phase 2: Feedback Analytics (Foundation + Full)

**Rationale:** Validates the one new architectural pattern (MCP process reading SQLite via read-only connection) with `get_feedback_summary` first, then builds the complex tool correlation logic for the remaining two tools. Splitting into sub-phases within one phase is optional -- the risk gradient is: simple aggregation first, complex JSON parsing second.
**Delivers:** 3 MCP analytics tools (`get_feedback_summary`, `get_feedback_by_tool`, `get_low_rated_responses`). New `feedback_analytics.py` module. Feedback analytics section in system prompt.
**Addresses features:** Vote counts, satisfaction rate, date-filtered queries, tool-to-feedback correlation, negative feedback review with comments
**Avoids pitfalls:** #3 (SQLite write contention), #8 (array index mapping), #10 (DB path config), #11 (WAL checkpoint), #12 (user privacy), #13 (namespace separation)
**Key decisions:**
- `sqlite3.connect("file:{path}?mode=ro", uri=True)` for read-only enforcement
- Open/close per call, no persistent connections
- `asyncio.to_thread()` wrapper for sync SQLite
- Two-step Python correlation (not giant SQL JOIN with json_each)
- Shared `_extract_tool_for_message()` utility with unit tests
- Aggregate-only analytics -- never expose per-user voting patterns
- `ATLAS_DB_PATH` environment variable for DB path

### Phase Ordering Rationale

- **Phase 0 before Phase 1** because RBAC verification is a hard external dependency that can block implementation for days/weeks in an enterprise environment
- **Phase 1 before Phase 2** because it has zero architectural risk and delivers immediate user value; also validates system prompt changes independently
- **Phase 2 foundation before Phase 2 correlation** because it validates cross-process SQLite access with the simplest possible query before building complex JSON parsing on top
- **The two feature clusters are independent** -- no code dependencies between trace and analytics. But the phasing creates a deliberate risk gradient: known pattern first, new pattern second, complex logic third
- **No frontend changes in any phase.** All new tools return data through the existing MCP-to-AI-to-chat pipeline. This is a backend-only milestone.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (PII decision):** Whether to strip Subject entirely, truncate to N characters, or gate behind a role. This is a stakeholder decision, not a technical one -- needs input from the MMC security/compliance team.
- **Phase 2 (tool correlation):** The `assistant_message_idx` to array position mapping needs validation against real `messages_json` data from production. Write tests with known conversation structures first. If the frontend's index counting logic diverges from the analytics utility, correlation results will be silently wrong.

Phases with standard patterns (skip additional research):
- **Phase 0:** Standard RBAC verification -- run a PowerShell cmdlet, check if it works
- **Phase 1 (tool implementation):** Identical to the pattern used 14 times. Copy an existing handler, change the cmdlet name and parameters.
- **Phase 2 (SQLite access):** WAL concurrent reads, `asyncio.to_thread()`, and `?mode=ro` URI mode are all well-documented and already used in the codebase (`_search_colleagues_handler`)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies. Get-MessageTraceV2 docs verified against Microsoft Learn (updated Feb 2026). All SQLite features already proven in project. |
| Features | HIGH | Feature landscape derived from official cmdlet documentation and direct codebase analysis. Edge cases and presentation patterns well-documented. |
| Architecture | HIGH | Option A (direct SQLite read from MCP) supported by existing codebase precedent (`_search_colleagues_handler`) and SQLite WAL guarantees. Three alternatives evaluated and rejected with rationale. |
| Pitfalls | HIGH | 16 pitfalls identified from official docs, codebase analysis, and domain knowledge. Critical pitfalls have concrete prevention strategies with detection methods. |

**Overall confidence:** HIGH

### Gaps to Address

- **RBAC verification (blocking):** Must confirm Message Tracking role on Atlas service principal before implementation. Cannot be resolved through research alone -- requires a live PowerShell test against Exchange Online.
- **PII policy for Subject lines:** Technical options are clear (strip, truncate, gate). The business decision on which approach to use needs stakeholder input. Recommend defaulting to strip-by-default with an opt-in flag for future consideration.
- **assistant_message_idx mapping correctness:** The correlation algorithm is logically sound but untested against real production data. Must write unit tests with known conversation structures before relying on analytics results. The frontend counting logic must be verified to match.
- **Environment variable unification:** Research files use both `ATLAS_DB_PATH` and `CHAT_DB_PATH`. Unify to `ATLAS_DB_PATH` during implementation. Verify it propagates correctly through `mcp_client.py` line 128 (`env=dict(os.environ)`).
- **Tool name unification:** Research files use `get_message_trace`, `trace_messages`, and `message_trace` interchangeably. Standardize on `get_message_trace` to match existing naming convention.

---

## Sources

### Primary (HIGH confidence)
- [Get-MessageTraceV2 - Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps) -- cmdlet parameters, output properties, deprecation status (updated Feb 2026)
- [Get-MessageTraceV2 GA announcement](https://techcommunity.microsoft.com/blog/exchange/announcing-general-availability-ga-of-the-new-message-trace-in-exchange-online/4420243) -- deprecation timeline, V2 migration guidance
- [SQLite WAL documentation](https://www.sqlite.org/wal.html) -- concurrent reader guarantees, checkpoint behavior
- [SQLite JSON1 extension](https://sqlite.org/json1.html) -- json_each, json_extract function reference
- Direct codebase analysis -- tools.py (17 tools), openai_client.py (SYSTEM_PROMPT ~680 tokens), feedback.py, schema.sql, mcp_client.py, exchange_client.py, ps_runner.py

### Secondary (MEDIUM confidence)
- [Exchange Online RBAC for Message Trace - TechCommunity](https://techcommunity.microsoft.com/discussions/exchange_general/rbac-role-to-allow-you-to-see-in-exchange-admin-portal-messagetrace/4446434) -- Message Tracking role requirement
- [Exchange Online feature permissions](https://learn.microsoft.com/en-us/exchange/permissions-exo/feature-permissions) -- role group documentation
- [MC1092458: Deprecation timeline](https://mc.merill.net/message/MC1092458) -- Get-MessageTrace removal schedule
- [Petri.com Get-MessageTrace guide](https://petri.com/powershell-get-messagetrace/) -- output property verification
- [RAG-MCP tool selection research](https://arxiv.org/html/2505.03275v1) -- tool count impact on LLM selection accuracy
- [Chatbot analytics metrics guide - Hiver](https://hiverhq.com/blog/chatbot-analytics) -- general analytics patterns

---
*Research completed: 2026-04-02*
*Replaces: SUMMARY.md for v1.3 (App Role Access Control, Feedback, Search, Export, Animations)*
*Ready for roadmap: yes*
