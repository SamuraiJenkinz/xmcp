# Technology Stack: v1.4 Message Trace & Feedback Analytics

**Project:** Atlas Exchange MCP Server
**Milestone:** v1.4 — Message Trace & Feedback Analytics
**Researched:** 2026-04-02
**Overall confidence:** HIGH

## Executive Summary

This milestone requires ZERO new Python packages and ZERO new npm packages. Both features build entirely on existing infrastructure:

- **Message Trace** uses `Get-MessageTrace` (or its successor `Get-MessageTraceV2`) via the existing `ExchangeClient.run_cmdlet_with_retry()` pattern -- identical to all 14 existing Exchange tools.
- **Feedback Analytics** uses SQLite `json_each()` and `json_extract()` against the existing `feedback` and `messages` tables -- functions already proven in the project's FTS5 triggers.

The only additions are new Python handler functions in `exchange_mcp/tools.py` and their MCP tool definitions -- the same pattern used 17 times already.

---

## Part 1: Message Trace Tool

### Cmdlet Decision: Get-MessageTrace vs Get-MessageTraceV2

| Criterion | Get-MessageTrace (Legacy) | Get-MessageTraceV2 (Current) |
|-----------|--------------------------|------------------------------|
| Status | Being deprecated | GA replacement |
| Date range | Last 10 days | Last 90 days (10 days per query) |
| Max results | 5000 (via PageSize) | 5000 (via ResultSize) |
| Pagination | Page/PageSize params | No pagination; cursor-based via StartingRecipientAddress + EndDate |
| Subject filter | Not available | SubjectFilterType: Contains/StartsWith/EndsWith |
| Throttling | Undocumented | 100 requests per 5-minute window |

**Recommendation: Use `Get-MessageTraceV2`** because:
1. Get-MessageTrace is explicitly marked as being deprecated
2. V2 supports 90-day lookback (even though single query is still 10 days)
3. V2 adds Subject filtering which is useful for Exchange admins
4. V2 is the cmdlet Microsoft is actively maintaining

**Confidence: HIGH** -- verified against [Microsoft Learn Get-MessageTraceV2 docs](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps) (updated 2026-02-27).

