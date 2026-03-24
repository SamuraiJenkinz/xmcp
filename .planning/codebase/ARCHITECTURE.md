# Architecture

## Pattern

**Dual-subsystem monorepo** — two independent Python packages (`exchange_mcp/` and `chat_app/`) connected at runtime via MCP stdio transport. The MCP server runs as a subprocess spawned by the chat app.

## Layers

### Exchange MCP Server (`exchange_mcp/`)

```
┌─────────────────────────────────────────┐
│  MCP Protocol Layer (server.py)         │  JSON-RPC over stdio
│  - list_tools / call_tool handlers      │
│  - Error classification (transient vs   │
│    non-transient)                       │
├─────────────────────────────────────────┤
│  Tool Dispatch Layer (tools.py)         │  1,875 lines
│  - TOOL_DEFINITIONS: 15 mcp.types.Tool │
│  - TOOL_DISPATCH: name → async handler  │
│  - DNS tools delegate to dns_utils.py   │
├─────────────────────────────────────────┤
│  Exchange Client (exchange_client.py)   │  Retry + auth
│  - run_cmdlet(ps_script) → dict/list    │
│  - Interactive or CBA authentication    │
│  - Exponential backoff for transient    │
├─────────────────────────────────────────┤
│  PS Runner (ps_runner.py)               │  Subprocess
│  - run_ps(script) → raw string          │
│  - -EncodedCommand (UTF-16LE Base64)    │
│  - Timeout enforcement + process kill   │
├─────────────────────────────────────────┤
│  DNS Utils (dns_utils.py)               │  No PowerShell
│  - dnspython async resolver             │
│  - TTL-respecting cache                 │
│  - DMARC/SPF/CNAME parsers              │
└─────────────────────────────────────────┘
```

### Chat Application (`chat_app/`)

```
┌─────────────────────────────────────────┐
│  Flask App Factory (app.py)             │  Entry point
│  - create_app() → Flask                 │
│  - Blueprint registration               │
│  - Graceful degradation on init errors  │
├─────────────────────────────────────────┤
│  Auth (auth.py)                         │  Azure AD SSO
│  - MSAL auth code flow                  │
│  - @login_required decorator            │
│  - Session-based identity               │
├─────────────────────────────────────────┤
│  Chat SSE (chat.py)                     │  Streaming
│  - POST /chat/stream → SSE generator    │
│  - Tool-calling loop (non-streaming)    │
│  - Final response (streaming chunks)    │
│  - Thread auto-naming                   │
├─────────────────────────────────────────┤
│  Conversations (conversations.py)       │  CRUD API
│  - /api/threads/* REST endpoints        │
│  - User-scoped ownership enforcement    │
├─────────────────────────────────────────┤
│  OpenAI Client (openai_client.py)       │  AI backend
│  - openai.OpenAI (not AzureOpenAI)      │
│  - System prompt (Atlas persona)        │
│  - run_tool_loop() — up to 5 iterations │
├─────────────────────────────────────────┤
│  MCP Client (mcp_client.py)             │  Bridge
│  - Daemon thread with own event loop    │
│  - Threading.Lock for serial MCP calls  │
│  - Sync wrapper: call_mcp_tool()        │
├─────────────────────────────────────────┤
│  Context Manager (context_mgr.py)       │  Token mgmt
│  - tiktoken o200k_base encoding         │
│  - 128K window, 4K safety buffer        │
│  - Prune oldest non-system messages     │
├─────────────────────────────────────────┤
│  Config (config.py) + Secrets           │  Configuration
│  - Environment variables → class attrs  │
│  - AWS Secrets Manager / .env fallback  │
├─────────────────────────────────────────┤
│  SQLite (db.py + schema.sql)            │  Persistence
│  - Flask g-object connection pattern    │
│  - WAL mode, auto-bootstrap schema      │
│  - threads + messages tables            │
└─────────────────────────────────────────┘
```

## Data Flow

### Chat Message Flow

```
User → Browser POST /chat/stream
     → Flask route (chat.py)
     → Load conversation from SQLite
     → prune_conversation() if over token limit
     → OpenAI chat completion (non-streaming, with tools)
     → Tool call? → call_mcp_tool() → MCP stdio → exchange_mcp server
                  → tool result → back to OpenAI loop (up to 5 rounds)
     → Final answer: stream via SSE chunks
     → Save conversation to SQLite
     → SSE "done" event
```

### MCP Tool Execution Flow

```
call_mcp_tool(name, args)
  → threading.Lock acquire
  → asyncio.run_coroutine_threadsafe to daemon loop
  → MCP ClientSession.call_tool() over stdio
  → exchange_mcp server.py call_tool handler
  → TOOL_DISPATCH[name](args, client)
  → ExchangeClient.run_cmdlet() or dns_utils.*
  → PowerShell subprocess (Exchange tools) or dnspython (DNS tools)
  → JSON result back up the chain
```

## Key Abstractions

| Abstraction | Location | Purpose |
|-------------|----------|---------|
| `TOOL_DISPATCH` | `exchange_mcp/tools.py` | Single routing dict: tool name → async handler |
| `ExchangeClient` | `exchange_mcp/exchange_client.py` | Wraps PS runner with Exchange auth + retry |
| `run_ps()` | `exchange_mcp/ps_runner.py` | Lowest-level PowerShell subprocess execution |
| `_async_run()` | `chat_app/mcp_client.py` | Sync-to-async bridge for Flask → MCP calls |
| `run_tool_loop()` | `chat_app/openai_client.py` | OpenAI tool-calling iteration loop |
| `prune_conversation()` | `chat_app/context_mgr.py` | Token-aware conversation window management |

## Entry Points

| Entry Point | Command | Purpose |
|-------------|---------|---------|
| MCP Server | `uv run python -m exchange_mcp.server` | Standalone stdio MCP server |
| MCP Dev | `uv run mcp dev exchange_mcp/server.py` | MCP Inspector dev mode |
| Chat App | `python -m chat_app.app` or Waitress | Flask web application |
| Tests | `uv run pytest` | Test suite |
| DB Init | `flask init-db` | Reset database schema |

## Cross-Cutting Concerns

- **Logging**: All modules use `logging.getLogger(__name__)`. MCP server logs to stderr (critical for stdio transport).
- **Error classification**: Both `server.py` and `exchange_client.py` classify errors as transient vs non-transient using string pattern matching.
- **Authentication**: Azure AD SSO (chat app) + Exchange Online interactive/CBA (MCP server) — two separate auth chains.
- **Configuration**: Environment variables → `Config` class, with AWS Secrets Manager override via `secrets.py`.
