"""Exchange Online MCP server — stdio transport entry point.

Logging is configured to stderr as the very first executable act so that
no import-time log messages can ever reach stdout (which is exclusively
reserved for JSON-RPC traffic).

Usage
-----
    uv run python -m exchange_mcp.server
    uv run mcp dev exchange_mcp/server.py

The server validates Exchange connectivity at startup and refuses to start
if the connection check fails.  After startup it enumerates all 18 tools
(15 Exchange + ping + 2 Graph colleague tools) via the list_tools handler.
"""

# ---------------------------------------------------------------------------
# Logging MUST be configured before any other imports — this is the
# critical ordering constraint for stdio MCP servers.  Any log message
# emitted before stream=sys.stderr is configured will go to stdout,
# corrupting the JSON-RPC stream.
# ---------------------------------------------------------------------------
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("exchange_mcp.server")

# ---------------------------------------------------------------------------
# Remaining imports (after logging is configured)
# ---------------------------------------------------------------------------
import json
import signal
import time

import anyio
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from exchange_mcp.exchange_client import ExchangeClient
from exchange_mcp.tools import TOOL_DEFINITIONS, TOOL_DISPATCH

# ---------------------------------------------------------------------------
# Error classification constants
# ---------------------------------------------------------------------------

# Patterns that indicate a transient error — include retry hint in message.
_TRANSIENT_PATTERNS: tuple[str, ...] = (
    "timeout",
    "connection",
    "network",
    "throttl",
    "unavailable",
    "reset",
    "socket",
    "timed out",
)

# Patterns that indicate a non-transient error — no retry hint.
_NON_TRANSIENT_PATTERNS: tuple[str, ...] = (
    "authentication",
    "access denied",
    "unauthorized",
    "aadsts",
    "couldn't find",
    "could not find",
    "not found",
    "invalid input",
    "cannot bind",
    "certificate",
    "appid",
    "invalid client",
    "invalid_client",
)

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("exchange-mcp", version="0.1.0")

# Module-level ExchangeClient reference — set during startup validation,
# available to call_tool handler in later plans (Phases 3-6).
_exchange_client: ExchangeClient | None = None


# ---------------------------------------------------------------------------
# Error sanitization
# ---------------------------------------------------------------------------


