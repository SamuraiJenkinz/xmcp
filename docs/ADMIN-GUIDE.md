# Atlas Administration Guide

This guide covers the internal architecture, tool reference, database management, monitoring, security model, and operational procedures for the Atlas Exchange Infrastructure MCP Server.

## System Architecture

Atlas consists of two main components:

1. **MCP Server** (`exchange_mcp/`) — a Model Context Protocol server that exposes 15 Exchange infrastructure tools over stdio JSON-RPC. It manages PowerShell subprocess execution and DNS lookups.

2. **Chat Application** (`chat_app/`) — a Flask web application that provides the user interface, Azure AD authentication, Azure OpenAI integration, and conversation persistence.

The chat app spawns the MCP server as a child process at startup. They communicate over stdin/stdout using the MCP stdio transport protocol. A `threading.Lock` serializes all MCP calls (one tool invocation at a time).

```
Flask App ──stdio──► MCP Server ──subprocess──► powershell.exe ──► Exchange Online
    │                    │
    │                    └──► dnspython ──► DNS (DMARC/SPF/DKIM)
    │
    ├──► Azure AD (MSAL auth code flow)
    ├──► Azure OpenAI (tool-calling loop)
    └──► SQLite (conversation persistence)
```

## Tool Reference

### Tool Inventory

All 15 tools are read-only. No tool can create, modify, or delete Exchange objects.

| # | Tool | Category | Exchange Cmdlets Used | Auth Required |
|---|------|----------|----------------------|---------------|
| 1 | `ping` | Connectivity | None | No |
| 2 | `get_mailbox_stats` | Mailbox | Get-MailboxStatistics, Get-Mailbox | Yes |
| 3 | `search_mailboxes` | Mailbox | Get-Mailbox | Yes |
| 4 | `get_shared_mailbox_owners` | Mailbox | Get-MailboxPermission, Get-RecipientPermission, Get-Mailbox | Yes |
| 5 | `list_dag_members` | DAG | Get-DatabaseAvailabilityGroup, Get-ExchangeServer, Get-MailboxDatabaseCopyStatus | Yes |
| 6 | `get_dag_health` | DAG | Get-DatabaseAvailabilityGroup, Get-MailboxDatabaseCopyStatus | Yes |
| 7 | `get_database_copies` | DAG | Get-MailboxDatabaseCopyStatus, Get-MailboxDatabase | Yes |
| 8 | `check_mail_flow` | Mail Flow | Get-AcceptedDomain, Get-SendConnector, Get-ReceiveConnector | Yes |
| 9 | `get_transport_queues` | Mail Flow | Get-TransportService, Get-Queue | Yes |
| 10 | `get_smtp_connectors` | Mail Flow | Get-SendConnector, Get-ReceiveConnector | Yes |
| 11 | `get_dkim_config` | Security | Get-DkimSigningConfig | Yes (+ DNS) |
| 12 | `get_dmarc_status` | Security | None (pure DNS) | No |
| 13 | `check_mobile_devices` | Security | Get-MobileDeviceStatistics | Yes |
| 14 | `get_hybrid_config` | Hybrid | Get-OrganizationRelationship, Get-FederationTrust, Get-IntraOrganizationConnector, Get-AvailabilityAddressSpace, Get-SendConnector | Yes |
| 15 | `get_connector_status` | Hybrid | Get-SendConnector, Get-ReceiveConnector, Get-ExchangeCertificate | Yes |

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

## Error Handling Chain

Errors flow through multiple layers with sanitization at each level:

```
PowerShell stderr
  → ExchangeClient: raise RuntimeError(stderr)
    → tools.py handler: raise RuntimeError(user_message)
      → server.py _sanitize_error(): strip PS tracebacks, add retry hints
        → MCP SDK: CallToolResult(isError=True, content=sanitized_message)
          → chat_app openai_client: tool_events[status="error"]
            → SSE: {"type": "tool", "status": "error", ...}
              → Browser: red "Error" badge on tool panel
```

**Sanitization rules** (`server.py:_sanitize_error()`):
- Strip everything after `stderr:` marker (removes raw PowerShell tracebacks)
- Remove `PowerShell exited with code N.` prefix
- Append "This may be a temporary issue — please try again." for transient errors
- No retry hint for authentication/input errors

## Database Management

### Schema

SQLite database with WAL mode and foreign keys enabled. Two tables:

- **threads** — one row per conversation thread (user_id, name, timestamps)
- **messages** — one row per thread containing the full message history as a JSON array

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
  "tools_count": 15
}
```

Monitor this endpoint. Key indicators:
- `mcp_connected: false` — MCP subprocess crashed or failed to start
- `tools_count < 15` — Tool registration issue

### Application Logs

All application logs go to **stderr**. The MCP server enforces strict stderr-only logging — stdout is reserved for JSON-RPC protocol messages.

To capture logs:

```bash
# Console
uv run python -m chat_app.app 2>atlas.log

# Windows Service (NSSM)
nssm set AtlasExchangeMCP AppStderr "C:\atlas\logs\atlas.log"
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

### Performance Monitoring

Expected latencies:

| Operation | Expected | Investigate if |
|-----------|----------|---------------|
| Tool call (simple) | 2-4 seconds | > 10 seconds |
| Tool call (composite, e.g., get_hybrid_config) | 5-10 seconds | > 20 seconds |
| SSE stream start | < 1 second | > 3 seconds |
| AI response generation | 1-3 seconds | > 10 seconds |
| Page load | < 500ms | > 2 seconds |

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

### No Free-Form PowerShell

The AI model cannot execute arbitrary PowerShell. All Exchange queries go through the MCP tool dispatch table, which maps tool names to specific handler functions. There is no mechanism for the AI to construct or inject PowerShell commands.

### Authentication Layers

| Layer | Mechanism | What it protects |
|-------|-----------|-----------------|
| User → Chat App | Azure AD SSO (MSAL auth code flow) | Only authenticated MMC colleagues can access the chat |
| Chat App → User Data | `session["user"]["oid"]` ownership check | Users can only see their own threads |
| Chat App → Exchange | Service account RBAC | Tool calls limited to assigned Exchange roles |
| Chat App → Azure OpenAI | API key (from AWS Secrets Manager) | AI calls restricted to MMC corporate endpoint |

### Data Privacy

- **No email content access** — no tools read message bodies or attachments
- **Conversation isolation** — SQLite queries always filter by `user_id` (Azure AD OID)
- **No data exfiltration** — the AI is instructed to only answer Exchange questions and cannot be prompted to send data externally
- **Error sanitization** — PowerShell tracebacks are stripped before reaching users

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

```bash
# Start MCP dev inspector
uv run mcp dev exchange_mcp/server.py

# This opens a web-based inspector where you can:
# - See all registered tools
# - Call tools with custom parameters
# - Inspect JSON results
```

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Per-call PSSession (no pooling) | 2-4s latency per tool call | Acceptable for v1; PSSession pooling planned for v2 |
| Tool events not persisted | Historical messages lose tool panels on reload | Copy JSON before navigating away |
| Single MCP connection with lock | One tool call at a time per instance | Scale horizontally with multiple instances if needed |
| 128K context window | Very long conversations get pruned | Start new threads for separate topics |
| SQLite single-writer | Limited concurrent write throughput | Sufficient for <100 concurrent users |
