"""MCP client async bridge for the Flask chat application.

Spawns the exchange_mcp.server subprocess once at Flask startup and keeps
the MCP stdio session alive for the application's lifetime.  Provides a
synchronous ``call_mcp_tool`` wrapper that Flask request handlers can call
directly, while all asyncio work is dispatched to a dedicated daemon thread
running its own event loop.

Architecture
------------
- A dedicated daemon thread owns a ``asyncio.AbstractEventLoop``.
- ``_async_run(coro)`` submits coroutines to that loop via
  ``asyncio.run_coroutine_threadsafe`` and blocks for the result — no
  ``asyncio.run()`` is ever called from Flask request handlers.
- A ``threading.Lock`` serialises all MCP calls: the MCP stdio session is
  a single JSON-RPC stream that does not support concurrent requests.
- ``init_mcp()`` must be called once at Flask startup (e.g. from the app
  factory).  Importing this module does NOT spawn any subprocess.

Usage
-----
::

    from chat_app.mcp_client import init_mcp, get_openai_tools, call_mcp_tool

    # In Flask app factory:
    init_mcp(app)

    # In a Flask route:
    tools = get_openai_tools()
    result = call_mcp_tool("ping", {})
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (set by init_mcp, read-only after that)
# ---------------------------------------------------------------------------

_mcp_session: ClientSession | None = None
_mcp_loop: asyncio.AbstractEventLoop | None = None
_mcp_tools: list[dict[str, Any]] = []  # Cached OpenAI-compatible function schemas
_mcp_lock: threading.Lock = threading.Lock()
_exit_stack: AsyncExitStack | None = None
_connected: bool = False

# ---------------------------------------------------------------------------
# Background event loop (daemon thread)
# ---------------------------------------------------------------------------


def _start_mcp_event_loop() -> asyncio.AbstractEventLoop:
    """Create and start a new asyncio event loop in the current thread.

    Intended to be called from a daemon thread.  The loop runs forever until
    the process exits or the loop is stopped explicitly.

    Returns:
        The running event loop (also set as the thread's current loop).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()
    return loop


def _async_run(coro: Any, timeout: float = 60.0) -> Any:
    """Dispatch an async coroutine to the background loop and block for the result.

    Args:
        coro:    The coroutine to run on the background event loop.
        timeout: Maximum seconds to wait for the result (default 60 s).

    Returns:
        The coroutine's return value.

    Raises:
        RuntimeError: If the background loop is not running.
        TimeoutError: If the coroutine does not complete within ``timeout`` seconds.
        Exception:    Any exception raised by the coroutine is re-raised here.
    """
    if _mcp_loop is None or not _mcp_loop.is_running():
        raise RuntimeError("MCP background event loop is not running")

    future = asyncio.run_coroutine_threadsafe(coro, _mcp_loop)
    return future.result(timeout=timeout)


# ---------------------------------------------------------------------------
# Async connection logic
# ---------------------------------------------------------------------------


async def _connect_mcp() -> None:
    """Open the MCP stdio session and cache tool schemas.

    Creates an ``AsyncExitStack``, enters the ``stdio_client`` context manager
    (which spawns the ``exchange_mcp.server`` subprocess), creates a
    ``ClientSession``, initialises it, calls ``list_tools``, and converts the
    tool definitions to OpenAI-compatible function schemas stored in
    ``_mcp_tools``.

    Sets ``_mcp_session``, ``_exit_stack``, ``_mcp_tools``, and ``_connected``
    on the module.

    Raises:
        Exception: Propagates any connection or initialisation failure so
                   ``init_mcp`` can log and handle it.
    """
    global _mcp_session, _exit_stack, _mcp_tools, _connected  # noqa: PLW0603

    params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "exchange_mcp.server"],
    )

    stack = AsyncExitStack()
    read_stream, write_stream = await stack.enter_async_context(stdio_client(params))

    session = ClientSession(read_stream, write_stream)
    await stack.enter_async_context(session)
    await session.initialize()

    # Enumerate tools and convert to OpenAI function schemas
    result = await session.list_tools()
    tools_list = result.tools

    openai_tools: list[dict[str, Any]] = []
    for tool in tools_list:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
        )

    _mcp_session = session
    _exit_stack = stack
    _mcp_tools = openai_tools
    _connected = True

    logger.info(
        "MCP client connected: %d tools cached as OpenAI schemas", len(openai_tools)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_mcp(app: Any = None) -> None:
    """Start the MCP background loop and connect to the exchange_mcp server.

    Spawns a daemon thread that runs an asyncio event loop, then synchronously
    waits for the MCP session to be established before returning.  This
    function must be called once from the Flask app factory (or equivalent
    startup code).  Importing this module does NOT spawn any subprocess.

    Args:
        app: Optional Flask application instance (unused; accepted for
             compatibility with Flask extension initialisation patterns).

    Raises:
        RuntimeError: If the background loop fails to start or the MCP session
                      cannot be established.
    """
    global _mcp_loop  # noqa: PLW0603

    # Start background event loop in daemon thread
    loop = asyncio.new_event_loop()
    _mcp_loop = loop

    thread = threading.Thread(
        target=loop.run_forever,
        name="mcp-event-loop",
        daemon=True,
    )
    thread.start()
    logger.info("MCP background event loop started (thread: %s)", thread.name)

    # Connect synchronously — wait up to 120 s for subprocess + Exchange auth
    try:
        _async_run(_connect_mcp(), timeout=120.0)
        logger.info("MCP client initialised successfully")
    except Exception as exc:
        logger.error("MCP client failed to initialise: %s", exc)
        raise RuntimeError(f"MCP init failed: {exc}") from exc


def get_openai_tools() -> list[dict[str, Any]]:
    """Return the cached list of OpenAI-compatible function schemas.

    Returns the tool definitions enumerated at startup via ``tools/list``,
    converted to OpenAI ``{type: "function", function: {...}}`` format ready
    for injection into chat completion requests.

    Returns:
        List of OpenAI function schema dicts.  Empty list if not connected.
    """
    return _mcp_tools


def call_mcp_tool(name: str, arguments: dict[str, Any]) -> str:
    """Synchronous wrapper: call an MCP tool and return the result text.

    Serialises concurrent Flask request threads through ``_mcp_lock`` to
    prevent interleaving on the single stdio JSON-RPC session, then dispatches
    the async ``session.call_tool`` to the background event loop and blocks
    for the result.

    Args:
        name:      The tool name (must match a name in ``get_openai_tools()``).
        arguments: Tool input arguments dict.

    Returns:
        The text content of the tool result.

    Raises:
        RuntimeError: If not connected or the tool call fails.
    """
    if not _connected or _mcp_session is None:
        raise RuntimeError("MCP client is not connected — call init_mcp() first")

    async def _call() -> str:
        result = await _mcp_session.call_tool(name=name, arguments=arguments)
        # Collect all TextContent text segments
        parts: list[str] = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
        return "\n".join(parts)

    with _mcp_lock:
        return _async_run(_call())


def is_connected() -> bool:
    """Return True if the MCP session is established and ready.

    Returns:
        Boolean connection status.
    """
    return _connected
