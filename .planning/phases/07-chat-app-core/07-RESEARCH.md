# Phase 7: Chat App Core - Research

**Researched:** 2026-03-21
**Domain:** Flask web app with Azure AD SSO, Azure OpenAI tool-calling loop, SSE streaming, MCP client integration, tiktoken context management
**Confidence:** HIGH (most findings verified against official docs/Context7)

---

## Summary

Phase 7 assembles five distinct technical subsystems: Azure AD authentication (MSAL), Azure OpenAI chat completions with tool calling, MCP client integration (subprocess stdio), SSE streaming to the browser, and tiktoken-based context window pruning.

The core challenge is the **async/sync bridge**: the MCP SDK client is fundamentally async (uses `asyncio`/`anyio`), but Flask with Waitress is a synchronous WSGI application. The recommended pattern is to run a dedicated background event loop in a daemon thread, spawn the MCP subprocess at app startup, and call the async MCP client from synchronous Flask routes using `loop.run_until_complete()`.

A **critical constraint** must be verified before implementation begins: the architecture doc pins `API_VERSION=2023-05-15` for the MMC CoreAPI gateway. This API version predates function calling support — the `tools` and `tool_choice` parameters were only added in `2023-12-01-preview`. The MMC gateway endpoint URL is a full path to a specific deployment (`/coreapi/openai/v1/deployments/.../chat/completions`), so the `api-version` query parameter may be ignored or overridden by the gateway internally. This must be confirmed before the tool-calling loop (plan 07-04/07-05) is implemented.

**Primary recommendation:** Use `msal>=1.35`, `openai>=1.0`, `tiktoken>=0.8`, and `flask-session>=0.8` as the new dependency additions. Spawn the MCP server subprocess once at Flask app startup using `asyncio` in a background daemon thread. Implement MSAL auth code flow with `SerializableTokenCache` stored in Flask's server-side session.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 (already installed) | Web framework | Already chosen; Jinja2 templates included |
| Waitress | 3.0.2 (already installed) | Production WSGI server | Already chosen; runs on Windows without C extensions |
| msal | >=1.35.0 | Azure AD auth code flow | Official Microsoft library for Entra ID |
| openai | >=1.0.0 | Azure OpenAI chat completions | Official SDK; AzureOpenAI client class |
| tiktoken | >=0.8.0 | Token counting for gpt-4o-mini | Official OpenAI tokenizer library |
| mcp | 1.26.0 (already installed) | MCP client to spawn exchange_mcp server | Already installed; official SDK |
| flask-session | >=0.8.0 | Server-side session storage | Required for MSAL SerializableTokenCache; default Flask cookie sessions have 4KB limit |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| boto3 | latest | AWS Secrets Manager at startup | Load AZURE_OPENAI_API_KEY, MSAL CLIENT_SECRET |
| python-dotenv | latest | Load .env in dev | Dev-only; prod loads from Secrets Manager |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| flask-session (filesystem) | Redis session store | Redis adds operational complexity; filesystem works for single-server deployment |
| tiktoken | Simple char/4 estimate | tiktoken is accurate; char estimate drifts ±20%, causing either waste or 128K violations |
| openai.AzureOpenAI | requests directly | SDK handles retries, type safety, streaming; no reason to use raw requests |

### Installation
```bash
uv add msal openai tiktoken flask-session boto3 python-dotenv
```

---

## Architecture Patterns

### Recommended Project Structure
```
chat_app/
├── app.py               # Flask factory, Waitress entry point
├── auth.py              # MSAL auth routes: /login, /auth/callback, /logout
├── chat.py              # Chat routes: /chat (GET render), /chat/stream (SSE)
├── mcp_client.py        # MCP subprocess lifecycle, async bridge, tool dispatch
├── openai_client.py     # Azure OpenAI wrapper: chat completions, tool-call loop
├── context_mgr.py       # tiktoken token counting, conversation pruning
├── secrets.py           # AWS Secrets Manager loader
├── config.py            # App configuration from environment
├── static/
│   ├── app.js           # SSE EventSource, chat UI logic, tool chip rendering
│   └── style.css        # Chat UI styles
└── templates/
    ├── base.html        # Layout: header with avatar/status, main content slot
    ├── splash.html      # "Sign in with Microsoft" branded landing page
    └── chat.html        # Chat interface with auto-expanding textarea
```

