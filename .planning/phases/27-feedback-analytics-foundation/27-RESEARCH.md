# Phase 27: Feedback Analytics Foundation - Research

**Researched:** 2026-04-06
**Domain:** Read-only SQLite analytics on existing feedback table + new MCP tool pattern (no Exchange dependency)
**Confidence:** HIGH

---

## Summary

Phase 27 adds two read-only analytics MCP tools (`get_feedback_summary`, `get_low_rated_responses`) that query the existing SQLite `feedback` table. The entire infrastructure already exists: the table schema, the tool registration pattern from Phase 26, and the `asyncio.to_thread` pattern for blocking I/O inside async handlers. No new packages are needed.

The primary design decisions are: (1) how the MCP process opens the database read-only without Flask's app context, (2) how to surface the `ATLAS_DB_PATH` env var from the existing `CHAT_DB_PATH` config, and (3) how to generate zero-filled daily trend data in Python since SQLite cannot enumerate days that have no rows. All three have clear, verified solutions using stdlib sqlite3 with URI mode.

The `feedback_analytics.py` module is a clean structural separation from Exchange tool handlers — it contains the two handler functions and imports nothing from Exchange client code. Handler signatures follow the established pattern (same `(arguments, client)` signature as all other tools) even though the `client` argument is unused.

**Primary recommendation:** Use `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` wrapped in `asyncio.to_thread` for each tool call. Read `ATLAS_DB_PATH` env var directly in each handler (same pattern as `AZURE_CERT_THUMBPRINT` in exchange_client.py). Put both handlers in a new `exchange_mcp/feedback_analytics.py` module. Register them in `tools.py` and `TOOL_DISPATCH`.

---

## Standard Stack

All infrastructure already exists. No new packages.

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| `sqlite3` | stdlib | Read-only database queries | No extra dependency; URI mode provides OS-level read-only enforcement |
| `asyncio.to_thread` | stdlib | Run blocking sqlite3 calls without blocking event loop | Established pattern for blocking I/O in this codebase (used for Graph API calls) |
| `os.environ.get` | stdlib | Read `ATLAS_DB_PATH` env var | Same pattern as all other env var reads in exchange_client.py |
| `mcp.types.Tool` | existing | MCP tool registration | Required by MCP SDK, used by all 18 existing tools |

### Supporting (existing in tools.py)
| Import | Purpose |
|---|---|
| `TOOL_DEFINITIONS` list | Add two new `types.Tool` entries here |
| `TOOL_DISPATCH` dict | Add two new handler registrations here |
| Established handler signature `(arguments, client)` | Feedback handlers follow same signature; `client` param is unused but required by dispatch table |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
exchange_mcp/
├── tools.py                    # Add tool definitions + import + dispatch entries
├── feedback_analytics.py       # NEW: two handler functions only
├── server.py                   # Update docstring tool count (18 → 20)
chat_app/
├── openai_client.py            # Append feedback analytics disambiguation section
```

No changes to Flask app, frontend, or database schema.

### Pattern 1: Read-Only SQLite Connection (URI Mode)

**What:** Open the SQLite database file in read-only mode using the URI connection string format. This prevents any write operation at the OS/SQLite level — even if a bug calls `conn.execute("INSERT ...")`, SQLite raises `OperationalError: attempt to write a readonly database`.

**When to use:** Every time a handler opens the database. Open and close within each call (no persistent connection — the MCP server is a long-running process but has no Flask request lifecycle to manage connections).

**Verified:** Tested against Python 3.11 sqlite3 stdlib (see Code Examples section).

```python
# Source: stdlib sqlite3 URI mode — verified working in Python 3.11
import sqlite3

