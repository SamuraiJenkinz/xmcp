# Phase 28: Tool Correlation & Analytics Completion - Research

**Researched:** 2026-04-06
**Domain:** SQLite JSON query-time correlation + MCP tool analytics + system prompt guidance
**Confidence:** HIGH

---

## Summary

Phase 28 adds one new MCP tool (`get_feedback_by_tool`) and extends the system prompt with
conversational analytics guidance. The implementation builds directly on the Phase 27 pattern:
same module (`feedback_analytics.py`), same `asyncio.to_thread` wrapping, same `_open_ro` helper,
same `_parse_date_range` helper, same tool registration pattern in `tools.py`.

The core challenge is **correlation logic**: the `feedback` table records
`(thread_id, assistant_message_idx)` but not tool names. Tool names are stored inside
`messages.messages_json` — a JSON array of OpenAI-format message dicts. To find which Exchange
tool was used for a given `assistant_message_idx`, the query must:
1. Join `feedback` → `messages` (via `thread_id`)
2. Parse `messages_json` using SQLite's `json_each()` to enumerate array elements
3. Walk backward from the content-bearing assistant message to find the preceding
   `tool_calls`-bearing assistant message and extract tool names

This is entirely doable in pure SQL using SQLite 3.38+ JSON functions (`json_extract`,
`json_each`) plus a window function or subquery for the index walk. No Python parsing of
`messages_json` is needed at the per-row level.

**Primary recommendation:** Implement correlation at query time using a single SQL query with
`json_each` and `json_extract`. Write the query as a SQL constant in `feedback_analytics.py`.
For multi-tool messages, attribute the feedback to each tool (fan-out). Bucket messages with no
identifiable tool call under `"general"` or omit them from per-tool breakdown (recommend omit
since `"general"` is not actionable). Add a unified `## Analytics Presentation` section to
SYSTEM_PROMPT covering all three analytics tools.

---

## Standard Stack

All infrastructure already exists. No new packages.

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| `sqlite3` | stdlib | Read-only JSON queries | Phase 27 established; URI mode read-only |
| `asyncio.to_thread` | stdlib | Blocking I/O off event loop | Phase 27 established pattern |
| `json_each` | SQLite built-in | Iterate `messages_json` array elements | Available since SQLite 3.38; no extension needed |
| `json_extract` | SQLite built-in | Extract `role`, `content`, `tool_calls` from array elements | Same |
| `mcp.types.Tool` | existing | Tool registration | Same as all 20 existing tools |

