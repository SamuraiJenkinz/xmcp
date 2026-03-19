# Architecture Patterns

**Project:** Exchange Infrastructure MCP Server + Python Chat App
**Researched:** 2026-03-19
**Confidence:** HIGH (all patterns verified against official documentation)

---

## Recommended Architecture

This system is four cooperating processes on a single domain-joined Windows server. There is no distributed deployment in v1.

```
Browser (MMC Internal Network / VPN)
    |
    | HTTPS
    v
+----------------------------------+
|  Chat Application  (app.py)      |  Flask/FastAPI + Jinja2
|  - Azure AD OIDC login           |  Port 5000/5001
|  - Conversation management       |  MSAL ConfidentialClientApplication
|  - Azure OpenAI tool-call loop   |
|  - SSE/streaming responses       |
|  - Session token store           |
+-----------------+----------------+
                  |
                  | In-process (direct Python import)
                  | OR subprocess/IPC (if isolated)
                  v
+----------------------------------+
|  MCP Client Layer  (in app.py)   |  mcp Python SDK (Tier 1)
|  - Spawn server.py via stdio     |
|  - tools/list on startup         |
|  - tools/call per turn           |
+-----------------+----------------+
                  |
                  | JSON-RPC 2.0 over stdio
                  v
+----------------------------------+
|  MCP Server  (server.py)         |  FastMCP (mcp[cli] >= 1.2.0)
|  - Tool registry (15 tools)      |
|  - Input schema validation       |
|  - Dispatch to exchange_client   |
|  - Error mapping                 |
+-----------------+----------------+
                  |
                  | Python function calls (direct import)
                  v
+----------------------------------+
|  Exchange Client (exchange_cl.)  |  asyncio + subprocess
|  - Build PowerShell scripts      |
|  - asyncio.create_subprocess_exec|
|  - New-PSSession per call        |
|  - Kerberos Negotiate auth       |
|  - Parse JSON output             |
|  - DNS lookups (dnspython)       |
+----------------------------------+
                  |
                  | WS-MAN / PowerShell Remoting (port 5985/5986)
                  v
+----------------------------------+
|  Exchange 2019 Management Shell  |
|  (Exchange Server FQDN)          |
+----------------------------------+
```

---

## Component Boundaries

### Component 1: Chat Application (app.py)

**Responsibility:** User-facing HTTP server. Owns authentication, conversation storage, and the Azure OpenAI interaction loop. Orchestrates the MCP client.

**Communicates with:**
- Browser: HTTP/HTTPS (Jinja2 templates + HTMX or fetch for streaming)
- Azure AD / Entra ID: OIDC redirect flow (login.microsoftonline.com)
- Azure OpenAI endpoint: HTTPS (openai Python SDK)
- MCP Server: stdio pipe (spawns server.py as subprocess, uses mcp SDK client)
- Database / file store: local SQLite or JSON files for conversation persistence

**Does NOT:**
- Execute PowerShell directly
- Know about Exchange topology
- Hold user credentials

**Key state owned:**
- Flask session or JWT cookie (user identity, access token)
- MSAL token cache (per-user, encrypted)
- Conversation threads (messages list per conversation_id)

---

### Component 2: MCP Server (server.py)

**Responsibility:** Protocol boundary. Exposes Exchange tools to any MCP-compatible client. Does not contain business logic — it validates input schemas and delegates to the exchange client.

**Communicates with:**
- MCP Client (app.py): JSON-RPC 2.0 over stdio
- Exchange Client: direct Python function calls (same process)

**Does NOT:**
- Authenticate users (no session, no tokens)
- Know about Azure AD
- Store state between calls

**Transport:** stdio only (v1). The server runs as a child process of app.py. Stdout is the JSON-RPC channel — never use print() to stdout in this process.

**Tool registration pattern (FastMCP):**

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("exchange-mcp")

@mcp.tool()
async def get_mailbox_statistics(alias: str) -> str:
    """Get mailbox size, item count, and last logon for a mailbox.

    Args:
        alias: The mailbox alias or email address
    """
    return await exchange_client.get_mailbox_statistics(alias)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

