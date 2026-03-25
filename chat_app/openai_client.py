"""Azure OpenAI client wrapper for Atlas chat application.

Connects to the MMC stg1 gateway endpoint using the standard openai.OpenAI
client (not AzureOpenAI) with a custom base_url. The gateway endpoint in
CHATGPT_ENDPOINT ends in /chat/completions — we strip that suffix since the
SDK appends it automatically.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from chat_app.config import Config
from chat_app.context_mgr import prune_conversation
from chat_app.mcp_client import call_mcp_tool, get_openai_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool-call loop constants
# ---------------------------------------------------------------------------

#: Maximum number of tool-calling iterations before forcing a final answer.
_MAX_TOOL_ITERATIONS: int = 5

#: Controls which OpenAI tools parameter format is used.
#: True  → use 'tools' / 'tool_choice'  (current spec)
#: False → use deprecated 'functions' / 'function_call' (fallback for older gateways)
_use_tools_param: bool = True

SYSTEM_PROMPT = """You are Atlas, MMC's Exchange infrastructure assistant built by Colleague Tech Services.

You help colleagues query live Exchange environment data — mailboxes, DAG health, mail flow, connectors, DKIM/DMARC, hybrid configuration, and mobile devices. You can also look up colleague profiles.

Rules:
1. Only answer questions about Exchange infrastructure or colleague lookups. If asked about unrelated topics, politely redirect: "I'm Atlas, built specifically for Exchange infrastructure queries and colleague lookups. I can help with mailbox stats, DAG health, mail flow, connectors, finding colleagues, and more. What would you like to know?"
2. When you have Exchange tools available, use them to get live data rather than guessing.
3. Present Exchange data in a clear, conversational way — summarize key findings, flag any concerning values (queue backlogs, unhealthy replication, disabled connectors), and offer follow-up suggestions.
4. Never fabricate Exchange data. If a tool call fails or returns an error, tell the user what went wrong and suggest alternatives.
5. Keep responses concise but informative. Use bullet points or tables for structured data when appropriate.
6. Address the user by name when available. Be helpful, professional, and direct.
7. Never assume or state identity associations between accounts. Only report what the tool result contains. If a tool result uses an email or ID without a display name, do NOT infer who that account belongs to from earlier conversation context — different accounts are different people.

## On-Premises vs Exchange Online Tools

Some tools only work against on-premises Exchange servers and will fail if the environment is Exchange Online:
- **On-prem only:** get_smtp_connectors, list_dag_members, get_dag_health, get_database_copies, get_transport_queues
- **Exchange Online only:** get_connector_status (uses Get-InboundConnector/Get-OutboundConnector)
- **Both environments:** All other tools (mailbox, permissions, mobile devices, DNS lookups, hybrid config, colleague lookup)

If an on-prem tool fails with a PowerShell error, tell the user: "This tool requires an on-premises Exchange connection. Your environment appears to be Exchange Online."

## Connector Queries

You have two different connector tools for different environments:
- get_smtp_connectors: On-premises Exchange Send/Receive connectors (Get-SendConnector, Get-ReceiveConnector). Only works against on-prem Exchange servers.
- get_connector_status: Exchange Online hybrid connectors (Get-InboundConnector, Get-OutboundConnector). Only works against Exchange Online.

Rules:
8. When a user asks about connectors, mail routing, or relay configuration, ask them to clarify: "Would you like to check **on-premises** connectors (Send/Receive) or **Exchange Online** connectors (Inbound/Outbound)?" Then use the appropriate tool based on their answer.
9. If the user has already specified "on-prem", "on-premises", or "send/receive connector" in their query, use get_smtp_connectors directly.
10. If the user has already specified "Exchange Online", "EXO", "cloud", "inbound", or "outbound" in their query, use get_connector_status directly.

## Colleague Lookup

You have two tools for finding colleagues:
- search_colleagues: Use when asked to find a colleague by name or email (e.g., 'find Jane Smith', 'who is alice@company.com?', 'look up Bob'). Returns up to 10 matches with name, title, department, and email.
- get_colleague_profile: Use when you have a specific email or user ID and want the full profile with photo. Requires a user_id parameter (accepts email address).

