# Atlas Administration Guide

This guide covers the internal architecture, tool reference, database management, monitoring, security model, and operational procedures for the Atlas Exchange Infrastructure MCP Server.

## System Architecture

Atlas consists of three main components:

1. **MCP Server** (`exchange_mcp/`) — a Model Context Protocol server that exposes 17 tools (15 Exchange infrastructure + 2 colleague lookup) over stdio JSON-RPC. It manages PowerShell subprocess execution, Microsoft Graph API calls, and DNS lookups.

2. **Chat Application** (`chat_app/`) — a Flask web application that provides Azure AD authentication, Azure OpenAI integration, conversation persistence, and serves the React frontend.

3. **React Frontend** (`frontend/`) — a React 19 SPA built with Vite, Fluent UI v9, and Tailwind v4. Produces a static bundle in `frontend_dist/` that Flask serves via a catch-all route.

The chat app spawns the MCP server as a child process at startup. They communicate over stdin/stdout using the MCP stdio transport protocol. A `threading.Lock` serializes all MCP calls (one tool invocation at a time).

```
React SPA (frontend_dist/) ──HTTP──> Flask App ──stdio──> MCP Server ──subprocess──> powershell.exe ──> Exchange Online
    |                                    |                    |
    |                                    |                    +──> dnspython ──> DNS (DMARC/SPF/DKIM)
    |                                    |                    +──> graph_client ──> Microsoft Graph API
    |                                    |
    |                                    +──> Azure AD (MSAL auth code flow)
    |                                    +──> Azure OpenAI (tool-calling loop)
    |                                    +──> SQLite (conversation persistence)
    |
    +──> /api/me, /api/threads, /api/photo ──> Flask API routes
    +──> /chat/stream ──> Flask SSE endpoint
    +──> /auth/* ──> Flask auth routes
```

### Frontend Architecture

The React frontend uses a **hybrid SPA pattern** controlled by the `ATLAS_UI` environment variable:

| `ATLAS_UI` Value | Behavior |
|------------------|----------|
| `react` (recommended) | Flask serves pre-built React SPA from `frontend_dist/` |
| `classic` (default) | Flask serves Jinja2 templates (legacy vanilla JS UI) |

The React app includes:
- **Fluent UI v9** (`@fluentui/react-components`) for the FluentProvider and theme system
- **Tailwind v4** for utility CSS with `tw:` prefix
- **62 `--atlas-` CSS custom properties** for the design token system
- **Three-tier surface hierarchy** matching Microsoft Fluent 2 webDarkTheme

Key frontend files:
- `frontend/src/App.tsx` — root component with provider nesting and theme management
- `frontend/src/contexts/` — AuthContext, ThreadContext, ChatContext (React Context + useReducer)
- `frontend/src/hooks/useStreamingMessage.ts` — SSE streaming with fetch + ReadableStream
- `frontend/src/styles/atlas-tokens.css` — all 62 design tokens
- `frontend/src/styles/components.css` — component styles using `@layer components`

## Tool Reference

### Tool Inventory

All 17 tools are read-only. No tool can create, modify, or delete Exchange objects or Azure AD data.

| # | Tool | Category | Source | Auth Required |
|---|------|----------|--------|---------------|
| 1 | `ping` | Connectivity | Direct | No |
| 2 | `get_mailbox_stats` | Mailbox | Exchange cmdlets | Yes |
| 3 | `search_mailboxes` | Mailbox | Exchange cmdlets | Yes |
| 4 | `get_shared_mailbox_owners` | Mailbox | Exchange cmdlets | Yes |
| 5 | `list_dag_members` | DAG | Exchange cmdlets | Yes |
| 6 | `get_dag_health` | DAG | Exchange cmdlets | Yes |
| 7 | `get_database_copies` | DAG | Exchange cmdlets | Yes |
| 8 | `check_mail_flow` | Mail Flow | Exchange cmdlets | Yes |
| 9 | `get_transport_queues` | Mail Flow | Exchange cmdlets | Yes |
| 10 | `get_smtp_connectors` | Mail Flow | Exchange cmdlets | Yes |
| 11 | `get_dkim_config` | Security | Exchange + DNS | Yes |
| 12 | `get_dmarc_status` | Security | DNS only | No |
| 13 | `check_mobile_devices` | Security | Exchange cmdlets | Yes |
| 14 | `get_hybrid_config` | Hybrid | Exchange cmdlets | Yes |
| 15 | `get_connector_status` | Hybrid | Exchange cmdlets | Yes |
| 16 | `search_colleagues` | Colleague | Microsoft Graph | Yes (app) |
| 17 | `get_colleague_profile` | Colleague | Microsoft Graph | Yes (app) |

