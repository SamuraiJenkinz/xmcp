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

#: Reserve tokens for the model's reply + tool definitions (~1,700 tokens)
_SAFETY_BUFFER: int = 8_192

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


def _group_messages(non_system: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group non-system messages into atomic units that must be removed together.

    Groups:
    - A standalone user or assistant message (no tool_calls) is its own group.
    - An assistant message with tool_calls + all subsequent tool/function result
      messages form one group (removing the assistant without the tool results
      causes an OpenAI API error).
    """
    groups: list[list[dict[str, Any]]] = []
    i = 0
    while i < len(non_system):
        msg = non_system[i]
        # Assistant with tool_calls — group with all following tool results
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            group = [msg]
            i += 1
            while i < len(non_system) and non_system[i].get("role") in ("tool", "function"):
                group.append(non_system[i])
                i += 1
            groups.append(group)
        # Orphaned tool/function result (no preceding assistant) — group alone
        elif msg.get("role") in ("tool", "function"):
            groups.append([msg])
            i += 1
        else:
            groups.append([msg])
            i += 1
    return groups


def prune_conversation(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove oldest non-system message groups until the conversation fits in the limit.

    Preserves:
    - All system messages (role == "system")
    - The most recent message group (to avoid sending an empty conversation)

    Tool call groups (assistant + tool results) are removed atomically to
    prevent orphaned tool messages that OpenAI would reject.

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
        return list(messages)

    # Group messages so tool call chains are removed atomically
    groups = _group_messages(non_system)

    while len(groups) > 1:
        # Flatten remaining groups
        remaining = [m for g in groups for m in g]
        candidate = system_messages + remaining
        candidate_count = count_tokens_in_messages(candidate)
        if candidate_count <= _EFFECTIVE_LIMIT:
            logger.info(
                "Pruned conversation to %d tokens (%d messages removed)",
                candidate_count,
                len(messages) - len(candidate),
            )
            return candidate
        # Remove the oldest group (may be a single message or a tool call chain)
        groups.pop(0)

    # Only one group remains
    result = system_messages + [m for g in groups for m in g]
    final_count = count_tokens_in_messages(result)
    logger.warning(
        "After maximum pruning conversation is still %d tokens "
        "(keeping last message group + system messages)",
        final_count,
    )
    return result
