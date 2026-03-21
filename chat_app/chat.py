"""Flask Blueprint: chat SSE streaming endpoint.

Provides one route:

- POST /chat/stream  — SSE endpoint that reads conversation from SQLite,
  runs the MCP tool-calling loop, sends tool status chips as SSE events,
  then streams the final AI response chunk by chunk using OpenAI streaming
  completions, then writes the updated conversation back to SQLite.

SSE event format (newline-delimited)::

    data: {"type": "tool",         "name": "<tool_name>", "status": "success|error"}\\n\\n
    data: {"type": "text",         "delta": "<chunk>"}\\n\\n
    data: {"type": "thread_named", "thread_id": <id>, "name": "<auto-name>"}\\n\\n
    data: {"type": "done"}\\n\\n
    data: {"type": "error",        "message": "<description>"}\\n\\n

Design notes:
- All session data and DB reads occur BEFORE entering the SSE generator
  (stream_with_context pattern) to prevent "Working outside of request
  context" errors with some session backends.
- Thread ownership is verified before entering the generator: the thread_id
  AND user_id must match, so users can never read or write another user's
  conversation.
- Conversation history is stored in the messages.messages_json column as a
  JSON array of OpenAI-format message dicts.  One row per thread (1:1).
- Auto-naming: when a thread's name is empty (newly created), the first user
  message is truncated to ~30 chars to produce a human-readable sidebar name.
  A ``thread_named`` SSE event is emitted before ``done`` so the frontend
  can update the sidebar title without a network round-trip.
- The tool-calling loop runs non-streaming (blocking) first; only the final
  text response is streamed chunk-by-chunk.
- After run_tool_loop the last assistant message in the conversation is the
  non-streaming final answer; we remove it before requesting the streaming
  response so we don't duplicate it.
- The complete streamed response is assembled from deltas and appended to the
  conversation as a plain assistant message before writing to SQLite.
- db.commit() is called explicitly after every write — close_db does not
  commit.
"""

from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Generator

from flask import Blueprint, Response, request, session, stream_with_context

from chat_app.auth import login_required
from chat_app.context_mgr import prune_conversation
from chat_app.db import get_db
from chat_app.openai_client import (
    SYSTEM_PROMPT,
    build_system_message,
    get_client,
    run_tool_loop,
)
from chat_app.config import Config

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat_bp", __name__)


# ---------------------------------------------------------------------------
# Auto-naming helpers
# ---------------------------------------------------------------------------