def _open_ro(db_path: str) -> sqlite3.Connection:
    """Open the Atlas SQLite database read-only."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
```

**WAL concurrent reader safety:** The Flask app opens the database with `PRAGMA journal_mode=WAL` at startup. WAL mode allows concurrent readers with no lock contention against writers. The read-only connection does not need to set WAL mode — it inherits the file's existing WAL mode and is safe to open simultaneously with the Flask writer.

### Pattern 2: asyncio.to_thread for Blocking sqlite3

**What:** `asyncio.to_thread(sync_function)` runs a blocking function in a thread pool without blocking the async event loop. This is the established pattern in this codebase for all non-async I/O (used for Graph API calls in `_search_colleagues_handler` and `_get_colleague_profile_handler`).

**When to use:** All sqlite3 operations inside async handler functions.

```python
# Source: pattern from exchange_mcp/tools.py lines 1950, 1983
import asyncio

async def _get_feedback_summary_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return aggregate feedback stats for a date range."""
    import os
    db_path = os.environ.get("ATLAS_DB_PATH", "").strip()
    if not db_path:
        return {"error": "ATLAS_DB_PATH is not configured. Set this environment variable to the Atlas database path."}

    def _query() -> dict:
        # all sqlite3 work here (blocking)
        ...

    return await asyncio.to_thread(_query)
```

### Pattern 3: ATLAS_DB_PATH Environment Variable

**What:** A new env var `ATLAS_DB_PATH` that points to the same SQLite file used by the Flask app (`CHAT_DB_PATH` / `Config.DATABASE`). The MCP server is a separate process that cannot access Flask's `current_app.config["DATABASE"]` directly.

**Why a separate var:** The Flask app uses `CHAT_DB_PATH` (loaded via dotenv). The MCP server also loads dotenv via its own startup. Adding `ATLAS_DB_PATH` to `.env.example` makes the deployment requirement explicit. On the server, both vars can point to the same file: e.g. `ATLAS_DB_PATH=/path/to/chat.db`.

**How other MCP env vars are handled:** `AZURE_CERT_THUMBPRINT`, `AZURE_CLIENT_ID`, `AZURE_TENANT_DOMAIN` are read directly via `os.environ.get()` / `os.environ["KEY"]` inside `exchange_client.py` — no Config class involved. Follow the same pattern.

**Graceful degradation when absent:** Return a structured error dict (not raise RuntimeError) so the AI can explain the misconfiguration to the user rather than seeing an opaque error.

### Pattern 4: Zero-Fill Daily Trend in Python

**What:** SQLite GROUP BY only returns rows that exist. Days with zero feedback produce no row. The CONTEXT.md decision requires "include days with zero feedback as zero counts". This zero-fill must be done in Python after fetching SQL results.

**Implementation:**
```python
# Source: verified with Python 3.11 datetime
from datetime import date, timedelta

def _zero_fill_trend(
    db_rows: dict[str, dict],  # {day_str: {up_votes, down_votes, total}}
    start_date: date,
    end_date: date,
) -> list[dict]:
    trend = []
    current = start_date
    while current <= end_date:
        day_str = current.strftime("%Y-%m-%d")
        row = db_rows.get(day_str, {})
        trend.append({
            "date": day_str,
            "total": row.get("total", 0),
            "up_votes": row.get("up_votes", 0),
            "down_votes": row.get("down_votes", 0),
        })
        current += timedelta(days=1)
    return trend
```

### Pattern 5: Date Handling (7-day default, 90-day max, ISO 8601 strings)

**What:** The feedback table stores `created_at` as ISO 8601 text (`YYYY-MM-DDTHH:MM:SSZ`). Date range filtering uses string comparison, which is correct for ISO 8601 because lexicographic order equals chronological order.

**Default window:** last 7 days (CONTEXT.md decision).
**Max lookback:** 90 days (CONTEXT.md decision).
**Custom range:** AI parses natural language and passes `start_date`/`end_date` as ISO strings.

```python
from datetime import datetime, timezone, timedelta, date as date_type

now = datetime.now(timezone.utc)
end_dt = now
start_dt = now - timedelta(days=7)  # default: last 7 days

# Parse user-provided dates (same pattern as Phase 26)
if arguments.get("end_date"):
    end_dt = datetime.fromisoformat(arguments["end_date"].replace("Z", "+00:00"))
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
if arguments.get("start_date"):
    start_dt = datetime.fromisoformat(arguments["start_date"].replace("Z", "+00:00"))
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

