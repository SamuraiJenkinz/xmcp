# Phase 2: MCP Server Scaffold - Research

**Researched:** 2026-03-19
**Domain:** MCP Python SDK (official low-level Server API), stdio transport, async tool dispatch, logging discipline
**Confidence:** HIGH

## Summary

This phase builds `exchange_mcp/server.py` — a runnable stdio MCP server that the `mcp dev` inspector can enumerate tools from. The mcp Python SDK is already installed at 1.26.0 in the project venv (confirmed via `uv.lock`). The SDK exposes two tiers: **FastMCP** (decorator-based, high-level) and the **low-level Server class** with explicit `@server.list_tools()` / `@server.call_tool()` decorator registration. The decision is locked to the official mcp SDK without FastMCP — meaning the low-level `Server` class is the right choice.

The low-level `Server` class uses `@server.list_tools()` and `@server.call_tool()` as decorators, not constructor parameters. The `call_tool` handler receives `(name: str, arguments: dict | None)` and returns `list[TextContent | ...]`. The built-in `call_tool` decorator wraps all unhandled exceptions as `isError=True` automatically — but the error message will be a raw Python exception string, so the tool handler must catch all errors internally and return sanitized `CallToolResult(isError=True, ...)` before the framework's catch fires. The `stdio_server()` context manager handles wrapping sys.stdin/stdout as UTF-8; **nothing else should ever write to stdout**. Logging must be configured to stderr before anything else runs — the very first lines of `server.py`.

The critical integration constraint: the MCP Server runs in an `anyio.run()` event loop, and the `ExchangeClient` methods are all `async` coroutines. This means tool handlers are simply `async def` functions that `await` `exchange_client` methods directly — no `run_in_executor` needed. The Flask+Waitress stack mentioned in the roadmap context is the companion HTTP chat interface (not the MCP transport layer); the MCP server itself is stdio-only.

**Primary recommendation:** Use `mcp.server.lowlevel.Server` with decorator-based `@server.list_tools()` and `@server.call_tool()` handlers, run via `anyio.run()` + `stdio_server()`, with logging configured to stderr as the absolute first act in `server.py`.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp | 1.26.0 | MCP protocol, Server class, stdio transport | Already locked in pyproject.toml; official Anthropic SDK |
| anyio | (transitive) | Async runtime for stdio_server + task group | Required by mcp; already in project venv |
| mcp.server.lowlevel.Server | 1.26.0 | Low-level server with decorator-based tool registration | Decision: no FastMCP |
| mcp.server.stdio.stdio_server | 1.26.0 | stdio transport async context manager | Official transport for v1 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging (stdlib) | Python 3.11+ | Structured diagnostic logging to stderr | Always — configured as first act |
| json (stdlib) | Python 3.11+ | Serialize tool results as TextContent | For structured JSON responses to LLM |
| asyncio (stdlib) | Python 3.11+ | Signal handling (SIGTERM on Unix; not available on Windows) | Shutdown handling |
| signal (stdlib) | Python 3.11+ | SIGTERM registration for graceful shutdown | Windows: no SIGTERM; use stdin-close detection |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| low-level Server | FastMCP | FastMCP is simpler but decision is locked to official SDK without FastMCP |
| anyio.run() | asyncio.run() | anyio.run() is what mcp uses internally; mixing would create nested event loop errors |
| decorator pattern | constructor on_list_tools= | Constructor pattern is an older API; decorator pattern is what the SDK docstring demonstrates and is cleaner |

**Installation:** Already installed — `mcp>=1.0.0` in pyproject.toml, resolved to 1.26.0 in uv.lock.

## Architecture Patterns

### Recommended Project Structure

```
exchange_mcp/
├── server.py           # MCP server entry point — logging first, then Server, then anyio.run()
├── exchange_client.py  # ExchangeClient (Phase 1 output)
├── ps_runner.py        # PowerShell runner (Phase 1 output)
├── dns_utils.py        # DNS utilities (Phase 1 output)
└── __init__.py
```

### Pattern 1: Logging Before Everything

**What:** Configure logging to stderr as the absolute first executable lines in server.py, before any imports that might emit output.
**When to use:** Always — this is the most critical ordering constraint for stdio MCP servers.
**Example:**
```python
# Source: modelcontextprotocol.io/docs/develop/build-server (official docs)
# This MUST be the first executable code — before any other imports or logic
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)
```