### Supporting (existing)
| Import | Purpose |
|---|---|
| `_open_ro` in `feedback_analytics.py` | Reuse as-is |
| `_parse_date_range` in `feedback_analytics.py` | Reuse as-is |
| `TOOL_DEFINITIONS` + `TOOL_DISPATCH` in `tools.py` | Add one entry each |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
exchange_mcp/
├── feedback_analytics.py   # Add _get_feedback_by_tool_handler + SQL constants
├── tools.py                # Add Tool definition + import + TOOL_DISPATCH entry
exchange_mcp/server.py      # Update docstring tool count (20 → 21)
chat_app/openai_client.py   # Add/update analytics system prompt section
tests/test_server.py        # Update tool count assertion (20 → 21)
```

No schema changes. No Flask changes. No frontend changes.

### Pattern 1: Query-Time Correlation via SQLite JSON Functions

**What:** A single SQL query joins `feedback` + `messages`, uses `json_each` to
iterate the `messages_json` array, and uses `json_extract` to identify each element's
role and tool_calls. Feedback is attributed to tools found in the `tool_calls` field of
the preceding intermediate assistant message.

**Why query-time over write-time:** The messages table already exists with data. No
migration or schema change needed. Write-time correlation would require modifying the
Flask chat pipeline (chat.py / openai_client.py) — out of scope for a backend-only phase.
Query-time reads what is already stored.

**SQLite JSON function availability:** SQLite 3.38 (released 2022-02-22) added
`json_extract` improvements. However, `json_each` and `json_extract` have been available
since SQLite 3.9 (2015). The production server runs Linux with a system SQLite — this is
safe to rely on.

**Messages JSON structure (confirmed from `_message_to_dict` in `openai_client.py`):**

```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "what mailboxes are over quota?"},
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {"id": "call_abc", "type": "function", "function": {"name": "get_mailbox_info", "arguments": "{}"}}
    ]
  },
  {"role": "tool", "tool_call_id": "call_abc", "name": "get_mailbox_info", "content": "..."},
  {"role": "assistant", "content": "Here are the mailboxes over quota..."}
]
```

**Key structural facts (verified from codebase):**
- Content-bearing assistant messages have `role = "assistant"` AND non-null, non-empty `content`
- Tool-invoking assistant messages have `role = "assistant"` AND `tool_calls` array (content is null)
- `assistant_message_idx` counts only content-bearing assistant messages (0-based), confirmed in
  `schema.sql` comment and `MessageList.tsx` line 73-75
- The content-bearing assistant message immediately follows the tool result messages
- Tool names are in `tool_calls[N].function.name` on the preceding intermediate assistant message

**Multi-tool attribution strategy (Claude's discretion → fan-out to each tool):**
Fan out: if a message involved tools A and B, count the feedback vote for both A and B.
This maximizes signal. It slightly inflates total vote counts (one vote may appear in
multiple tool rows), which must be noted in the tool description and system prompt.
Alternative (last tool only) loses signal. Alternative (first tool only) is arbitrary.

**No-tool-identified messages (Claude's discretion → omit from per-tool breakdown):**
If there is no `tool_calls`-bearing assistant message before the content-bearing one
(i.e., the AI answered without using any Exchange tool), there is no tool to attribute.
Omitting these from `get_feedback_by_tool` is correct — the tool is about tool-level
satisfaction, and non-tool responses are outside that scope.

### Pattern 2: SQL Approach for Correlation

The correlation query needs to:
1. For each feedback row, fetch the corresponding `messages_json`
2. Find the content-bearing assistant message at the given `assistant_message_idx`
3. Look at the message immediately before it (or further back) for a `tool_calls`-bearing
   assistant message
4. Extract tool names from the `tool_calls` array

**The challenge:** `messages_json` is a JSON array. Each element has an array index.
`assistant_message_idx` is a count of content-bearing assistant messages (not the raw
array index). SQLite `json_each` returns `(key, value)` pairs where `key` is the 0-based
array position.

**Recommended approach — Python-side correlation:** Rather than a single complex SQL CTE,
use a simpler two-step approach:
1. SQL: Fetch all feedback rows in the date range, joined with the corresponding
   `messages_json` per thread
2. Python: For each unique `(thread_id, assistant_message_idx)`, walk the `messages_json`
   array in Python to find the tool names

This is correct because `asyncio.to_thread` already runs the entire query in a thread.
The Python walk is O(message_count_per_thread) per feedback row — acceptable since
message arrays are small (capped by `prune_conversation`).

**Why Python-side is better than pure SQL for this:** A pure SQL approach requires a
lateral join or recursive CTE to walk backward through the array from a dynamically
computed position. SQLite supports this but the query becomes complex, fragile, and
hard to test. Python walking of a small JSON array is simpler, testable, and correct.

**Python correlation algorithm (verified against codebase):**

```python
import json