def _auto_name(text: str, max_chars: int = 30) -> str:
    """Truncate *text* to *max_chars* characters for use as a thread name.

    If the text is within the limit it is returned as-is (stripped).
    Otherwise it is trimmed at *max_chars* characters (trailing whitespace
    removed) and an ellipsis character (U+2026) is appended.

    Args:
        text:      Raw user message text.
        max_chars: Maximum character count before truncation (default 30).

    Returns:
        A short string suitable for the threads.name column.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\u2026"


def _fallback_name() -> str:
    """Return a timestamp-based thread name when the user message is empty.

    Format: ``Chat — Mar 21, 2:30 PM``

    Uses Windows-style format directives (%#d, %#I) to suppress leading
    zeros on day and hour — the server runs on Windows.

    Returns:
        A human-readable timestamp string.
    """
    now = datetime.datetime.now()
    return now.strftime("Chat \u2014 %b %#d, %#I:%M %p")


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def _sse(event_dict: dict[str, Any]) -> str:
    """Format a dict as an SSE ``data:`` line.

    Args:
        event_dict: Arbitrary JSON-serialisable dict.

    Returns:
        String in SSE wire format: ``data: <json>\\n\\n``
    """
    return f"data: {json.dumps(event_dict)}\n\n"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@chat_bp.route("/chat/stream", methods=["POST"])
@login_required
def chat_stream() -> Response:
    """SSE endpoint: process a user message and stream the AI response.

    Request body (JSON):
        ``{"message": "<user text>", "thread_id": <int>}``

    Returns:
        A ``text/event-stream`` response containing:

        1. Zero or more ``tool`` events for each MCP tool call made.
        2. One or more ``text`` events with delta chunks of the AI response.
        3. A ``thread_named`` event if the thread was auto-named (first msg).
        4. A single ``done`` event when the stream is complete.
        5. An ``error`` event if something goes wrong (replaces done).
    """
    # -----------------------------------------------------------------------
    # Read ALL session/request data BEFORE entering the generator.
    # Flask's stream_with_context carries the request context, but reading
    # from session inside a generator can be unreliable across thread
    # boundaries with some session backends.
    # -----------------------------------------------------------------------
    body = request.json or {}
    user_message: str = body.get("message", "").strip()
    thread_id = body.get("thread_id")

    if not user_message:
        return Response(
            _sse({"type": "error", "message": "No message provided"}),
            content_type="text/event-stream",
        )

    if thread_id is None:
        return Response(
            _sse({"type": "error", "message": "No thread selected"}),
            content_type="text/event-stream",
        )

    # Capture user identity for ownership check and logging
    user_info = session.get("user") or {}
    username = user_info.get("preferred_username", "unknown")
    user_id = user_info.get("oid", "")

    # Verify thread ownership before entering the generator — never trust
    # a frontend-supplied ID without confirming it belongs to this user.
    db = get_db()
    thread_row = db.execute(
        "SELECT id, name FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, user_id),
    ).fetchone()

    if thread_row is None:
        return Response(
            _sse({"type": "error", "message": "Thread not found"}),
            content_type="text/event-stream",
        )

    # Load conversation from SQLite (replaces former session["conversation"])
    msg_row = db.execute(
        "SELECT messages_json FROM messages WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    conversation: list[dict[str, Any]] = (
        json.loads(msg_row["messages_json"]) if msg_row else []
    )
    if not conversation:
        conversation = [build_system_message()]

    # Capture current thread name BEFORE generator for auto-naming decision
    thread_name: str = thread_row["name"] if thread_row["name"] else ""

    def generate() -> Generator[str, None, None]:
        nonlocal conversation

        # Track the auto-generated name so the thread_named event can be
        # emitted before done.
        auto_name_applied: str | None = None

        try:
            # ---------------------------------------------------------------
            # 1. Append user message and prune conversation
            # ---------------------------------------------------------------
            conversation.append({"role": "user", "content": user_message})
            conversation = prune_conversation(conversation)

            logger.info("Chat request from %s: %r", username, user_message[:80])

            # ---------------------------------------------------------------
            # 2. Run tool-calling loop (non-streaming) to resolve Exchange data
            # ---------------------------------------------------------------
            conversation, tool_events = run_tool_loop(conversation)

            # ---------------------------------------------------------------
            # 3. Send tool status chips as SSE events
            # ---------------------------------------------------------------
            for event in tool_events:
                yield _sse({
                    "type": "tool",
                    "name": event["name"],
                    "status": event["status"],
                })

            # ---------------------------------------------------------------
            # 4. Remove the last assistant message that run_tool_loop appended
            #    (non-streaming final answer) so we can stream it fresh.
            # ---------------------------------------------------------------
            if conversation and conversation[-1].get("role") == "assistant":
                conversation = conversation[:-1]

            # ---------------------------------------------------------------
            # 5. Stream final AI response chunk-by-chunk
            # ---------------------------------------------------------------
            client = get_client()
            stream = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=conversation,
                stream=True,
            )

            full_response_parts: list[str] = []
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                delta_text = delta.content if delta.content is not None else ""
                if delta_text:
                    full_response_parts.append(delta_text)
                    yield _sse({"type": "text", "delta": delta_text})

            # ---------------------------------------------------------------
            # 6. Append complete assistant message and persist to SQLite
            # ---------------------------------------------------------------
            full_response = "".join(full_response_parts)
            conversation.append({"role": "assistant", "content": full_response})

            # Write updated conversation back to the messages table
            db = get_db()
            db.execute(
                "UPDATE messages SET messages_json = ? WHERE thread_id = ?",
                (json.dumps(conversation), thread_id),
            )

            # Auto-name thread if this is the first message (name is empty).
            # Touch updated_at on every message so the thread sorts to top.
            if not thread_name:
                auto_name_applied = (
                    _auto_name(user_message)
                    if user_message.strip()
                    else _fallback_name()
                )
                db.execute(
                    "UPDATE threads"
                    " SET name = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')"
                    " WHERE id = ?",
                    (auto_name_applied, thread_id),
                )
            else:
                db.execute(
                    "UPDATE threads"
                    " SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')"
                    " WHERE id = ?",
                    (thread_id,),
                )

            db.commit()

            logger.info(
                "Chat response to %s: %d chars, %d tool calls",
                username,
                len(full_response),
                len(tool_events),
            )

            # ---------------------------------------------------------------
            # 7. Emit thread_named event if auto-naming occurred
            # ---------------------------------------------------------------
            if auto_name_applied is not None:
                yield _sse({
                    "type": "thread_named",
                    "thread_id": thread_id,
                    "name": auto_name_applied,
                })

            # ---------------------------------------------------------------
            # 8. Signal stream completion
            # ---------------------------------------------------------------
            yield _sse({"type": "done"})

        except Exception as exc:
            logger.exception("Error in chat_stream for user %s: %s", username, exc)
            yield _sse({"type": "error", "message": str(exc)})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx proxy buffering
        },
    )