### Tool Parameters

#### get_mailbox_stats

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_address` | string | Yes | UPN or email address of the mailbox |

#### search_mailboxes

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filter_type` | string | Yes | One of: `database`, `type`, `name` |
| `filter_value` | string | Yes | Database name, mailbox type (e.g., `SharedMailbox`), or display name pattern |
| `max_results` | integer | No | Maximum results to return (default: 100) |

#### get_shared_mailbox_owners

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_address` | string | Yes | UPN or email address of the shared mailbox |

#### list_dag_members

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dag_name` | string | No | Name of the DAG. If omitted, returns all DAGs. |

#### get_dag_health

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dag_name` | string | Yes | Name of the DAG to check |

#### get_database_copies

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `database_name` | string | Yes | Name of the mailbox database |

#### check_mail_flow

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sender` | string | Yes | Sender email address |
| `recipient` | string | Yes | Recipient email address |

#### get_transport_queues

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `server_name` | string | No | Specific server to check (default: all servers) |
| `backlog_threshold` | integer | No | Message count threshold for backlog flagging (default: 100) |

#### get_smtp_connectors

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `connector_type` | string | No | One of: `send`, `receive`, `all` (default: `all`) |

#### get_dkim_config

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain` | string | No | Domain to check. If omitted, returns all domains. |

#### get_dmarc_status

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `domain` | string | Yes | Domain to check DMARC/SPF for |

#### check_mobile_devices

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_address` | string | Yes | UPN or email of the user whose devices to check |

#### search_colleagues

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Name (or partial name) to search for in Azure AD |

#### get_colleague_profile

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_id` | string | Yes | Microsoft Graph API object ID (GUID) from search_colleagues results |

#### get_hybrid_config, get_connector_status, ping

No parameters.

## Exchange Client Architecture

### PowerShell Execution Model

File: `exchange_mcp/ps_runner.py`

Every Exchange tool call follows this sequence:

1. Build a PowerShell script string with preamble (UTF-8 encoding, `$ErrorActionPreference = 'Stop'`)
2. Encode the script as Base64 UTF-16LE
3. Spawn `powershell.exe -NonInteractive -NoProfile -EncodedCommand <base64>`
4. Wait for completion with a 60-second timeout
5. On timeout: `proc.kill()` + `proc.wait()` (no orphaned processes)
6. Parse stdout as JSON; stderr is captured for error messages

### Session Lifecycle

File: `exchange_mcp/exchange_client.py`

Each tool call wraps the Exchange cmdlet in a PowerShell `try/catch/finally` block:

```powershell
try {
    Connect-ExchangeOnline ...
    # Run cmdlet
    $result | ConvertTo-Json -Depth 10
} catch {
    Write-Error $_.Exception.Message
} finally {
    Disconnect-ExchangeOnline -Confirm:$false
}
```

This ensures `Disconnect-ExchangeOnline` always runs, even on error. No persistent sessions are maintained.

### Retry Logic

File: `exchange_mcp/exchange_client.py` — `run_cmdlet_with_retry()`

- **Max retries:** 3
- **Backoff:** Exponential (1s, 2s, 4s)
- **Retryable patterns:** timeout, connection, network, throttling, unavailable, reset, socket
- **Non-retryable patterns** (immediate raise): authentication, access denied, AADSTS errors, not found, invalid input, certificate errors

### Auth Modes

| Mode | When | Mechanism |
|------|------|-----------|
| Interactive | `AZURE_CERT_THUMBPRINT` not set | Browser popup via `Connect-ExchangeOnline` |
| Certificate (CBA) | `AZURE_CERT_THUMBPRINT` set | `Connect-ExchangeOnline -CertificateThumbPrint -AppID -Organization` |

Auth mode is auto-detected at `ExchangeClient.__init__()`. Both modes use per-call sessions.

## Microsoft Graph Client

File: `exchange_mcp/graph_client.py`

### Authentication

Uses MSAL `ConfidentialClientApplication` with client credentials flow (application permissions). Token is cached at module level with automatic refresh.

### Endpoints Used

| Endpoint | Permission | Purpose |
|----------|-----------|---------|
| `GET /users?$search="displayName:{name}"` | User.Read.All | Colleague search |
| `GET /users/{id}` | User.Read.All | Colleague profile |
| `GET /users/{id}/photo/$value` | ProfilePhoto.Read.All | Colleague photo (via Flask proxy) |

### Photo Proxy

File: `chat_app/routes.py` — `/api/photo/<user_id>`

- Requires authentication (session check)
- TTL cache prevents repeated Graph API calls for the same photo
- Returns SVG placeholder with initials on 404 (no photo in Azure AD)
- Binary photo data never enters the LLM context

## Error Handling Chain

Errors flow through multiple layers with sanitization at each level:

```
PowerShell stderr
  -> ExchangeClient: raise RuntimeError(stderr)
    -> tools.py handler: raise RuntimeError(user_message)
      -> server.py _sanitize_error(): strip PS tracebacks, add retry hints
        -> MCP SDK: CallToolResult(isError=True, content=sanitized_message)
          -> chat_app openai_client: tool_events[status="error"]
            -> SSE: {"type": "tool", "status": "error", ...}
              -> React: "Error" badge on tool panel
