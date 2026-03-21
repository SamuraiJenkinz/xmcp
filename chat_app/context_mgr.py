"""tiktoken-based token counting and conversation pruning for Atlas chat.

Manages the gpt-4o-mini context window (128 K tokens) by counting tokens using
the o200k_base encoding and pruning the oldest non-system messages when the
conversation approaches the limit.

Token counting follows the OpenAI cookbook recipe:
- 3 tokens reply primer for the whole conversation
- 3 tokens per-message overhead
- Tokens for each string value in the message (role, content, name, etc.)
- For tool_calls: tokens for function name and arguments strings

Reference:
    https://github.com/openai/openai-cookbook/blob/main/examples/
    How_to_count_tokens_with_tiktoken.ipynb
"""

from __future__ import annotations

import logging
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENCODING = tiktoken.get_encoding("o200k_base")

#: gpt-4o-mini context window (tokens)
_MAX_TOKENS: int = 128_000

#: Reserve this many tokens for the model's reply
_SAFETY_BUFFER: int = 4_096

#: Prune when the conversation exceeds this many tokens
_EFFECTIVE_LIMIT: int = _MAX_TOKENS - _SAFETY_BUFFER

#: Per-message overhead (OpenAI cookbook: every message has 3 overhead tokens)
_TOKENS_PER_MESSAGE: int = 3

#: Reply primer overhead — added once for the whole conversation
_TOKENS_REPLY_PRIMER: int = 3


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _count_str(s: str) -> int:
    """Return the number of tokens in a single string."""
    return len(_ENCODING.encode(s))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def count_tokens_in_messages(messages: list[dict[str, Any]]) -> int:
    """Count tokens in a list of chat messages using the o200k_base encoding.

    Follows the OpenAI cookbook recipe:
    - ``_TOKENS_REPLY_PRIMER`` added once for the whole conversation
    - ``_TOKENS_PER_MESSAGE`` added for every message
    - Tokens counted for every string value: role, content, name, tool_call_id
    - For ``tool_calls`` entries: tokens for function name + arguments

    Args:
        messages: List of message dicts as stored in the conversation history.

    Returns:
        Estimated total token count.
    """
    num_tokens = _TOKENS_REPLY_PRIMER

    for message in messages:
        num_tokens += _TOKENS_PER_MESSAGE

        # role
        role = message.get("role", "")
        if isinstance(role, str):
            num_tokens += _count_str(role)

        # content (may be None for tool-call-only assistant messages)
        content = message.get("content")
        if isinstance(content, str):
            num_tokens += _count_str(content)
        elif isinstance(content, list):
            # Multi-part content (e.g. text + image_url parts)
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text", "")
                    if isinstance(text, str):
                        num_tokens += _count_str(text)

        # name (tool message name field or user name)
        name = message.get("name")
        if isinstance(name, str):
            num_tokens += _count_str(name)

        # tool_call_id
        tool_call_id = message.get("tool_call_id")
        if isinstance(tool_call_id, str):
            num_tokens += _count_str(tool_call_id)

        # tool_calls (assistant message with function call requests)
        tool_calls = message.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    fn_name = func.get("name", "")
                    fn_args = func.get("arguments", "")
                    if isinstance(fn_name, str):
                        num_tokens += _count_str(fn_name)
                    if isinstance(fn_args, str):
                        num_tokens += _count_str(fn_args)

    return num_tokens


def get_token_count(messages: list[dict[str, Any]]) -> int:
    """Convenience wrapper around count_tokens_in_messages.

    Args:
        messages: List of message dicts.

    Returns:
        Estimated total token count.
    """
    return count_tokens_in_messages(messages)


def prune_conversation(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove oldest non-system messages until the conversation fits in the limit.

    Preserves:
    - All system messages (role == "system")
    - The most recent user message (to avoid sending an empty conversation)

    Non-system, non-latest-user messages are removed oldest-first until
    ``count_tokens_in_messages(result) <= _EFFECTIVE_LIMIT``.

    Does NOT mutate the input list.

    Args:
        messages: Conversation history as plain dicts.

    Returns:
        New list fitting within ``_EFFECTIVE_LIMIT`` tokens.
    """
    current_count = count_tokens_in_messages(messages)
    if current_count <= _EFFECTIVE_LIMIT:
        return list(messages)

    logger.info(
        "Conversation at %d tokens (limit %d) — pruning oldest messages",
        current_count,
        _EFFECTIVE_LIMIT,
    )

    # Separate system messages from non-system messages
    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if not non_system:
        # Nothing to prune — only system messages
        return list(messages)

    # We always keep at least the latest message (to avoid an empty context)
    # Attempt to prune from the oldest non-system messages first
    while len(non_system) > 1:
        # Rebuild conversation: system messages first, then remaining non-system
        candidate = system_messages + non_system
        candidate_count = count_tokens_in_messages(candidate)
        if candidate_count <= _EFFECTIVE_LIMIT:
            logger.info(
                "Pruned conversation to %d tokens (%d messages removed)",
                candidate_count,
                len(messages) - len(candidate),
            )
            return candidate
        # Remove the oldest non-system message
        non_system.pop(0)

    # Only one non-system message remains — return system + that message
    result = system_messages + non_system
    final_count = count_tokens_in_messages(result)
    logger.warning(
        "After maximum pruning conversation is still %d tokens "
        "(keeping 1 non-system message + system messages)",
        final_count,
    )
    return result