### Pattern 1: MSAL Auth Code Flow with SerializableTokenCache

**What:** Two-step Azure AD login: redirect to Microsoft login page, then receive authorization code at callback URL and exchange for tokens. Tokens are serialized into Flask session to survive request boundaries.

**When to use:** Any SSO web app where colleagues authenticate with their MMC Entra ID identity.

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
# + MSAL Python 1.35.0 docs at https://msal-python.readthedocs.io/en/latest/

import msal
from flask import session, redirect, request, url_for

def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        client_id=Config.CLIENT_ID,
        client_credential=Config.CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{Config.TENANT_ID}",
        token_cache=cache,
    )

def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

# Login route — initiates the flow
@app.route("/login")
def login():
    flow = _build_msal_app().initiate_auth_code_flow(
        scopes=["User.Read"],
        redirect_uri=url_for("auth_callback", _external=True),
    )
    session["auth_flow"] = flow
    return redirect(flow["auth_uri"])

# Callback route — exchanges auth code for tokens
@app.route("/auth/callback")
def auth_callback():
    cache = _load_cache()
    app_msal = _build_msal_app(cache=cache)
    try:
        result = app_msal.acquire_token_by_auth_code_flow(
            session.pop("auth_flow", {}), request.args
        )
    except ValueError:
        return redirect(url_for("login"))  # CSRF, retry
    if "error" in result:
        return render_template("error.html", error=result.get("error_description"))
    session["user"] = result.get("id_token_claims")
    _save_cache(cache)
    return redirect(url_for("chat"))

# Silent re-auth using refresh token
def get_token_silently():
    cache = _load_cache()
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:
        result = cca.acquire_token_silent(["User.Read"], account=accounts[0])
        _save_cache(cache)
        return result
    return None
```

### Pattern 2: MCP Client Async Bridge in Flask

**What:** Spawn the MCP stdio server subprocess at Flask startup, maintain a single `ClientSession`, bridge async MCP calls into synchronous Flask request handlers using a dedicated background event loop thread.

**When to use:** Any synchronous web framework that needs to call an async MCP server.

**Example:**
```python
# Source: https://modelcontextprotocol.io/docs/develop/build-client
# MCP SDK version 1.26.0

import asyncio
import threading
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_mcp_session: ClientSession | None = None
_mcp_loop: asyncio.AbstractEventLoop | None = None
_mcp_tools: list[dict] | None = None  # Cached as OpenAI tool schemas

def _start_mcp_event_loop():
    """Run dedicated asyncio event loop in daemon thread."""
    global _mcp_loop
    _mcp_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_mcp_loop)
    _mcp_loop.run_forever()

def _async_run(coro):
    """Execute coroutine on the MCP event loop from synchronous context."""
    future = asyncio.run_coroutine_threadsafe(coro, _mcp_loop)
    return future.result(timeout=30)

async def _connect_mcp():
    global _mcp_session, _mcp_tools
    exit_stack = AsyncExitStack()
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "exchange_mcp.server"],
        env=None,  # inherits from Flask process
    )
    transport = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio, write = transport
    session = await exit_stack.enter_async_context(ClientSession(stdio, write))
    await session.initialize()
    response = await session.list_tools()
    _mcp_session = session
    # Convert MCP tool definitions to OpenAI function schema format
    _mcp_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            }
        }
        for tool in response.tools
    ]

def init_mcp(app):
    """Called once during Flask app startup."""
    thread = threading.Thread(target=_start_mcp_event_loop, daemon=True)
    thread.start()
    # Wait for loop to start
    import time; time.sleep(0.1)
    _async_run(_connect_mcp())

def call_mcp_tool(name: str, arguments: dict) -> str:
    """Synchronous wrapper — callable from Flask route handlers."""
    async def _call():
        result = await _mcp_session.call_tool(name, arguments)
        # result.content is list[TextContent]; each has .text
        return result.content[0].text if result.content else ""
    return _async_run(_call())

def get_mcp_tools() -> list[dict]:
    return _mcp_tools or []