```

**Sanitization rules** (`server.py:_sanitize_error()`):
- Strip everything after `stderr:` marker (removes raw PowerShell tracebacks)
- Remove `PowerShell exited with code N.` prefix
- Append "This may be a temporary issue — please try again." for transient errors
- No retry hint for authentication/input errors

## SSE Streaming Architecture

File: `chat_app/openai_client.py` — `run_tool_loop()`

The tool-calling loop is **blocking** — all tool calls complete before the SSE stream emits results. This means:

- Tool events include `start_time` and `end_time` (epoch float seconds from `time.time()`)
- The frontend calculates elapsed time from these timestamps
- There is no real-time "Running" state for tool panels (tools complete before the stream resumes)
- The Stop button works via `AbortController` on the fetch request in the React frontend

### SSE Event Types

| Event Type | Fields | Purpose |
|------------|--------|---------|
| `text` | `content` | Streaming text delta |
| `tool` | `name`, `args`, `result`, `status`, `start_time`, `end_time` | Tool invocation result |
| `done` | — | Stream complete |
| `error` | `message` | Error occurred |
| `cancel` | — | User cancelled stream |
| `thread_name` | `name`, `thread_id` | Auto-naming event |

## Database Management

### Schema

SQLite database with WAL mode and foreign keys enabled. Main tables:

- **threads** — one row per conversation thread (user_id, name, timestamps)
- **messages** — one row per thread containing the full message history as a JSON array
- **feedback** — per-message thumbs up/down votes with optional comment (added v1.3)
- **threads_fts** — FTS5 virtual table for full-text search across message content (added v1.3)

The `messages_json` field includes tool events (tool name, arguments, result, status, timestamps) so that historical messages retain their tool panels.

The `feedback` table has a UNIQUE constraint on `(thread_id, assistant_message_idx, user_id)`, CHECK on vote values ('up'/'down'), and ON DELETE CASCADE from threads. Two analytics indexes (`idx_feedback_user_vote`, `idx_feedback_thread`) support future reporting queries.

The `threads_fts` FTS5 virtual table is kept in sync via 3 triggers (AFTER INSERT, AFTER UPDATE, AFTER DELETE on messages). An idempotent backfill runs on every startup via `migrate_db()`.

### Schema Migrations

Starting with v1.3, `migrate_db()` runs inside the app context on every startup. It executes idempotent DDL (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `CREATE TRIGGER IF NOT EXISTS`) so existing databases gain new tables automatically. No manual migration steps are required.

### Database Location

Default: `chat.db` in the project root. Override with `CHAT_DB_PATH` environment variable.

### Auto-Bootstrap

The database is created automatically on first connection. No manual initialization is needed. The schema in `chat_app/schema.sql` is executed via `db.py:init_db()` when the database file does not exist.

### Manual Operations

```bash
# View all threads
uv run python -c "
import sqlite3
db = sqlite3.connect('chat.db')
db.row_factory = sqlite3.Row
for row in db.execute('SELECT id, user_id, name, created_at, updated_at FROM threads ORDER BY updated_at DESC'):
    print(dict(row))
