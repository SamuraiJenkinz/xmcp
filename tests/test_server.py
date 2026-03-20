"""Unit tests for exchange_mcp.server — MCP server scaffold.

All tests mock ExchangeClient to avoid any live Exchange Online connection.
Tests cover:
    - list_tools returns all 16 registered tools (15 Exchange + ping)
    - call_tool ping returns JSON-encoded pong result
    - call_tool unknown tool raises ValueError/RuntimeError
    - _sanitize_error strips PowerShell stderr sections
    - _sanitize_error adds transient retry hint for transient errors
    - _sanitize_error does NOT add hint for non-transient errors
    - server instance exists with correct name
    - all 16 tool definitions have corresponding dispatch entries
    - all tool descriptions are under 800 characters
    - remaining stub tools raise RuntimeError with "not yet implemented"
    - ping dispatch returns {"status": "pong"}
    - all tool schemas have required "type" and "properties" fields
"""

from __future__ import annotations

import pytest

from exchange_mcp.server import (
    _sanitize_error,
    handle_call_tool,
    handle_list_tools,
    server,
)
from exchange_mcp.tools import TOOL_DEFINITIONS, TOOL_DISPATCH


# ---------------------------------------------------------------------------
# 1. test_list_tools_returns_ping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_tools_returns_ping() -> None:
    """handle_list_tools() must return a list that includes a 'ping' tool."""
    tools = await handle_list_tools()

    assert isinstance(tools, list)
    tool_names = [t.name for t in tools]
    assert "ping" in tool_names


# ---------------------------------------------------------------------------
# 2. test_call_tool_ping_returns_pong
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_call_tool_ping_returns_pong() -> None:
    """handle_call_tool('ping') must return a single TextContent with a pong result."""
    import json

    results = await handle_call_tool("ping", None)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].type == "text"
    # The result is JSON-encoded; parse and check status field
    parsed = json.loads(results[0].text)
    assert parsed.get("status") == "pong"


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


# ---------------------------------------------------------------------------
# 8. test_list_tools_returns_all_16
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_tools_returns_all_16() -> None:
    """handle_list_tools() must return exactly 16 tools (15 Exchange + ping)."""
    tools = await handle_list_tools()

    assert len(tools) == 16


# ---------------------------------------------------------------------------
# 9. test_all_tool_names_in_dispatch
# ---------------------------------------------------------------------------


def test_all_tool_names_in_dispatch() -> None:
    """Every tool in TOOL_DEFINITIONS must have a matching entry in TOOL_DISPATCH."""
    for tool in TOOL_DEFINITIONS:
        assert tool.name in TOOL_DISPATCH, (
            f"Tool '{tool.name}' is in TOOL_DEFINITIONS but missing from TOOL_DISPATCH"
        )


# ---------------------------------------------------------------------------
# 10. test_tool_descriptions_under_800_chars
# ---------------------------------------------------------------------------


def test_tool_descriptions_under_800_chars() -> None:
    """Every tool description must be at most 800 characters."""
    for tool in TOOL_DEFINITIONS:
        assert len(tool.description) <= 800, (
            f"Tool '{tool.name}' description is {len(tool.description)} chars (limit 800)"
        )


# ---------------------------------------------------------------------------
# 11. test_call_tool_not_implemented_raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_call_tool_not_implemented_raises() -> None:
    """handle_call_tool() with a stub Exchange tool must raise RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        await handle_call_tool(
            "get_transport_queues",
            {},
        )

    assert "not yet implemented" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 12. test_dispatch_ping_returns_pong
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_dispatch_ping_returns_pong() -> None:
    """Calling the ping handler directly from TOOL_DISPATCH must return a pong dict."""
    handler = TOOL_DISPATCH["ping"]
    result = await handler({}, None)

    assert isinstance(result, dict)
    assert result.get("status") == "pong"


# ---------------------------------------------------------------------------
# 13. test_tool_schemas_have_required_fields
# ---------------------------------------------------------------------------


def test_tool_schemas_have_required_fields() -> None:
    """Every tool's inputSchema must have 'type': 'object' and 'properties'."""
    for tool in TOOL_DEFINITIONS:
        schema = tool.inputSchema
        assert schema.get("type") == "object", (
            f"Tool '{tool.name}' inputSchema missing 'type': 'object'"
        )
        assert "properties" in schema, (
            f"Tool '{tool.name}' inputSchema missing 'properties'"
        )
