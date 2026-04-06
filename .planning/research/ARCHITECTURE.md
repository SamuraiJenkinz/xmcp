# Architecture Patterns: v1.4 Message Trace & Feedback Analytics

**Domain:** MCP tool integration + cross-process data access
**Researched:** 2026-04-02
**Overall confidence:** HIGH (based on direct codebase analysis, no external sources needed)

## Current Architecture Summary

```
User Browser
    |
    v
Flask (Waitress WSGI, sync)
    |-- chat_app/app.py ................ routes, session
    |-- chat_app/openai_client.py ...... tool-calling loop
    |-- chat_app/feedback.py ........... feedback CRUD (Flask Blueprint)
    |-- chat_app/db.py ................. SQLite via Flask g context
    |-- chat_app/mcp_client.py ......... stdio bridge to MCP child process
    |
    v  (stdin/stdout JSON-RPC)
MCP Server (asyncio subprocess)
    |-- exchange_mcp/server.py ......... async Server, tool dispatch
    |-- exchange_mcp/tools.py .......... 17 tool defs + handlers
    |-- exchange_mcp/exchange_client.py  PowerShell subprocess per call
    |-- exchange_mcp/ps_runner.py ...... Base64-encoded PS execution
```

Key architectural constraints:
- MCP server is a **child process** spawned by `mcp_client.py` via `stdio_client()`
- Communication is **stdio JSON-RPC only** -- no shared memory, no HTTP
- SQLite is accessed **exclusively** from Flask via `get_db()` (per-request `g` context)
- MCP server has **no Flask app context** and no access to `get_db()`
- Tool handler signature: `async def handler(arguments: dict, client: ExchangeClient | None) -> dict`
- The `client` parameter is always `ExchangeClient` -- there is no mechanism to inject other dependencies
- The MCP subprocess inherits `os.environ` via `StdioServerParameters(env=dict(os.environ))` in `mcp_client.py`

## Feature 1: trace_messages (Message Trace)

### Integration: Straightforward

This follows the **exact same pattern** as every other Exchange tool. No architectural changes needed.

**New components:**
| Component | File | Change Type |
|-----------|------|-------------|
| Tool definition | `exchange_mcp/tools.py` | Add to `TOOL_DEFINITIONS` list |
| Handler function | `exchange_mcp/tools.py` | New `_trace_messages_handler` |
| Dispatch entry | `exchange_mcp/tools.py` | Add to `TOOL_DISPATCH` dict |
| System prompt | `chat_app/openai_client.py` | Add trace_messages guidance to `SYSTEM_PROMPT` |

**Data flow (identical to existing tools):**
```
User: "trace messages from alice@contoso.com in the last 24 hours"
  -> OpenAI: tool_call trace_messages {sender_address: "alice@contoso.com", start_date: "24h"}
  -> mcp_client.call_mcp_tool("trace_messages", {...})
  -> MCP server -> _trace_messages_handler
  -> exchange_client.run_cmdlet("Get-MessageTrace ...")
  -> JSON result back through the chain
```

### Date Range Parameter Design

**Recommendation: Accept both ISO and relative, normalize to ISO in the handler.**

The tool inputSchema should accept:
```json
{
  "sender_address": "string (optional)",
  "recipient_address": "string (optional)",
  "start_date": "string (optional) - ISO 8601 or relative like '24h', '7d'",
  "end_date": "string (optional) - ISO 8601, defaults to now",
  "message_id": "string (optional) - filter by specific Message-ID header",
  "status": "string (optional) - enum: Delivered, Failed, Pending, Expanded, FilteredAsSpam, Quarantined"
}
```

**Rationale:**
- LLMs handle both relative ("last 24 hours" -> "24h") and absolute ("since March 1st" -> "2026-03-01") formats well
- The handler normalizes both to PowerShell DateTime expressions for Get-MessageTrace
- Default: last 48 hours when no start_date provided (Get-MessageTrace max lookback is 10 days for EXO)
- At least one of sender_address or recipient_address is required for reasonable performance -- enforce in handler

