# External Integrations

**Analysis Date:** 2026-03-24

## APIs & External Services

**Azure OpenAI (LLM):**
- Service: Azure OpenAI API
  - SDK/Client: `openai` 2.29+ package
  - Implementation: `chat_app/openai_client.py`
  - Endpoint configuration: `CHATGPT_ENDPOINT` env var (e.g., `https://stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com/coreapi/openai/v1/deployments/{model}/chat/completions`)
  - API Key: `AZURE_OPENAI_API_KEY` env var
  - Model: `OPENAI_MODEL` env var (default: `mmc-tech-gpt-4o-mini-128k-2024-07-18`)
  - API Version: `API_VERSION` env var (default: `2023-05-15`)
  - Tool-calling loop: Max 5 iterations (`_MAX_TOOL_ITERATIONS` in `openai_client.py`)

**Exchange Online (Cmdlet Execution):**
- Service: Microsoft Exchange Online
  - PowerShell module: `ExchangeOnlineManagement`
  - Client wrapper: `exchange_mcp/exchange_client.py` (async subprocess runner)
  - Authentication modes:
    - Interactive (default): Browser-based OAuth popup (`_PS_CONNECT_INTERACTIVE`)
    - Certificate-based (CBA): For unattended/production use (`_PS_CONNECT_CBA`)
  - Environment variables:
    - `AZURE_CLIENT_ID` - App registration ID
    - `AZURE_CERT_THUMBPRINT` - Client certificate thumbprint (optional, for CBA)
    - `AZURE_TENANT_DOMAIN` - Tenant domain (e.g., `mmc.onmicrosoft.com`, for CBA)
  - Retry logic: Exponential backoff for transient errors (up to `max_retries` attempts)
  - Error handling: Non-transient errors (auth, invalid input) fail immediately; transient errors (throttling, network, timeouts) retry

**DNS Resolution (DMARC/SPF):**
- Service: System DNS resolver
  - Library: `dnspython` 2.8+
  - Implementation: `exchange_mcp/dns_utils.py`
  - Resolvers:
    - `get_txt_records()` - Async TXT record lookup with TTL-based caching
    - `get_cname_record()` - Async CNAME record lookup
    - `get_dmarc_record()` - DMARC record parsing (RFC 7489)
    - `get_spf_record()` - SPF record parsing (RFC 7208)
  - Cache behavior: Per-name TTL-respecting cache (default 300 seconds for negative responses)
  - Error handling: Raises `LookupError` on unexpected DNS failures

## Data Storage

**Databases:**
- Type: SQLite
  - Location: `CHAT_DB_PATH` env var (default: `chat.db` in project root)
  - Client: Built-in `sqlite3` standard library
  - Implementation: `chat_app/db.py`
  - Features:
    - WAL (Write-Ahead Logging) mode for concurrent reads
    - Foreign key enforcement enabled
    - Auto-bootstrap schema on first startup (`chat_app/schema.sql`)
    - Per-request connection pooling via Flask `g` object
  - Tables: Conversations and message history (user_id, thread_id, created_at, updated_at)

**File Storage:**
- Type: Filesystem only (no cloud storage)
  - Session storage: Filesystem-based via Flask-Session (`SESSION_FILE_DIR` env var, default `/tmp/flask-sessions`)
  - Database file: Local SQLite file

**Caching:**
- In-memory: DNS resolution cache with TTL expiry (`exchange_mcp/dns_utils.py`)
- Session cache: MCP tool definitions cached in memory after first enumeration (`chat_app/mcp_client.py`)

## Authentication & Identity

**Auth Provider:**
- Azure AD (Entra ID)
  - Service: Microsoft Entra ID (Azure Active Directory)
  - Implementation: `chat_app/auth.py` using MSAL (Microsoft Authentication Library)
  - SDK: `msal` 1.35.1+
  - Flow: OAuth 2.0 Authorization Code Flow
  - Configuration:
    - `AZURE_CLIENT_ID` - App registration ID
    - `AZURE_CLIENT_SECRET` - Client secret
    - `AZURE_TENANT_ID` - Tenant ID
    - Authority: `https://login.microsoftonline.com/{AZURE_TENANT_ID}`
  - Session management: Token cache stored in Flask session (serialized)
  - Redirect URI: `/auth/callback` endpoint

**User Context:**
- Session-based: User identity stored in Flask `session['user']` dict with fields:
  - `oid` - Azure AD object ID (used as user_id in database)
  - `name` - User's display name
  - Other claims from ID token

## Monitoring & Observability

**Error Tracking:**
- Type: Not detected (no dedicated error tracking service integrated)
- Logging: Python standard `logging` module with file/stderr handlers configured
  - MCP server logs to stderr (see `exchange_mcp/server.py` lines 26-30)
  - Flask app logs to application handler

**Logs:**
- Approach: Standard Python logging with automatic configuration in MCP server and Flask app
- No central log aggregation detected

## CI/CD & Deployment

**Hosting:**
- Platform: Not auto-detected, but code supports:
  - Local development: Flask development server
  - Production: Waitress WSGI server (`waitress` 3.0+)
  - Cloud: Compatible with AWS (Secrets Manager integration), Azure (OpenAI, Entra ID)

**CI Pipeline:**
- Service: Not detected
- Tests: pytest with markers for network and Exchange tests

## Environment Configuration

**Required env vars:**
- `FLASK_SECRET_KEY` - Flask session encryption key
- `AZURE_CLIENT_ID` - Azure AD app registration ID
- `AZURE_CLIENT_SECRET` - Azure AD client secret (loaded from Secrets Manager or .env)
- `AZURE_TENANT_ID` - Azure tenant ID
- `CHATGPT_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key

**Optional env vars:**
- `AZURE_CERT_THUMBPRINT` - Certificate thumbprint for CBA (if omitted, interactive auth used)
- `AZURE_TENANT_DOMAIN` - Tenant domain for CBA (e.g., `mmc.onmicrosoft.com`)
- `CHAT_HOST` - Flask host (default: `0.0.0.0`)
- `CHAT_PORT` - Flask port (default: `5000`)
- `CHAT_DB_PATH` - SQLite database path
- `SESSION_FILE_DIR` - Flask session directory (default: `/tmp/flask-sessions`)
- `API_VERSION` - Azure OpenAI API version (default: `2023-05-15`)
- `OPENAI_MODEL` - Azure OpenAI model name
- `AWS_SECRET_NAME` - AWS Secrets Manager secret name (default: `/mmc/cts/exchange-mcp`)
- `AWS_REGION` - AWS region for Secrets Manager (default: `us-east-1`)

**Secrets location:**
- Primary: AWS Secrets Manager (`boto3` client with region fallback)
- Fallback: `.env` file loaded via `python-dotenv` (development only)
- Implementation: `chat_app/secrets.py` with try-except fallback pattern

## Webhooks & Callbacks

**Incoming:**
- `/auth/callback` - Azure AD OAuth callback endpoint (handles authorization code exchange)
- `/api/health` - Health check endpoint (reports MCP connectivity and tool count)

**Outgoing:**
- Exchange Online MCP subprocess: Stdin/stdout stdio transport (not HTTP webhooks)
- Azure OpenAI: HTTP requests via `openai` SDK to Azure OpenAI endpoint

---

*Integration audit: 2026-03-24*
