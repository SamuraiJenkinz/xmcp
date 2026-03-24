# Structure

## Directory Layout

```
C:/xmcp/
├── exchange_mcp/                  # MCP Server package (2,969 LOC)
│   ├── __init__.py                # Package marker
│   ├── server.py          (282)   # MCP stdio server, list_tools/call_tool
│   ├── tools.py          (1875)   # 15 tool definitions + dispatch handlers
│   ├── exchange_client.py (372)   # Exchange auth, retry, run_cmdlet()
│   ├── ps_runner.py       (134)   # Async PowerShell subprocess runner
│   └── dns_utils.py       (305)   # DNS resolver, DMARC/SPF parsers, TTL cache
│
├── chat_app/                      # Flask Chat Application (1,789 LOC)
│   ├── __init__.py                # Package marker
│   ├── app.py             (126)   # Flask app factory, blueprint registration
│   ├── auth.py            (179)   # Azure AD MSAL auth code flow + @login_required
│   ├── chat.py            (331)   # SSE streaming endpoint, tool-calling loop
│   ├── config.py           (69)   # Config class from env vars
│   ├── context_mgr.py     (199)   # tiktoken counting + conversation pruning
│   ├── conversations.py   (133)   # Thread CRUD REST API blueprint
│   ├── db.py               (78)   # SQLite connection management (Flask pattern)
│   ├── mcp_client.py      (259)   # MCP client bridge (daemon thread + async)
│   ├── openai_client.py   (352)   # Azure OpenAI wrapper, system prompt, tool loop
│   ├── secrets.py          (62)   # AWS Secrets Manager / .env loader
│   ├── schema.sql                 # SQLite schema (threads + messages)
│   ├── static/
│   │   ├── app.js                 # Frontend JS (sidebar, SSE, tool panels, dark mode)
│   │   └── style.css              # Styles (responsive, dark mode, tool panels)
│   └── templates/
│       ├── base.html              # Layout template
│       ├── chat.html              # Main chat interface
│       └── splash.html            # Login splash page
│
├── tests/                         # Test suite (5,130 LOC)
│   ├── __init__.py
│   ├── test_ps_runner.py    (69)  # Real PowerShell subprocess tests
│   ├── test_exchange_client.py (366) # Exchange client with mocked ps_runner
│   ├── test_server.py      (230)  # MCP server handler tests
│   ├── test_tool_descriptions.py (321) # Tool schema validation
│   ├── test_tools_mailbox.py (609) # Mailbox tool handler tests
│   ├── test_tools_dag.py  (1056)  # DAG tool handler tests
│   ├── test_tools_flow.py  (830)  # Mail flow tool handler tests
│   ├── test_tools_hybrid.py (592) # Hybrid tool handler tests
│   ├── test_tools_security.py (587) # Security/DNS tool handler tests
│   ├── test_dns_utils.py   (302)  # DNS utility tests
│   └── test_integration.py (168)  # Cross-module integration tests
│
├── scripts/                       # Verification scripts
│   ├── verify_dns.py              # DNS connectivity check
│   └── verify_exchange.py         # Exchange connectivity check
│
├── pyproject.toml                 # Project config, dependencies, pytest markers
├── .env                           # Local environment variables (not committed)
├── chat.db                        # SQLite database (auto-created)
└── exchange-mcp-architecture.md   # Architecture reference document
```

## Key Locations

| What | Where |
|------|-------|
| Tool definitions | `exchange_mcp/tools.py:TOOL_DEFINITIONS` |
| Tool dispatch table | `exchange_mcp/tools.py:TOOL_DISPATCH` |
| PowerShell execution | `exchange_mcp/ps_runner.py:run_ps()` |
| Exchange auth + retry | `exchange_mcp/exchange_client.py:run_cmdlet()` |
| DNS lookups | `exchange_mcp/dns_utils.py` |
| MCP server entry | `exchange_mcp/server.py` |
| Flask app factory | `chat_app/app.py:create_app()` |
| SSE chat endpoint | `chat_app/chat.py:chat_bp` |
| OpenAI tool loop | `chat_app/openai_client.py:run_tool_loop()` |
| MCP client bridge | `chat_app/mcp_client.py:call_mcp_tool()` |
| Auth flow | `chat_app/auth.py:auth_bp` |
| DB schema | `chat_app/schema.sql` |
| System prompt | `chat_app/openai_client.py:SYSTEM_PROMPT` |
| Token pruning | `chat_app/context_mgr.py:prune_conversation()` |
| Config | `chat_app/config.py:Config` |

## Naming Conventions

- **Files**: `snake_case.py` — flat within each package, no sub-packages
- **Functions**: `snake_case` — `run_cmdlet()`, `get_mailbox_stats()`, `call_mcp_tool()`
- **Constants**: `UPPER_SNAKE_CASE` — `TOOL_DEFINITIONS`, `TOOL_DISPATCH`, `SYSTEM_PROMPT`, `_MAX_TOOL_ITERATIONS`
- **Private**: Leading underscore — `_PS_PREAMBLE`, `_encode_command()`, `_TRANSIENT_PATTERNS`
- **Classes**: `PascalCase` — `Config`, `ExchangeClient`
- **Blueprints**: `{name}_bp` — `auth_bp`, `chat_bp`, `conversations_bp`
- **Tests**: `test_{module}.py` with `test_{what}__{scenario}` or `test_{verb}_{noun}` functions
- **Tool names**: `snake_case` matching Exchange cmdlet semantics — `get_mailbox_stats`, `get_dag_health`

## Adding New Code

### New Exchange Tool
1. Add `types.Tool(...)` to `TOOL_DEFINITIONS` in `exchange_mcp/tools.py`
2. Add async handler function `async def _handle_{name}(args, client)`
3. Add entry to `TOOL_DISPATCH` dict
4. Add tests in `tests/test_tools_{category}.py`

### New Chat Route
1. Create blueprint or add to existing in `chat_app/`
2. Register in `chat_app/app.py:create_app()`
3. Apply `@login_required` decorator

### New Config Value
1. Add class attribute in `chat_app/config.py:Config`
2. Add override in `Config.update_from_secrets()` if secret-sourced
