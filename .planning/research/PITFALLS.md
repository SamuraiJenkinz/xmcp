# Domain Pitfalls — v1.4 Message Trace & Feedback Analytics

**Domain:** Adding message trace (Get-MessageTrace) and feedback analytics (MCP-served SQLite queries) to an existing Exchange MCP chat app
**Project:** Atlas — Marsh McLennan Exchange infrastructure chat
**Milestone:** v1.4 (Message Trace, Feedback Analytics)
**Researched:** 2026-04-02
**Confidence:** HIGH — verified against actual codebase (tools.py, openai_client.py, db.py, feedback.py) and official Microsoft documentation

---

## Critical Pitfalls

### Pitfall 1: Get-MessageTrace Is Deprecated — Must Use Get-MessageTraceV2

**Severity:** CRITICAL
**What goes wrong:** Get-MessageTrace and Get-MessageTraceDetail were deprecated September 1, 2025. Building on the legacy cmdlet means the feature will break when Microsoft completes removal. The legacy Reporting Webservice deprecation is scheduled for April 8, 2026 — days from now.
**Why it happens:** Training data, older documentation, and Stack Overflow answers all reference Get-MessageTrace. It is easy to implement against the legacy cmdlet without realizing it is already deprecated.
**Consequences:** Feature stops working entirely after Microsoft removes the legacy cmdlet. Requires a rewrite of parameter handling, pagination logic, and result parsing.
**Prevention:** Implement against Get-MessageTraceV2 from the start. Key differences from the legacy cmdlet:
- No Page/PageSize parameters. Uses ResultSize (1-5000, default 1000) instead.
- Pagination requires cursor-style: use StartingRecipientAddress and EndDate from the last result's Recipient/Received properties for the next query.
- 10-day query window limit remains the same.
**Detection:** Check the cmdlet name in tools.py. If it says `Get-MessageTrace` without the V2 suffix, it is wrong.
**Phase:** Must be addressed in Phase 1 (tool implementation). Non-negotiable.
**Source:** [Microsoft announcement of GA and deprecation timeline](https://techcommunity.microsoft.com/blog/exchange/announcing-general-availability-ga-of-the-new-message-trace-in-exchange-online/4420243)

---

### Pitfall 2: Unbounded Result Sets Causing PowerShell Timeout

**Severity:** CRITICAL
**What goes wrong:** A user asks "trace all messages from contoso.com in the last 10 days" on an 80,000-mailbox environment. Get-MessageTraceV2 attempts to return thousands of results. The PowerShell subprocess (per-call PSSession pattern with Connect-ExchangeOnline/Disconnect) hangs or times out. The SSE stream stalls. The UI shows no feedback.
**Why it happens:** The existing tool pattern works well for single-object queries (get_mailbox_stats, get_dag_health). Message trace is fundamentally different — it is a search returning variable-length result sets, potentially massive ones.
**Consequences:** PowerShell process hangs consuming server resources. SSE stream shows no tool status for 30+ seconds. User retries, spawning more hanging processes. Worst case: server resource exhaustion.
**Prevention:**
1. **Hard cap ResultSize** to a sane default (50-100 results) in the tool handler, regardless of what the user requests. The system prompt should tell Atlas to inform users that results are limited.
2. **Enforce mandatory filters.** Require at least one of: SenderAddress, RecipientAddress, or MessageId. Do not allow org-wide unfiltered traces.
3. **Add timeout to the PowerShell subprocess call** (the existing per-call PSSession pattern should have an explicit timeout, e.g., 30 seconds).
4. **Stream tool status early.** Send a "searching..." tool status SSE event before the PowerShell call begins, so the UI shows activity.
**Detection:** Test with a broad query (wildcard domain, full 10-day range) in staging. If it takes >10 seconds, the cap is too loose.
**Phase:** Phase 1 (tool implementation). The parameter validation and result capping must be in the handler from day one.

---

### Pitfall 3: SQLite Concurrent Write Contention — Flask + MCP Server

**Severity:** CRITICAL
**What goes wrong:** Currently, only Flask writes to SQLite (feedback inserts/updates, thread mutations). If the MCP server also needs to write to the database (even for analytics logging or caching), two separate processes hold write locks. In WAL mode, SQLite allows one writer at a time. The second writer blocks until the first commits, and if the first holds the lock during a long operation (PowerShell call + network I/O), the second gets "database is locked" errors.
**Why it happens:** WAL mode allows concurrent readers + one writer. People assume WAL means "concurrent everything" and add a second writing process.
**Consequences:** Intermittent "database is locked" errors on feedback submission or thread creation. Data loss if the error is not retried. Difficult to reproduce under low-concurrency testing with <20 users.
**Prevention:**
1. **MCP feedback analytics tools must be read-only.** The MCP server should only SELECT from the feedback table, never INSERT/UPDATE/DELETE. All writes go through Flask.
2. **Use `PRAGMA busy_timeout = 5000`** on all database connections (both Flask and MCP server) so that a blocked writer retries for 5 seconds before raising an error.
3. **Keep write transactions short.** The existing feedback.py pattern (single INSERT + immediate commit) is correct. Do not wrap multiple operations in long transactions.
4. **Open the database in read-only mode from the MCP process** (`sqlite3.connect("file:atlas.db?mode=ro", uri=True)`) to make it impossible for MCP code to accidentally write.
**Detection:** Load test with concurrent feedback submissions + analytics queries. Watch for "database is locked" in logs.
**Phase:** Phase 2 (feedback analytics MCP tools). Must be designed read-only from the start.
**Source:** [SQLite WAL documentation](https://www.sqlite.org/wal.html)

---

## High Pitfalls

### Pitfall 4: Date/Time Format Confusion in Message Trace Parameters

**Severity:** HIGH
**What goes wrong:** Users say "trace messages from yesterday" or "last 3 days." The tool handler must convert this to StartDate/EndDate parameters. Get-MessageTraceV2 expects dates in the short date format defined by the server's regional settings, but returns results with UTC timestamps. If the handler passes local time (server is in a US timezone) but the user expects Australian or UTC times, results are off by hours. Messages appear to be missing.
**Why it happens:** Exchange Online internally stores everything in UTC. The cmdlet accepts dates in the local format of the machine running the command. The PowerShell subprocess runs on a Windows server with its own timezone. There is a mismatch between what the LLM constructs, what PowerShell interprets, and what Exchange stores.
**Consequences:** Missing results (query range off by hours). User confusion about timestamps. Edge case: querying "today's messages" at midnight UTC returns nothing because the server timezone hasn't rolled over yet.
**Prevention:**
1. **Always pass dates in UTC format explicitly** to the PowerShell cmdlet: `Get-MessageTraceV2 -StartDate "2026-04-01T00:00:00Z" -EndDate "2026-04-02T00:00:00Z"`.
2. **Have the tool handler construct dates, not the LLM.** Accept relative parameters like `days_ago` (integer, 1-10) from the AI, and compute UTC dates in Python code.
3. **Display result timestamps with explicit UTC label** in the tool response JSON so the AI presents them correctly.
**Detection:** Test at timezone boundaries (midnight UTC, midnight local server time). Check if results include messages the user knows were sent.
**Phase:** Phase 1 (tool implementation). Parameter design decision.

---

### Pitfall 5: Tool Confusion — check_mail_flow vs. Message Trace

**Severity:** HIGH
**What goes wrong:** Atlas already has `check_mail_flow` which tests routing logic (connector matching, accepted domains). Message trace shows actual delivery history. Users ask "did my email get delivered?" and the AI picks `check_mail_flow` (tests if it *could* route) instead of message trace (shows if it *did* deliver). Or vice versa: users ask "can I send to fabrikam.com?" and the AI runs a message trace.
**Why it happens:** The tool descriptions overlap in domain: both relate to "mail flow." With 18-19 tools in the system, the LLM has more opportunity to pick the wrong one. Research shows ~10% performance degradation in tool selection accuracy when scaling from 10 to 100 tools — at 18-19 tools this is not catastrophic but the semantic overlap makes it worse.
**Consequences:** Wrong tool called. Wasted PowerShell session. Confusing results shown to the user. User loses trust in Atlas.
**Prevention:**
1. **Make tool descriptions explicitly contrastive.** In the message trace tool description, add: "Use for checking if a specific email WAS delivered. For testing whether email CAN route between two addresses, use check_mail_flow instead."
2. **Mirror the disambiguation in check_mail_flow's description:** "Tests routing logic (connectors, accepted domains). Does NOT show actual delivery history — use message_trace for that."
3. **Add a system prompt section** explaining the distinction: "## Message Trace vs Mail Flow\n- message_trace: Historical delivery data. 'Was this email delivered?'\n- check_mail_flow: Routing logic simulation. 'Can email flow between these addresses?'"
**Detection:** During QA, test these exact queries: "did john's email to bob get delivered?", "can I send email to fabrikam.com?", "is email flowing to external domains?" and verify correct tool selection.
**Phase:** Phase 1 (tool implementation + system prompt update). Must be done together.

---

### Pitfall 6: PII Exposure in Message Trace Results

**Severity:** HIGH
**What goes wrong:** Get-MessageTraceV2 returns Subject lines, sender/recipient email addresses, and message sizes. Subject lines frequently contain PII — names, account numbers, project names, confidential deal names. The tool result is stored in `messages_json` (the conversation history), persisted in SQLite, and visible in the chat UI's collapsible tool result panels.
**Why it happens:** Other Exchange tools return infrastructure data (mailbox sizes, connector configs, DAG health) which is not PII-sensitive. Message trace is fundamentally different — it exposes communication metadata.
**Consequences:** PII stored in conversation history. Subject lines with confidential information visible in the UI. Potential compliance violations (GDPR, Australian Privacy Act if applicable to Marsh McLennan's APAC operations). Data retained indefinitely in SQLite.
**Prevention:**
1. **Strip Subject lines from the tool result** before returning to the AI. Return only: Received timestamp, SenderAddress, RecipientAddress, Status (Delivered/Failed/etc.), MessageId. No Subject.
2. **Document this design decision explicitly** — future developers will wonder why Subject is excluded.
3. **If Subject is needed:** Truncate to first 10 characters + "..." and add a `[REDACTED]` marker. Or gate access behind an additional role.
4. **Ensure the system prompt tells Atlas to NOT ask for or reference email subject lines.**
**Detection:** Review the tool handler output schema. If "Subject" appears in the returned fields, flag it.
**Phase:** Phase 1 (tool implementation). Must strip PII in the handler, not rely on the AI to redact.

---

### Pitfall 7: System Prompt Token Bloat

**Severity:** HIGH
**What goes wrong:** The current system prompt is already ~680 tokens with 7 rules, 3 sections (on-prem vs online, connector queries, colleague lookup), and a detailed rule about colleague profile rendering. Adding message trace rules, check_mail_flow disambiguation, feedback analytics tool guidance, and PII handling instructions could push the prompt to 1000+ tokens. This eats into the context window available for conversation history and tool results.
**Why it happens:** Each new tool category needs routing guidance. The natural approach is to keep adding sections to SYSTEM_PROMPT. It works until it doesn't.
**Consequences:** Less room for conversation history, which means earlier messages get pruned sooner (context_mgr.prune_conversation). Tool results — especially large message trace results — compete with the system prompt for context. With an 80,000-mailbox environment, tool results can be large.
**Prevention:**
1. **Put disambiguation rules in tool descriptions, not the system prompt.** The tool description is only included when the tool is relevant. The system prompt is included in every request.
2. **Keep system prompt additions to 2-3 lines maximum** for v1.4. Focus on the single most important rule: "message_trace shows delivery history, check_mail_flow tests routing logic."
3. **Audit the existing prompt.** Rule 7 (identity associations) and the colleague lookup rules (11-14) are long. Consider whether these can move to tool descriptions.
**Detection:** Count tokens in SYSTEM_PROMPT after changes. If it exceeds 800 tokens, refactor.
**Phase:** Phase 1 (system prompt update). Must be considered alongside tool implementation.

---

### Pitfall 8: messages_json Array Indexing for Tool Correlation

**Severity:** HIGH
**What goes wrong:** Feedback analytics needs to correlate feedback (which uses `assistant_message_idx` as an integer index into the conversation) with which tools were called. The `messages_json` column stores the full OpenAI conversation array. To find which tools an assistant message used, you must: (1) find the assistant message at the index, (2) look backwards in the array for preceding tool_call and tool messages. But `assistant_message_idx` is the index of the assistant message among *assistant* messages only (0th assistant response, 1st assistant response, etc.), not the raw array index. If the implementation assumes raw array indexing, tool correlation will be wrong.
**Why it happens:** The feedback table stores `assistant_message_idx` (set by the frontend based on message rendering order). The messages_json array interleaves user, assistant, tool_call, and tool messages. The mapping between "3rd assistant message" and "array index 11" requires counting by role.
**Consequences:** Analytics report wrong tools for wrong messages. "Most used tools" metrics are incorrect. Debugging is painful because the data looks plausible — just offset by N positions.
**Prevention:**
1. **Write a shared utility function** that converts `assistant_message_idx` to the actual array position in messages_json. Use it in both the feedback analytics MCP tools and any future features.
2. **Add a test** that creates a known conversation with interleaved messages and verifies the index mapping.
3. **Consider storing the raw array index alongside assistant_message_idx in the feedback table** for direct lookup (schema migration).
**Detection:** Create a test conversation with 3+ tool calls and verify that feedback on the 2nd assistant message correctly maps to the tools used in that response.
**Phase:** Phase 2 (feedback analytics). This is the core data model challenge for analytics.

---

## Moderate Pitfalls

### Pitfall 9: 10-Day Query Window Limitation Not Communicated

**Severity:** MEDIUM
**What goes wrong:** A user asks "trace messages from last month" or "when did the migration emails go out 3 weeks ago?" Get-MessageTraceV2 only covers the last 10 days. The tool returns no results. The AI says "no messages found" without explaining the 10-day limitation. The user thinks the messages were never sent.
**Prevention:**
1. **Validate date range in the tool handler.** If the computed StartDate is >10 days ago, return an error message explaining the limitation before calling PowerShell.
2. **Include the limitation in the tool description:** "Returns delivery data for the last 10 days only. For older data, use Start-HistoricalSearch in the Exchange Admin Center."
3. **Have the tool result include the queried date range** so the AI can communicate it: `{"queried_range": "2026-03-23 to 2026-04-02", "note": "Only last 10 days available"}`
**Phase:** Phase 1 (tool implementation).

---

### Pitfall 10: MCP Server Database Path Configuration

**Severity:** MEDIUM
**What goes wrong:** The MCP server (exchange_mcp) runs as a subprocess communicating via stdio JSON-RPC. It currently has no access to the Flask SQLite database. To add feedback analytics tools, the MCP server needs the database file path. If this is hardcoded, it breaks across environments (dev, staging, production). If it uses a different path than Flask, it opens a different database.
**Prevention:**
1. **Pass the database path as an environment variable** to the MCP subprocess. The MCP server reads it on startup.
2. **Verify the path exists and is readable** on MCP server startup. Fail fast with a clear error if not.
3. **Open in read-only mode** (see Pitfall 3).
4. **Do not resolve relative paths** — use the absolute path from Flask's configuration.
**Detection:** Start the MCP server in isolation and verify it can read from the feedback table.
**Phase:** Phase 2 (feedback analytics MCP tools).

---

### Pitfall 11: WAL Checkpoint Starvation from Long-Running Analytics Queries

**Severity:** MEDIUM
**What goes wrong:** If the MCP server runs a complex analytics query (e.g., aggregate all feedback with json_each over messages_json for every thread), it holds a read transaction open for seconds. During that time, WAL checkpointing cannot complete. If this happens repeatedly (user keeps asking for analytics), the WAL file grows indefinitely, consuming disk space.
**Why it happens:** WAL checkpointing cannot shrink the WAL file while any reader holds a snapshot. Long analytical queries hold snapshots longer than typical single-row lookups.
**Prevention:**
1. **Keep analytics queries fast.** Pre-aggregate where possible. Index the feedback table (already done: `idx_feedback_thread`, `idx_feedback_user_vote`).
2. **Do not use json_each on messages_json in analytics queries** if avoidable. Instead, store tool names in the feedback table directly (denormalize), or build a materialized summary table.
3. **Set a query timeout** in the MCP server's database connection: `connection.execute("PRAGMA busy_timeout = 5000")`.
4. **Monitor WAL file size** in production. Alert if it exceeds 50MB.
**Phase:** Phase 2 (feedback analytics). Design decision about query patterns.

---

### Pitfall 12: Feedback Analytics Exposing Individual User Voting Patterns

**Severity:** MEDIUM
**What goes wrong:** The feedback table stores `user_id` (Azure AD OID). An analytics tool that returns "user X downvoted 15 messages about DAG health" exposes individual feedback patterns. This could create a chilling effect (users stop giving honest feedback) or be used to identify "problem" users.
**Prevention:**
1. **Aggregate only.** Analytics tools should return: total upvotes, total downvotes, vote counts per tool, vote counts per time period. Never per-user breakdowns.
2. **Enforce aggregation in SQL.** Use GROUP BY on tool name or time period, never on user_id.
3. **If per-user data is needed for debugging:** Require a separate admin role, log access, and do not expose through the chat AI.
4. **Document the privacy design decision** in the tool handler comments.
**Phase:** Phase 2 (feedback analytics MCP tools).

---

### Pitfall 13: Adding Non-Exchange Tools to the Exchange MCP Server

**Severity:** MEDIUM
**What goes wrong:** The MCP server is `exchange_mcp` — its tools are Exchange cmdlets + colleague lookup. Feedback analytics tools (querying SQLite) are categorically different: they are internal app data, not Exchange infrastructure. Mixing them violates the single-responsibility principle and confuses the tool namespace.
**Prevention:**
1. **Option A: Separate MCP server.** Create a `feedback_mcp` or `analytics_mcp` server. The chat app connects to both MCP servers. Cleanest separation but adds operational complexity (two subprocesses).
2. **Option B: Namespaced tools in the same server.** Add tools like `analytics_feedback_summary`, `analytics_tool_popularity` with a clear `analytics_` prefix. Keep them in a separate module file. Pragmatic for a <20 user deployment.
3. **Recommendation: Option B for v1.4.** The operational overhead of two MCP servers is not justified for 2-3 analytics tools. Use the prefix convention and separate module file. If analytics grows beyond 5 tools, split into its own server.
**Phase:** Phase 2 (feedback analytics). Architectural decision before implementation.

---

### Pitfall 14: RBAC for Message Trace May Differ from Existing Permissions

**Severity:** MEDIUM
**What goes wrong:** The existing Exchange tools use whatever permissions the service account has (Connect-ExchangeOnline credentials). Get-MessageTraceV2 may require different role group membership than the existing Get-Mailbox, Get-DistributionGroup cmdlets. If the service account lacks the Message Tracking role, the cmdlet fails with an access denied error that looks like a bug.
**Prevention:**
1. **Verify the service account has the "Message Tracking" management role** in Exchange Online before writing any code.
2. **Test the cmdlet manually** in a PowerShell session using the service account credentials: `Get-MessageTraceV2 -SenderAddress "test@contoso.com" -StartDate (Get-Date).AddDays(-1)`.
3. **If the role is missing:** Request it through the change management process. This may take days/weeks in an enterprise environment — do it first.
**Detection:** Run the manual test. If you get "The operation couldn't be performed because object couldn't be found on the server," the permissions are wrong.
**Phase:** Pre-Phase 1. Must be verified before any implementation begins.
**Source:** [Exchange Online feature permissions](https://learn.microsoft.com/en-us/exchange/permissions-exo/feature-permissions)

---

## Minor Pitfalls

### Pitfall 15: Message Trace Result Rendering in Collapsible Panels

**Severity:** LOW
**What goes wrong:** Existing tool results (mailbox stats, DAG health) are single objects or small arrays that render well in the collapsible JSON panels. Message trace returns arrays of 50-100 objects. The collapsible panel becomes an unreadable wall of JSON.
**Prevention:** Have the AI summarize results in prose/table format in its response text, and keep the raw JSON in the collapsible panel as a reference. The system prompt already says "Present Exchange data in a clear, conversational way" — this covers it, but test with large result sets.
**Phase:** Phase 1 (UI testing after tool implementation).

---

### Pitfall 16: Empty Results vs. No Matching Messages

**Severity:** LOW
**What goes wrong:** Get-MessageTraceV2 returns an empty array for both "no messages match your filter" and "your date range is outside the 10-day window." The tool handler cannot distinguish these cases without additional logic.
**Prevention:** Check the date range validity before calling PowerShell. If the range is valid and results are empty, the tool can confidently say "no matching messages found in the queried range."
**Phase:** Phase 1 (tool implementation).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|---|---|---|---|
| Pre-implementation | RBAC permissions not verified (#14) | MEDIUM | Manual PowerShell test with service account |
| Phase 1: Message Trace tool | Using deprecated Get-MessageTrace (#1) | CRITICAL | Use Get-MessageTraceV2 exclusively |
| Phase 1: Message Trace tool | Unbounded result sets (#2) | CRITICAL | Hard cap ResultSize, mandatory filters |
| Phase 1: Message Trace tool | Date/time format issues (#4) | HIGH | Compute UTC dates in Python, not the LLM |
| Phase 1: Message Trace tool | PII in Subject lines (#6) | HIGH | Strip Subject from tool results |
| Phase 1: System prompt | Tool confusion with check_mail_flow (#5) | HIGH | Contrastive descriptions + prompt section |
| Phase 1: System prompt | Token bloat (#7) | HIGH | Move rules to tool descriptions |
| Phase 2: Feedback analytics | SQLite concurrent access (#3) | CRITICAL | MCP server opens DB read-only |
| Phase 2: Feedback analytics | Array index mapping (#8) | HIGH | Shared utility + tests |
| Phase 2: Feedback analytics | User privacy (#12) | MEDIUM | Aggregate-only analytics |
| Phase 2: Feedback analytics | MCP server architecture (#13) | MEDIUM | Namespaced tools, separate module |
| Phase 2: Feedback analytics | WAL checkpoint starvation (#11) | MEDIUM | Fast queries, avoid json_each on large data |

---

## Sources

- [Get-MessageTraceV2 official documentation](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps)
- [Microsoft announcement: GA of new Message Trace](https://techcommunity.microsoft.com/blog/exchange/announcing-general-availability-ga-of-the-new-message-trace-in-exchange-online/4420243)
- [MC1092458: Deprecation timeline](https://mc.merill.net/message/MC1092458)
- [SQLite WAL documentation](https://www.sqlite.org/wal.html)
- [SQLite concurrent writes and locking](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [Exchange Online feature permissions](https://learn.microsoft.com/en-us/exchange/permissions-exo/feature-permissions)
- [RAG-MCP: Tool selection degradation research](https://arxiv.org/html/2505.03275v1)
- [Writer engineering: MCP tool bloat](https://writer.com/engineering/rag-mcp/)
- Codebase analysis: `exchange_mcp/tools.py` (17 tools), `chat_app/openai_client.py` (SYSTEM_PROMPT ~680 tokens), `chat_app/feedback.py`, `chat_app/db.py` (feedback schema)