# Enforce 90-day max
range_days = (end_dt - start_dt).total_seconds() / 86400
if range_days > 90:
    raise RuntimeError(
        f"Date range of {range_days:.0f} days exceeds the 90-day maximum. "
        "Narrow the date range to 90 days or fewer."
    )
if start_dt >= end_dt:
    raise RuntimeError("start_date must be before end_date.")

start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
```

### Anti-Patterns to Avoid

- **Do NOT use `CHAT_DB_PATH` in the MCP module.** It is a Flask app config concern. The MCP process reads `ATLAS_DB_PATH` independently.
- **Do NOT import `chat_app.db.get_db` in the MCP module.** `get_db` requires Flask's `g` object and `current_app`, which don't exist in the MCP process.
- **Do NOT use `conn.execute("PRAGMA journal_mode=WAL")` on the read-only connection.** WAL mode is a property of the file, not the connection. A read-only connection cannot write PRAGMAs that modify the DB file.
- **Do NOT open a persistent module-level SQLite connection.** Open and close within each handler call to avoid stale file handles and WAL reader issues on long-lived processes.
- **Do NOT raise RuntimeError for missing ATLAS_DB_PATH.** Return a structured dict with an `"error"` key so the AI can explain it to the user (consistent with "graceful degradation" when a tool dependency is unavailable).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Read-only database enforcement | Custom wrapper that checks query type | `sqlite3.connect(..., uri=True)` with `?mode=ro` | OS-level enforcement; stdlib; zero extra code |
| Blocking I/O in async handler | `asyncio.run_in_executor(None, ...)` | `asyncio.to_thread(fn)` | Same stdlib function used for Graph calls in this codebase |
| Daily zero-fill | SQL recursive CTE generating all dates | Python `timedelta` loop after GROUP BY | Simpler, readable, no SQLite extension needed |
| Date parsing | Custom strptime formats | `datetime.fromisoformat()` + `.replace("Z", "+00:00")` | Already established in Phase 26 handler |
| Satisfaction rate | Custom decimal precision logic | `round(100 * up / total, 1)` | One line, consistent with 1 decimal place |
| Tool registration | Custom routing | `TOOL_DEFINITIONS` + `TOOL_DISPATCH` in tools.py | Established pattern; dispatch table is single truth |

**Key insight:** SQLite URI mode read-only (`?mode=ro`) provides OS-level write protection with zero custom code. A bug that tries to write still raises `OperationalError` before touching disk.

---

## Common Pitfalls

### Pitfall 1: Importing chat_app.db in the MCP Process

**What goes wrong:** `from chat_app.db import get_db` raises errors at import or call time because `get_db` uses Flask's `g` object (request-scoped) and `current_app` (app context-scoped). Neither exists in the MCP server process.

**Why it happens:** Developers see the existing db module and assume it's reusable. It is not — it's Flask-specific.

**How to avoid:** Read `ATLAS_DB_PATH` from env, open sqlite3 directly inside the handler. No Flask imports in `feedback_analytics.py`.

**Warning signs:** `RuntimeError: Working outside of application context` at tool call time.

### Pitfall 2: WAL Mode PRAGMA on Read-Only Connection

**What goes wrong:** `conn.execute("PRAGMA journal_mode=WAL")` on a read-only URI connection raises `OperationalError: attempt to write a readonly database`.

**Why it happens:** The Flask `get_db()` sets WAL mode on its connections. Copying that pattern to the read-only handler causes a crash.

**How to avoid:** Do not set any PRAGMAs on the read-only connection. The file is already in WAL mode; the reader inherits it. Only set `conn.row_factory = sqlite3.Row` (this doesn't write to disk).

**Warning signs:** `OperationalError` on the PRAGMA line itself (not on a SELECT).

### Pitfall 3: Empty Date Range Returns Missing Keys

**What goes wrong:** If there is zero feedback in the date range, the summary SQL still returns one row (with COUNT=0, SUM=NULL). Python `dict(row)` then has `up_votes: None` instead of `0`. If the caller does arithmetic (`up / total`) on None, it raises `TypeError`.

**Why it happens:** SQL `SUM` on an empty set returns NULL, not 0.

**How to avoid:** Use `row["up_votes"] or 0` (not `row["up_votes"]`) when reading SUM columns. Also handle `total == 0` before computing satisfaction rate (avoid zero-division).

**Warning signs:** `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` in the handler.

### Pitfall 4: Database File Not Found (Missing ATLAS_DB_PATH or Wrong Path)

**What goes wrong:** If `ATLAS_DB_PATH` is empty or wrong, `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` raises `OperationalError: unable to open database file`.

**Why it happens:** The MCP server and Flask app are separate processes with independent env. If ATLAS_DB_PATH is not set, the handler will not know where to find the database.

**How to avoid:** Check for empty `db_path` before connecting and return a structured error dict. Catch `OperationalError` from connect and return a user-friendly message.

**Warning signs:** `OperationalError: unable to open database file` in server logs.

### Pitfall 5: asyncio.to_thread Returns Coroutine, Not Result

**What goes wrong:** `result = asyncio.to_thread(fn)` (without `await`) returns a coroutine object, not the result. All downstream access to `result` fails silently or with confusing errors.

**Why it happens:** `asyncio.to_thread` is a coroutine function. It must be awaited.

**How to avoid:** Always `result = await asyncio.to_thread(fn)`. This is the same as the Graph call pattern at lines 1950 and 1983 of tools.py.

**Warning signs:** `result` is a `<coroutine object>`, subsequent `.get()` calls raise `AttributeError`.

### Pitfall 6: Tool Count Mismatch in Tests

**What goes wrong:** `test_server.py` has a hardcoded assertion `assert len(tools) == 17` (currently, after Phase 26 it should be 18 but docstring/comment says 17 — see line 152, 155 of test_server.py). Adding 2 tools without updating this test causes test failure.

**Why it happens:** The test explicitly counts tools. Adding tools without updating the test breaks CI.

**How to avoid:** Update `test_list_tools_returns_all_17` assertion from 18 → 20, and its docstring. Update server.py docstring tool count from 18 → 20. Note: the test at line 155 currently asserts 17 but Phase 26 already added one more (should be 18 now). Verify by running tests before starting Phase 27 work.

**Warning signs:** `AssertionError: assert 20 == 18` in test_server.py.

### Pitfall 7: String Comparison Date Filtering Edge Cases

**What goes wrong:** `created_at >= start_str AND created_at <= end_str` uses lexicographic string comparison. This works correctly ONLY because `created_at` is always stored in `YYYY-MM-DDTHH:MM:SSZ` format. If any rows have a different format (e.g., without the Z suffix), string comparison may produce wrong results.

**Why it happens:** SQLite stores dates as TEXT. The schema enforces the format via `DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))`, but rows inserted programmatically might differ.

**How to avoid:** Verify feedback rows use the canonical format before relying on string comparison. From `feedback.py` inspection: `updated_at strftime('%Y-%m-%dT%H:%M:%SZ', 'now')` — consistent format confirmed. This is safe.

**Warning signs:** Missing recent entries in results despite data existing in the database.

---

## Code Examples

Verified patterns from official sources and codebase inspection:

### Read-Only SQLite Connection

```python
# Source: stdlib sqlite3 docs + verified in Python 3.11
import sqlite3
import os

