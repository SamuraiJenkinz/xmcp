"""Per-message feedback REST API Blueprint.

Provides endpoints to submit, retrieve, and retract thumbs up/down
feedback on assistant messages. All routes require @role_required
and enforce thread ownership — users can never access another user's
feedback or threads.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from chat_app.auth import role_required
from chat_app.db import get_db

feedback_bp = Blueprint("feedback_bp", __name__)


def _user_id() -> str:
    """Return the Azure AD OID for the current session user."""
    return (session.get("user") or {}).get("oid", "")


def _owns_thread(db, thread_id: int, user_id: str) -> bool:
    """Return True if the thread exists and belongs to the user."""
    row = db.execute(
        "SELECT id FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, user_id),
    ).fetchone()
    return row is not None


@feedback_bp.route("/api/threads/<int:thread_id>/feedback", methods=["GET"])
@role_required
def get_feedback(thread_id: int):
    """Return all feedback votes for a thread owned by the current user."""
    db = get_db()
    uid = _user_id()
    if not _owns_thread(db, thread_id, uid):
        return jsonify({"error": "Not found"}), 404

    rows = db.execute(
        "SELECT assistant_message_idx, vote, comment"
        " FROM feedback"
        " WHERE thread_id = ? AND user_id = ?",
        (thread_id, uid),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@feedback_bp.route(
    "/api/threads/<int:thread_id>/feedback/<int:message_index>",
    methods=["POST"],
)
@role_required
def submit_feedback(thread_id: int, message_index: int):
    """Upsert a vote. Body: {"vote": "up"|"down", "comment": "..."}

    If vote is null or missing, delegates to retraction (DELETE).
    """
    db = get_db()
    uid = _user_id()
    if not _owns_thread(db, thread_id, uid):
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) or {}
    vote = data.get("vote")

    # vote=null means retract
    if vote is None:
        db.execute(
            "DELETE FROM feedback"
            " WHERE thread_id = ? AND assistant_message_idx = ? AND user_id = ?",
            (thread_id, message_index, uid),
        )
        db.commit()
        return jsonify({"retracted": True})

    if vote not in ("up", "down"):
        return jsonify({"error": "vote must be 'up' or 'down'"}), 400

    comment = (data.get("comment") or "")[:500] or None  # truncate, None if empty

    db.execute(
        "INSERT INTO feedback"
        " (thread_id, assistant_message_idx, user_id, vote, comment, updated_at)"
        " VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
        " ON CONFLICT(thread_id, assistant_message_idx, user_id)"
        " DO UPDATE SET vote=excluded.vote, comment=excluded.comment,"
        "  updated_at=excluded.updated_at",
        (thread_id, message_index, uid, vote, comment),
    )
    db.commit()
    return jsonify({"vote": vote, "comment": comment})


@feedback_bp.route(
    "/api/threads/<int:thread_id>/feedback/<int:message_index>",
    methods=["DELETE"],
)
@role_required
def delete_feedback(thread_id: int, message_index: int):
    """Retract a vote by deleting the row."""
    db = get_db()
    uid = _user_id()
    if not _owns_thread(db, thread_id, uid):
        return jsonify({"error": "Not found"}), 404

    db.execute(
        "DELETE FROM feedback"
        " WHERE thread_id = ? AND assistant_message_idx = ? AND user_id = ?",
        (thread_id, message_index, uid),
    )
    db.commit()
    return jsonify({"retracted": True})