**Why ordering matters:** Any log message emitted before `stream=sys.stderr` is configured will go to stdout, corrupting the JSON-RPC stream and causing `mcp dev` to fail silently.

### Pattern 2: Low-Level Server with Decorator Registration

**What:** Create a `Server` instance, use `@server.list_tools()` and `@server.call_tool()` decorators to register handlers, run via `anyio.run()` + `stdio_server()`.
**When to use:** Always for this project — FastMCP is excluded by decision.
**Example:**
```python
# Source: /c/xmcp/.venv/Lib/site-packages/mcp/server/lowlevel/server.py (inspected directly)
import anyio
import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

server = Server("exchange-mcp", version="0.1.0")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_mailbox_stats",
            description="...",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_address": {"type": "string", "description": "..."}
                },
                "required": ["email_address"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    arguments = arguments or {}
    # ... dispatch to exchange client ...
    return [types.TextContent(type="text", text=json.dumps(result))]

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    anyio.run(main)
```

### Pattern 3: Tool Error Wrapping Template

**What:** Catch all exceptions inside `call_tool`, classify as transient/non-transient, return `CallToolResult(isError=True)` with sanitized message. Do NOT let raw exceptions bubble up to the SDK's catch (which would expose `RuntimeError: PowerShell exited with code 1. stderr:\n...` directly to the LLM).
**When to use:** Every tool handler — this is the template for Phases 3-6.
**Example:**
```python
# Source: combination of mcp types.py inspection + CONTEXT.md decisions
import json
from mcp import types

_TRANSIENT_HINT = "This is usually transient — try again in a moment."

def _is_transient_error(msg: str) -> bool:
    """True for network/timeout errors that may resolve on retry."""
    lower = msg.lower()
    non_retryable = ("authentication", "access denied", "unauthorized", "aadsts",
                     "couldn't find", "not found", "invalid input", "cannot bind")
    return not any(p in lower for p in non_retryable)

def _wrap_error(exc: Exception) -> list[types.TextContent]:
    """Return sanitized error text content with optional retry hint."""
    raw_msg = str(exc)
    # Strip PowerShell traceback: keep only first line before 'stderr:'
    if "stderr:" in raw_msg:
        raw_msg = raw_msg.split("stderr:")[0].strip()
    hint = f" {_TRANSIENT_HINT}" if _is_transient_error(raw_msg) else ""
    sanitized = f"Exchange error: {raw_msg}.{hint}"
    return [types.TextContent(type="text", text=sanitized)]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    start = time.monotonic()
    arguments = arguments or {}
    logger.info("tool_call name=%s args=%s", name, arguments)
    try:
        result = await _dispatch(name, arguments)
        duration = time.monotonic() - start
        logger.info("tool_ok name=%s duration=%.2fs", name, duration)
        return [types.TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        duration = time.monotonic() - start
        logger.error("tool_error name=%s duration=%.2fs error=%r", name, duration, str(exc))
        # Return isError=True — SDK wraps this in CallToolResult automatically
        # when we raise, but then message is unsanitized. Return directly instead.
        raise  # Let SDK's built-in catch create CallToolResult(isError=True, content=[...])
        # BUT: the SDK's catch uses str(exc) verbatim — which includes PS traceback.
        # So we must NOT raise. Instead return the wrapped error content,
        # and signal isError by raising types.McpError or returning directly.
```

**Critical nuance:** The SDK's `call_tool` decorator catches `Exception` and calls `self._make_error_result(str(e))` — this will pass the raw `RuntimeError` message (containing PS traceback) directly to the LLM. Therefore, the tool handler MUST catch exceptions itself and return sanitized content, or raise a custom exception with an already-sanitized message. The cleanest pattern: catch all exceptions in the handler, build sanitized `TextContent`, and return it — but to signal `isError=True`, the handler must raise a special sentinel or the SDK must be configured to forward errors as-is. Looking at the SDK source: `_make_error_result` creates `CallToolResult(isError=True, content=[TextContent(...)])`. The handler function itself returns `list[TextContent]` for SUCCESS and raises for ERROR — so the pattern is:

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        # Sanitize before the SDK's catch can grab the raw message
        sanitized = _sanitize_error(exc)
        raise RuntimeError(sanitized) from None  # SDK catches this, makes isError=True