def _get_db_path() -> str | None:
    """Return ATLAS_DB_PATH from env, or None if not configured."""
    return os.environ.get("ATLAS_DB_PATH", "").strip() or None

def _open_ro(db_path: str) -> sqlite3.Connection:
    """Open the Atlas SQLite database in read-only mode (WAL-safe)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
```

### get_feedback_summary SQL Query

```python
# Verified: returns correct counts; SUM on empty set = NULL (handle with `or 0`)
SUMMARY_SQL = """
    SELECT
        COUNT(*)                                                  AS total_votes,
        SUM(CASE WHEN vote = 'up'   THEN 1 ELSE 0 END)          AS up_votes,
        SUM(CASE WHEN vote = 'down' THEN 1 ELSE 0 END)          AS down_votes,
        SUM(CASE WHEN comment IS NOT NULL AND comment != ''
                 THEN 1 ELSE 0 END)                              AS comment_count
    FROM feedback
    WHERE created_at >= ? AND created_at <= ?
"""
```

### Daily Trend SQL Query (before zero-fill)

```python
# Verified: groups by YYYY-MM-DD prefix of ISO timestamp
TREND_SQL = """
    SELECT
        substr(created_at, 1, 10)                               AS day,
        COUNT(*)                                                 AS total,
        SUM(CASE WHEN vote = 'up'   THEN 1 ELSE 0 END)         AS up_votes,
        SUM(CASE WHEN vote = 'down' THEN 1 ELSE 0 END)         AS down_votes
    FROM feedback
    WHERE created_at >= ? AND created_at <= ?
    GROUP BY day
    ORDER BY day ASC