### Get-MessageTraceV2 Parameters (Complete Reference)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `-SenderAddress` | MultiValuedProperty | No | Filter by sender email. Comma-separated for multiple. |
| `-RecipientAddress` | MultiValuedProperty | No | Filter by recipient email. Comma-separated for multiple. |
| `-StartDate` | System.DateTime | No | Start of date range. Short date format (MM/dd/yyyy). Default: 48h ago. |
| `-EndDate` | System.DateTime | No | End of date range. Short date format. |
| `-MessageId` | MultiValuedProperty | No | Filter by Message-ID header (include angle brackets, quote value). |
| `-MessageTraceId` | System.Guid | No | Filter by system-generated trace GUID. |
| `-Status` | MultiValuedProperty | No | Delivered, Expanded, Failed, FilteredAsSpam, GettingStatus, Pending, Quarantined |
| `-Subject` | String | No | Filter by subject line. |
| `-SubjectFilterType` | String | No | Contains, StartsWith, EndsWith. Use with -Subject. |
| `-FromIP` | String | No | Source IP (incoming messages). |
| `-ToIP` | String | No | Destination IP (outgoing messages). |
| `-ResultSize` | Int32 | No | Max results 1-5000. Default: 1000. |
| `-StartingRecipientAddress` | String | No | Cursor for subsequent queries (use last row's RecipientAddress). |

### Get-MessageTraceV2 Output Properties

| Property | Type | Description |
|----------|------|-------------|
| `Received` | DateTime (UTC) | When the message was received by the system |
| `SenderAddress` | String | Sender email address |
| `RecipientAddress` | String | Recipient email address |
| `Subject` | String | Message subject line |
| `Status` | String | Delivery status (Delivered, Failed, Pending, etc.) |
| `MessageTraceId` | Guid | System-generated trace identifier |
| `MessageId` | String | Message-ID header value |
| `Size` | Int64 | Message size in bytes |
| `FromIP` | String | Source IP address |
| `ToIP` | String | Destination IP address |
| `StartDate` | DateTime | Query start date (echoed back) |
| `EndDate` | DateTime | Query end date (echoed back) |
| `Index` | Int32 | Result index |
| `Organization` | String | Organization name |

**Confidence: HIGH** -- output properties verified across [Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps), [Petri.com guide](https://petri.com/powershell-get-messagetrace/), and [o365info](https://o365info.com/get-messagetrace/).

### Exact PowerShell Script for the MCP Tool

The tool handler should construct a cmdlet line like this:

```powershell
# Minimal: sender search
Get-MessageTraceV2 -SenderAddress 'user@contoso.com' -StartDate '03/23/2026' -EndDate '04/02/2026' -ResultSize 100

# Recipient search
Get-MessageTraceV2 -RecipientAddress 'user@contoso.com' -StartDate '03/23/2026' -EndDate '04/02/2026' -ResultSize 100

# Combined: both sender and recipient
Get-MessageTraceV2 -SenderAddress 'sender@contoso.com' -RecipientAddress 'recipient@contoso.com' -StartDate '03/23/2026' -EndDate '04/02/2026'

# With subject filter
Get-MessageTraceV2 -SenderAddress 'user@contoso.com' -Subject 'Quarterly Report' -SubjectFilterType 'Contains' -StartDate '03/23/2026' -EndDate '04/02/2026'

# With status filter
Get-MessageTraceV2 -SenderAddress 'user@contoso.com' -Status 'Failed' -StartDate '03/23/2026' -EndDate '04/02/2026'
```

The `ExchangeClient._build_cmdlet_script()` wraps this with Connect/Disconnect and `ConvertTo-Json -Depth 10` automatically. No changes to exchange_client.py needed.

### Select-Object for Relevant Fields

To reduce JSON payload and avoid returning internal/echoed fields:

```powershell
Get-MessageTraceV2 -SenderAddress '{sender}' -StartDate '{start}' -EndDate '{end}' -ResultSize {limit} | Select-Object Received, SenderAddress, RecipientAddress, Subject, Status, MessageTraceId, Size, FromIP, ToIP
```

### Pagination Strategy

Get-MessageTraceV2 does NOT support Page/PageSize. For Atlas, pagination is likely unnecessary because:
- Default ResultSize of 100 (matching `ExchangeClient.default_result_size`) is sufficient for conversational use
- Users asking "trace emails from alice last week" rarely need 1000+ results
- The AI can present top results and offer to narrow the search

If pagination is ever needed, use cursor-based approach:
```powershell
# Take last row's RecipientAddress and Received as cursor
Get-MessageTraceV2 -SenderAddress '{sender}' -StartDate '{start}' -EndDate '{last_received_time}' -StartingRecipientAddress '{last_recipient}' -ResultSize 100
```

**Recommendation: Do NOT implement pagination in v1.4.** Set ResultSize to 100. If users need more, they should narrow their date range or add filters.

### RBAC Requirements

| Role | Already Assigned? | Notes |
|------|-------------------|-------|
| Message Tracking | Verify | Required for Get-MessageTraceV2 |
| View-Only Recipients | Likely yes | Already needed for Get-Mailbox and other existing tools |

**Action required:** Verify the Azure AD app registration / service principal has the "Message Tracking" management role. If Atlas already runs Get-Mailbox, Get-TransportRule, etc. successfully, the account likely has Organization Management or a custom role group that includes Message Tracking. **Verify before implementation, do not assume.**

**Confidence: MEDIUM** -- RBAC specifics depend on the actual role group assigned to the Atlas service principal. The documentation says "you need to be assigned permissions" but does not list the specific role on the cmdlet page. The Message Tracking role is the standard requirement per [Microsoft TechCommunity RBAC discussion](https://techcommunity.microsoft.com/discussions/exchange_general/rbac-role-to-allow-you-to-see-in-exchange-admin-portal-messagetrace/4446434).

### Integration with Existing Code

**No changes to existing files. New code only.**

| File | Change |
|------|--------|
| `exchange_mcp/tools.py` | Add 1 new Tool definition + 1 handler function |
| `exchange_mcp/server.py` | No change (uses TOOL_DEFINITIONS/TOOL_DISPATCH from tools.py) |
| `exchange_mcp/exchange_client.py` | No change (run_cmdlet_with_retry handles this) |
| `exchange_mcp/ps_runner.py` | No change |

### MCP Tool Definition

```python
types.Tool(
    name="get_message_trace",
    description=(
        "Search Exchange Online message trace logs for the last 10 days. "
        "Returns delivery status, timestamps, sender, recipient, and subject "
        "for emails matching the specified filters. "
        "Use when asked about email delivery: 'Did alice's email to bob arrive?', "
        "'Show me failed deliveries from last week', 'Trace messages from john@contoso.com'. "
        "Requires at least one of sender_address or recipient_address."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "sender_address": {
                "type": "string",
                "description": "Sender email address to filter by.",
            },
            "recipient_address": {
                "type": "string",
                "description": "Recipient email address to filter by.",
            },
            "start_date": {
                "type": "string",
                "description": "Start date in MM/DD/YYYY format. Defaults to 48 hours ago. Max 10 days back.",
            },
            "end_date": {
                "type": "string",
                "description": "End date in MM/DD/YYYY format. Defaults to now.",
            },
            "status": {
                "type": "string",
                "enum": ["Delivered", "Failed", "Pending", "Quarantined", "FilteredAsSpam", "Expanded"],
                "description": "Filter by delivery status.",
            },
            "subject": {
                "type": "string",
                "description": "Filter by subject line (contains match).",
            },
        },
        "required": [],
    },
)
```

### Handler Pattern

```python
async def _handle_get_message_trace(
    arguments: dict[str, Any], client: ExchangeClient
) -> str:
    sender = arguments.get("sender_address", "")
    recipient = arguments.get("recipient_address", "")
    if not sender and not recipient:
        return json.dumps({"error": "At least one of sender_address or recipient_address is required."})

    parts = ["Get-MessageTraceV2"]
    if sender:
        parts.append(f"-SenderAddress '{sender}'")
    if recipient:
        parts.append(f"-RecipientAddress '{recipient}'")
    if arguments.get("start_date"):
        parts.append(f"-StartDate '{arguments['start_date']}'")
    if arguments.get("end_date"):
        parts.append(f"-EndDate '{arguments['end_date']}'")
    if arguments.get("status"):
        parts.append(f"-Status '{arguments['status']}'")
    if arguments.get("subject"):
        parts.append(f"-Subject '{arguments['subject']}' -SubjectFilterType 'Contains'")
    parts.append(f"-ResultSize {client.default_result_size}")
    parts.append("| Select-Object Received, SenderAddress, RecipientAddress, Subject, Status, MessageTraceId, Size")

    cmdlet = " ".join(parts)
    result = await client.run_cmdlet_with_retry(cmdlet)
    # Normalize: always return list
    if isinstance(result, dict):
        result = [result]
    return json.dumps(result, default=str)
```

### Timeout Consideration

Get-MessageTraceV2 can be slow for broad queries. The existing `ExchangeClient.timeout` of 60 seconds should be sufficient for scoped queries. The retry logic in `run_cmdlet_with_retry` handles transient failures. No timeout change needed.

### Throttling

Microsoft enforces 100 requests per 5-minute window. This is unlikely to be hit in conversational use (1 user, 1 query at a time). No client-side rate limiting needed for v1.4.

---

## Part 2: Feedback Analytics MCP Tools

### Architecture Decision: MCP Tools, Not Flask Endpoints

Feedback analytics are exposed as MCP tools (called by the AI) rather than REST endpoints. This means:
- The AI calls `get_feedback_stats` or `get_feedback_details` as a tool
- The AI receives structured data and presents it conversationally
- Users ask "show me feedback this week" in chat, not via a dashboard

This requires the MCP server to have read access to the SQLite database. Currently the MCP server does NOT access the SQLite database -- it only runs PowerShell. The feedback analytics tools will be the first MCP tools that query SQLite directly.

### Database Access from MCP Server

The MCP server runs in a separate process from the Flask app. It needs its own SQLite connection.

**Approach: Direct sqlite3 connection in the handler.**

```python
import sqlite3

def _get_analytics_db() -> sqlite3.Connection:
    """Open a read-only connection to the chat database for analytics queries."""
    db_path = os.environ.get("ATLAS_DB_PATH", "instance/atlas.db")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
```

Key decisions:
- **Read-only mode** (`?mode=ro`) -- analytics tools never write to the database
- **WAL mode** -- already enabled on the database, so concurrent reads from MCP while Flask writes are safe
- **No Flask dependency** -- the MCP server must not import Flask; use plain sqlite3
- **Environment variable** for database path -- `ATLAS_DB_PATH` shared between Flask and MCP processes

### SQLite JSON Functions (Verified)

SQLite version 3.49.1 (verified on this machine) includes full JSON1 extension support. The project already uses `json_each()` and `json_extract()` extensively in FTS5 triggers (see `chat_app/schema.sql` lines 66-99).

Available functions for analytics:
- `json_each(json_text)` -- table-valued function iterating array elements
- `json_extract(json_text, path)` -- extract value at JSON path
- `json_array_length(json_text)` -- count array elements

### Feedback Table Schema (Existing, No Changes)

```sql
CREATE TABLE feedback (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id             INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    assistant_message_idx INTEGER NOT NULL,
    user_id               TEXT    NOT NULL,
    vote                  TEXT    NOT NULL CHECK(vote IN ('up', 'down')),
    comment               TEXT,
    created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(thread_id, assistant_message_idx, user_id)
);
```

Existing indexes (sufficient, no new indexes needed):
- `idx_feedback_thread` on `(thread_id, assistant_message_idx)`
- `idx_feedback_user_vote` on `(user_id, vote, created_at DESC)`

### Messages JSON Structure (Existing)

The `messages.messages_json` column stores an OpenAI-format conversation array:

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "Show me alice's mailbox stats"},
  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_abc", "type": "function", "function": {"name": "get_mailbox_stats", "arguments": "{\"email_address\": \"alice@contoso.com\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_abc", "name": "get_mailbox_stats", "content": "{...json result...}"},
  {"role": "assistant", "content": "Alice's mailbox is 2.1 GB..."}
]
```

**Key insight:** Tool call information is embedded in the conversation as:
1. `role: "assistant"` messages with `tool_calls` array (the request)
2. `role: "tool"` messages with `name` field (the response)

The `assistant_message_idx` in the feedback table is a 0-based ordinal counting only content-bearing assistant messages (those with `role: "assistant"` and non-null `content`).

### SQL Queries for Analytics

#### Tool 1: get_feedback_stats

Summary statistics over a date range.

```sql
-- Feedback volume by vote type for a date range
SELECT
    vote,
    COUNT(*) as count,
    COUNT(comment) as with_comments
FROM feedback
WHERE created_at >= :start_date
  AND created_at < :end_date
GROUP BY vote;
```

```sql
-- Feedback volume by day
SELECT
    date(created_at) as day,
    SUM(CASE WHEN vote = 'up' THEN 1 ELSE 0 END) as thumbs_up,
    SUM(CASE WHEN vote = 'down' THEN 1 ELSE 0 END) as thumbs_down
FROM feedback
WHERE created_at >= :start_date
  AND created_at < :end_date
GROUP BY date(created_at)
ORDER BY day;
```

#### Tool 2: get_negative_feedback

Thumbs-down entries with comments for review.

```sql
-- Thumbs-down with comments
SELECT
    f.thread_id,
    f.assistant_message_idx,
    f.comment,
    f.created_at,
    t.name as thread_name
FROM feedback f
JOIN threads t ON t.id = f.thread_id
WHERE f.vote = 'down'
  AND f.comment IS NOT NULL
  AND f.created_at >= :start_date
  AND f.created_at < :end_date
ORDER BY f.created_at DESC
LIMIT :limit;
```

#### Tool 3: get_feedback_by_tool (Tool-Feedback Correlation)

This is the complex query. We need to find which MCP tools were invoked in the conversation turn that received feedback.

**Strategy:** For each feedback row, load the messages_json for that thread, find the assistant message at the given index, and look backwards in the conversation for the preceding tool calls.

**Option A: In-SQL with json_each (preferred for small result sets)**

```sql
-- For a single thread+message_idx, find the tools used in that conversation turn
-- This extracts tool names from role="tool" messages that appear before the
-- assistant message at the given index
SELECT
    json_extract(j.value, '$.name') as tool_name
FROM messages m,
     json_each(m.messages_json) j
WHERE m.thread_id = :thread_id
  AND json_extract(j.value, '$.role') = 'tool'
  AND j.key < :message_array_position
ORDER BY j.key;
```

**Option B: Aggregated tool-feedback correlation (recommended)**

The clean approach is a two-step process in Python:

1. Query feedback rows for the date range
2. For each feedback row, query the messages_json to extract tool names

```python
async def _correlate_feedback_with_tools(db, start_date, end_date, limit=50):
    """Return feedback entries annotated with which tools were invoked."""
    feedback_rows = db.execute("""
        SELECT f.thread_id, f.assistant_message_idx, f.vote, f.comment,
               f.created_at, t.name as thread_name
        FROM feedback f
        JOIN threads t ON t.id = f.thread_id
        WHERE f.created_at >= ? AND f.created_at < ?
        ORDER BY f.created_at DESC
        LIMIT ?
    """, (start_date, end_date, limit)).fetchall()

    results = []
    for row in feedback_rows:
        # Get the tools used in that conversation turn
        tools = db.execute("""
            SELECT DISTINCT json_extract(j.value, '$.name') as tool_name
            FROM messages m, json_each(m.messages_json) j
            WHERE m.thread_id = ?
              AND json_extract(j.value, '$.role') = 'tool'
        """, (row['thread_id'],)).fetchall()

        results.append({
            "thread_id": row['thread_id'],
            "thread_name": row['thread_name'],
            "assistant_message_idx": row['assistant_message_idx'],
            "vote": row['vote'],
            "comment": row['comment'],
            "created_at": row['created_at'],
            "tools_used": [t['tool_name'] for t in tools],
        })
    return results
```

**Why two-step instead of one giant SQL?** Because:
1. `json_each` on messages_json for every row in a JOIN is expensive
2. The two-step approach is clearer and easier to debug
3. Feedback volume is low (tens to hundreds of rows), so N+1 is acceptable
4. Mapping `assistant_message_idx` (content-bearing ordinal) back to the actual array position requires counting, which is easier in Python

**Option C: Full in-SQL correlation (for aggregate "which tools get the most thumbs-down")**

```sql
-- Aggregate: tool name -> feedback vote counts
-- This finds ALL tools used in threads that have feedback
SELECT
    json_extract(j.value, '$.name') as tool_name,
    SUM(CASE WHEN f.vote = 'up' THEN 1 ELSE 0 END) as thumbs_up,
    SUM(CASE WHEN f.vote = 'down' THEN 1 ELSE 0 END) as thumbs_down,
    COUNT(*) as total_feedback
FROM feedback f
JOIN messages m ON m.thread_id = f.thread_id
JOIN json_each(m.messages_json) j
WHERE json_extract(j.value, '$.role') = 'tool'
  AND f.created_at >= :start_date
  AND f.created_at < :end_date
GROUP BY tool_name
ORDER BY thumbs_down DESC;
```

**Note:** This is an approximation -- it correlates tools used anywhere in the thread with feedback on any message in that thread. For precise per-turn correlation, use Option B (Python).

### MCP Tool Definitions for Feedback Analytics

**Tool 1: get_feedback_stats**
```python
types.Tool(
    name="get_feedback_stats",
    description=(
        "Returns feedback statistics: total votes, thumbs up/down counts, "
        "daily breakdown, and comments count for a date range. "
        "Use when asked about feedback trends: 'How is Atlas doing this week?', "
        "'Show me feedback stats', 'Any negative feedback lately?'."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back. Default 7.",
                "default": 7,
            },
        },
        "required": [],
    },
)
```

**Tool 2: get_negative_feedback**
```python
types.Tool(
    name="get_negative_feedback",
    description=(
        "Returns recent thumbs-down feedback with user comments, thread context, "
        "and which Exchange tools were involved. "
        "Use when asked to review complaints: 'What are users unhappy about?', "
        "'Show me thumbs-down feedback with comments', 'What tools are getting bad feedback?'."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back. Default 7.",
                "default": 7,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum entries to return. Default 20.",
                "default": 20,
            },
        },
        "required": [],
    },
)
```

**Tool 3: get_feedback_by_tool**
```python
types.Tool(
    name="get_feedback_by_tool",
    description=(
        "Returns feedback aggregated by which Exchange tool was invoked. "
        "Shows which tools get the most positive/negative feedback. "
        "Use when asked about tool quality: 'Which tools need improvement?', "
        "'Show feedback broken down by tool', 'What's working well?'."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back. Default 30.",
                "default": 30,
            },
        },
        "required": [],
    },
)
```

---

## Part 3: What NOT to Add

### No New Python Packages

| Temptation | Why NOT |
|------------|---------|
| pandas for analytics | Overkill for 3 SQL queries. SQLite handles aggregation natively. |
| sqlalchemy for DB access | The project uses raw sqlite3 everywhere. Adding an ORM for 3 read queries is inconsistent. |
| plotly/matplotlib for charts | MCP tools return data, not images. The AI presents results as text/tables. |
| aiohttp for async DB | sqlite3 is synchronous but fast. Analytics queries hit indexed columns on small tables. No need for async DB driver. |

### No New npm Packages

| Temptation | Why NOT |
|------------|---------|
| recharts/chart.js for dashboards | v1.4 is MCP-tool-first. Users get analytics conversationally, not via dashboard UI. |
| Additional UI components | No new frontend components needed. The AI presents analytics in chat. |

### No Schema Changes

| Temptation | Why NOT |
|------------|---------|
| Denormalized tool_name column on feedback | Adds write-path complexity. The correlation query is fast enough on small data. |
| Separate analytics table | Premature. If analytics volume grows, extract later. |
| New indexes on messages | json_each on messages_json is only called for feedback correlation, not hot-path. |

### No New MCP Server Infrastructure

| Temptation | Why NOT |
|------------|---------|
| Separate analytics MCP server | One server is simpler. Add tools to existing TOOL_DEFINITIONS. |
| WebSocket for real-time analytics | Conversational analytics via chat is sufficient for v1.4. |
| Background analytics pre-computation | Premature optimization. SQLite is fast for the expected data volume. |

---

## Part 4: Environment Configuration

### New Environment Variable

| Variable | Value | Purpose |
|----------|-------|---------|
| `ATLAS_DB_PATH` | `instance/atlas.db` (default) | Database path shared between Flask app and MCP server for analytics queries |

Both the Flask app and MCP server need to agree on the database path. The Flask app already uses `current_app.config["DATABASE"]`. The MCP server will use `os.environ.get("ATLAS_DB_PATH")`.

**Note:** This should be set in the same environment where the MCP server runs. On Windows (Waitress + subprocess), this is the parent process environment.

---

## Part 5: Integration Points Summary

### Message Trace (New Exchange Tool)

```
User asks about email delivery
  -> AI calls get_message_trace tool
    -> exchange_mcp/tools.py handler builds PowerShell cmdlet string
      -> ExchangeClient.run_cmdlet_with_retry() in exchange_client.py
        -> ps_runner.run_ps() spawns pwsh.exe with Connect + Get-MessageTraceV2 + ConvertTo-Json
          -> Returns JSON array of trace results
        -> Handler normalizes and returns to AI
      -> AI presents results conversationally