**Handler date normalization pattern:**
```python
def _parse_date_param(value: str | None, default_hours_ago: int = 48) -> str:
    """Convert '24h', '7d', or ISO string to PowerShell-compatible datetime."""
    if value is None:
        return f"(Get-Date).AddHours(-{default_hours_ago})"
    if re.match(r'^\d+h$', value):
        hours = int(value[:-1])
        return f"(Get-Date).AddHours(-{hours})"
    if re.match(r'^\d+d$', value):
        days = int(value[:-1])
        return f"(Get-Date).AddDays(-{days})"
    # Assume ISO format, convert to PowerShell datetime literal
    return f"[datetime]'{value}'"
```

### Get-MessageTrace Constraints (EXO-specific)

- **Max lookback: 10 days** for real-time Get-MessageTrace
- For older traces: Get-HistoricalSearch (async, returns a report) -- different UX, defer to future milestone
- **Max results: 1000 per call** (PageSize parameter)
- At least one address filter required for performance -- tool description should guide the AI
- Results include: Received, SenderAddress, RecipientAddress, Subject, Status, MessageId, Size

## Feature 2: Feedback Analytics (The Architectural Decision)

### The Core Problem

Feedback data lives in SQLite, accessed via Flask's `get_db()`. The MCP server is a child process with **no Flask app context** and **no direct DB access**. The AI needs to query feedback analytics through the tool-calling loop so it can reason about the data conversationally.

### Option Analysis

#### Option A: MCP tools query SQLite directly

The MCP server opens its own read-only SQLite connection using the same DB path.

**How it works:**
- MCP server reads `CHAT_DB_PATH` env var (already propagated via `dict(os.environ)` in `mcp_client.py` line 128)
- Handler opens `sqlite3.connect(db_path, mode=ro)` directly (no Flask context needed)
- Uses `asyncio.to_thread()` for sync SQLite calls (same pattern as `_search_colleagues_handler` at tools.py line 1897)

**Pros:**
- Simplest implementation -- no new communication channels
- Precedent exists: `_search_colleagues_handler` already imports from `chat_app` at function scope and uses `asyncio.to_thread()` for sync operations
- SQLite WAL mode explicitly supports concurrent readers from multiple processes
- No latency overhead (direct file access)
- The AI sees these as normal tools -- no special routing needed

**Cons:**
- Couples MCP server to SQLite schema (but same codebase, same repo)
- Two processes accessing the same DB file (but WAL mode is designed for this)
- MCP server gains a new dependency type (DB reads, not just PowerShell)

#### Option B: MCP tools call Flask API endpoints (HTTP to localhost)

**Pros:** Clean DB access separation
**Cons:** Circular dependency (Flask spawns MCP, MCP calls Flask). Requires auth context bypass for internal calls. Additional latency. If Flask is overloaded, analytics fail too.

**Verdict: REJECTED** -- circular dependency is an anti-pattern, complexity for no benefit.

#### Option C: Feedback analytics as Flask endpoints only (not MCP tools)

**Pros:** No MCP changes needed
**Cons:** The AI cannot query and reason about feedback data conversationally. User asks "how's feedback looking?" and gets a link instead of analysis. Defeats the entire value proposition.

**Verdict: REJECTED** -- defeats the purpose of conversational analytics.

#### Option D: Chat app intercepts tool calls before MCP dispatch

**How it works:** `mcp_client.call_mcp_tool()` checks if tool name starts with `feedback_`, handles in-process using `get_db()`, otherwise dispatches to MCP normally.

**Pros:** Feedback tools get native Flask DB access
**Cons:** Splits dispatch table across two locations (mcp_client.py AND tools.py). Tool definitions must still be in TOOL_DEFINITIONS for OpenAI, but handlers are NOT in TOOL_DISPATCH -- confusing split. Future DB-accessing tools create more interception points. Testing becomes harder.

**Verdict: REJECTED** -- fractures the dispatch model, maintenance burden.

### DECISION: Option A -- MCP tools query SQLite directly

**Rationale (in priority order):**

1. **SQLite WAL is designed for this.** WAL mode supports one writer + multiple concurrent readers across processes. The MCP server only needs read access for analytics.

2. **Precedent exists in the codebase.** `_search_colleagues_handler` (tools.py:1885) already imports from `chat_app` at function scope and uses `asyncio.to_thread()` for sync operations. Feedback analytics follows the identical pattern.

3. **Minimal architectural change.** No new communication channels, no interception logic, no new protocols. Just new tool handlers that read SQLite instead of running PowerShell.

4. **Uniform tool model.** The AI treats all tools identically. No special routing, no system prompt workarounds. `get_feedback_summary` is dispatched exactly like `get_mailbox_stats`.