FastMCP generates the `inputSchema` JSON Schema automatically from Python type hints and docstrings. The `description` field of the docstring becomes the tool description visible to the LLM.

**Error handling:**
- Protocol errors (unknown tool, malformed arguments) → JSON-RPC error object, code -32602
- Execution errors (PowerShell failure, timeout) → tool result with `isError: true` and descriptive text
- Never raise unhandled exceptions — catch at the `@mcp.tool` level and return `isError: true`

---

### Component 3: Exchange Client (exchange_client.py)

**Responsibility:** The only component that touches Exchange. Builds PowerShell command strings, spawns subprocesses, manages session lifecycle, and parses output.

**Communicates with:**
- MCP Server: direct Python function calls (caller)
- Exchange Server: WS-MAN over port 5985/5986 (via PowerShell remoting)
- DNS: dnspython for DMARC/SPF/DKIM lookups (direct)
- Windows Credential Manager or environment: for service account credentials (if needed for session bootstrap)

**Session model (per-call, no pooling):**

```
For each tool invocation:
  1. Build inline PowerShell script block:
       $session = New-PSSession -ConfigurationName Microsoft.Exchange
                  -ConnectionUri "http://<exchserver>/PowerShell/"
                  -Authentication Negotiate
       Import-PSSession $session -DisableNameChecking | Out-Null
       <cmdlet invocation with ConvertTo-Json output>
       Remove-PSSession $session

  2. asyncio.create_subprocess_exec("powershell.exe", "-Command", script)
  3. Await with asyncio.wait_for(proc.communicate(), timeout=30)
  4. Parse stdout as JSON
  5. Return structured dict to MCP server
```

**Kerberos context:** Because the Windows server is domain-joined and the chat app runs as (or impersonates) the logged-in user's identity, `Authentication Negotiate` in New-PSSession triggers Kerberos ticket acquisition from the domain controller. The Kerberos Service Ticket is issued to the Exchange HTTP service SPN (http/<exchserver>). This requires the service account (or impersonated user) to have the Exchange RBAC roles listed in constraints.

**DNS tools:** Direct calls via `dns.resolver.resolve()` for MX/TXT/DMARC records. No subprocess needed for these — pure Python.

**Critical constraint:** `asyncio.create_subprocess_exec` on Windows requires the event loop to be `ProactorEventLoop` (which is the default on Python 3.8+ Windows). Flask's development server does not use asyncio — PowerShell subprocess calls must be run via `asyncio.run()` or in a thread pool if the web framework is synchronous (Flask). FastAPI is async-native and is the preferred choice for this reason.

---

### Component 4: Azure OpenAI Integration (inside app.py)

**Responsibility:** Manages the multi-turn conversation loop with Azure OpenAI, including tool calling. This is not a separate process — it is the core logic function of app.py.

**Pattern:** Chat Completions API with `tools` parameter (not Assistants API).

```
Turn flow:
  1. User submits message
  2. app.py appends to messages list: {role: "user", content: "..."}
  3. First API call:
       response = client.chat.completions.create(
           model=deployment_name,
           messages=messages,
           tools=mcp_tools_as_openai_format,
           tool_choice="auto"
       )
  4. If response.choices[0].message.tool_calls:
       For each tool_call:
         a. Extract tool name + JSON arguments
         b. Route to MCP client → MCP server → Exchange client
         c. Get result string
         d. Append to messages: {role: "tool", tool_call_id: id, content: result}
  5. Second API call (same messages + tool results)
  6. Stream final response to browser via SSE
  7. Append assistant message to conversation history
```

**Tool format translation:** MCP tools (JSON Schema `inputSchema`) map directly to OpenAI `tools` format. The `name`, `description`, and `parameters` (the `inputSchema`) are identical in structure. The chat app builds the `tools` array once at startup from the `tools/list` response.