```

### Pattern 3: Azure OpenAI Tool-Calling Loop

**What:** First call with `tools` parameter. If model returns `tool_calls`, dispatch each to MCP, append `tool` role messages, make second completion call. Repeat until no more tool_calls in response.

**When to use:** Any query that may require Exchange data lookup.

**CRITICAL NOTE:** The `tools` parameter requires API version >= `2023-12-01-preview`. The MMC gateway is pinned to `2023-05-15`. Verify with the CTS team whether the gateway supports `tools`. If not, use the deprecated `functions`/`function_call` parameters which ARE in `2023-05-15` (based on research — see Open Questions).

**Example:**
```python
# Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/function-calling
# API version: 2023-05-15 pinned; verify 'tools' support with MMC gateway team

import json
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=Config.CHATGPT_ENDPOINT,  # full MMC gateway URL
    api_key=Config.AZURE_OPENAI_API_KEY,
    api_version=Config.API_VERSION,          # "2023-05-15" — verify gateway support
)

def run_tool_call_loop(messages: list[dict], tools: list[dict]) -> str:
    """Execute tool-calling loop and return final text response."""
    while True:
        response = client.chat.completions.create(
            model="mmc-tech-gpt-4o-mini-128k-2024-07-18",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        response_message = response.choices[0].message
        messages.append(response_message)

        if not response_message.tool_calls:
            return response_message.content

        # Execute all tool calls and append results
        for tool_call in response_message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            tool_result = call_mcp_tool(tool_name, tool_args)
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_name,
                "content": tool_result,
            })
```

**Important:** The `messages.append(response_message)` call appends the SDK's `ChatCompletionMessage` object, which the SDK can serialize. Alternatively convert to dict: `{"role": "assistant", "content": None, "tool_calls": [...]}`.

### Pattern 4: SSE Streaming to Browser

**What:** Flask generator function yields `data: ...\n\n` SSE frames. `stream_with_context` preserves Flask's request context across yield boundaries. Final OpenAI response streams chunk by chunk.

**When to use:** After the tool-calling loop is complete, stream the final LLM text response.

**Example:**
```python
# Source: https://flask.palletsprojects.com/en/stable/patterns/streaming/

from flask import Response, stream_with_context
import json

@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    user_message = request.json.get("message")
    conversation = session.get("conversation", [])

    def generate():
        # Phase 1: Tool execution status chips
        # Run tool loop (non-streaming) to get final messages
        # This is fine: tool calls are fast (2-4s), stream is for final answer only
        updated_messages, tool_events = run_tool_loop_with_events(
            conversation + [{"role": "user", "content": user_message}]
        )
        for event in tool_events:
            yield f"data: {json.dumps({'type': 'tool', 'name': event})}\n\n"

        # Phase 2: Stream final AI response
        stream = client.chat.completions.create(
            model="mmc-tech-gpt-4o-mini-128k-2024-07-18",
            messages=updated_messages,
            stream=True,
        )
        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_text += delta.content
                yield f"data: {json.dumps({'type': 'text', 'content': delta.content})}\n\n"

        # Phase 3: Done signal — update server-side conversation
        updated_messages.append({"role": "assistant", "content": full_text})
        session["conversation"] = updated_messages
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # IMPORTANT: Access session BEFORE entering generator (session not available in generator)
    _ = session.get("user")  # Force session load
    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Session in generators:** Flask session is NOT accessible inside a generator unless `stream_with_context` is used AND the session was accessed before the generator starts. Save conversation to session AFTER streaming completes via a separate POST to `/chat/save` or use server-side storage (SQLite per Phase 8).

### Pattern 5: tiktoken Context Window Pruning

**What:** Count tokens in the messages list before every API call. If total exceeds limit minus safety buffer, remove oldest non-system messages until it fits.

**When to use:** Before every API call to prevent 128K context overflow.