def _sanitize_error(exc: Exception) -> str:
    """Strip PowerShell traceback and add optional transient retry hint.

    Strips everything after 'stderr:' (which contains the PS stack trace),
    removes the 'PowerShell exited with code N.' prefix, and appends a
    transient-error hint when the error is likely to resolve on retry.

    Args:
        exc: The exception to sanitize.

    Returns:
        A clean, LLM-friendly error message string.
    """
    original = str(exc)
    raw = original

    # Strip PowerShell traceback — keep only the part before 'stderr:'
    if "stderr:" in raw:
        raw = raw.split("stderr:")[0].strip()

    # Remove PowerShell exit code prefix (e.g. "PowerShell exited with code 1.")
    for prefix in ("PowerShell exited with code 1.", "PowerShell exited with code"):
        if prefix in raw:
            idx = raw.find(prefix)
            end = raw.find(".", idx + len(prefix))
            if end != -1:
                cleaned = raw[end + 1:].strip()
            else:
                cleaned = raw[idx + len(prefix):].strip()
            if cleaned:
                raw = cleaned

    # If stripping produced an empty string, fall back to original
    if not raw.strip():
        raw = original.split("stderr:")[0].strip() if "stderr:" in original else original
    if not raw.strip():
        raw = "The Exchange cmdlet failed. Check server logs for details"

    lower = raw.lower()

    # Determine transient vs non-transient
    is_non_transient = any(p in lower for p in _NON_TRANSIENT_PATTERNS)
    is_transient = not is_non_transient and any(p in lower for p in _TRANSIENT_PATTERNS)

    hint = " This is usually transient — try again in a moment." if is_transient else ""
    return f"Exchange error: {raw}.{hint}"


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Return the list of all registered Exchange MCP tools.

    Delegates to TOOL_DEFINITIONS from exchange_mcp.tools, which enumerates
    all 18 tools (15 Exchange + ping + 2 Graph colleague tools).  Phases 3-6
    replace stub handlers in TOOL_DISPATCH without changing this registration list.
    """
    return TOOL_DEFINITIONS


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """Dispatch a tool call by name and return sanitized TextContent results.

    Logs each call with name, arguments, duration, and success/failure.
    On error, strips raw PowerShell tracebacks and raises a sanitized
    RuntimeError so the SDK's built-in exception handler creates an
    isError=True CallToolResult with a clean message.

    Routing:
        1. Look up the handler in TOOL_DISPATCH (raises ValueError if unknown).
        2. Await the handler with (arguments, _exchange_client).
        3. NotImplementedError from stubs → RuntimeError "not yet implemented".
        4. All other exceptions → sanitized RuntimeError (strips PS tracebacks).

    Args:
        name:      The tool name (must be one of the registered tools).
        arguments: Tool input arguments (may be None for tools with no params).

    Returns:
        A list containing a single TextContent with the JSON-encoded tool result.

    Raises:
        RuntimeError: With a sanitized message on any tool execution failure.
    """
    arguments = arguments or {}
    start = time.monotonic()
    logger.info("tool_call name=%s args=%r", name, arguments)

    try:
        if name not in TOOL_DISPATCH:
            raise ValueError(f"Unknown tool: {name!r}")

        handler = TOOL_DISPATCH[name]
        result = await handler(arguments, _exchange_client)

        duration = time.monotonic() - start
        logger.info("tool_ok name=%s duration=%.2fs", name, duration)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except NotImplementedError as exc:
        duration = time.monotonic() - start
        logger.warning("tool_not_implemented name=%s duration=%.2fs", name, duration)
        raise RuntimeError(str(exc)) from None

    except Exception as exc:
        duration = time.monotonic() - start
        logger.error(
            "tool_error name=%s duration=%.2fs error=%r",
            name,
            duration,
            str(exc),
        )
        # Sanitize before the SDK's catch grabs the raw message.
        # SDK's _make_error_result(str(e)) creates CallToolResult(isError=True).
        raise RuntimeError(_sanitize_error(exc)) from None


# ---------------------------------------------------------------------------
# SIGTERM handler
# ---------------------------------------------------------------------------


def _handle_sigterm(signum: int, frame: object) -> None:
    """Log and exit cleanly on SIGTERM.

    The per-call PSSession design (Phase 1) means there are no persistent
    sessions to tear down — the main concern is logging the shutdown event
    so operators can distinguish a SIGTERM from an unhandled crash.
    """
    logger.info("SIGTERM received -- shutting down")
    sys.exit(0)


try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except (OSError, ValueError):
    # Windows may raise on certain signal registrations; log and continue.
    logger.debug("SIGTERM handler could not be registered (Windows limitation)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Start the MCP server with startup validation and stdio transport.

    Validates Exchange connectivity BEFORE opening the stdio transport so
    that startup failures produce a clean sys.exit(1) rather than a broken
    pipe seen by the MCP client.
    """
    global _exchange_client  # noqa: PLW0603

    logger.info("exchange-mcp starting up...")

    # -- Startup validation (before stdio transport opens) ------------------
    client = ExchangeClient()
    _exchange_client = client

    logger.info("Validating Exchange connection (auth_mode=%s)...", client.auth_mode)
    ok = await client.verify_connection()
    if not ok:
        logger.warning(
            "Exchange connection check failed (auth_mode=%s). "
            "Server starting in degraded mode — tools will attempt auth per-call.",
            client.auth_mode,
        )

    # -- Initialize Graph client (colleague lookup) --------------------------
    try:
        from chat_app.graph_client import init_graph
        from chat_app.config import Config

        init_graph(
            client_id=Config.AZURE_CLIENT_ID,
            client_secret=Config.AZURE_CLIENT_SECRET,
            tenant_id=Config.AZURE_TENANT_ID,
        )
    except Exception as exc:
        logger.warning("Graph client not available in MCP process: %s", exc)

    # -- Startup banner -----------------------------------------------------
    logger.info(
        "exchange-mcp v0.1.0 started | auth=%s | tools=%d | endpoint=Exchange Online",
        client.auth_mode,
        len(TOOL_DEFINITIONS),
    )

    # -- Open stdio transport and serve -------------------------------------
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(main)