```

Identical pattern to all 14 existing Exchange tools. Zero new infrastructure.

### Feedback Analytics (New SQLite Tools)

```
User asks about feedback
  -> AI calls get_feedback_stats / get_negative_feedback / get_feedback_by_tool
    -> exchange_mcp/tools.py handler opens read-only SQLite connection
      -> Executes parameterized SQL queries against feedback + messages tables
        -> Returns JSON result to AI
      -> AI presents analytics conversationally
```

New pattern: first time MCP tools query SQLite. But minimal -- just `sqlite3.connect()` with read-only mode.

---

## Part 6: New Tool Count

After v1.4, tool count goes from 17 to 21:

| # | Tool | Type | Source |
|---|------|------|--------|
| 18 | `get_message_trace` | Exchange PowerShell | Get-MessageTraceV2 via ExchangeClient |
| 19 | `get_feedback_stats` | SQLite Analytics | Direct DB query |
| 20 | `get_negative_feedback` | SQLite Analytics | Direct DB query |
| 21 | `get_feedback_by_tool` | SQLite Analytics | Direct DB query |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Get-MessageTraceV2 parameters | HIGH | Official Microsoft Learn docs, updated 2026-02-27 |
| Get-MessageTraceV2 output fields | HIGH | Multiple sources agree: MS Learn, Petri, o365info |
| RBAC requirements | MEDIUM | Message Tracking role needed; exact assignment depends on Atlas service principal config |
| SQLite json_each/json_extract | HIGH | Already used in project's FTS5 triggers; SQLite 3.49.1 verified |
| Feedback correlation SQL | HIGH | Pattern matches existing json_each usage in schema.sql |
| No new packages needed | HIGH | Verified: all functionality uses stdlib sqlite3 + existing ExchangeClient |
| Get-MessageTrace deprecation | HIGH | Microsoft docs explicitly state V2 is the replacement |

## Sources

- [Get-MessageTraceV2 - Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps)
- [Get-MessageTrace - Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetrace?view=exchange-ps)
- [SQLite JSON Functions](https://sqlite.org/json1.html)
- [Exchange Online RBAC for Message Trace - TechCommunity](https://techcommunity.microsoft.com/discussions/exchange_general/rbac-role-to-allow-you-to-see-in-exchange-admin-portal-messagetrace/4446434)
- [Get-MessageTraceV2 GitHub Source](https://github.com/MicrosoftDocs/office-docs-powershell/blob/main/exchange/exchange-ps/ExchangePowerShell/Get-MessageTraceV2.md)
