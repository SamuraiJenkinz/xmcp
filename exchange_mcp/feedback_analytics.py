"""Feedback analytics module for the Exchange MCP server.

Provides read-only access to Atlas chat feedback data stored in a SQLite
database.  All database I/O is performed via asyncio.to_thread so that
blocking sqlite3 calls do not stall the MCP event loop.

No Flask or Exchange Online dependencies — this module reads SQLite directly.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime, timezone, timedelta, date as date_type
from typing import Any
from urllib.parse import quote


# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

SUMMARY_SQL = """
    SELECT
        COUNT(*) AS total_votes,
        SUM(CASE WHEN vote='up'   THEN 1 ELSE 0 END) AS up_votes,
        SUM(CASE WHEN vote='down' THEN 1 ELSE 0 END) AS down_votes,
        SUM(CASE WHEN comment IS NOT NULL AND comment != '' THEN 1 ELSE 0 END) AS comment_count
    FROM feedback
    WHERE created_at >= ? AND created_at <= ?
"""

TREND_SQL = """
    SELECT
        substr(created_at, 1, 10) AS day,
        COUNT(*) AS total,
        SUM(CASE WHEN vote='up'   THEN 1 ELSE 0 END) AS up_votes,
        SUM(CASE WHEN vote='down' THEN 1 ELSE 0 END) AS down_votes
    FROM feedback
    WHERE created_at >= ? AND created_at <= ?
    GROUP BY day
    ORDER BY day ASC
"""

LOW_RATED_SQL = """
    SELECT
        f.created_at,
        t.name AS thread_name,
        f.comment,
        CASE WHEN f.comment IS NOT NULL AND f.comment != '' THEN 1 ELSE 0 END AS has_comment,
        f.thread_id,
        f.assistant_message_idx
    FROM feedback f
    JOIN threads t ON t.id = f.thread_id
    WHERE f.vote = 'down'
      AND f.created_at >= ? AND f.created_at <= ?
    ORDER BY f.created_at DESC
    LIMIT ?
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _open_ro(db_path: str) -> sqlite3.Connection:
    """Open *db_path* as a read-only SQLite connection.

    Uses the URI filename format so that Windows paths with spaces are
    percent-encoded safely.  No PRAGMAs are written — the database already
    has WAL mode set, and read-only connections cannot issue write PRAGMAs.
    """
    uri = f"file:{quote(db_path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _zero_fill_trend(
    db_rows: dict[str, dict],
    start_date: date_type,
    end_date: date_type,
) -> list[dict]:
    """Return a daily trend list with zero-filled entries for days with no data.

    Args:
        db_rows: Dict keyed by "YYYY-MM-DD" with row data from TREND_SQL.
        start_date: First date in the range (inclusive).
        end_date: Last date in the range (inclusive).

    Returns:
        List of dicts with keys: date, total, up_votes, down_votes.
    """
    result: list[dict] = []
    current = start_date
    while current <= end_date:
        day_str = current.strftime("%Y-%m-%d")
        row = db_rows.get(day_str)
        if row:
            result.append(
                {
                    "date": day_str,
                    "total": row["total"],
                    "up_votes": row["up_votes"],
                    "down_votes": row["down_votes"],
                }
            )
        else:
            result.append(
                {
                    "date": day_str,
                    "total": 0,
                    "up_votes": 0,
                    "down_votes": 0,
                }
            )
        current += timedelta(days=1)
    return result


def _parse_date_range(
    arguments: dict,
) -> tuple[datetime, datetime, str, str]:
    """Parse and validate a date range from handler arguments.

    Defaults to the last 7 days (UTC).  Enforces a 90-day maximum range.

    Returns:
        (start_dt, end_dt, start_str, end_str) where str values are formatted
        as "%Y-%m-%dT%H:%M:%SZ".

    Raises:
        RuntimeError: If the range exceeds 90 days or start >= end.
    """
    now = datetime.now(timezone.utc)
    default_start = now - timedelta(days=7)

    raw_start = arguments.get("start_date")
    raw_end = arguments.get("end_date")

    if raw_start:
        start_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
    else:
        start_dt = default_start

    if raw_end:
        end_dt = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
    else:
        end_dt = now

    if start_dt >= end_dt:
        raise RuntimeError("start_date must be before end_date.")

    if (end_dt - start_dt).days > 90:
        raise RuntimeError(
            "Date range exceeds the 90-day maximum. Please narrow the range."
        )

    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return start_dt, end_dt, start_str, end_str


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


async def _get_feedback_summary_handler(
    arguments: dict[str, Any],
    client: Any,  # client is unused — feedback analytics reads SQLite directly, not Exchange Online
) -> dict[str, Any]:
    """Return aggregate feedback statistics over a date range.

    Reads the Atlas SQLite database at ATLAS_DB_PATH in read-only mode and
    returns vote counts, satisfaction rate, comment count, and a daily trend.
    """
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

    def _query() -> dict:
        conn: sqlite3.Connection | None = None
        try:
            try:
                conn = _open_ro(db_path)
            except Exception as exc:
                return {"error": f"Cannot open database: {exc}"}

            # --- Summary row ---
            row = conn.execute(SUMMARY_SQL, (start_str, end_str)).fetchone()
            total = row["total_votes"] or 0
            up = row["up_votes"] or 0
            down = row["down_votes"] or 0
            comment_count = row["comment_count"] or 0
            satisfaction_pct = round(100 * up / total, 1) if total > 0 else None

            # --- Daily trend ---
            trend_rows = conn.execute(TREND_SQL, (start_str, end_str)).fetchall()
            trend_by_day: dict[str, dict] = {
                r["day"]: {
                    "total": r["total"],
                    "up_votes": r["up_votes"] or 0,
                    "down_votes": r["down_votes"] or 0,
                }
                for r in trend_rows
            }
            daily_trend = _zero_fill_trend(
                trend_by_day, start_dt.date(), end_dt.date()
            )

            return {
                "total_votes": total,
                "up_votes": up,
                "down_votes": down,
                "satisfaction_pct": satisfaction_pct,
                "comment_count": comment_count,
                "daily_trend": daily_trend,
                "date_range": {"start": start_str, "end": end_str},
            }
        finally:
            if conn is not None:
                conn.close()

    return await asyncio.to_thread(_query)


async def _get_low_rated_responses_handler(
    arguments: dict[str, Any],
    client: Any,  # client is unused — feedback analytics reads SQLite directly, not Exchange Online
) -> dict[str, Any]:
    """Return individual thumbs-down feedback entries over a date range.

    Reads the Atlas SQLite database at ATLAS_DB_PATH in read-only mode and
    returns the most recent thumbs-down votes with thread name and comment text.
    """
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

    raw_limit = arguments.get("limit")
    limit = int(raw_limit) if raw_limit is not None else 20
    limit = max(1, min(100, limit))

    def _query() -> dict:
        conn: sqlite3.Connection | None = None
        try:
            try:
                conn = _open_ro(db_path)
            except Exception as exc:
                return {"error": f"Cannot open database: {exc}"}

            rows = conn.execute(LOW_RATED_SQL, (start_str, end_str, limit)).fetchall()
            entries = [
                {
                    "timestamp": row["created_at"],
                    "thread_name": row["thread_name"],
                    "comment": row["comment"] if row["comment"] else None,
                    "has_comment": bool(row["has_comment"]),
                }
                for row in rows
            ]
            return {
                "entries": entries,
                "count": len(entries),
                "date_range": {"start": start_str, "end": end_str},
            }
        finally:
            if conn is not None:
                conn.close()

    return await asyncio.to_thread(_query)