**Token management:** gpt-4o-mini-128k has a 128K context window. For Exchange queries (structured data responses), typical tool results are 1-5KB. Token pressure becomes a concern after approximately 50+ conversation turns or very large mailbox enumeration outputs. Mitigation: summarize or truncate tool results before appending to the messages list.

**Streaming:** Use `stream=True` in the completions request. Yield SSE chunks to the browser. Tool calls must be assembled from stream chunks before they can be dispatched — buffer the stream until `finish_reason == "tool_calls"` before executing tools.

---

## Data Flow

### Conversation Turn (Happy Path)

```
Browser
  --[POST /chat/message]--> app.py
                              |
                              +--> MSAL token cache check (is user authenticated?)
                              |
                              +--> Build messages list
                              |
                              +--> AzureOpenAI.chat.completions.create(tools=[...])
                              |       |
                              |       v
                              |    Azure OpenAI (stg1 MMC endpoint)
                              |       |
                              |    Response: tool_calls=["get_mailbox_stats"]
                              |       |
                              +--> MCP ClientSession.call_tool("get_mailbox_statistics", {alias: "jdoe"})
                              |       |
                              |     [JSON-RPC over stdio pipe]
                              |       |
                              |    server.py: dispatch to exchange_client.get_mailbox_statistics("jdoe")
                              |       |
                              |    exchange_client.py:
                              |       +--> Build PS script (New-PSSession + Get-MailboxStatistics | ConvertTo-Json)
                              |       +--> asyncio.create_subprocess_exec("powershell.exe", ...)
                              |       +--> [Kerberos ticket → Exchange WS-MAN]
                              |       +--> Exchange 2019 Management Shell executes cmdlet
                              |       +--> Returns JSON stdout
                              |       +--> Parse + return dict
                              |       |
                              |    server.py: return tool result {content: [{type: "text", text: "..."}]}
                              |       |
                              |     [JSON-RPC response over stdio]
                              |       |
                              +--> Append tool result to messages
                              |
                              +--> AzureOpenAI.chat.completions.create(messages + tool results, stream=True)
                              |       |
                              |    [Stream chunks]
                              |       |
  <--[SSE stream]------------- app.py yields chunks to browser
```

### Authentication Flow (First Login)

```
Browser
  --[GET /]--> app.py (no session) --> redirect to /auth/login
  --[GET /auth/login]--> app.py
    --> MSAL.initiate_auth_code_flow(scopes=[...], redirect_uri=...)
    --> store flow in session
    --> redirect to login.microsoftonline.com/tenantId/oauth2/v2.0/authorize

  Azure AD login page
    --> user authenticates (password + MFA)
    --> redirect to /auth/callback?code=...&state=...

  --[GET /auth/callback]--> app.py
    --> MSAL.acquire_token_by_auth_code_flow(session["flow"], request.args)
    --> cache token in session (encrypted)
    --> extract UPN from id_token claims
    --> redirect to /

  Subsequent requests:
    --> check session for valid token
    --> MSAL.acquire_token_silent() (uses refresh token if access token expired)
```

### Identity Pass-Through to Exchange

```
app.py runs on domain-joined Windows server
  |
  The Windows service account (or user context) under which app.py runs
  must be configured for Kerberos Constrained Delegation (KCD):

  Option A: Service account delegation
    - app.py runs as a dedicated service account (e.g., svc-xmcp)
    - svc-xmcp is configured with KCD to Exchange HTTP SPNs
    - When spawning powershell.exe, it inherits svc-xmcp context
    - New-PSSession -Authentication Negotiate → Kerberos as svc-xmcp
    - Exchange sees svc-xmcp identity (audit trail shows service account)

  Option B: True per-user delegation (complex, v2 consideration)
    - Requires Azure AD app configured for OBO flow
    - App acquires Kerberos token on behalf of user via S4U2Proxy
    - Passes user identity all the way to Exchange shell
    - Exchange audit log shows actual colleague UPN

  For v1: Option A is simpler and achievable. The UPN of the logged-in
  user is logged in the app's own audit log even if Exchange sees the
  service account. Full S4U2Proxy delegation is a v2 enhancement.
```

