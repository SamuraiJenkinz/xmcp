"""Azure OpenAI client wrapper for Atlas chat application.

Connects to the MMC stg1 gateway endpoint using the standard openai.OpenAI
client (not AzureOpenAI) with a custom base_url. The gateway endpoint in
CHATGPT_ENDPOINT ends in /chat/completions — we strip that suffix since the
SDK appends it automatically.
"""

from __future__ import annotations

import logging

from openai import OpenAI

from chat_app.config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Atlas, MMC's Exchange infrastructure assistant built by Colleague Tech Services.

You help colleagues query live Exchange environment data — mailboxes, DAG health, mail flow, connectors, DKIM/DMARC, hybrid configuration, and mobile devices.

Rules:
1. Only answer questions about Exchange infrastructure. If asked about unrelated topics, politely redirect: "I'm Atlas, built specifically for Exchange infrastructure queries. I can help with mailbox stats, DAG health, mail flow, connectors, and more. What would you like to know?"
2. When you have Exchange tools available, use them to get live data rather than guessing.
3. Present Exchange data in a clear, conversational way — summarize key findings, flag any concerning values (queue backlogs, unhealthy replication, disabled connectors), and offer follow-up suggestions.
4. Never fabricate Exchange data. If a tool call fails or returns an error, tell the user what went wrong and suggest alternatives.
5. Keep responses concise but informative. Use bullet points or tables for structured data when appropriate.
6. Address the user by name when available. Be helpful, professional, and direct."""

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