"

# Count messages per user
uv run python -c "
import sqlite3
db = sqlite3.connect('chat.db')
for row in db.execute('SELECT user_id, COUNT(*) as threads FROM threads GROUP BY user_id'):
    print(row)
"

# Delete threads older than 90 days
uv run python -c "
import sqlite3
db = sqlite3.connect('chat.db')
db.execute(\"DELETE FROM threads WHERE updated_at < datetime('now', '-90 days')\")
db.commit()
print('Done')
"
```

### Backup

SQLite with WAL mode supports safe backup while the application is running:

```powershell
# Simple file copy (safe with WAL mode)
Copy-Item chat.db "chat.db.backup.$(Get-Date -Format yyyyMMdd)"

# Or use SQLite backup command
sqlite3 chat.db ".backup 'chat.db.backup'"
```

### Database Growth

Each conversation thread stores its entire message history as a JSON array in a single `messages_json` TEXT field. Database growth depends on usage:

- ~1 KB per short exchange (1 question + 1 answer)
- ~5-10 KB per exchange involving tool calls (tool results stored in messages)
- A typical user with 50 threads over a month: ~500 KB

For environments with many users, consider periodic cleanup of threads older than a configurable retention period.

## Monitoring

### Health Check Endpoint

```
GET /api/health
```

Returns:
```json
{
  "status": "ok",
  "mcp_connected": true,
  "tools_count": 17
}
```

Monitor this endpoint. Key indicators:
- `mcp_connected: false` — MCP subprocess crashed or failed to start
- `tools_count < 17` — Tool registration issue (expected: 15 Exchange + 2 Graph)

### Application Logs

All application logs go to **stderr**. The MCP server enforces strict stderr-only logging — stdout is reserved for JSON-RPC protocol messages.

To capture logs:

```powershell
# Console
uv run python -m chat_app.app 2>atlas.log

# Windows Service (NSSM)
nssm set AtlasExchangeMCP AppStderr "D:\atlas\logs\atlas.log"
nssm set AtlasExchangeMCP AppStderrCreationDisposition 4  # Append
```

### Key Log Patterns

| Pattern | Meaning | Action |
|---------|---------|--------|
| `Exchange connection verified` | MCP server started successfully | Normal |
| `Exchange error:` | Tool execution failed | Check error message for cause |
| `TimeoutError` | PowerShell command exceeded 60s | Exchange may be overloaded |
| `AADSTS` | Azure AD authentication error | Check credentials/certificate |
| `MCP init failed` | Chat app couldn't connect to MCP server | Check PowerShell/Exchange access |
| `Graph API error` | Microsoft Graph call failed | Check Graph API permissions and credentials |

### Performance Monitoring

Expected latencies:

| Operation | Expected | Investigate if |
|-----------|----------|---------------|
| Tool call (simple) | 2-4 seconds | > 10 seconds |
| Tool call (composite, e.g., get_hybrid_config) | 5-10 seconds | > 20 seconds |
| Colleague search | 1-2 seconds | > 5 seconds |
| SSE stream start | < 1 second | > 3 seconds |
| AI response generation | 1-3 seconds | > 10 seconds |
| Page load (React SPA) | < 500ms | > 2 seconds |
| Frontend build (npm run build) | 5-15 seconds | > 30 seconds |

## Security Model

### Read-Only Operations

All 15 Exchange tools are strictly read-only. The following PowerShell cmdlets are used — all are `Get-*` or `Test-*`:

- `Get-Mailbox`, `Get-MailboxStatistics`, `Get-MailboxPermission`, `Get-RecipientPermission`
- `Get-DatabaseAvailabilityGroup`, `Get-MailboxDatabaseCopyStatus`, `Get-MailboxDatabase`
- `Get-SendConnector`, `Get-ReceiveConnector`, `Get-TransportService`, `Get-Queue`
- `Get-DkimSigningConfig`, `Get-MobileDeviceStatistics`
- `Get-OrganizationRelationship`, `Get-FederationTrust`, `Get-IntraOrganizationConnector`
- `Get-AvailabilityAddressSpace`, `Get-ExchangeCertificate`, `Get-AcceptedDomain`
- `Get-OrganizationConfig` (startup validation only)

No `Set-*`, `New-*`, `Remove-*`, `Enable-*`, or `Disable-*` cmdlets are used.

The 2 colleague lookup tools use Microsoft Graph API `GET` requests only (read-only application permissions).

### No Free-Form PowerShell

The AI model cannot execute arbitrary PowerShell. All Exchange queries go through the MCP tool dispatch table, which maps tool names to specific handler functions. There is no mechanism for the AI to construct or inject PowerShell commands.

### Access Control (v1.3)

Atlas uses Azure AD **App Roles** for access gating. The `role_required` decorator on all 9 protected routes checks:

1. **Authentication** (401) — user has a valid session with `id_token_claims`
2. **Authorization** (403) — user's roles claim includes `Atlas.User`

Users who authenticate but lack the App Role see a Fluent 2 "Access Denied" page showing their UPN and a mailto link to the admin.

**Setup:** Create the `Atlas.User` App Role in Azure AD:
1. Go to **App registrations** > your Atlas app > **App roles**
2. Click **Create app role**:
   - Display name: `Atlas User`
   - Value: `Atlas.User`
   - Allowed member types: Users/Groups
   - Description: `Access to Atlas Exchange Infrastructure tool`
3. Go to **Enterprise applications** > your Atlas app > **Users and groups**
4. Click **Add user/group** and assign the IT engineers security group to the `Atlas.User` role

The `roles` claim is extracted from `id_token_claims` at login and stored in the session. `/api/me` returns the user's roles array for frontend introspection.

### Authentication Layers

| Layer | Mechanism | What it protects |
|-------|-----------|-----------------|
| User -> Chat App | Azure AD SSO (MSAL auth code flow) | Only authenticated MMC colleagues can access the chat |
| Chat App -> App Role | `role_required` decorator (Atlas.User) | Only authorized IT engineers can use Atlas features |
| Chat App -> User Data | `session["user"]["oid"]` ownership check | Users can only see their own threads |
| Chat App -> Exchange | Service account RBAC | Tool calls limited to assigned Exchange roles |
| Chat App -> Graph API | MSAL client credentials (application permissions) | Directory reads scoped to User.Read.All, ProfilePhoto.Read.All |
| Chat App -> Azure OpenAI | API key (from AWS Secrets Manager) | AI calls restricted to MMC corporate endpoint |
| Photo Proxy | Authenticated session required | Photos served only to logged-in users |

### Data Privacy

- **No email content access** — no tools read message bodies or attachments
- **Conversation isolation** — SQLite queries always filter by `user_id` (Azure AD OID)
- **No data exfiltration** — the AI is instructed to only answer Exchange questions and cannot be prompted to send data externally
- **Error sanitization** — PowerShell tracebacks are stripped before reaching users
- **Photo privacy** — colleague photos served through authenticated proxy; binary data never enters AI context

### Secret Management

| Secret | Storage | Never |
|--------|---------|-------|
| Azure AD client secret | AWS Secrets Manager or `.env` | Committed to git |
| Azure OpenAI API key | AWS Secrets Manager or `.env` | Committed to git |
| Flask secret key | AWS Secrets Manager or `.env` | Left as default in production |
| Certificate thumbprint | Environment variable | Committed to git |

### Session Security

- Server-side filesystem sessions (not client-side cookies)
- Session signed with `FLASK_SECRET_KEY`
- MSAL token cache serialized per-user in session
- Conditional Access `interaction_required` errors redirect to `/login` (forces re-auth)

## Operational Procedures

### Certificate Rotation (CBA Mode)

1. Generate new certificate
2. Upload public key to Azure AD app registration
3. Update `AZURE_CERT_THUMBPRINT` environment variable
4. Restart Atlas service
5. Remove old certificate from Azure AD after confirming new one works

### Client Secret Rotation

1. Create new secret in Azure AD app registration
2. Update `AZURE_CLIENT_SECRET` in AWS Secrets Manager (or `.env`)
3. Restart Atlas service
4. Delete old secret from Azure AD

### Frontend Updates

The pre-built React frontend is committed to the repository under `frontend_dist/`. Production servers receive frontend updates via `git pull` — no Node.js or npm required.

For developers modifying the frontend source (`frontend/src/`):

```bash
cd frontend
npm install    # If package.json changed
npm run build  # Rebuild to frontend_dist/
# Commit the updated frontend_dist/ to the repo
# Restart Flask — it serves the new bundle immediately
```

### Adding Exchange RBAC Roles

If new tools are added in future versions that require additional Exchange roles:

```powershell
# Check current assignments
Get-ManagementRoleAssignment -RoleAssignee "svc-exchange-mcp"

# Add new role
New-ManagementRoleAssignment -Role "New-Role-Name" -User "svc-exchange-mcp"
```

### Database Maintenance

```powershell
# Check database size
Get-Item chat.db | Select-Object Length

# Vacuum (reclaim space after deletions)
sqlite3 chat.db "VACUUM;"

# Check integrity
sqlite3 chat.db "PRAGMA integrity_check;"
```

### MCP Server Standalone Testing

The MCP server can be tested independently of the chat app:

```powershell
# Start MCP dev inspector
uv run mcp dev exchange_mcp/server.py

# This opens a web-based inspector where you can:
# - See all registered tools
# - Call tools with custom parameters
# - Inspect JSON results
```

### Switching Between Classic and React UI

```powershell
# React frontend (recommended for v1.2+)
$env:ATLAS_UI = "react"

# Classic Jinja2 templates (legacy)
$env:ATLAS_UI = "classic"
# or remove the variable (defaults to classic)
Remove-Item Env:\ATLAS_UI
```

Both modes use the same Flask backend, database, and MCP server. Only the frontend rendering differs.

### Feedback Data (v1.3)

The `feedback` table stores per-message thumbs up/down votes. Useful queries for analytics:

```sql
-- Vote summary
SELECT vote, COUNT(*) FROM feedback GROUP BY vote;

-- Recent feedback with comments
SELECT f.vote, f.comment, f.created_at, t.name as thread_name
FROM feedback f JOIN threads t ON f.thread_id = t.id
WHERE f.comment IS NOT NULL
ORDER BY f.created_at DESC LIMIT 20;

-- Feedback per user
SELECT user_id, COUNT(*) as votes, SUM(CASE WHEN vote='up' THEN 1 ELSE 0 END) as up,
       SUM(CASE WHEN vote='down' THEN 1 ELSE 0 END) as down
FROM feedback GROUP BY user_id;
```

### Full-Text Search (v1.3)

The FTS5 search index is maintained automatically by triggers. If the index becomes corrupted:

```bash
# Rebuild FTS index
uv run python -c "
import sqlite3
db = sqlite3.connect('chat.db')
db.execute('INSERT INTO threads_fts(threads_fts) VALUES(\"rebuild\")')
db.commit()
print('FTS index rebuilt')
"
```

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Per-call PSSession (no pooling) | 2-4s latency per tool call | Acceptable; PSSession pooling planned for future |
| Historical tool panels always show "Done" | Error status not persisted to SQLite | New streams show correct status; only affects reloaded history |
| Historical tool panels lose elapsed time | Timestamps only in SSE events, not persisted | New streams show elapsed time correctly |
| Single MCP connection with lock | One tool call at a time per instance | Scale horizontally with multiple instances if needed |
| 128K context window | Very long conversations get pruned | Start new threads for separate topics |
| SQLite single-writer | Limited concurrent write throughput | Sufficient for <100 concurrent users |
| No "Running" badge on tool panels | Blocking SSE architecture | Tools complete before stream resumes; elapsed time shown after |
| login_required returns 302 not 401 | Mitigated by role_required in v1.3 | role_required is now the canonical decorator on all routes |
| Sidebar transition lacks reduced-motion override | Users with OS reduce-motion still see 225ms sidebar animation | Low severity — CSS polish item for future fix |