def _find_tool_names(messages: list[dict], assistant_message_idx: int) -> list[str]:
    """Walk messages_json to find tool names for the given content-bearing assistant index.

    assistant_message_idx: 0-based count of content-bearing assistant messages.
    Content-bearing = role 'assistant' AND content is not None and not empty string.

    Returns list of tool names from the tool_calls of the closest preceding
    intermediate assistant message (role 'assistant', has tool_calls).
    Returns [] if no tool calls found before that message.
    """
    # Find the raw array index of the target content-bearing assistant message
    content_assistant_count = 0
    target_raw_idx = None
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            if content_assistant_count == assistant_message_idx:
                target_raw_idx = i
                break
            content_assistant_count += 1

    if target_raw_idx is None:
        return []  # index out of range

    # Walk backward from target_raw_idx - 1 to find tool_calls
    for i in range(target_raw_idx - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Extract tool names from tool_calls
            return [
                tc.get("function", {}).get("name", "")
                for tc in msg["tool_calls"]
                if tc.get("function", {}).get("name")
            ]
        if msg.get("role") == "user":
            # Reached the user message without finding tool_calls — no tools used
            break

    return []
```

**Note on `content` field:** An assistant message is "content-bearing" if `content` is
truthy (not None, not empty string). The tool-invoking intermediate assistant messages
typically have `content = null` in the API response. The final answer always has non-null
non-empty content.

### Pattern 3: Per-Tool Breakdown SQL

```python
# Source: feedback_analytics.py pattern; messages join on thread_id
TOOL_FEEDBACK_SQL = """
    SELECT
        f.thread_id,
        f.assistant_message_idx,
        f.vote,
        m.messages_json
    FROM feedback f
    JOIN messages m ON m.thread_id = f.thread_id
    WHERE f.created_at >= ? AND f.created_at <= ?
"""
```

Then in Python: for each row, parse `messages_json`, call `_find_tool_names`, fan out to
each tool name, accumulate per-tool vote counts.

**Aggregation in Python:**

```python
from collections import defaultdict

tool_stats: dict[str, dict] = defaultdict(lambda: {"up": 0, "down": 0})
for row in rows:
    messages = json.loads(row["messages_json"])
    tool_names = _find_tool_names(messages, row["assistant_message_idx"])
    if not tool_names:
        continue  # omit no-tool messages
    for tool_name in tool_names:
        if row["vote"] == "up":
            tool_stats[tool_name]["up"] += 1
        else:
            tool_stats[tool_name]["down"] += 1
```

**Final output structure per tool:**

```python
{
    "tool_name": "get_mailbox_info",
    "up_votes": 12,
    "down_votes": 5,
    "total_votes": 17,
    "satisfaction_pct": 70.6,  # None if total < min_votes_threshold
    "low_confidence": True      # True when total < 5 (configurable threshold)
}
```

**Sort order:** By `satisfaction_pct ASC` (worst first) — directly answers "which tools
have the worst experience". Tools with `total_votes < min_votes_threshold` should be
sorted last (not mixed with statistically meaningful results).

### Pattern 4: Low-Rated Examples by Tool (FBAN-06)

FBAN-06 requires top-N worst-rated tool queries. This extends `get_feedback_by_tool`
with an optional `tool_name` filter parameter that returns specific examples of low-rated
interactions for that tool.

Two approaches:
1. Single tool with two modes (breakdown vs drill-down) controlled by `tool_name` param
2. Include top-N examples directly in the per-tool breakdown

**Recommendation:** Include top-N worst-rated examples as a sub-field in each tool's
entry in the per-tool breakdown. Set `include_examples` parameter (default False) so
the AI can request examples when the user wants them without always fetching message
content.

Alternatively, keep it simple: when `tool_name` is provided, return examples for that
tool; when absent, return the per-tool breakdown. This matches the "drill-down" user
story (FBAN-06: "worst-rated tool queries").

**Example fields per low-rated entry (Claude's discretion — no PII):**
- `timestamp` (created_at from feedback)
- `comment` (user's comment, may be null)
- `thread_name` (from threads JOIN — already used in get_low_rated_responses)

Do NOT include the user message content — it could expose query details that constitute
PII or sensitive operational context. Thread name is safe (it's the truncated user query
visible in the sidebar, already stored as metadata).

### Pattern 5: Tool Registration (established pattern)

```python
# In feedback_analytics.py — add handler
async def _get_feedback_by_tool_handler(
    arguments: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    ...

# In tools.py — add import
from exchange_mcp.feedback_analytics import (
    _get_feedback_summary_handler,
    _get_feedback_by_tool_handler,
    _get_low_rated_responses_handler,
)

# In tools.py — add Tool definition to TOOL_DEFINITIONS
types.Tool(
    name="get_feedback_by_tool",
    description=(
        "Return per-Exchange-tool feedback breakdown showing satisfaction rates and vote counts. "
        "Optionally returns worst-rated interaction examples for a specific tool. "
        "Default: last 7 days, minimum 3 votes to show confidence."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "ISO 8601 start. Default: 7 days ago."},
            "end_date": {"type": "string", "description": "ISO 8601 end. Default: now."},
            "tool_name": {"type": "string", "description": "Filter to a specific tool name for low-rated examples."},
            "limit": {"type": "integer", "description": "Max examples to return when tool_name is set (1-50). Default: 10."},
        },
        "required": [],
    },
),