**Example:**
```python
# Source: https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken

import tiktoken

_ENCODING = tiktoken.get_encoding("o200k_base")  # gpt-4o-mini encoding
_MAX_TOKENS = 128_000
_SAFETY_BUFFER = 4_096   # Reserve for response
_EFFECTIVE_LIMIT = _MAX_TOKENS - _SAFETY_BUFFER

def count_tokens_in_messages(messages: list[dict]) -> int:
    """Count tokens for gpt-4o-mini (3 tokens per message overhead)."""
    tokens = 3  # reply primer
    for msg in messages:
        tokens += 3  # per-message overhead
        for key, value in msg.items():
            if isinstance(value, str):
                tokens += len(_ENCODING.encode(value))
            elif key == "tool_calls" and value:
                # Tool call arguments are JSON strings
                for tc in value:
                    tokens += len(_ENCODING.encode(tc.function.arguments or ""))
                    tokens += len(_ENCODING.encode(tc.function.name or ""))
    return tokens

def prune_conversation(messages: list[dict]) -> list[dict]:
    """Remove oldest non-system messages until within token limit.

    Always preserves: system prompt (index 0).
    Removes from: oldest user/assistant/tool messages first.
    """
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    while count_tokens_in_messages(system_msgs + other_msgs) > _EFFECTIVE_LIMIT:
        if not other_msgs:
            break  # Cannot prune further; system prompt itself is too large
        other_msgs.pop(0)  # Remove oldest non-system message

    return system_msgs + other_msgs
```

### Anti-Patterns to Avoid

- **Storing full conversation in client-side cookie:** Flask default sessions use signed cookies with a 4KB size limit. A long Exchange conversation with JSON tool results will exceed this. Use `flask-session` with `SESSION_TYPE = "filesystem"` for single-server deployments.
- **Creating a new asyncio event loop per request:** `asyncio.run()` creates a new event loop per call. For MCP, this would spawn a new subprocess per request. Create one event loop at startup and reuse it.
- **Blocking Flask's request thread with asyncio.run():** On Windows, nested event loops cause errors. Use `loop.run_until_complete()` on a separate thread's event loop, not `asyncio.run()` from a Flask route.
- **Streaming tool calls:** Do not stream the initial tool-calling loop. Stream only the final text response. Tool calls are fast (2-4s), and streaming partial JSON tool arguments to the browser is not useful. Show a status chip instead.
- **Reading session in a generator without stream_with_context:** Flask's request context is torn down when the response starts. Without `stream_with_context`, `session` access inside a generator raises a RuntimeError.
- **Appending OpenAI SDK message objects to conversation list for session storage:** SDK `ChatCompletionMessage` objects are not JSON-serializable. Convert to plain dicts before storing in session.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Azure AD SSO token flow | Custom OAuth2 redirect/callback | msal.ConfidentialClientApplication | CSRF protection, nonce validation, PKCE, token refresh — all built in |
| Token refresh | Check expiry and re-request | msal.acquire_token_silent() | Handles refresh token rotation, clock skew, token cache atomically |
| Token counting | count_chars / 4 rough estimate | tiktoken with o200k_base encoding | gpt-4o-mini uses byte-pair encoding; character estimates are wrong for CJK and symbols |
| SSE chunking | Manual response.write() | Flask Response(stream_with_context(gen())) | Correct Content-Type, buffer flushing, context preservation |
| MCP subprocess lifecycle | subprocess.Popen directly | mcp.client.stdio.stdio_client | Handles stdin/stdout framing, JSON-RPC protocol, session initialization |
| OpenAI retry logic | time.sleep() retry loop | openai SDK built-in | SDK handles 429 rate limits, 500 errors with exponential backoff |
| Conversation serialization | Custom dict-to-JSON | Convert to plain dicts before session storage | SDK objects not serializable; maintain a separate plain-dict conversation list |

**Key insight:** In auth and AI SDK domains, the libraries handle dozens of edge cases (token refresh races, CSRF, encoding quirks) that will manifest as production bugs if hand-rolled.

---

## Common Pitfalls

### Pitfall 1: API Version Does Not Support Tool Calling
**What goes wrong:** Azure OpenAI returns `400 BadRequest: Unrecognized parameter: tools` or silently ignores tool definitions, resulting in the model not calling any tools.
**Why it happens:** The architecture doc pins `API_VERSION=2023-05-15`. This version's OpenAPI spec does not include the `tools` or `function_call` parameters. Function calling was added in `2023-07-01-preview` (as `functions`) and upgraded to `tools` in `2023-12-01-preview`.
**How to avoid:** Confirm with the MMC CTS team whether the CoreAPI gateway internally routes to a newer API version regardless of the `api-version` query parameter. If needed, request the team update the approved API version to at least `2023-12-01-preview`. As a fallback, use the deprecated `functions` parameter (supported from `2023-07-01-preview`).
**Warning signs:** ChatCompletion responses have no `tool_calls` attribute; model describes actions it "would" take instead of calling tools.

