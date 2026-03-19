"""Unit tests for exchange_mcp.server — MCP server scaffold.

All tests mock ExchangeClient to avoid any live Exchange Online connection.
Tests cover:
    - list_tools returns the ping placeholder tool
    - call_tool ping returns '"pong"'
    - call_tool unknown tool raises ValueError/RuntimeError
    - _sanitize_error strips PowerShell stderr sections
    - _sanitize_error adds transient retry hint for transient errors
    - _sanitize_error does NOT add hint for non-transient errors
    - server instance exists with correct name
"""

from __future__ import annotations

import pytest

from exchange_mcp.server import (
    _sanitize_error,
    handle_call_tool,
    handle_list_tools,
    server,
)


# ---------------------------------------------------------------------------
# 1. test_list_tools_returns_ping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_tools_returns_ping() -> None:
    """handle_list_tools() must return a list with exactly one 'ping' tool."""
    tools = await handle_list_tools()

    assert isinstance(tools, list)
    assert len(tools) == 1
    assert tools[0].name == "ping"


# ---------------------------------------------------------------------------
# 2. test_call_tool_ping_returns_pong
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_call_tool_ping_returns_pong() -> None:
    """handle_call_tool('ping') must return a single TextContent with '"pong"'."""
    results = await handle_call_tool("ping", None)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].type == "text"
    assert results[0].text == '"pong"'


# ---------------------------------------------------------------------------
# 3. test_call_tool_unknown_tool_raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_call_tool_unknown_tool_raises() -> None:
    """handle_call_tool() must raise for an unrecognised tool name."""
    with pytest.raises((ValueError, RuntimeError)) as exc_info:
        await handle_call_tool("nonexistent", None)

    assert "Unknown tool" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. test_sanitize_error_strips_stderr
# ---------------------------------------------------------------------------


def test_sanitize_error_strips_stderr() -> None:
    """_sanitize_error() must strip the 'stderr:' section from PS error messages."""
    raw_message = (
        "PowerShell exited with code 1. stderr:\n"
        "At C:\\path\\file.ps1: line 3\n"
        "Connect-ExchangeOnline: AADSTS70011: The provided request must include a 'scope' input parameter."
    )
    exc = RuntimeError(raw_message)

    result = _sanitize_error(exc)

    # Must not contain raw PS traceback markers
    assert "stderr:" not in result
    assert "At C:\\" not in result
    # Must start with our Exchange error prefix
    assert result.startswith("Exchange error:")


# ---------------------------------------------------------------------------
# 5. test_sanitize_error_transient_hint
# ---------------------------------------------------------------------------


def test_sanitize_error_transient_hint() -> None:
    """_sanitize_error() must append retry hint for transient (connection) errors."""
    exc = RuntimeError("connection reset by peer")

    result = _sanitize_error(exc)

    assert "try again in a moment" in result.lower()


# ---------------------------------------------------------------------------
# 6. test_sanitize_error_non_transient_no_hint
# ---------------------------------------------------------------------------


def test_sanitize_error_non_transient_no_hint() -> None:
    """_sanitize_error() must NOT append retry hint for non-transient errors."""
    exc = RuntimeError("authentication failed: AADSTS70011 invalid scope")

    result = _sanitize_error(exc)

    assert "try again in a moment" not in result.lower()


# ---------------------------------------------------------------------------
# 7. test_server_instance_exists
# ---------------------------------------------------------------------------


def test_server_instance_exists() -> None:
    """The module-level server instance must exist with the expected name."""
    from mcp.server import Server

    assert isinstance(server, Server)
    assert server.name == "exchange-mcp"