"""
```

### get_low_rated_responses SQL Query

```python
# Source: verified against schema.sql and feedback.py
# thread_name comes from threads JOIN — no user_id exposed
LOW_RATED_SQL = """
    SELECT
        f.created_at,
        t.name                                                   AS thread_name,
        f.comment,
        CASE WHEN f.comment IS NOT NULL AND f.comment != ''
             THEN 1 ELSE 0 END                                   AS has_comment,
        f.thread_id,
        f.assistant_message_idx
    FROM feedback f
    JOIN threads t ON t.id = f.thread_id
    WHERE f.vote = 'down'
        AND f.created_at >= ? AND f.created_at <= ?
    ORDER BY f.created_at DESC
    LIMIT ?
"""
```

### Full Handler Skeleton: get_feedback_summary

```python
# Source: pattern from exchange_mcp/tools.py _get_message_trace_handler (Phase 26)
# and _search_colleagues_handler (asyncio.to_thread pattern)

async def _get_feedback_summary_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return aggregate feedback stats (vote counts, satisfaction, daily trend)."""
    import os
    import sqlite3
    import asyncio
    from datetime import datetime, timezone, timedelta, date as date_type

    db_path = os.environ.get("ATLAS_DB_PATH", "").strip()
    if not db_path:
        return {
            "error": (
                "ATLAS_DB_PATH is not configured. "
                "Set this environment variable to the Atlas database path."
            )
        }

    # Date range — default 7 days
    now = datetime.now(timezone.utc)
    end_dt = now
    start_dt = now - timedelta(days=7)
    if arguments.get("end_date"):
        end_dt = datetime.fromisoformat(arguments["end_date"].replace("Z", "+00:00"))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    if arguments.get("start_date"):
        start_dt = datetime.fromisoformat(arguments["start_date"].replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

    range_days = (end_dt - start_dt).total_seconds() / 86400
    if range_days > 90:
        raise RuntimeError(
            f"Date range of {range_days:.0f} days exceeds the 90-day maximum."
        )
    if start_dt >= end_dt:
        raise RuntimeError("start_date must be before end_date.")

    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    start_date = start_dt.date()
    end_date = end_dt.date()

    def _query() -> dict:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        except Exception as exc:
            return {"error": f"Cannot open database: {exc}"}
        conn.row_factory = sqlite3.Row
        try:
            # Summary row
            row = conn.execute(SUMMARY_SQL, (start_str, end_str)).fetchone()
            total = row["total_votes"] or 0
            up = row["up_votes"] or 0
            down = row["down_votes"] or 0
            comment_count = row["comment_count"] or 0
            satisfaction_pct = round(100 * up / total, 1) if total > 0 else None

            # Daily trend
            trend_rows = conn.execute(TREND_SQL, (start_str, end_str)).fetchall()
            trend_by_day = {
                r["day"]: {
                    "total": r["total"] or 0,
                    "up_votes": r["up_votes"] or 0,
                    "down_votes": r["down_votes"] or 0,
                }
                for r in trend_rows
            }
            trend = _zero_fill_trend(trend_by_day, start_date, end_date)
        finally:
            conn.close()

        return {
            "total_votes": total,
            "up_votes": up,
            "down_votes": down,
            "satisfaction_pct": satisfaction_pct,
            "comment_count": comment_count,
            "daily_trend": trend,
            "date_range": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            },
        }

    return await asyncio.to_thread(_query)
