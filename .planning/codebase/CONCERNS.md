# Concerns

## Technical Debt

### Monolithic tools.py (1,875 lines)
- `exchange_mcp/tools.py` contains all 15 tool definitions AND all handler implementations in a single file
- Adding new tools increases file size linearly — no module splitting
- Refactoring to `tools/{category}.py` would improve maintainability

### Unbounded DNS Cache
- `exchange_mcp/dns_utils.py:_cache` is a module-level dict with TTL-based expiry
- Entries are only evicted on access (lazy eviction) — no periodic sweep
- Under sustained diverse queries, memory grows without bound
- No cache size limit configured

### Duplicated Error Classification
- Both `exchange_mcp/server.py` and `exchange_mcp/exchange_client.py` maintain separate pattern lists for transient vs non-transient errors
- `_TRANSIENT_PATTERNS` / `_NON_TRANSIENT_PATTERNS` in server.py
- `_NON_RETRYABLE_PATTERNS` in exchange_client.py
- These lists could drift out of sync

### Tool Events Not Persisted
- Tool call results (name, params, status, result JSON) are only sent as SSE events
- Not stored in SQLite `messages_json` column
- Historical conversations lose tool visibility panels on reload
- Noted in STATE.md as known tech debt

### Copy Button Missing on Historical Messages
- Copy-to-clipboard button only renders on new SSE-streamed messages
- Historical messages loaded from SQLite don't get the button
- Noted in STATE.md as known tech debt

## Security Concerns

### CHATGPT_ENDPOINT Not in Secrets Pipeline
- Must be set as bare environment variable, not through AWS Secrets Manager
- Noted in STATE.md as operational concern

### Hardcoded Default Secret Key
- `chat_app/config.py`: `SECRET_KEY = "dev-secret-change-in-prod"`
- Falls through to insecure default if FLASK_SECRET_KEY env var not set
- Should fail loudly in production rather than use default

### PowerShell Injection Surface
- `exchange_mcp/exchange_client.py` builds PowerShell scripts from templates with string interpolation
- Tool handlers in `tools.py` insert user-provided arguments into PS scripts
- Input validation exists but relies on pattern matching — no strict allow-listing
- The `-EncodedCommand` approach prevents shell metacharacter injection but not PS injection within the script body

### No Rate Limiting
- MCP server has no request rate limiting
- Chat app has no per-user rate limiting on `/chat/stream`
- Could lead to excessive Exchange/OpenAI API consumption

## Performance Concerns

### Sequential PowerShell Execution
- Each Exchange tool call spawns a new `powershell.exe` process
- Connect-ExchangeOnline runs per call (no session pooling)
- Typical latency: 2-4 seconds per tool call
- Multi-tool conversations can accumulate 7-15+ seconds of PS overhead

### Single-Process MCP Server
- MCP stdio server handles one request at a time (JSON-RPC over stdio is serial)
- `chat_app/mcp_client.py` uses `threading.Lock` to enforce this
- Adequate for <100 users but blocks concurrent tool calls

### Token Counting on Every Message
- `context_mgr.py` counts tokens for the full conversation on every request
- Uses tiktoken (o200k_base) which is CPU-bound
- Could become a bottleneck with very long conversations

## Fragile Areas

### PowerShell JSON Output Parsing
- Exchange cmdlets return inconsistent JSON structures (single object vs array)
- `exchange_client.py` normalizes via `json.loads()` but edge cases exist
- A cmdlet returning unexpected format causes `json.JSONDecodeError`

### Error String Pattern Matching
- Both server.py and exchange_client.py classify errors by substring matching
- New error messages from Exchange Online could be misclassified
- No structured error codes from PowerShell — only free-text stderr

### MCP Client Daemon Thread
- `chat_app/mcp_client.py` runs async MCP session on a daemon thread
- Thread + event loop lifecycle is fragile — process crash during init can leave orphaned subprocess
- No health check or reconnection logic for the MCP subprocess

## Missing Capabilities

- **No request/response logging**: No audit trail of which user invoked which tool
- **No retry quota management**: Exponential backoff has no circuit breaker
- **No structured error types**: All errors are RuntimeError with string messages
- **No health endpoint**: No `/health` or `/status` route for monitoring
- **No graceful shutdown**: No signal handling for clean MCP subprocess termination in chat app

## Test Coverage Gaps

- **Entire chat_app/ is untested** — no Flask route tests, no SSE tests, no auth tests
- **No database tests** — SQLite schema, CRUD operations, concurrent access
- **No frontend tests** — JavaScript functionality untested
- **No end-to-end tests** — full user flow never exercised in test suite
- **Error path coverage**: Many Exchange error scenarios in tools.py lack dedicated tests