---

## Suggested Build Order

Dependencies determine sequence. Build from the bottom up.

### Layer 0: Foundation (no dependencies)
Build first because everything depends on it.

1. **Project scaffold** — directory structure, pyproject.toml/requirements.txt, .env pattern, config.py
2. **Exchange client skeleton** — async PowerShell subprocess runner with a single test cmdlet (Get-ExchangeServer). Validate Kerberos auth, JSON output parsing, timeout handling.
3. **DNS utilities** — dnspython resolver functions. Zero dependencies on other components.

### Layer 1: MCP Server (depends on Exchange client)
Build second because the chat app needs it to enumerate tools.

4. **MCP server** — FastMCP server with all 15 tools registered. Each tool wraps the corresponding exchange_client function. Validate with `mcp dev server.py` or the MCP Inspector before integrating with the chat app.
5. **Tool schemas** — Verify all 15 tool `inputSchema` definitions are accurate and descriptions are LLM-friendly.

### Layer 2: Chat Application Core (depends on MCP server)
Build third, iteratively.

6. **Flask/FastAPI skeleton** — basic routing, Jinja2 templates, health check endpoint
7. **Azure AD auth** — MSAL ConfidentialClientApplication, auth code flow, session management, /auth/login + /auth/callback routes
8. **Azure OpenAI integration** — basic chat completions without tool calling (verify connectivity to MMC stg1 endpoint)
9. **MCP client integration** — spawn server.py on app startup, tools/list, inject tools into OpenAI requests
10. **Tool calling loop** — detect tool_calls in response, route to MCP server, append results, make second call
11. **Streaming** — SSE streaming of final response to browser

### Layer 3: UI and Polish (depends on chat app core)
Build last.

12. **Conversation persistence** — SQLite or JSON file store for multi-session history
13. **Sidebar navigation** — multiple conversation threads
14. **Tool visibility** — display which tool was invoked and the raw result
15. **Export/copy** — response export functionality

---

## Key Interfaces Between Components

### Interface 1: MCP stdio transport (app.py ↔ server.py)

**Protocol:** JSON-RPC 2.0 over stdin/stdout pipe
**Client-side:** `mcp.ClientSession` + `mcp.client.stdio.stdio_client()`
**Server-side:** `mcp.run(transport="stdio")`
**Critical rule:** Nothing in server.py may write to stdout except the MCP SDK. All logging must go to stderr or a file.

```python
# app.py startup pattern
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def start_mcp_client():
    async with stdio_client(
        StdioServerParameters(command="python", args=["server.py"])
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            # store tools for OpenAI format conversion
```

### Interface 2: Exchange client (server.py ↔ exchange_client.py)

**Protocol:** Direct async Python function calls
**Signature pattern:** `async def get_mailbox_statistics(alias: str) -> dict`
**Returns:** structured dict (parsed from PowerShell JSON output) or raises a typed exception
**Error contract:** Exchange client raises `ExchangeError(message, exit_code)` on failure. MCP server catches this and returns `isError: true`.

### Interface 3: Azure OpenAI tools (app.py ↔ Azure OpenAI)

**Protocol:** HTTPS / openai SDK `chat.completions.create()`
**Tools format:** OpenAI function schema derived from MCP `tools/list` response:
```python
def mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema  # already JSON Schema format
        }
    }
```

### Interface 4: PowerShell subprocess (exchange_client.py ↔ Windows)

**Protocol:** asyncio subprocess via `asyncio.create_subprocess_exec`
**Output contract:** PowerShell script must emit exactly one JSON object to stdout. Errors go to stderr. Exit code 0 = success.
**Script pattern:**
```powershell
try {
    $session = New-PSSession -ConfigurationName Microsoft.Exchange `
        -ConnectionUri "http://exchserver.domain.local/PowerShell/" `
        -Authentication Negotiate -ErrorAction Stop
    Import-PSSession $session -DisableNameChecking | Out-Null
    $result = Get-MailboxStatistics -Identity $alias |
        Select-Object DisplayName, TotalItemSize, ItemCount, LastLogonTime |
        ConvertTo-Json -Compress
    Write-Output $result
    Remove-PSSession $session
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
```