# In tools.py — add to TOOL_DISPATCH
"get_feedback_by_tool": _get_feedback_by_tool_handler,
```

### Pattern 6: System Prompt — Analytics Presentation Guidance

The CONTEXT.md specifies:
- Tone: Executive summary — concise, professional reporting style
- Actionable recommendations: Yes
- Low confidence flagging: Yes
- Scope: Claude's discretion — all analytics tools or just new one

**Recommendation:** Update the existing `## Feedback Analytics` section (established in
Phase 27) rather than adding a second section. Add rules for `get_feedback_by_tool` plus
universal presentation guidance covering all three analytics tools.

**New rules to add (continuing from rule 22):**

```
## Feedback Analytics

[existing tool entries for get_feedback_summary, get_low_rated_responses]
- **get_feedback_by_tool**: Returns per-tool satisfaction breakdown. Use when asked:
  "Which tools get the most negative feedback?", "Which Exchange tools work worst?",
  "Show me satisfaction rates by tool". With a tool_name, returns low-rated examples
  for that specific tool.

[existing rules 19-22]

23. When asked which tools perform worst, use get_feedback_by_tool (no tool_name).
    Present results as a ranked list from worst to best satisfaction.
24. When asked about specific poor interactions with a named tool, use
    get_feedback_by_tool with that tool_name to retrieve examples.
25. When presenting analytics results:
    a. Lead with the most actionable finding (e.g., "get_transport_queues has the
       lowest satisfaction at 32% across 19 interactions").
    b. Flag low-confidence results explicitly: "Limited data (3 votes) — treat with
       caution."
    c. Suggest a concrete action for the worst-performing tool: "Consider reviewing
       the get_transport_rules implementation or response quality."
    d. Do not dump raw numbers — summarize and interpret them conversationally.
26. When get_feedback_by_tool returns an empty tool list (all feedback was from
    non-tool interactions), say: "No tool-attributed feedback found in this period."
```

### Anti-Patterns to Avoid

- **Do NOT implement write-time correlation.** Would require changing `chat.py` /
  `openai_client.py` — out of scope and adds risk to the live chat path.
- **Do NOT add a `tool_name` column to the feedback table.** Schema migration is
  out of scope. Query-time correlation is sufficient.
- **Do NOT parse `messages_json` in SQL using complex recursive CTEs.** Python parsing
  after fetching the row is simpler, testable, and correct.
- **Do NOT use `json.loads` on rows returned from `sqlite3.Row`.** Call
  `row["messages_json"]` to get the string first, then `json.loads(...)`.
- **Do NOT call `json.loads` on every row in a loop without short-circuit.** If a
  `thread_id` appears in multiple feedback rows, cache `messages_json` by `thread_id`
  in a `dict` to avoid repeated parsing of the same message array.
- **Do NOT present analytics as raw dicts or JSON to the user.** System prompt rule
  must enforce conversational prose. FBAN-11 is explicit about this.
- **Do NOT attribute feedback to tools like `get_feedback_summary` itself.** The
  analytics tools are used in a different context (reporting, not Exchange operations).
  They will naturally appear in the per-tool breakdown; the system prompt should
  acknowledge this is expected.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Read-only DB access | Custom write guard | `sqlite3.connect(..., uri=True)` with `?mode=ro` | Phase 27 established; OS-level enforcement |
| Async blocking I/O | `run_in_executor` | `asyncio.to_thread` | Phase 27 established; same event loop pattern |
| Date range parsing | Custom date logic | `_parse_date_range` (already in `feedback_analytics.py`) | Reuse existing function exactly as-is |
| JSON array walking | Complex SQL CTE | Python list walk after fetching row | Simpler, testable, correct for small arrays |
| Per-tool aggregation | pandas/numpy | `defaultdict` + Python loop | stdlib; no new dependencies |
| Satisfaction % | Custom rounding | `round(100 * up / total, 1) if total > 0 else None` | Phase 27 established pattern |

**Key insight:** The messages_json arrays are small (bounded by `prune_conversation`
context window limits). Python-side JSON parsing of fetched rows is O(messages_per_thread)
per feedback row — not a database performance concern.