```

### Full Handler Skeleton: get_low_rated_responses

```python
async def _get_low_rated_responses_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return thumbs-down entries with comment text, thread name, and timestamp."""
    import os
    import sqlite3
    import asyncio
    from datetime import datetime, timezone, timedelta

    db_path = os.environ.get("ATLAS_DB_PATH", "").strip()
    if not db_path:
        return {
            "error": (
                "ATLAS_DB_PATH is not configured. "
                "Set this environment variable to the Atlas database path."
            )
        }

    # Date range — default 7 days
    now = datetime.now(timezone.utc)
    end_dt = now
    start_dt = now - timedelta(days=7)
    if arguments.get("end_date"):
        end_dt = datetime.fromisoformat(arguments["end_date"].replace("Z", "+00:00"))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    if arguments.get("start_date"):
        start_dt = datetime.fromisoformat(arguments["start_date"].replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

    range_days = (end_dt - start_dt).total_seconds() / 86400
    if range_days > 90:
        raise RuntimeError(
            f"Date range of {range_days:.0f} days exceeds the 90-day maximum."
        )

    limit = int(arguments.get("limit") or 10)
    limit = max(1, min(limit, 100))  # enforce 1-100 range

    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _query() -> dict:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        except Exception as exc:
            return {"error": f"Cannot open database: {exc}"}
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(LOW_RATED_SQL, (start_str, end_str, limit)).fetchall()
        finally:
            conn.close()

        entries = [
            {
                "timestamp": r["created_at"],
                "thread_name": r["thread_name"],
                "comment": r["comment"],  # None if no comment
                "has_comment": bool(r["has_comment"]),
            }
            for r in rows
        ]
        return {
            "entries": entries,
            "count": len(entries),
            "date_range": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            },
        }

    return await asyncio.to_thread(_query)
```

### System Prompt Section (following Phase 26 pattern)

```
## Feedback Analytics

You have two tools for querying Atlas feedback data:
- **get_feedback_summary**: Returns aggregate vote counts (thumbs-up/down/total), satisfaction
  percentage, and daily trend breakdown. Use when asked: "How is feedback looking this week?",
  "What's our satisfaction rate?", "Show me feedback trends for the last month".
- **get_low_rated_responses**: Returns individual thumbs-down entries with thread name, timestamp,
  and comment text (when provided). Use when asked: "Show me negative feedback", "What are users
  complaining about?", "Give me the thumbs-down responses with comments".

Rules:
[N]. When asked about overall feedback health or satisfaction rates, use get_feedback_summary.
[N+1]. When asked to review specific negative feedback or user comments, use get_low_rated_responses.
[N+2]. Both tools default to the last 7 days. For different periods, pass start_date and end_date.
[N+3]. Feedback analytics show no per-user identity — data is fully aggregate and anonymous.
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|---|---|---|
| Opening SQLite with write access and hoping nothing writes | URI mode `?mode=ro` for OS-level read-only enforcement | Requirement FBAN-07: write operations provably impossible from analytics module |
| Thread-blocking in async handlers | `asyncio.to_thread` | Event loop stays responsive; established pattern in this codebase since Phase 11 |

**No deprecated approaches apply** — this is a new module with no legacy to replace.

---

## Open Questions

1. **Current tool count discrepancy in test_server.py**
   - What we know: `test_list_tools_returns_all_17` asserts `len(tools) == 17` (line 155). Phase 26 added `get_message_trace` making it 18. The server.py docstring says "18 tools".
   - What's unclear: Was the test updated when Phase 26 was completed, or is it still at 17?
   - Recommendation: First plan task should run `pytest tests/test_server.py` to confirm current passing count. Update the assertion to 20 (18 + 2 new tools) in Phase 27.

2. **ATLAS_DB_PATH vs CHAT_DB_PATH naming**
   - What we know: The Flask app uses `CHAT_DB_PATH`. CONTEXT.md specifies `ATLAS_DB_PATH` for the MCP server.
   - What's unclear: Whether the deployment team would prefer a single var or two. On the production server, both would point to the same file.
   - Recommendation: Implement `ATLAS_DB_PATH` as specified in requirements (INFRA-02). Document in `.env.example` that it should point to the same file as `CHAT_DB_PATH`.

3. **AI response snippet in negative feedback entries**
   - What we know: CONTEXT.md says "timestamp, thread name, comment text, AI response snippet are candidates" for fields in `get_low_rated_responses`. The actual AI response is stored in `messages.messages_json` (a JSON array), not directly in the feedback table.
   - What's unclear: Whether CONTEXT.md marks this as Claude's discretion (it does — "Claude's Discretion: Fields included per negative feedback entry").
   - Recommendation: Do NOT include AI response snippet in Phase 27. Retrieving it requires a JOIN on `messages` + JSON parsing via `json_each`, which adds significant complexity and query cost. The feedback analytics foundation should work with the direct feedback table columns. Phase 28 can add response correlation if needed.

4. **Database path with spaces on Windows**
   - What we know: The production server is Linux (`usdf11v1784.mercer.com`). URI mode paths must use `%20` for spaces, or the path must not contain spaces.
   - What's unclear: Whether the production db path contains spaces.
   - Recommendation: Add URL-encoding for the db path in the URI: `from urllib.parse import quote; uri = f"file:{quote(db_path)}?mode=ro"`. This handles spaces correctly and is a 1-line change.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `chat_app/schema.sql` — complete feedback table schema (columns, types, constraints)
- Codebase: `chat_app/db.py` — WAL mode setup, migrate_db confirms feedback indexes
- Codebase: `chat_app/feedback.py` — date format (`strftime('%Y-%m-%dT%H:%M:%SZ', 'now')`), vote values, comment truncation
- Codebase: `exchange_mcp/tools.py` lines 1933-2201 — ping handler (no-client pattern), asyncio.to_thread pattern (lines 1950, 1983), TOOL_DISPATCH structure
- Codebase: `exchange_mcp/server.py` — handler signature, dispatch, error sanitization
- Codebase: `chat_app/config.py` — CHAT_DB_PATH env var; ATLAS_DB_PATH is a new parallel var for the MCP process
- Python 3.11 stdlib: `sqlite3` URI mode `file:path?mode=ro` — verified working (tested in project venv)
- Python 3.11 stdlib: `PRAGMA query_only = ON` — alternative verified working (tested in project venv)
- Python 3.11 stdlib: `asyncio.to_thread` — used in this codebase at tools.py:1950, 1983

### Secondary (MEDIUM confidence)
- SQLite official docs: WAL mode allows unlimited concurrent readers with writer — no locking needed for read-only connection
- SQLite URI docs: `?mode=ro` prevents all writes at the VFS layer (OS level enforcement)

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; stdlib sqlite3 + existing asyncio pattern
- Feedback table schema: HIGH — read directly from schema.sql and db.py in codebase
- Read-only SQLite URI mode: HIGH — verified with working Python 3.11 test in project venv
- SQL queries: HIGH — verified producing correct results against in-memory test database
- Architecture pattern: HIGH — follows identical dispatch/module structure to Phase 26
- Date handling: HIGH — same pattern as Phase 26 handler (datetime.fromisoformat)
- Pitfalls: HIGH — derived from direct codebase analysis and runtime verification

**Research date:** 2026-04-06
**Valid until:** 2026-07-06 (stable stdlib; schema is schema.sql in-repo)