### Implementation Pattern for Feedback Analytics

**New file: `exchange_mcp/feedback_analytics.py`**

```python
import sqlite3
import json
import os
import asyncio
from typing import Any

_DB_PATH: str | None = None

def _get_analytics_db() -> sqlite3.Connection:
    """Open a read-only SQLite connection to the chat database.
    
    Uses URI mode with ?mode=ro to enforce read-only access.
    Connection is opened per-call and must be closed by caller.
    """
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.environ.get(
            "CHAT_DB_PATH",
            os.path.join(os.path.dirname(__file__), "..", "chat.db"),
        )
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


async def get_feedback_summary_handler(
    arguments: dict[str, Any], client: Any
) -> dict[str, Any]:
    """Return aggregate feedback statistics."""
    def _query():
        db = _get_analytics_db()
        try:
            # ... aggregate queries ...
            return result
        finally:
            db.close()
    return await asyncio.to_thread(_query)
```

**Key design decisions:**
- **Read-only connection** (`?mode=ro` URI) -- MCP server must never write to feedback
- **Open/close per call** -- no persistent connection (matches per-call PowerShell pattern)
- **`asyncio.to_thread()`** -- wraps sync SQLite in async handler (same as Graph API handlers)
- **Separate module** -- `feedback_analytics.py` keeps tools.py focused on Exchange tools

### Feedback Analytics Tool Granularity

**Recommendation: 3 specific tools.**

| Tool | Purpose | Trigger phrases |
|------|---------|-----------------|
| `get_feedback_summary` | Aggregate stats: total votes, up/down ratio, votes per day, most-commented messages | "How's feedback looking?" / "What's our satisfaction rate?" |
| `get_feedback_by_tool` | Correlate feedback with Exchange tools: which tools get thumbs-up vs thumbs-down | "Which tools are users unhappy with?" / "Best-rated tool?" |
| `get_low_rated_responses` | Recent thumbs-down with comments and tool context | "Show me negative feedback" / "What are users complaining about?" |

**Why 3 specific tools, not 1 general-purpose query tool:**
- LLMs choose well from small sets of clearly-described tools; they struggle with query DSLs
- Each tool maps to a distinct natural-language question pattern
- A general `query_feedback(params)` risks SQL injection and prompt confusion
- 3 is enough to cover the primary analytics use cases; more can be added later

### Tool Correlation: Mapping Feedback to Tools

The hardest analytics query correlates `feedback.assistant_message_idx` with tool calls embedded in `messages_json`. The `messages_json` array contains the full conversation including system, user, assistant, and tool messages. The `assistant_message_idx` is a 0-based ordinal counting only **content-bearing assistant messages** (per schema.sql comment, line 27-28).

**Correlation algorithm:**
1. Load `messages_json` for the thread from `messages` table
2. Parse the JSON array
3. Walk the array counting assistant messages with non-null content until reaching `assistant_message_idx`
4. Look backwards from that position for preceding `tool` role messages to identify which tool produced the data the AI used

```python
def _extract_tool_for_message(messages_json: str, assistant_idx: int) -> str | None:
    """Find which tool was called before the Nth assistant message."""
    messages = json.loads(messages_json)
    assistant_count = 0
    target_pos = None
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            if assistant_count == assistant_idx:
                target_pos = i
                break
            assistant_count += 1
    if target_pos is None:
        return None
    # Walk backwards to find the tool call
    for j in range(target_pos - 1, -1, -1):
        if messages[j].get("role") == "tool":
            return messages[j].get("name")
        if messages[j].get("role") in ("user", "system"):
            break  # Passed the tool boundary
    return None  # No tool call preceded this response
```

This correlation logic lives in `feedback_analytics.py`, not in SQL. SQLite's JSON functions cannot do this array traversal efficiently.

## Component Boundaries

### New Components

| Component | Location | Type |
|-----------|----------|------|
| `exchange_mcp/feedback_analytics.py` | NEW file | 3 analytics handlers + read-only DB access + tool correlation |
| `trace_messages` tool def | `exchange_mcp/tools.py` | Added to `TOOL_DEFINITIONS` |
| `_trace_messages_handler` | `exchange_mcp/tools.py` | New handler function |
| 3 feedback tool defs | `exchange_mcp/tools.py` | Added to `TOOL_DEFINITIONS` |
| 3 feedback dispatch entries | `exchange_mcp/tools.py` | Added to `TOOL_DISPATCH`, importing from `feedback_analytics.py` |