---

## Common Pitfalls

### Pitfall 1: Content-Bearing vs Tool-Invoking Assistant Messages

**What goes wrong:** Miscounting `assistant_message_idx` by including intermediate
assistant messages (those with `tool_calls` but null content) in the ordinal count.

**Why it happens:** Walking the array and counting every message with `role == "assistant"`
gives the wrong index. The frontend counts only those where `m.type === 'assistant'`
which maps to messages with actual content (non-null, non-empty).

**How to avoid:** In `_find_tool_names`, only count assistant messages where
`msg.get("content")` is truthy. Intermediate tool-calling messages have `content = null`.

**Warning signs:** Tool correlation returns tools from the wrong turn in the conversation.

### Pitfall 2: Messages JSON Caching

**What goes wrong:** Multiple feedback rows for the same thread parse `messages_json`
repeatedly — once per feedback row. On threads with many votes, this wastes CPU inside
`asyncio.to_thread`.

**Why it happens:** The JOIN returns one row per feedback entry. A thread with 10 feedback
rows will parse the same `messages_json` string 10 times.

**How to avoid:** Build a `{thread_id: messages_list}` dict from the first parse, then
look up subsequent rows from the cache before parsing.

**Warning signs:** Noticeably slow response on accounts with many feedback entries.

### Pitfall 3: Empty `tool_calls` or Malformed JSON

**What goes wrong:** `json.loads(row["messages_json"])` raises `json.JSONDecodeError` if
a row has corrupt data. `msg.get("tool_calls", [])` returns something unexpected if the
format deviates from the OpenAI spec (e.g., legacy `function_call` format).

**Why it happens:** Legacy `function_call` format is used as a fallback in
`openai_client.py` for older gateways. In that format, the assistant message has
`function_call: {name, arguments}` not `tool_calls: [...]`.

**How to avoid:**
- Wrap `json.loads` in try/except and skip corrupt rows
- Check for both `tool_calls` AND `function_call` when walking backward
- Extract tool name from `function_call.name` if `tool_calls` is absent

```python
# Handle legacy function_call format
if msg.get("role") == "assistant":
    if msg.get("tool_calls"):
        return [
            tc.get("function", {}).get("name", "")
            for tc in msg["tool_calls"]
            if tc.get("function", {}).get("name")
        ]
    elif msg.get("function_call", {}).get("name"):
        return [msg["function_call"]["name"]]
```

**Warning signs:** Missing tool attribution for sessions that used the fallback format.

### Pitfall 4: Low-Vote Threshold and None Satisfaction

**What goes wrong:** Tools with 1-2 votes appear with precise satisfaction numbers
(e.g., "100% satisfaction from 1 vote") that mislead the AI into presenting them as
high-confidence findings.

**Why it happens:** `round(100 * 1 / 1, 1) = 100.0` — mathematically correct but
statistically meaningless.

**How to avoid:** Add a `low_confidence: bool` flag when `total_votes < 5` (or chosen
threshold). The system prompt guidance (rule 25b) instructs the AI to flag these.
Return `satisfaction_pct: None` only when `total == 0`; set `low_confidence: True`
when `total < threshold` even if `satisfaction_pct` is computed.

**Warning signs:** AI presents "100% satisfaction" for a tool with 1 vote as a
reliable finding.

### Pitfall 5: Tool Count Test Assertion

**What goes wrong:** `tests/test_server.py` asserts `len(tools) == 20`. Adding
`get_feedback_by_tool` without updating it causes CI failure.

**Why it happens:** The test is hardcoded. Currently at 20 after Phase 27.

**How to avoid:** Update `test_list_tools_returns_all_20` → `test_list_tools_returns_all_21`,
update assertion from 20 → 21, update docstring. Also update `server.py` docstring
("20 tools" → "21 tools").

**Warning signs:** `AssertionError: assert 21 == 20` in `test_server.py`.

### Pitfall 6: Omission of SUM/COUNT NULL Handling

**What goes wrong:** Aggregation in Python using `defaultdict` returns `0` correctly
for absent keys — but the final satisfaction_pct computation raises `ZeroDivisionError`
if total is 0 (which cannot happen if we only include tools with votes, but defensive
coding requires the check).