### Interface 5: Azure AD / MSAL (app.py ↔ login.microsoftonline.com)

**Protocol:** OIDC authorization code flow via MSAL Python `ConfidentialClientApplication`
**Scopes required:** `openid`, `profile`, `email`, `offline_access` (for token refresh)
**Token storage:** MSAL in-memory cache per session (keyed by user sub claim). For multi-process deployments, use `msal.SerializableTokenCache` persisted to encrypted session store.

---

## Architecture Patterns to Follow

### Pattern 1: Stateless MCP server

The MCP server has zero state between calls. All state lives in the chat application (conversation history, user session) or in Exchange (the authoritative data source). This makes the MCP server restartable without data loss and testable in isolation.

### Pattern 2: Tool result as text, not structured data

MCP tool results return `{type: "text", text: "..."}`. Format Exchange output as human-readable text (not raw JSON) in the tool result — the LLM will parse it into a natural language response. For large outputs, summarize or paginate at the Exchange client level. Keep tool results under 8KB.

### Pattern 3: Fail loud at the Exchange boundary

When PowerShell fails (cmdlet error, auth failure, timeout), return a descriptive error message that the LLM can relay to the user. "Failed to retrieve mailbox statistics: Access denied for alias jdoe (exit code 1)" is useful. Swallowing errors produces confused LLM responses.

### Pattern 4: Single-process MCP for v1

In v1, run the MCP server as a subprocess of the chat app (stdio transport). Do not build an HTTP MCP server. This eliminates network configuration, TLS setup, and multi-client complexity. If the chat app needs to scale to multiple workers in v2, revisit with Streamable HTTP transport.

### Pattern 5: Conversation messages list as the source of truth

Never store Azure OpenAI responses in a separate format. The `messages` list (with role, content, tool_call_id entries) is the canonical conversation representation. Persist this list verbatim to the database. Reload it verbatim when resuming a conversation. This guarantees correct multi-turn context.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Persistent PSSession pooling

**What:** Creating a pool of long-lived Exchange PSSession objects, reused across tool calls.
**Why bad:** PSSession expiration (Exchange default: 15 minutes idle) causes silent failures. Session state accumulates (imported modules, variables). Auth token expiry breaks pool silently. Session leaks are hard to detect.
**Instead:** Per-call sessions as specified in constraints. Accept the ~2-3 second overhead. Optimize by caching the session within a single MCP tool call that needs multiple cmdlets.

### Anti-Pattern 2: Writing to stdout in server.py

**What:** Using `print()` or `logging.StreamHandler(sys.stdout)` in the MCP server process.
**Why bad:** Corrupts the JSON-RPC framing. The MCP client will receive malformed data and crash or hang.
**Instead:** All logging in server.py goes to `sys.stderr` or a file handler. `print(..., file=sys.stderr)` is safe.

### Anti-Pattern 3: Putting Azure OpenAI tool-call logic in the MCP server

**What:** The MCP server calling Azure OpenAI directly to orchestrate multi-tool workflows.
**Why bad:** The MCP server is a protocol boundary, not an orchestrator. It should be dumb. Complex logic in server.py makes it untestable and coupled to the AI provider.
**Instead:** All OpenAI interaction lives in app.py. The MCP server only validates input, calls exchange_client, and returns results.

### Anti-Pattern 4: Streaming Exchange output through the subprocess as it arrives

**What:** Using stdout streaming from PowerShell to get partial results.
**Why bad:** PowerShell's ConvertTo-Json only emits complete objects. Partial JSON is unparseable. Exchange cmdlets buffer internally anyway.
**Instead:** Buffer all PowerShell stdout and parse as a complete JSON document after the process exits.