### Modified Components

| Component | Location | Change |
|-----------|----------|--------|
| System prompt | `chat_app/openai_client.py` | Add message trace + feedback analytics sections |
| (Possibly) MCP env | `chat_app/mcp_client.py` | Verify `CHAT_DB_PATH` propagates -- likely already works via `dict(os.environ)` |

### Unchanged Components

| Component | Why unchanged |
|-----------|---------------|
| `chat_app/feedback.py` | CRUD endpoints remain as-is; analytics is additive, read-only |
| `chat_app/db.py` | No schema changes; feedback table already has needed columns + indexes |
| `exchange_mcp/server.py` | Tool dispatch unchanged; new tools auto-register via TOOL_DEFINITIONS/TOOL_DISPATCH |
| `exchange_mcp/exchange_client.py` | trace_messages uses existing `run_cmdlet()` directly |

## System Prompt Changes

Add two new sections to `SYSTEM_PROMPT` in `chat_app/openai_client.py`:

```
## Message Tracing

You have a tool for tracing email delivery:
- trace_messages: Traces message delivery path for the last 10 days. Requires at
  least a sender_address or recipient_address. Accepts relative time ('24h', '7d')
  or ISO 8601 dates. Default range: last 48 hours.

Rules:
15. Always ask for at least one email address (sender or recipient) before tracing.
16. If the user asks about messages older than 10 days, explain that real-time
    tracing covers 10 days maximum and suggest checking transport logs.
17. Summarize trace results: total messages found, delivery statuses, any failures
    with error details. Use a table for multiple results.

## Feedback Analytics

You have tools for analyzing user feedback on Atlas responses:
- get_feedback_summary: Overall statistics (vote counts, satisfaction rate, trends).
  Use when asked about general feedback health.
- get_feedback_by_tool: Which Exchange tools get positive vs negative feedback.
  Use when asked about tool quality or per-tool satisfaction.
- get_low_rated_responses: Recent thumbs-down votes with comments and tool context.
  Use when asked about complaints or negative feedback.

Rules:
18. These tools show feedback from ALL users across ALL threads -- they are
    analytics views, not personal feedback lookups.
19. Focus on actionable insights: which tools need improvement, common complaint
    themes, satisfaction trends over time.
20. Never expose raw user identifiers or thread IDs. Summarize and analyze
    the data rather than dumping records.
```

## Data Flow Diagrams

### Message Trace Flow (new -- follows existing tool pattern)
```
User: "trace messages from alice@contoso.com last 24 hours"
  |
  v
Flask openai_client.py -> OpenAI API
  |                            |
  |                    tool_call: trace_messages
  |                      {sender_address: "alice@contoso.com", start_date: "24h"}
  v
mcp_client.call_mcp_tool("trace_messages", {...})
  |
  v (stdio JSON-RPC)
MCP server -> _trace_messages_handler
  |
  v
exchange_client.run_cmdlet("Get-MessageTrace -SenderAddress 'alice@contoso.com' ...")
  |
  v
JSON result -> chain -> AI summarizes -> user sees trace results
```

### Feedback Analytics Flow (new -- SQLite read from MCP process)
```
User: "which tools get the worst feedback?"
  |
  v
Flask openai_client.py -> OpenAI API
  |                            |
  |                    tool_call: get_feedback_by_tool {}
  v
mcp_client.call_mcp_tool("get_feedback_by_tool", {})
  |
  v (stdio JSON-RPC)
MCP server -> get_feedback_by_tool_handler (feedback_analytics.py)
  |
  v
asyncio.to_thread:
  sqlite3.connect("file:chat.db?mode=ro", uri=True)  -- read-only
  SQL aggregation + Python tool correlation
  connection.close()
  |
  v
JSON result -> chain -> AI interprets -> user sees analytics insights
```

## Suggested Build Order

**Phase 1: trace_messages tool** (zero architectural risk)
1. Add tool definition to `TOOL_DEFINITIONS` in tools.py
2. Implement `_trace_messages_handler` with date normalization logic
3. Add dispatch entry to `TOOL_DISPATCH`
4. Add message tracing section to `SYSTEM_PROMPT`
5. Test with real Get-MessageTrace calls against EXO