**How to avoid:** Always guard with `if total > 0` before computing satisfaction_pct.
This is the Phase 27 established pattern.

---

## Code Examples

### `_find_tool_names` — Core Correlation Function

```python
# Verified against messages_json structure from openai_client.py _message_to_dict
def _find_tool_names(messages: list[dict], assistant_message_idx: int) -> list[str]:
    """Return tool names used for the content-bearing assistant message at assistant_message_idx.

    Content-bearing: role='assistant' AND content is truthy (not None, not '').
    Walks backward from target message to find preceding tool_calls or function_call.
    Returns [] if no tools were used (pure text response).
    """
    # Step 1: find raw array index of the target content-bearing assistant message
    content_count = 0
    target_raw_idx = None
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            if content_count == assistant_message_idx:
                target_raw_idx = i
                break
            content_count += 1

    if target_raw_idx is None:
        return []

    # Step 2: walk backward for tool_calls or function_call
    for i in range(target_raw_idx - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "assistant":
            # Current tool_calls format
            if msg.get("tool_calls"):
                return [
                    tc.get("function", {}).get("name", "")
                    for tc in msg["tool_calls"]
                    if tc.get("function", {}).get("name")
                ]
            # Legacy function_call format
            fc = msg.get("function_call")
            if fc and fc.get("name"):
                return [fc["name"]]
        if msg.get("role") == "user":
            break  # reached user message — no tools in this turn

    return []
```

### Per-Tool Breakdown SQL

```python
# Source: established pattern from feedback_analytics.py Phase 27
# Fetches all feedback with messages_json for correlation in Python
TOOL_FEEDBACK_SQL = """
    SELECT
        f.thread_id,
        f.assistant_message_idx,
        f.vote,
        f.comment,
        f.created_at,
        t.name AS thread_name,
        m.messages_json
    FROM feedback f
    JOIN threads t ON t.id = f.thread_id
    JOIN messages m ON m.thread_id = f.thread_id
    WHERE f.created_at >= ? AND f.created_at <= ?
    ORDER BY f.created_at DESC
"""
```

### Per-Tool Aggregation

```python
# Python-side aggregation with caching and legacy format support
import json
from collections import defaultdict

def _aggregate_by_tool(
    rows: list,
    min_votes: int = 3,
) -> list[dict]:
    """Aggregate feedback rows into per-tool statistics."""
    # Cache messages_json by thread_id to avoid repeated JSON parsing
    messages_cache: dict[int, list] = {}

    tool_stats: dict[str, dict] = defaultdict(
        lambda: {"up": 0, "down": 0, "examples": []}
    )

    for row in rows:
        thread_id = row["thread_id"]
        if thread_id not in messages_cache:
            try:
                messages_cache[thread_id] = json.loads(row["messages_json"])
            except (json.JSONDecodeError, TypeError):
                continue  # skip corrupt rows

        tool_names = _find_tool_names(
            messages_cache[thread_id], row["assistant_message_idx"]
        )
        if not tool_names:
            continue  # omit non-tool messages

        for tool_name in tool_names:
            stat = tool_stats[tool_name]
            if row["vote"] == "up":
                stat["up"] += 1
            else:
                stat["down"] += 1
                # Collect low-rated examples (up to 10 per tool)
                if len(stat["examples"]) < 10:
                    stat["examples"].append({
                        "timestamp": row["created_at"],
                        "thread_name": row["thread_name"],
                        "comment": row["comment"] if row["comment"] else None,
                    })

    # Build output list sorted by satisfaction_pct ascending (worst first)
    result = []
    low_confidence_tools = []
    for tool_name, stat in tool_stats.items():
        total = stat["up"] + stat["down"]
        satisfaction_pct = round(100 * stat["up"] / total, 1) if total > 0 else None
        low_confidence = total < min_votes
        entry = {
            "tool_name": tool_name,
            "up_votes": stat["up"],
            "down_votes": stat["down"],
            "total_votes": total,
            "satisfaction_pct": satisfaction_pct,
            "low_confidence": low_confidence,
        }
        if low_confidence:
            low_confidence_tools.append(entry)
        else:
            result.append(entry)

    # Sort high-confidence tools worst-first, then low-confidence tools after
    result.sort(key=lambda x: x["satisfaction_pct"] if x["satisfaction_pct"] is not None else 100)
    low_confidence_tools.sort(key=lambda x: x["satisfaction_pct"] if x["satisfaction_pct"] is not None else 100)

    return result + low_confidence_tools
```