### Pitfall 2: Flask Session Too Small for Conversation History
**What goes wrong:** After a few Exchange queries, new messages silently fail to persist. The conversation resets on the next request.
**Why it happens:** Flask's default cookie-based session has a 4KB limit. Exchange tool results (JSON) are verbose — a single `get_mailbox_stats` response can be 500-800 tokens (~2-3KB). Two tool calls fill the cookie.
**How to avoid:** Install `flask-session` and configure `SESSION_TYPE = "filesystem"` or `"sqlalchemy"`. Use `flask_session.Session(app)` after `app.config` is set.
**Warning signs:** `session.modified` is True but data is truncated; no error raised — data silently dropped.

### Pitfall 3: Session Not Accessible Inside SSE Generator
**What goes wrong:** `RuntimeError: Working outside of request context` when `session["conversation"]` is accessed inside the generator passed to `Response()`.
**Why it happens:** Flask tears down the request context when the response begins. SSE generators run after this point.
**How to avoid:** (1) Use `stream_with_context()` which preserves the app context. (2) Read ALL session data needed BEFORE entering the generator. (3) Write back to session AFTER the stream completes via a separate mechanism.
**Warning signs:** RuntimeError in the generator; conversation is never updated after a stream.

### Pitfall 4: MCP Subprocess Stdout Corruption
**What goes wrong:** MCP client receives malformed JSON-RPC responses; connection closes unexpectedly.
**Why it happens:** Any `print()` statement or logging to stdout in `server.py` corrupts the stdio JSON-RPC transport. The existing server correctly routes all logging to stderr.
**How to avoid:** Never add print() statements to exchange_mcp/server.py. All logging must use `logging.getLogger()` which is already configured to `stream=sys.stderr`.
**Warning signs:** `mcp.exceptions.McpError: Invalid JSON` in the client; connection drops after a few tool calls.

### Pitfall 5: Blocking Flask's Request Thread with asyncio.run()
**What goes wrong:** `RuntimeError: This event loop is already running` or deadlock.
**Why it happens:** On Windows with Waitress, `asyncio.run()` creates a new event loop in the calling thread. If Flask uses `async def` views (which start their own event loop), nesting fails.
**How to avoid:** Create ONE dedicated asyncio event loop in a daemon thread at startup. Dispatch all async MCP operations to that loop using `asyncio.run_coroutine_threadsafe()`. Never call `asyncio.run()` from Flask request handlers.
**Warning signs:** Deadlock on tool call; `asyncio.run() cannot be called when another event loop is running`.

### Pitfall 6: Parallel Tool Calls Require Sequential MCP Dispatch
**What goes wrong:** gpt-4o-mini may return multiple `tool_calls` in a single response (parallel function calling). If dispatched concurrently to MCP, the MCP session may not support concurrent calls on a single `ClientSession`.
**Why it happens:** MCP stdio transport is sequential JSON-RPC. Concurrent requests on the same session may interleave JSON-RPC frames.
**How to avoid:** Process `tool_calls` sequentially even if the model returns them in parallel. Iterate through `response_message.tool_calls` and call `_async_run(session.call_tool(...))` for each one in order.
**Warning signs:** Malformed MCP responses; tool results assigned to wrong tool_call_ids.

### Pitfall 7: tool_calls Message Serialization for Session Storage
**What goes wrong:** `TypeError: Object of type ChatCompletionMessage is not JSON serializable` when storing conversation to Flask session.
**Why it happens:** `messages.append(response_message)` appends a SDK `ChatCompletionMessage` pydantic model, not a plain dict.
**How to avoid:** After each API response, convert the assistant message to a plain dict:
```python
assistant_dict = {
    "role": "assistant",
    "content": response_message.content,
    "tool_calls": [
        {
            "id": tc.id,
            "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
        }
        for tc in (response_message.tool_calls or [])
    ] or None,
}
messages.append(assistant_dict)
```
**Warning signs:** JSON serialization error when saving to session; crash on first tool-calling response.

---

## Code Examples