**Phase 2: Feedback analytics foundation** (validates the new pattern)
1. Create `exchange_mcp/feedback_analytics.py` with `_get_analytics_db()`
2. Implement `get_feedback_summary` handler (simplest -- just aggregates)
3. Add tool definition + dispatch entry in tools.py
4. Verify DB path resolution works in MCP subprocess context
5. Test: Flask writes feedback, MCP reads it back via analytics tool

**Phase 3: Remaining analytics tools + system prompt** (builds on validated pattern)
1. Implement `get_feedback_by_tool` handler (requires tool correlation logic)
2. Implement `get_low_rated_responses` handler
3. Add tool definitions + dispatch entries
4. Add feedback analytics section to `SYSTEM_PROMPT`
5. End-to-end test: user asks about feedback, AI calls correct tool, presents insights

**Ordering rationale:**
- Phase 1 has zero architectural risk -- identical to the pattern used 14 times already
- Phase 2 validates the one new architectural decision (MCP process reading SQLite) with the simplest query
- Phase 3 builds on the validated infrastructure with progressively complex correlation queries
- If Phase 2 reveals issues with cross-process SQLite access (unlikely but possible on Windows), the fix is contained before building the complex tools

## Anti-Patterns to Avoid

### Anti-Pattern: Write Access from MCP
The MCP server must NEVER write to the feedback table. Writes go through Flask's `feedback.py` Blueprint which has auth context and ownership validation. Enforce with `?mode=ro` in SQLite URI -- write attempts fail at the connection level.

### Anti-Pattern: Persistent DB Connections in MCP
Do NOT keep a persistent SQLite connection in the MCP server. Open and close per-call, matching the per-call PowerShell pattern. Avoids WAL checkpoint contention and stale reads.

### Anti-Pattern: Raw SQL Exposure to AI
Do NOT create a general-purpose "run this query" tool. Each analytics tool has fixed SQL with at most parameterized date ranges. The AI chooses which analytics view it needs, not how to query.

### Anti-Pattern: Duplicating CRUD Logic
The analytics module uses raw SQL for read-only aggregates. Do NOT replicate the Flask Blueprint's insert/update/delete patterns. The two access patterns are intentionally different: CRUD via Flask, analytics via MCP.

### Anti-Pattern: Importing Flask Modules in MCP for DB Access
Do NOT import `chat_app.db.get_db()` in the MCP process. That function requires Flask's `g` context and `current_app`. The analytics module manages its own `sqlite3.connect()` with the raw file path.

## Scalability Considerations

| Concern | Current (<50 users) | At 200 users | At 1000+ users |
|---------|----------------------|--------------|----------------|
| SQLite WAL concurrent reads | Fine | Fine | May need read replicas or PostgreSQL |
| Feedback table size | Negligible | ~10K rows, fast | ~100K rows, add date-range partitioning |
| Tool correlation (JSON parse in Python) | Fast | Acceptable | Pre-compute a correlation lookup table |
| Message trace result volume | Fine | Fine | Paginate, summarize server-side |

For the current scale (enterprise internal tool, <50 concurrent users), SQLite WAL with read-only MCP access is more than adequate.

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| trace_messages integration pattern | HIGH | Identical to 14 existing Exchange tools in codebase |
| SQLite WAL multi-process reads | HIGH | WAL is designed for concurrent readers; documented behavior |
| `asyncio.to_thread()` for sync SQLite | HIGH | Exact pattern used by `_search_colleagues_handler` (tools.py:1897) |
| `CHAT_DB_PATH` env propagation to MCP | HIGH | `mcp_client.py:128` passes `env=dict(os.environ)` to subprocess |
| `?mode=ro` SQLite URI parameter | HIGH | Standard Python sqlite3 URI parameter |
| Tool correlation algorithm correctness | MEDIUM | Logic is sound but needs testing against real messages_json data |
| Get-MessageTrace 10-day limit | MEDIUM | Based on training knowledge of EXO; should verify against current docs |

## Sources

- Direct codebase analysis of all referenced files
- SQLite WAL documentation: concurrent multi-process reader support is the designed use case
- Python sqlite3 module: URI `?mode=ro` is the standard read-only parameter
- Existing codebase patterns: `_search_colleagues_handler` for `asyncio.to_thread()` bridge