Rules:
11. When search_colleagues returns exactly 1 match, immediately call get_colleague_profile using that match's email as the user_id. Do not ask the user to confirm.
12. When search_colleagues returns multiple matches, do NOT list the results in your text — the UI automatically renders search result cards. Respond briefly, e.g. "I found 3 people matching 'Anderson'. Which one would you like the full profile for?" Only call get_colleague_profile after the user identifies a specific person.
13. Never call get_colleague_profile speculatively or before you have a specific email/ID.
14. After get_colleague_profile succeeds, do NOT list the profile fields in your text response — the UI automatically renders a profile card. Respond briefly, for example: "Here's Jane Smith's profile." or "Found it — here's their profile card." """

_client: OpenAI | None = None


def _get_base_url() -> str:
    """Derive SDK base_url from CHATGPT_ENDPOINT.

    The env var is the full path ending in /chat/completions.
    The SDK appends /chat/completions automatically, so strip it.

    Example:
        CHATGPT_ENDPOINT = "https://stg1.example.com/coreapi/openai/v1/deployments/model/chat/completions"
        _get_base_url()  -> "https://stg1.example.com/coreapi/openai/v1/deployments/model"
    """
    endpoint = Config.CHATGPT_ENDPOINT
    suffix = "/chat/completions"
    if endpoint.endswith(suffix):
        return endpoint[: -len(suffix)]
    return endpoint


def init_openai() -> None:
    """Initialize the OpenAI client. Called once at app startup.

    Uses openai.OpenAI (not AzureOpenAI) with a custom base_url derived by
    stripping /chat/completions from CHATGPT_ENDPOINT. The MMC gateway also
    accepts the api-key header so we set it in default_headers.
    """
    global _client
    base_url = _get_base_url()
    _client = OpenAI(
        base_url=base_url,
        api_key=Config.AZURE_OPENAI_API_KEY,
        default_headers={
            "api-key": Config.AZURE_OPENAI_API_KEY,  # MMC gateway may expect this header
        },
    )
    logger.info("OpenAI client initialized (base_url=%s)", base_url)


def get_client() -> OpenAI:
    """Return the initialized OpenAI client.

    Raises:
        RuntimeError: If init_openai() has not been called.
    """
    if _client is None:
        raise RuntimeError("OpenAI client not initialized — call init_openai() first")
    return _client


def _message_to_dict(message) -> dict:
    """Convert an OpenAI SDK ChatCompletionMessage to a plain dict.

    SDK objects are NOT JSON-serializable. We must convert to plain dicts
    before storing in session or passing to subsequent API calls.

    Handles tool_calls when present (used in 07-05 tool-call loop).
    """
    result = {
        "role": message.role,
        "content": message.content,
    }
    if hasattr(message, "tool_calls") and message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]
    return result


def chat_completion(messages: list[dict]) -> dict:
    """Run a single chat completion (no tools, no streaming).

    Args:
        messages: Conversation history as plain dicts with 'role' and 'content'.

    Returns:
        Assistant message as a plain dict with 'role' and 'content'.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=messages,
    )
    assistant_msg = response.choices[0].message
    return _message_to_dict(assistant_msg)


def build_system_message(user_name: str = "Colleague") -> dict:
    """Build the system message dict for the conversation.

    Args:
        user_name: Display name of the authenticated user (unused in prompt
            body for now, reserved for future personalisation).

    Returns:
        System message dict with 'role': 'system' and SYSTEM_PROMPT as content.
    """
    return {
        "role": "system",
        "content": SYSTEM_PROMPT,
    }


