"""Thread CRUD REST API Blueprint for conversation persistence.

Provides 6 JSON endpoints that the sidebar frontend calls via fetch.
All routes require authentication and enforce user_id ownership on every
database query — users can never read or modify another user's threads.
"""

from __future__ import annotations

import json
import re

from flask import Blueprint, jsonify, request, session

from chat_app.auth import role_required
from chat_app.db import get_db

conversations_bp = Blueprint("conversations_bp", __name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _user_id() -> str:
    """Return the Azure AD OID for the current session user.

    The OID (object ID) is a stable UUID string that uniquely identifies
    the user across the Azure AD tenant.  Falls back to empty string if
    the session has no user (should not occur under @role_required).
    """
    return (session.get("user") or {}).get("oid", "")


def _build_fts5_query(raw: str) -> str | None:
    """Convert a raw search string into a safe FTS5 MATCH expression.

    Each whitespace-delimited token is wrapped in double-quotes (with any
    embedded double-quotes escaped) and given a trailing ``*`` for prefix
    matching.  Returns ``None`` for blank input so callers can short-circuit
    before touching the database.

    Examples::

        'DAG health' -> '"DAG"* "health"*'
        'AND'        -> '"AND"*'        (neutralises bare FTS5 operators)
        ''           -> None
    """
    tokens = raw.strip().split()
    if not tokens:
        return None
    # Escape embedded double-quotes then wrap each token for prefix match.
    parts = ['"' + t.replace('"', '""') + '"*' for t in tokens]
    return " ".join(parts)


def _strip_mark_tags(snippet: str) -> str:
    """Remove <mark> and </mark> tags from a FTS5 snippet() result.

    The snippet() function wraps matched terms in configurable tags.  We use
    <mark>/<mark> as delimiters and strip them here so the API returns plain
    text — the frontend can apply its own highlighting if desired.
    """
    return re.sub(r"</?mark>", "", snippet)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@conversations_bp.route("/api/threads", methods=["GET"])
@role_required
def list_threads():
    """Return all threads for the current user, newest first."""
    db = get_db()
    rows = db.execute(
        "SELECT id, name, updated_at FROM threads"
        " WHERE user_id = ? ORDER BY updated_at DESC",
        (_user_id(),),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@conversations_bp.route("/api/threads", methods=["POST"])
@role_required
def create_thread():
    """Create a new empty thread and its associated messages row.

    Returns the new thread id so the frontend can switch to it immediately.
    """
    db = get_db()
    cur = db.execute(
        "INSERT INTO threads (user_id, name) VALUES (?, '')",
        (_user_id(),),
    )
    thread_id = cur.lastrowid
    db.execute(
        "INSERT INTO messages (thread_id, messages_json) VALUES (?, '[]')",
        (thread_id,),
    )
    db.commit()
    return jsonify({"id": thread_id, "name": ""}), 201


@conversations_bp.route("/api/threads/<int:thread_id>/messages", methods=["GET"])
@role_required
def get_messages(thread_id: int):
    """Return the message history for a thread owned by the current user.

    Returns 404 if the thread does not exist or belongs to another user.
    """
    db = get_db()
    # Verify ownership before touching messages
    thread = db.execute(
        "SELECT id FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, _user_id()),
    ).fetchone()
    if thread is None:
        return jsonify({"error": "Not found"}), 404

    row = db.execute(
        "SELECT messages_json FROM messages WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    messages = json.loads(row["messages_json"]) if row else []
    return jsonify({"messages": messages})


@conversations_bp.route("/api/threads/<int:thread_id>", methods=["PATCH"])
@role_required
def rename_thread(thread_id: int):
    """Rename a thread owned by the current user.

    Reads ``name`` from the JSON request body, strips whitespace, and
    truncates to 100 characters.  The ``updated_at`` timestamp is NOT
    bumped here — renaming should not re-order threads in the sidebar.
    """
    data = request.get_json(force=True) or {}
    new_name = (data.get("name") or "").strip()[:100]
    db = get_db()
    db.execute(
        "UPDATE threads SET name = ?"
        " WHERE id = ? AND user_id = ?",
        (new_name, thread_id, _user_id()),
    )
    db.commit()
    return jsonify({"id": thread_id, "name": new_name})


@conversations_bp.route("/api/threads/<int:thread_id>", methods=["DELETE"])
@role_required
def delete_thread(thread_id: int):
    """Delete a thread owned by the current user.

    The ON DELETE CASCADE constraint in schema.sql removes the associated
    messages row automatically.
    """
    db = get_db()
    db.execute(
        "DELETE FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, _user_id()),
    )
    db.commit()
    return jsonify({"deleted": True})


@conversations_bp.route("/api/threads/search", methods=["GET"])
@role_required
def search_threads():
    """Full-text search across threads owned by the current user.

    Query parameter ``q`` is required.  Returns up to 20 matching threads
    ordered by FTS5 rank (best match first).  Each result includes a plain-
    text snippet with ``...`` context around the matched terms.

    Edge cases handled gracefully (return ``[]`` not 500):
    - Empty or blank ``q``
    - Bare FTS5 operators (``AND``, ``OR``, ``NOT``)
    - Unclosed quotes or other malformed FTS5 input
    """
    raw_q = request.args.get("q", "").strip()
    fts_query = _build_fts5_query(raw_q)
    if fts_query is None:
        return jsonify([])

    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT t.id,
                   t.name,
                   t.updated_at,
                   snippet(threads_fts, 0, '<mark>', '</mark>', '...', 16) AS snippet
            FROM   threads_fts
            JOIN   threads t ON threads_fts.rowid = t.id
            WHERE  threads_fts MATCH ?
            AND    t.user_id = ?
            ORDER  BY rank
            LIMIT  20
            """,
            (fts_query, _user_id()),
        ).fetchall()
    except Exception:
        # Malformed FTS5 expression or any other DB error — return empty list.
        return jsonify([])

    results = [
        {
            "id": r["id"],
            "name": r["name"],
            "updated_at": r["updated_at"],
            "snippet": _strip_mark_tags(r["snippet"] or ""),
        }
        for r in rows
    ]
    return jsonify(results)