### Initialize AzureOpenAI Client with MMC Gateway
```python
# Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/function-calling
# Note: The MMC CHATGPT_ENDPOINT is a full path URL ending in /chat/completions
# The openai SDK's AzureOpenAI expects an azure_endpoint (base URL), not the full path.
# Use the plain openai.OpenAI with base_url instead.

from openai import OpenAI  # Not AzureOpenAI — MMC uses a custom gateway URL

client = OpenAI(
    base_url="https://stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com/coreapi/openai/v1/",
    api_key=secrets["AZURE_OPENAI_API_KEY"],
    # api_version handled via base_url path for custom gateways
)
```

**Alternative if gateway requires `api-key` header with full deployment path:**
```python
import httpx
# Use httpx directly for the MMC gateway if openai SDK's URL manipulation conflicts
# with the full deployment path format
```

**IMPORTANT:** The architecture doc CHATGPT_ENDPOINT is a full URL ending in `.../chat/completions`. The OpenAI SDK adds `/chat/completions` to `base_url` automatically. Test whether the SDK double-appends the path. If so, set `base_url` to the parent deployment URL, not the full endpoint.

### MSAL Flask Session Pattern (Minimal)
```python
# Source: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens

import msal
from flask import session

SCOPES = ["https://graph.microsoft.com/User.Read"]

def get_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        token_cache=cache,
    )

def load_token_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def save_token_cache(cache: msal.SerializableTokenCache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()
```

### tiktoken Token Count for gpt-4o-mini
```python
# Source: https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken
# o200k_base encoding for gpt-4o-mini (confirmed authoritative source)

import tiktoken

def num_tokens_from_messages(messages: list[dict]) -> int:
    enc = tiktoken.get_encoding("o200k_base")
    num_tokens = 3  # every reply is primed with 3 tokens
    for message in messages:
        num_tokens += 3  # per-message overhead
        for key, value in message.items():
            if isinstance(value, str):
                num_tokens += len(enc.encode(value))
    return num_tokens
```

### MCP Tool List to OpenAI Tool Schema Conversion
```python
# Source: MCP SDK 1.26.0 list_tools() response structure
# + https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/function-calling

async def list_tools_as_openai_schemas(session: ClientSession) -> list[dict]:
    response = await session.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": (tool.description or "")[:1024],  # Azure limit: 1024 chars
                "parameters": tool.inputSchema,
            }
        }
        for tool in response.tools
    ]
```