### Handler Skeleton

```python
# Source: follows _get_low_rated_responses_handler pattern exactly
async def _get_feedback_by_tool_handler(
    arguments: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Return per-tool satisfaction breakdown with optional low-rated examples."""
    db_path = os.environ.get("ATLAS_DB_PATH", "").strip()
    if not db_path:
        return {
            "error": (
                "ATLAS_DB_PATH is not configured. "
                "Set this environment variable to the Atlas database path."
            )
        }

    try:
        start_dt, end_dt, start_str, end_str = _parse_date_range(arguments)
    except RuntimeError as exc:
        return {"error": str(exc)}

    tool_name_filter: str | None = arguments.get("tool_name") or None
    raw_limit = arguments.get("limit")
    limit = int(raw_limit) if raw_limit is not None else 10
    limit = max(1, min(50, limit))

    def _query() -> dict:
        conn: sqlite3.Connection | None = None
        try:
            try:
                conn = _open_ro(db_path)
            except Exception as exc:
                return {"error": f"Cannot open database: {exc}"}

            rows = conn.execute(TOOL_FEEDBACK_SQL, (start_str, end_str)).fetchall()
            rows = [dict(r) for r in rows]  # convert sqlite3.Row to dict for processing
        finally:
            if conn is not None:
                conn.close()

        tool_breakdown = _aggregate_by_tool(rows)

        if tool_name_filter:
            # Drill-down mode: return examples for a specific tool
            for entry in tool_breakdown:
                if entry["tool_name"] == tool_name_filter:
                    examples = entry.get("examples", [])[:limit]
                    return {
                        "tool_name": tool_name_filter,
                        "examples": examples,
                        "count": len(examples),
                        "date_range": {"start": start_str, "end": end_str},
                    }
            return {
                "tool_name": tool_name_filter,
                "examples": [],
                "count": 0,
                "message": f"No feedback found for tool '{tool_name_filter}' in this period.",
                "date_range": {"start": start_str, "end": end_str},
            }

        # Summary mode: return per-tool breakdown
        # Strip examples from summary mode (not needed, reduces payload size)
        for entry in tool_breakdown:
            entry.pop("examples", None)

        return {
            "tools": tool_breakdown,
            "tool_count": len(tool_breakdown),
            "date_range": {"start": start_str, "end": end_str},
        }

    return await asyncio.to_thread(_query)
```

### System Prompt Addition