```

### Pattern 4: Startup Validation and Banner

**What:** Before entering the `stdio_server()` context, run startup validation synchronously (via `asyncio.run()` or inside the async main before server.run). If Exchange auth fails, emit error on stderr and `sys.exit(1)`.
**When to use:** Every server startup — fail fast is a locked decision.
**Example:**
```python
async def main() -> None:
    # --- Startup validation (before stdio transport opens) ---
    client = ExchangeClient()
    ok = await client.verify_connection()
    if not ok:
        logger.error("FATAL: Exchange connection failed at startup. Check credentials and connectivity.")
        sys.exit(1)

    auth_mode = client.auth_mode
    tool_count = len(await handle_list_tools())
    logger.info(
        "exchange-mcp v0.1.0 | auth=%s | tools=%d | endpoint=Exchange Online",
        auth_mode, tool_count
    )

    # --- Open stdio transport and serve ---
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

### Pattern 5: Graceful Shutdown

**What:** On SIGTERM or stdin close, tear down any active PowerShell sessions. The `stdio_server()` loop exits naturally when stdin closes (anyio task group cancels). SIGTERM requires OS signal handling.
**When to use:** Required per CONTEXT.md decisions.
**Critical Windows note:** `signal.SIGTERM` is available on Windows but `signal.SIGKILL` is not. The per-call PSSession design (Phase 1) means there are no persistent sessions to tear down — the graceful shutdown concern is mainly ensuring in-flight calls complete before exit.
**Example:**
```python
import signal

def _handle_sigterm(signum, frame):
    logger.info("SIGTERM received — shutting down")
    sys.exit(0)  # anyio task group will cancel naturally

signal.signal(signal.SIGTERM, _handle_sigterm)
```

### Anti-Patterns to Avoid

- **Calling `asyncio.run()` inside `anyio.run()`:** The mcp SDK uses anyio internally; calling `asyncio.run()` from inside an anyio event loop raises `RuntimeError: This event loop is already running`. Use `await` directly.
- **Using `print()` without `file=sys.stderr`:** Any `print()` call without the stderr redirect corrupts the JSON-RPC stream. Use `logger.*` exclusively.
- **Configuring logging after first import:** Third-party imports may emit log messages. Configure `basicConfig(stream=sys.stderr)` before any other imports.
- **Letting raw RuntimeError propagate to SDK catch:** The SDK's `_make_error_result(str(e))` will include `PowerShell exited with code 1. stderr:\n<full traceback>` in the LLM response. Always sanitize before raising.
- **Using `asyncio.run()` as the entry point:** Use `anyio.run(main)` — the mcp SDK is anyio-based and uses anyio internally; `asyncio.run()` works as anyio can run on top of asyncio, but `anyio.run()` is more correct.
- **Returning a `dict` directly from `call_tool` handler:** The SDK's call_tool decorator supports dict returns (maps to structuredContent), but this project should return `list[TextContent]` to maintain simple, reliable LLM tool result handling.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-RPC framing over stdio | Custom stdin/stdout reader | `mcp.server.stdio.stdio_server()` | Handles UTF-8 re-wrapping, message framing, flush, and concurrent stdin_reader + stdout_writer tasks |
| Tool input validation | Manual `if "param" not in arguments` checks | `inputSchema` in Tool definition + SDK validates | SDK auto-validates via jsonschema when `validate_input=True` (default in `call_tool` decorator) |
| MCP protocol handshake | Custom initialization negotiation | `server.create_initialization_options()` + `server.run()` | SDK handles all MCP lifecycle: initialize, capabilities, ping |
| Tool capability advertisement | Manual `tools/list` JSON response | `@server.list_tools()` decorator | SDK wraps list into correct `ListToolsResult`, caches for input validation |
| Error wrapping into isError | Manual `{"isError": True, ...}` dicts | `raise RuntimeError(sanitized_msg)` inside `@server.call_tool()` handler | SDK's built-in `_make_error_result()` constructs proper `CallToolResult(isError=True)` |

**Key insight:** The mcp SDK handles all protocol-level concerns. The only application-level concern is: (1) returning the right types from handlers and (2) sanitizing errors before they reach the SDK's catch.

## Common Pitfalls

### Pitfall 1: Stdout Pollution Kills the Connection