### Anti-Pattern 5: Storing credentials in the MCP server or Exchange client

**What:** Hardcoding Exchange credentials or API keys in server.py or exchange_client.py.
**Why bad:** Credential exposure via code review, logs, or error messages. Violates MMC security policy.
**Instead:** Azure OpenAI API key from AWS Secrets Manager at app startup. Exchange authentication via Kerberos (no password needed when running in correct domain context).

### Anti-Pattern 6: Using Flask's synchronous context with asyncio subprocesses naively

**What:** Calling `asyncio.run()` inside a Flask route handler that is already in a synchronous thread.
**Why bad:** On Python 3.10+, `asyncio.run()` in a thread that already has a running event loop raises `RuntimeError`. Flask's dev server is synchronous.
**Instead:** Either use FastAPI (async-native, recommended) or use `concurrent.futures.ThreadPoolExecutor` with `loop.run_in_executor()` for the async subprocess calls if staying with Flask.

---

## Scalability Considerations

This is an internal tool with limited concurrency requirements. These are directional notes, not v1 requirements.

| Concern | At 10 concurrent users | At 100 concurrent users | At 1000 concurrent users |
|---------|----------------------|------------------------|-------------------------|
| PowerShell subprocesses | Fine (10 parallel PS processes) | Process limit risk; consider pooling | Requires session pooling or distributed deployment |
| Azure OpenAI latency | Acceptable (1-5s/turn) | Queue depth may build; add per-user rate limiting | Requires async queue + worker pool |
| Exchange WS-MAN connections | Fine | Monitor throttling (EMS default: 18 max sessions per user) | Requires service account with elevated throttling policy |
| Conversation storage | In-memory or file store fine | SQLite fine | Migrate to PostgreSQL |
| MCP server instances | One per app process | One per app worker | One per app worker (no state to share) |

---

## Confidence Assessment

| Area | Confidence | Source |
|------|------------|--------|
| MCP stdio transport + FastMCP patterns | HIGH | Official MCP docs (modelcontextprotocol.io), verified 2026-03-19 |
| Azure OpenAI tool calling (chat completions) | HIGH | Official Microsoft Learn docs, verified 2026-03-19 |
| MSAL Python auth code flow | HIGH | Official MSAL Python docs + Microsoft identity platform docs, verified 2026-03-19 |
| OAuth 2.0 OBO flow mechanics | HIGH | Official Microsoft identity platform docs, verified 2026-03-19 |
| PSSession per-call pattern for Exchange | HIGH | Official Exchange + PowerShell docs |
| asyncio subprocess on Windows (ProactorEventLoop) | MEDIUM | Python 3.11 docs + known Windows asyncio behavior (training knowledge, consistent with docs) |
| Kerberos KCD for identity pass-through | MEDIUM | Azure AD Seamless SSO docs describe the Kerberos ticket flow; true S4U2Proxy delegation for this pattern is documented but implementation-specific to MMC AD config |
| gpt-4o-mini tool calling parallel support | HIGH | Azure OpenAI function calling docs confirm gpt-4o-mini (2024-07-18) supports parallel function calls |

---

## Sources

- MCP Architecture: https://modelcontextprotocol.io/docs/concepts/architecture (verified 2026-03-19)
- MCP Tools: https://modelcontextprotocol.io/docs/concepts/tools (verified 2026-03-19)
- MCP Python Server quickstart: https://modelcontextprotocol.io/docs/develop/build-server (verified 2026-03-19)
- Azure OpenAI Function Calling: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/function-calling (verified 2026-03-19)
- OAuth 2.0 OBO Flow: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow (verified 2026-03-19)
- Azure AD Seamless SSO / Kerberos: https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-sso-how-it-works (verified 2026-03-19)
- MSAL Python: https://learn.microsoft.com/en-us/entra/msal/python/ (verified 2026-03-19)
- Exchange Management Tools: https://learn.microsoft.com/en-us/exchange/plan-and-deploy/post-installation-tasks/install-management-tools (verified 2026-03-19)
