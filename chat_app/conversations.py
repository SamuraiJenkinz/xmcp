"""Thread CRUD REST API Blueprint for conversation persistence.

Provides 5 JSON endpoints that the sidebar frontend calls via fetch.
All routes require authentication and enforce user_id ownership on every
database query — users can never read or modify another user's threads.
"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request, session

from chat_app.auth import login_required
from chat_app.db import get_db

conversations_bp = Blueprint("conversations_bp", __name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _user_id() -> str:
    """Return the Azure AD OID for the current session user.

    The OID (object ID) is a stable UUID string that uniquely identifies
    the user across the Azure AD tenant.  Falls back to empty string if
    the session has no user (should not occur under @login_required).
    """
    return (session.get("user") or {}).get("oid", "")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@conversations_bp.route("/api/threads", methods=["GET"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