def run_tool_loop(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> tuple[list[dict], list[dict[str, Any]]]:
    """Run the OpenAI chat-completion + MCP tool-calling loop.

    Repeatedly calls the OpenAI completion API.  When the model returns
    ``tool_calls`` (or legacy ``function_call``), each tool is dispatched
    sequentially to MCP via ``call_mcp_tool`` and the results are appended as
    ``role=tool`` (or ``role=function``) messages.  Looping continues until the
    model produces a response with no pending tool calls or until
    ``_MAX_TOOL_ITERATIONS`` iterations have been consumed.

    Falls back from the current ``tools`` / ``tool_choice`` parameter format to
    the deprecated ``functions`` / ``function_call`` format if the MMC gateway
    rejects the request (e.g. API version 2023-05-15 may not support ``tools``).
    The fallback state is stored in the module-level ``_use_tools_param`` flag so
    all subsequent calls within the same process use the compatible format.

    Args:
        messages: Conversation history as plain dicts (mutated in-place by
                  appending assistant and tool messages).
        tools:    Optional list of OpenAI tool schemas.  If ``None`` the cached
                  schemas from ``get_openai_tools()`` are used.

    Returns:
        Tuple of ``(messages, tool_events)`` where:
        - ``messages`` is the updated conversation history (all plain dicts).
        - ``tool_events`` is a list of ``{"name": str, "status": str}`` dicts
          for each tool invocation, suitable for streaming to the UI.
    """
    global _use_tools_param  # noqa: PLW0603

    client = get_client()
    if tools is None:
        tools = get_openai_tools()

    tool_events: list[dict[str, Any]] = []

    for _iteration in range(_MAX_TOOL_ITERATIONS):
        # Build completion kwargs depending on which parameter format to use.
        if _use_tools_param:
            kwargs: dict[str, Any] = {
                "model": Config.OPENAI_MODEL,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
        else:
            # Deprecated 'functions' format for older gateway API versions
            kwargs = {
                "model": Config.OPENAI_MODEL,
                "messages": messages,
            }
            if tools:
                # Convert from OpenAI tools schema to legacy functions schema
                functions = [t["function"] for t in tools]
                kwargs["functions"] = functions
                kwargs["function_call"] = "auto"

        # Call the completion API; detect 'tools' rejection and retry with fallback.
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            exc_str = str(exc)
            if _use_tools_param and (
                "tools" in exc_str.lower()
                or "unrecognized" in exc_str.lower()
                or "unsupported" in exc_str.lower()
            ):
                logger.warning(
                    "Gateway rejected 'tools' parameter (%s); switching to deprecated 'functions' format",
                    exc_str,
                )
                _use_tools_param = False
                # Retry immediately with functions format
                functions = [t["function"] for t in tools] if tools else []
                retry_kwargs: dict[str, Any] = {
                    "model": Config.OPENAI_MODEL,
                    "messages": messages,
                }
                if functions:
                    retry_kwargs["functions"] = functions
                    retry_kwargs["function_call"] = "auto"
                response = client.chat.completions.create(**retry_kwargs)
            else:
                raise

        choice = response.choices[0]
        assistant_msg = _message_to_dict(choice.message)
        messages.append(assistant_msg)

        # --- Handle current tool_calls format ---
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_name = tc.function.name
                try:
                    arguments = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    arguments = {}
                logger.info("Dispatching MCP tool: %s(%s)", tool_name, arguments)
                try:
                    result_text = call_mcp_tool(tool_name, arguments)
                    tool_events.append({
                        "name": tool_name,
                        "status": "success",
                        "params": arguments,
                        "result": result_text,
                    })
                except Exception as exc:
                    result_text = f"Tool error: {exc}"
                    tool_events.append({
                        "name": tool_name,
                        "status": "error",
                        "params": arguments,
                        "result": result_text,
                    })
                    logger.warning("MCP tool %s failed: %s", tool_name, exc)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_name,
                        "content": result_text,
                    }
                )
            # Prune after tool results to stay within context window
            messages = prune_conversation(messages)
            # Continue looping — send tool results back to the model
            continue

        # --- Handle legacy function_call format ---
        if choice.message.function_call:
            fc = choice.message.function_call
            tool_name = fc.name
            try:
                arguments = json.loads(fc.arguments) if fc.arguments else {}
            except json.JSONDecodeError:
                arguments = {}
            logger.info("Dispatching MCP tool (legacy function_call): %s(%s)", tool_name, arguments)
            try:
                result_text = call_mcp_tool(tool_name, arguments)
                tool_events.append({
                    "name": tool_name,
                    "status": "success",
                    "params": arguments,
                    "result": result_text,
                })
            except Exception as exc:
                result_text = f"Tool error: {exc}"
                tool_events.append({
                    "name": tool_name,
                    "status": "error",
                    "params": arguments,
                    "result": result_text,
                })
                logger.warning("MCP tool %s failed: %s", tool_name, exc)
            messages.append(
                {
                    "role": "function",
                    "name": tool_name,
                    "content": result_text,
                }
            )
            # Prune after tool results to stay within context window
            messages = prune_conversation(messages)
            # Continue looping — send function result back to the model
            continue

        # No tool calls — model produced a final text response; exit loop
        break

    else:
        logger.warning(
            "Tool-calling loop hit maximum iterations (%d) without reaching a final response",
            _MAX_TOOL_ITERATIONS,
        )

    return messages, tool_events


def chat_with_tools(
    messages: list[dict],
    user_message: str,
) -> tuple[list[dict], list[dict[str, Any]]]:
    """Append a user message and run the full tool-calling loop.

    Convenience wrapper that combines appending the user turn with
    ``run_tool_loop``.  Suitable for use from Flask request handlers.

    Args:
        messages:     Conversation history as plain dicts (mutated in-place).
        user_message: The user's new message text.

    Returns:
        Tuple of ``(messages, tool_events)`` — see ``run_tool_loop`` for detail.
    """
    messages.append({"role": "user", "content": user_message})
    return run_tool_loop(messages)