### Flask-Session Configuration
```python
# Source: flask-session docs; required for MSAL token cache + long conversation storage
from flask import Flask
from flask_session import Session

app = Flask(__name__)
app.config.update(
    SESSION_TYPE="filesystem",         # or "sqlalchemy" for prod
    SESSION_FILE_DIR="/tmp/flask-sessions",
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SECRET_KEY=secrets["FLASK_SECRET_KEY"],
)
Session(app)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `functions` + `function_call` params | `tools` + `tool_choice` params | 2023-12-01-preview | Deprecated but still functional; MMC may still use old form |
| `AzureOpenAI(azure_endpoint=...)` | `OpenAI(base_url=...)` for custom gateways | 2024+ | AzureOpenAI expects standard Azure URL patterns; custom gateways need base_url |
| Manual PKCE/CSRF in auth flow | `initiate_auth_code_flow()` auto-handles | MSAL Python 1.x | Built-in security; no hand-rolling needed |
| `identity` package wrapper | Direct `msal.ConfidentialClientApplication` | N/A | `identity` package is community-maintained; direct MSAL is authoritative |

**Deprecated/outdated:**
- `functions` parameter: Deprecated in `2023-12-01-preview`, replaced by `tools`. Still functional but may not work at all with `2023-05-15`.
- `msal.PublicClientApplication` for web apps: Use `ConfidentialClientApplication` — web servers can store secrets securely.

---

## Open Questions

1. **Does the MMC CoreAPI gateway support the `tools` parameter with `API_VERSION=2023-05-15`?**
   - What we know: The `2023-05-15` API spec does not define `tools` or `functions` parameters. Function calling was added in `2023-07-01-preview`.
   - What's unclear: The MMC gateway is a custom proxy (`/coreapi/openai/v1/`). The gateway may ignore `api-version` and route to a newer version internally. Alternatively, it may strictly enforce `2023-05-15` semantics.
   - Recommendation: **Test this first in plan 07-03** by making a basic chat completion with the MMC gateway. Then in plan 07-04, test adding `tools` parameter. If rejected, check whether `functions`+`function_call` (pre-`2023-12-01-preview` style) is accepted. Escalate to CTS if neither works.

2. **Does the MMC gateway accept the OpenAI Python SDK's `base_url` approach or require the full deployment URL?**
   - What we know: The architecture doc shows `CHATGPT_ENDPOINT` as the full path ending in `/chat/completions`. The OpenAI SDK appends `/chat/completions` to `base_url`.
   - What's unclear: If `base_url` is set to the deployment base, the SDK will produce the correct full URL. If set to the full endpoint including `/chat/completions`, the SDK will double-append.
   - Recommendation: Set `base_url` to the deployment URL without the trailing path component (strip `/chat/completions` from the env var). Verify by checking the SDK's actual HTTP request.

3. **Conditional Access policies: Does MMC Entra ID require MFA or device compliance on the chat app?**
   - What we know: MSAL handles Conditional Access error codes (`interaction_required`, `AADSTS50076`).
   - What's unclear: Specific MMC Conditional Access policies are not documented here.
   - Recommendation: Handle `interaction_required` error by redirecting to login. Test with a real MMC account in the dev environment.

4. **Can MCP's `ClientSession` handle concurrent requests from multiple Flask workers?**
   - What we know: Waitress uses threads (not processes). The MCP session is a single shared instance. Concurrent thread access to the same `ClientSession` may have race conditions.
   - What's unclear: Whether MCP SDK 1.26.0 `ClientSession.call_tool()` is thread-safe.
   - Recommendation: Add a threading lock around `call_tool()` invocations. The per-call PSSession design means Exchange operations themselves are isolated, so serializing MCP calls is the right approach.

---

## Sources

### Primary (HIGH confidence)
- `https://msal-python.readthedocs.io/en/latest/` — MSAL Python 1.35.0 documentation; auth code flow, SerializableTokenCache API
- `https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens` — Official acquiring tokens guide; initiate_auth_code_flow, acquire_token_by_auth_code_flow patterns
- `https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/function-calling` — Azure OpenAI function calling; confirmed gpt-4o-mini-2024-07-18 supports parallel function calling; tools/tool_choice message format
- `https://modelcontextprotocol.io/docs/develop/build-client` — MCP Python client pattern; StdioServerParameters, stdio_client, ClientSession, AsyncExitStack
- `https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken` — tiktoken token counting; o200k_base encoding for gpt-4o-mini; 3 tokens per message overhead
- `https://flask.palletsprojects.com/en/stable/patterns/streaming/` — Flask streaming; stream_with_context, SSE Content-Type pattern
- `https://raw.githubusercontent.com/Azure/azure-rest-api-specs/main/specification/cognitiveservices/data-plane/AzureOpenAI/inference/stable/2023-05-15/inference.json` — Confirmed: 2023-05-15 API spec does NOT contain tools or functions parameters

### Secondary (MEDIUM confidence)
- `https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle` — API version changelog; confirms tools parameter added in 2023-12-01-preview
- `https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-web-app-python-sign-in` — Flask MSAL redirect URI pattern `/getAToken`; environment variables CLIENT_ID, CLIENT_SECRET, AUTHORITY

### Tertiary (LOW confidence)
- WebSearch results on Flask asyncio bridge patterns — Multiple sources confirm `asyncio.run_coroutine_threadsafe()` pattern for calling async from sync in a separate thread event loop

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All libraries are official, versions verified from uv.lock and official docs
- Architecture: HIGH — MCP client pattern verified from official MCP docs; MSAL pattern from official MS docs; SSE from Flask official docs
- Pitfalls: HIGH for pitfalls 3-7 (verified from official docs); MEDIUM for pitfall 1 (API version constraint requires runtime verification)
- Open question 1 (API version): LOW confidence on resolution — requires runtime test against MMC gateway

**Research date:** 2026-03-21
**Valid until:** 2026-04-20 (30 days — stable libraries; MSAL and OpenAI SDK update frequently but API patterns are stable)
