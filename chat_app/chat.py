"""Flask Blueprint: chat SSE streaming endpoint.

Provides two routes:

- POST /chat/stream  — SSE endpoint that runs the MCP tool-calling loop,
  sends tool status chips as SSE events, then streams the final AI response
  chunk by chunk using OpenAI streaming completions.

- POST /chat/clear   — Clears the conversation history from the session.

SSE event format (newline-delimited)::

    data: {"type": "tool",  "name": "<tool_name>", "status": "success|error"}\\n\\n
    data: {"type": "text",  "delta": "<chunk>"}\\n\\n
    data: {"type": "done"}\\n\\n
    data: {"type": "error", "message": "<description>"}\\n\\n

Design notes:
- Session data is read BEFORE entering the SSE generator (stream_with_context
  pattern) to prevent "Working outside of request context" errors.
- The tool-calling loop runs non-streaming (blocking) first; only the final
  text response is streamed chunk-by-chunk.
- After run_tool_loop the last assistant message in the conversation is the
  non-streaming final answer; we remove it before requesting the streaming
  response so we don't duplicate it.
- The complete streamed response is assembled from deltas and appended to the
  conversation as a plain assistant message before saving to session.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Generator

from flask import Blueprint, Response, request, session, stream_with_context

from chat_app.auth import login_required
from chat_app.context_mgr import prune_conversation
from chat_app.openai_client import (
    SYSTEM_PROMPT,
    build_system_message,
    get_client,
    run_tool_loop,
)
from chat_app.config import Config

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat_bp", __name__)

# Session key for conversation history
_CONVERSATION_KEY = "conversation"


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
        ``{"message": "<user text>"}``

    Returns:
        An ``text/event-stream`` response containing:

        1. Zero or more ``tool`` events for each MCP tool call made.
        2. One or more ``text`` events with delta chunks of the AI response.
        3. A single ``done`` event when the stream is complete.
        4. An ``error`` event if something goes wrong.
    """
    # -----------------------------------------------------------------------
    # Read ALL session/request data BEFORE entering the generator.
    # Flask's stream_with_context carries the request context, but reading
    # from session inside a generator can be unreliable across thread
    # boundaries with some session backends.
    # -----------------------------------------------------------------------
    user_message: str = (request.json or {}).get("message", "").strip()
    if not user_message:
        return Response(
            _sse({"type": "error", "message": "No message provided"}),
            content_type="text/event-stream",
        )

    # Load (or initialise) conversation history from session
    conversation: list[dict[str, Any]] = session.get(_CONVERSATION_KEY, [])
    if not conversation:
        conversation = [build_system_message()]

    # Capture user identity for logging before entering generator
    user_info = session.get("user") or {}
    username = user_info.get("preferred_username", "unknown")

    def generate() -> Generator[str, None, None]:
        nonlocal conversation

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
            # run_tool_loop appends the final assistant message to conversation.
            # We strip it here and re-request via streaming completions so the
            # user sees partial text as it arrives.
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
            # 6. Append complete assistant message and save to session
            # ---------------------------------------------------------------
            full_response = "".join(full_response_parts)
            conversation.append({"role": "assistant", "content": full_response})
            session[_CONVERSATION_KEY] = conversation
            session.modified = True

            logger.info(
                "Chat response to %s: %d chars, %d tool calls",
                username,
                len(full_response),
                len(tool_events),
            )

            # ---------------------------------------------------------------
            # 7. Signal stream completion
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


@chat_bp.route("/chat/clear", methods=["POST"])
@login_required
def chat_clear() -> tuple[dict[str, Any], int]:
    """Clear the conversation history from the session.

    Returns:
        JSON ``{"cleared": true}`` with HTTP 200.
    """
    session.pop(_CONVERSATION_KEY, None)
    session.modified = True
    logger.info(
        "Conversation cleared for user %s",
        (session.get("user") or {}).get("preferred_username", "unknown"),
    )
    return {"cleared": True}, 200