```
## Feedback Analytics

You have three tools for querying Atlas feedback data:
- **get_feedback_summary**: Returns aggregate vote counts (thumbs-up/down/total), satisfaction
  percentage, and daily trend breakdown. Use when asked: "How is feedback looking this week?",
  "What's our satisfaction rate?", "Show me feedback trends for the last month".
- **get_low_rated_responses**: Returns individual thumbs-down entries with thread name, timestamp,
  and comment text (when provided). Use when asked: "Show me negative feedback", "What are users
  complaining about?", "Give me the thumbs-down responses with comments".
- **get_feedback_by_tool**: Returns per-Exchange-tool satisfaction breakdown showing vote counts
  and satisfaction rates per tool. Optionally returns worst-rated examples for a specific tool.
  Use when asked: "Which Exchange tools get the most negative feedback?", "Which tool has the
  worst satisfaction?", "Show me bad interactions with get_mailbox_info".

19. When asked about overall feedback health or satisfaction rates, use get_feedback_summary.
20. When asked to review specific negative feedback or user comments, use get_low_rated_responses.
21. Both tools default to the last 7 days. For different periods, pass start_date and end_date as ISO 8601 strings.
22. Feedback analytics show no per-user identity — all data is fully aggregate and anonymous. Do not attempt to identify who left specific feedback.
23. When asked which tools perform worst or have the lowest satisfaction, use get_feedback_by_tool without tool_name.
24. When asked for specific examples of poor interactions with a named tool, use get_feedback_by_tool with that tool_name.
25. When presenting analytics results: lead with the most actionable finding; flag low-confidence data explicitly (e.g., "Limited data — 3 votes — treat with caution"); suggest a concrete action for the worst-performing tool (e.g., "Consider reviewing get_transport_queues — it has the lowest satisfaction at 32%"); do not present raw JSON or number dumps.
26. If get_feedback_by_tool returns an empty tool list, say: "No tool-attributed feedback was found in this period — all interactions may have been answered without Exchange tool calls."
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| No tool attribution in feedback | Query-time JSON correlation | Phase 28 | Identifies which tools produce poor UX |
| Summary-only analytics | Per-tool breakdown + drill-down | Phase 28 | Actionable recommendations per tool |
| Raw analytics output | Conversational system prompt guidance | Phase 28 | AI presents results as executive summaries |

**No deprecated approaches** — this is a new capability on an existing foundation.

---

## Open Questions

1. **`messages_json` cache size in memory**
   - What we know: `prune_conversation` limits context to stay within the OpenAI model's
     context window. Message arrays are bounded but no explicit count limit was found.
   - What's unclear: Maximum realistic number of feedback rows fetched in a 7-day window.
   - Recommendation: The cache is local to `_query()` inside `asyncio.to_thread` and is
     freed when the function returns. Memory is not a concern for analytics queries.

2. **SQLite version on production server**
   - What we know: Production server is Linux (`usdf11v1784.mercer.com`). The Phase 27
     research confirmed `json_each`/`json_extract` available since SQLite 3.9 (2015).
   - What's unclear: Exact SQLite version on the production server.
   - Recommendation: Python-side JSON parsing (recommended approach) avoids any SQLite
     version dependency for the correlation logic. Only the basic `JOIN` SQL is used.

3. **Feedback from analytics tools in per-tool breakdown**
   - What we know: `get_feedback_summary`, `get_low_rated_responses`, and
     `get_feedback_by_tool` itself can be invoked and rated. They will appear in the
     per-tool breakdown.
   - What's unclear: Whether this is desirable or confusing.
   - Recommendation: Do not filter them out — they are legitimate tools that users rate.
     The system prompt can acknowledge this is expected if it arises.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `chat_app/schema.sql` lines 26-29 — `assistant_message_idx` definition and
  "content-bearing" comment
- Codebase: `frontend/src/components/ChatPane/MessageList.tsx` lines 73-75 — frontend
  ordinal computation (filter `m.type === 'assistant'` which maps to content-bearing)
- Codebase: `chat_app/openai_client.py` lines 157-181 — `_message_to_dict` confirming
  `tool_calls` structure stored in messages_json
- Codebase: `chat_app/openai_client.py` lines 311-353 — tool loop confirming both
  `tool_calls` and legacy `function_call` formats are stored
- Codebase: `exchange_mcp/feedback_analytics.py` — Phase 27 module, all helpers to reuse
- Codebase: `exchange_mcp/tools.py` lines 2220-2247 — TOOL_DISPATCH, current 20 tools
- Codebase: `tests/test_server.py` lines 146-155 — current assertion `len(tools) == 20`
- Codebase: `chat_app/openai_client.py` SYSTEM_PROMPT lines 93-105 — existing Phase 27
  Feedback Analytics section (rules 19-22, last rule number)

### Secondary (MEDIUM confidence)
- SQLite docs: `json_each`, `json_extract` available since SQLite 3.9 (2015) — safe to rely on
- Python stdlib: `collections.defaultdict` — standard aggregation pattern

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all patterns established in Phase 27
- Correlation algorithm: HIGH — verified `_message_to_dict` output structure; `assistant_message_idx` definition confirmed in schema.sql and frontend code
- SQL approach: HIGH — basic JOIN with Python-side JSON parsing; no complex SQL
- Architecture pattern: HIGH — identical to Phase 27 module/registration structure
- System prompt rules: HIGH — established pattern from Phases 26-27; numbers confirmed
- Pitfalls: HIGH — derived from direct codebase analysis

**Research date:** 2026-04-06
**Valid until:** 2026-07-06 (stable stdlib; schema is in-repo; pattern stable)