**What goes wrong:** Any output to stdout (from `print()`, a misconfigured logger, a stray `import` that logs, or even Python's deprecation warning to stdout) corrupts the JSON-RPC message stream. `mcp dev` will either hang or show a parse error with no clear message.
**Why it happens:** stdio_server wraps sys.stdout — any byte written outside the JSON-RPC path is injected mid-stream.
**How to avoid:** `logging.basicConfig(stream=sys.stderr)` must be the first line. Use `python -W error::DeprecationWarning` in dev to catch rogue warnings. Never use `print()`.
**Warning signs:** `mcp dev` connects but shows zero tools, or exits immediately with a JSON parse error.

### Pitfall 2: Raw PowerShell Tracebacks Reach the LLM

**What goes wrong:** An Exchange cmdlet fails; `ExchangeClient.run_cmdlet()` raises `RuntimeError("PowerShell exited with code 1. stderr:\nAt C:\\...: line 3\nConnect-ExchangeOnline: ...")`. The SDK's default `call_tool` exception handler passes `str(exc)` to `_make_error_result()` — the full traceback appears in the LLM's tool result.
**Why it happens:** The SDK catch is intentionally broad; it's the tool handler's job to sanitize.
**How to avoid:** Catch `Exception` inside the `call_tool` handler, strip the `stderr:` section, produce a human-readable message, then raise `RuntimeError(sanitized_msg)`.
**Warning signs:** In `mcp dev`, tool call results contain PowerShell stack traces or `At C:\...` file references.

### Pitfall 3: Using `asyncio.run()` Instead of `anyio.run()`

**What goes wrong:** `asyncio.run(main())` works but creates a subtle conflict: anyio (used internally by mcp) detects it's running inside an asyncio event loop and uses the asyncio backend — this is actually fine for most cases, but `anyio.run(main)` is the intended entry point and avoids any potential backend selection issues.
**Why it happens:** Many Python examples use `asyncio.run()` because that's the common pattern.
**How to avoid:** Use `anyio.run(main)` as the entry point — matches the SDK's own examples and documentation.
**Warning signs:** Subtle async cancellation issues that don't reproduce easily.

### Pitfall 4: Startup Validation Before `stdio_server()` Opens

**What goes wrong:** Startup validation (Exchange connection check) runs after `stdio_server()` is entered — at that point, stdin is being read. If validation raises and `sys.exit(1)` is called, the stdio streams may not be cleanly closed, and the client sees a broken pipe rather than a clean error.
**Why it happens:** Placing all logic inside `async with stdio_server()`.
**How to avoid:** Run `verify_connection()` and emit the startup banner BEFORE entering `stdio_server()`. Exit with `sys.exit(1)` on failure. Only open the stdio transport after validation passes.
**Warning signs:** `mcp dev` shows "connection closed unexpectedly" rather than a meaningful error.

### Pitfall 5: Tool Description Too Vague for Tool Selection

**What goes wrong:** A description like "Gets mailbox information" does not give the LLM enough signal to choose `get_mailbox_stats` over `search_mailboxes`. The LLM selects the wrong tool or falls back to asking for clarification.
**Why it happens:** Descriptions are written from an implementation perspective rather than from the LLM's natural language query perspective.
**How to avoid:** Include a "Use when asked about..." sentence with concrete example queries. Keep under 800 characters. Use plain English (not Exchange jargon).
**Warning signs:** In `mcp dev` tool testing, prompts like "how full is john's mailbox" don't map to `get_mailbox_stats`.

### Pitfall 6: `call_tool` Handler Not Covered by Startup Validation

**What goes wrong:** The startup validation passes (Exchange was reachable at start), but a tool call fails later with a cryptic error because the client is creating a per-call session but the Exchange endpoint is unreachable mid-session.
**Why it happens:** Per-call PSSession means every tool call is independently vulnerable.
**How to avoid:** The error wrapping pattern (Pitfall 2 solution) handles this at runtime — transient errors get the retry hint. This is working-as-designed for per-call sessions.
**Warning signs:** This is expected behavior; only worry if errors aren't being sanitized correctly.

## Code Examples

Verified patterns from official sources and direct SDK inspection:

### Minimal Working Server (Low-Level)

```python
# Source: /c/xmcp/.venv/Lib/site-packages/mcp/server/lowlevel/server.py docstring
# + /c/xmcp/.venv/Lib/site-packages/mcp/server/stdio.py
import sys
import logging
import json
import anyio
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# MUST be first — before any other imports that might log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

server = Server("exchange-mcp", version="0.1.0")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="ping",
            description="Placeholder tool. Use when testing server connectivity.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "ping":
        return [types.TextContent(type="text", text='"pong"')]
    raise ValueError(f"Unknown tool: {name}")

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    anyio.run(main)
```

### Tool Definition with inputSchema

```python
# Source: /c/xmcp/.venv/Lib/site-packages/mcp/types.py Tool class (inspected directly)
# Tool.name comes from BaseMetadata; Tool.inputSchema is required dict (JSON Schema)
types.Tool(
    name="get_mailbox_stats",
    description=(
        "Returns mailbox size, quota usage, item count, and last login time for one user. "
        "Use when asked about how full a mailbox is, when someone last used their email, "
        "or what database a mailbox lives on. "
        "Example queries: 'how full is john@contoso.com', 'when did jane last log in', "
        "'what quota does the finance mailbox have'."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "email_address": {
                "type": "string",
                "description": "Email address of the user whose mailbox to check.",
            }
        },
        "required": ["email_address"],
    },
)
```

### isError=True Pattern (Sanitized Error Return)

```python
# Source: /c/xmcp/.venv/Lib/site-packages/mcp/server/lowlevel/server.py _make_error_result()
# The SDK catches Exception from the handler and calls _make_error_result(str(e))
# To sanitize, catch first and raise a pre-sanitized RuntimeError

_TRANSIENT_PATTERNS = ("timeout", "connection", "network", "throttl", "unavailable", "reset")
_NON_TRANSIENT_PATTERNS = ("authentication", "access denied", "unauthorized", "aadsts",
                            "couldn't find", "not found", "invalid input", "cannot bind",
                            "certificate", "appid")

def _sanitize_exc(exc: Exception) -> str:
    """Strip PS traceback; return clean message with optional retry hint."""
    raw = str(exc)
    # Strip everything after 'stderr:' (PS traceback)
    if "stderr:" in raw:
        raw = raw.split("stderr:")[0].strip()
    # Remove PS exit code prefix
    raw = raw.replace("PowerShell exited with code 1.", "").strip()
    lower = raw.lower()
    is_transient = (
        not any(p in lower for p in _NON_TRANSIENT_PATTERNS)
        and any(p in lower for p in _TRANSIENT_PATTERNS)
    )
    hint = " This is usually transient — try again in a moment." if is_transient else ""
    return f"Exchange error: {raw}.{hint}"

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    arguments = arguments or {}
    start = time.monotonic()
    logger.info("tool_call name=%s args=%r", name, arguments)
    try:
        result = await _dispatch(name, arguments)
        logger.info("tool_ok name=%s duration=%.2fs", name, time.monotonic() - start)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as exc:
        logger.error("tool_error name=%s duration=%.2fs error=%r",
                     name, time.monotonic() - start, str(exc))
        raise RuntimeError(_sanitize_exc(exc)) from None
        # SDK's _make_error_result(str(e)) creates CallToolResult(isError=True)
```

### Startup Banner + Validation Pattern

```python
# Source: CONTEXT.md decisions + asyncio/logging patterns
async def main() -> None:
    from exchange_mcp.exchange_client import ExchangeClient

    client = ExchangeClient()

    # Validate BEFORE opening stdio transport
    logger.info("Validating Exchange connection...")
    ok = await client.verify_connection()
    if not ok:
        logger.error(
            "FATAL: Cannot reach Exchange Online. "
            "Check credentials (auth_mode=%s) and network connectivity. "
            "Server will not start.",
            client.auth_mode,
        )
        sys.exit(1)

    tools = await handle_list_tools()
    logger.info(
        "exchange-mcp v0.1.0 started | auth=%s | tools=%d | endpoint=Exchange Online",
        client.auth_mode,
        len(tools),
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
```

### `mcp dev` Usage for Inspection

```bash
# Source: modelcontextprotocol.io/docs/tools/inspector
# Run from project root with venv active:
uv run mcp dev exchange_mcp/server.py

# mcp dev starts the server as subprocess, launches web inspector UI
# Click "Tools" → "List tools" to enumerate registered tools
# mcp dev does NOT require you to start the server separately for stdio
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Constructor-based handler registration (`on_list_tools=fn`) | Decorator-based (`@server.list_tools()`) | mcp SDK ~1.0+ | Decorator pattern is in SDK docstring as primary; constructor params still work but undocumented in 1.26 |
| `asyncio.run()` entry point | `anyio.run()` entry point | mcp SDK 1.x | anyio is the correct runtime; asyncio.run works but anyio.run is idiomatic |
| Custom stdio framing | `stdio_server()` context manager | mcp 1.0 | stdio_server handles UTF-8 re-wrap, concurrent reader/writer tasks |

**Deprecated/outdated:**
- `FastMCP`: Not deprecated, but excluded by project decision — research confirms it's available in mcp 1.26.0 as `mcp.server.fastmcp.FastMCP`
- Direct stdout writes: Never valid for stdio MCP servers; corrupts JSON-RPC stream

## Open Questions

1. **Windows SIGTERM behavior**
   - What we know: `signal.SIGTERM` is technically available on Windows but behaves differently than on Unix. PowerShell processes spawned as subprocesses may not be sent SIGTERM reliably on Windows.
   - What's unclear: Whether the per-call PSSession design (which already cleans up in finally blocks) makes SIGTERM handling irrelevant for graceful shutdown in practice.
   - Recommendation: Implement `signal.signal(signal.SIGTERM, handler)` but accept that on Windows, graceful shutdown mostly relies on per-call cleanup already happening. No in-flight session state to lose.

2. **Log format choice (Claude's discretion)**
   - What we know: CONTEXT.md grants Claude discretion on log format. Options are structured JSON (machine-readable, easier to grep) vs. human-readable text (easier to read directly in a terminal).
   - Recommendation: Use human-readable text format (`"%(asctime)s %(levelname)-8s %(name)s: %(message)s"`) for v1 — simpler, easier to read during debugging, sufficient for an internal admin tool. Structured JSON logging adds complexity without clear benefit until there's a log aggregation system.

3. **mcp dev inspector availability**
   - What we know: `mcp dev server.py` requires the mcp CLI to be installed (`pip install "mcp[cli]"`). The project's `pyproject.toml` only has `mcp>=1.0.0` (no `[cli]` extra). The mcp[cli] extra adds `typer` and the inspector CLI.
   - What's unclear: Whether `uv run mcp dev` works without the `[cli]` extra in pyproject.toml.
   - Recommendation: Test with `uv run --with "mcp[cli]" mcp dev exchange_mcp/server.py`. If needed, add `mcp[cli]` as a dev dependency.

## Sources

### Primary (HIGH confidence)

- `/c/xmcp/.venv/Lib/site-packages/mcp/server/lowlevel/server.py` — Server class, `@list_tools()`, `@call_tool()` decorators, `_make_error_result()`, `run()` method. Version 1.26.0 confirmed via dist-info.
- `/c/xmcp/.venv/Lib/site-packages/mcp/server/stdio.py` — `stdio_server()` context manager, UTF-8 stream wrapping, concurrent stdin/stdout task pattern.
- `/c/xmcp/.venv/Lib/site-packages/mcp/types.py` — `Tool`, `TextContent`, `CallToolResult`, `ListToolsResult` Pydantic models. Confirmed `isError: bool = False` default on `CallToolResult`.
- `/c/xmcp/.venv/Lib/site-packages/mcp/server/__init__.py` — Exports: `Server`, `FastMCP`, `NotificationOptions`, `InitializationOptions`.
- `https://modelcontextprotocol.io/docs/develop/build-server` — Official "Never write to stdout" logging guidance; `logging.basicConfig(stream=sys.stderr)` pattern confirmed.
- `https://modelcontextprotocol.io/docs/concepts/tools` — Tool protocol spec: `isError` in result, two error mechanisms (protocol errors vs tool execution errors), `inputSchema` required field.

### Secondary (MEDIUM confidence)

- `https://github.com/modelcontextprotocol/python-sdk` — README confirms FastMCP as recommended approach; low-level Server confirmed as available for custom requirements.
- `https://modelcontextprotocol.io/docs/tools/inspector` — `mcp dev server.py` usage confirmed; inspector enumerates tools via web UI.
- WebSearch "python mcp server logging stderr" — Multiple authoritative sources confirm: stdout is exclusively JSON-RPC, logging must go to stderr.

### Tertiary (LOW confidence)

- None — all critical findings verified against installed SDK source directly.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — mcp 1.26.0 installed and inspected directly in project venv
- Architecture patterns: HIGH — derived from actual SDK source code (server.py, stdio.py, types.py)
- Pitfalls: HIGH for stdio/logging/error-wrapping (derived from SDK source); MEDIUM for Windows SIGTERM behavior (untested)
- Tool descriptions: MEDIUM — pattern from CONTEXT.md decisions + MCP spec, but LLM tool-selection effectiveness requires empirical validation

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (mcp SDK is actively developed; recheck if upgrading past 1.26.0)
