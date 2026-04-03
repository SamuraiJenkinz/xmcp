# Atlas Deployment Guide

This guide covers deploying the Exchange Infrastructure MCP Server and Atlas chat application on a Windows server within the MMC network.

## Architecture Overview

```
                                    +----------------------------+
                                    |   Azure AD / Entra ID      |
                                    |   (SSO Authentication)     |
                                    +-------------+--------------+
                                                  |
  +----------+     HTTPS      +-------------------v------------------+
  | Browser  |<-------------->|  Flask + Waitress (port 5000)        |
  | (User)   |   SSE stream   |  chat_app/app.py                    |
  +----------+                |                                      |
                              |  React 19 SPA (frontend_dist/)       |
                              |  Fluent UI v9 + Tailwind v4          |
                              |                                      |
                              |  +-----------------------------+     |
                              |  |  Azure OpenAI (gpt-4o-mini) |     |
                              |  |  MMC stg1 endpoint          |     |
                              |  +-----------------------------+     |
                              |                                      |
                              |  +-----------------------------+     |
                              |  |  Microsoft Graph API         |     |
                              |  |  (User.Read.All, Photos)    |     |
                              |  +-----------------------------+     |
                              |                                      |
                              |  +-----------------------------+     |
                              |  |  MCP Server (stdio)          |     |
                              |  |  exchange_mcp/server.py      |     |
                              |  |  17 tools (15 Exchange + 2   |     |
                              |  |  colleague lookup)           |     |
                              |  +-------------+---------------+     |
                              +----------------+---------------------+
                                               |
                              +----------------v---------------------+
                              |  PowerShell subprocess               |
                              |  Connect-ExchangeOnline              |
                              |  Per-call PSSession lifecycle        |
                              +----------------+---------------------+
                                               |
                              +----------------v---------------------+
                              |  Exchange Online / On-Prem           |
                              |  80,000+ mailboxes                   |
                              +--------------------------------------+
```

### Frontend Architecture (v1.3)

Atlas uses a **hybrid SPA pattern**:
- Flask serves the React SPA from `frontend_dist/` via a catch-all route
- The React app (built with Vite) handles all client-side routing
- API requests (`/api/*`, `/auth/*`, `/chat/*`) are served directly by Flask
- **ATLAS_UI=react** environment variable activates the React frontend; default is "classic" (Jinja2 templates)

**v1.3 additions:** App Role access gating (role_required decorator), feedback endpoints (feedback_bp Blueprint), FTS5 search endpoint, motion@12.38.0 animation library.

## Prerequisites

### Server Requirements

| Requirement | Details |
|-------------|---------|
| **Operating System** | Windows Server 2019+ or Windows 11 (domain-joined) |
| **Python** | 3.11 or higher |
| **uv** | Latest version ([install](https://docs.astral.sh/uv/getting-started/installation/)) |
| **PowerShell** | 5.1+ (built-in) or PowerShell 7 |
| **ExchangeOnlineManagement** | PowerShell module (see below) |
| **Network** | Same subnet as Exchange management servers |
| **Memory** | 2 GB minimum |
| **Disk** | 500 MB for application + SQLite database growth |

### Install PowerShell Module

```powershell
# Run as Administrator
Install-Module ExchangeOnlineManagement -Force -Scope AllUsers

# Verify installation
Get-Module ExchangeOnlineManagement -ListAvailable
```

### Install uv (Python Package Manager)

```powershell
# Via PowerShell
irm https://astral.sh/uv/install.ps1 | iex

# Verify
uv --version
```

## Azure AD App Registration

Atlas requires an Azure AD (Entra ID) app registration for SSO authentication.

### Step 1: Create the App Registration

1. Go to [Azure Portal](https://portal.azure.com) > Azure Active Directory > App registrations
2. Click **New registration**
3. Configure:
   - **Name:** `Atlas - Exchange Infrastructure`
   - **Supported account types:** Accounts in this organizational directory only (Single tenant)
   - **Redirect URI:** Web — `https://<your-host>/auth/callback`
4. Click **Register**

### Step 2: Configure Authentication

1. Go to **Authentication** in the app registration
2. Under **Web**, verify the redirect URI: `https://<your-host>/auth/callback`
3. Under **Implicit grant and hybrid flows**, leave all unchecked (we use auth code flow)
4. Set **Logout URL:** `https://<your-host>/logout`

### Step 3: Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Set description: `Atlas Production`
4. Set expiry: 24 months (set a calendar reminder to rotate)
5. Copy the **Value** immediately — it will not be shown again

### Step 4: API Permissions

1. Go to **API permissions**
2. Ensure **Microsoft Graph > User.Read** (Delegated) is present (added by default)
3. Add **Microsoft Graph > User.Read.All** (Application) — for colleague search
4. Add **Microsoft Graph > ProfilePhoto.Read.All** (Application) — for colleague photos
5. Click **Grant admin consent for [organization]**

### Step 5: Create App Role (v1.3)

1. Go to **App roles** in the app registration
2. Click **Create app role**:
   - **Display name:** `Atlas User`
   - **Value:** `Atlas.User`
   - **Allowed member types:** Users/Groups
   - **Description:** `Access to Atlas Exchange Infrastructure tool`
3. Click **Apply**
4. Go to **Enterprise applications** > your Atlas app > **Users and groups**
5. Click **Add user/group** and assign the IT engineers security group to the `Atlas.User` role

> **Important:** Users who authenticate but lack the Atlas.User role will see an "Access Denied" page. All API endpoints return 403 (not data) for users without the role.

### Step 6: Record Values

You will need these values for configuration:

| Value | Where to find it |
|-------|-----------------|
| **Application (client) ID** | Overview page |
| **Directory (tenant) ID** | Overview page |
| **Client secret** | Certificates & secrets (copied in Step 3) |

## Exchange RBAC Setup

The Atlas service account needs read-only Exchange management roles.

### Create Service Account (if needed)

```powershell
# In Exchange Management Shell
New-Mailbox -Name "svc-exchange-mcp" -UserPrincipalName svc-exchange-mcp@mmc.com -Password (ConvertTo-SecureString "P@ssw0rd" -AsPlainText -Force)
```

### Assign Minimum Roles

```powershell
# Required for all 15 tools (all read-only)
New-ManagementRoleAssignment -Role "View-Only Recipients"     -User "svc-exchange-mcp"
New-ManagementRoleAssignment -Role "View-Only Configuration"  -User "svc-exchange-mcp"
New-ManagementRoleAssignment -Role "Mailbox Search"           -User "svc-exchange-mcp"
New-ManagementRoleAssignment -Role "Database Copies"          -User "svc-exchange-mcp"
```

### For Certificate-Based Auth (CBA) — Unattended/Production

1. Create a self-signed certificate or use a CA-issued certificate:

```powershell
$cert = New-SelfSignedCertificate -Subject "CN=Atlas Exchange MCP" -CertStoreLocation "Cert:\CurrentUser\My" -KeyExportPolicy Exportable -KeySpec Signature -KeyLength 2048 -KeyAlgorithm RSA -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(2)
$cert.Thumbprint
```

2. Export the public key (.cer) and upload it to the Azure AD app registration under **Certificates & secrets > Certificates**

3. Register the app in Exchange:

```powershell
New-ServicePrincipal -AppId "<AZURE_CLIENT_ID>" -ObjectId "<service-principal-object-id>"
New-ManagementRoleAssignment -App "<AZURE_CLIENT_ID>" -Role "View-Only Recipients"
New-ManagementRoleAssignment -App "<AZURE_CLIENT_ID>" -Role "View-Only Configuration"
```

## Installation

### Clone and Install

```powershell
git clone https://github.com/SamuraiJenkinz/xmcp.git
cd xmcp

# Install Python dependencies (creates .venv automatically)
uv sync
```

The pre-built React frontend is included in the repository under `frontend_dist/`. No Node.js or npm is required on the production server.

> **For developers rebuilding the frontend:** Install Node.js 20+, then `cd frontend && npm install && npm run build`. Commit the updated `frontend_dist/` to the repo.

### Verify Python Environment

```powershell
uv run python --version   # Should be 3.11+
uv run python -- -c "import mcp; print('MCP OK')"
uv run python -- -c "import flask; print('Flask OK')"
```

## Configuration

### Option A: AWS Secrets Manager (Production)

Store secrets in AWS Secrets Manager at `/mmc/cts/exchange-mcp` in `us-east-1`:

```json
{
  "FLASK_SECRET_KEY": "<random-64-char-string>",
  "AZURE_CLIENT_ID": "<from-app-registration>",
  "AZURE_CLIENT_SECRET": "<from-app-registration>",
  "AZURE_TENANT_ID": "<from-app-registration>",
  "AZURE_OPENAI_API_KEY": "<from-cts-team>"
}
```

Set these environment variables on the server:

```powershell
# Required — not in Secrets Manager
$env:CHATGPT_ENDPOINT = "https://stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com/coreapi/openai/v1/deployments/mmc-tech-gpt-4o-mini-128k-2024-07-18/chat/completions"

# Required — activates React frontend
$env:ATLAS_UI = "react"

# Optional — override defaults
$env:CHAT_PORT = "5000"
$env:CHAT_HOST = "0.0.0.0"
$env:CHAT_DB_PATH = "D:\atlas\data\chat.db"
$env:SESSION_FILE_DIR = "D:\atlas\sessions"

# For CBA Exchange auth (unattended)
$env:AZURE_CERT_THUMBPRINT = "<certificate-thumbprint>"
$env:AZURE_CLIENT_ID = "<app-client-id>"
$env:AZURE_TENANT_DOMAIN = "mmc.onmicrosoft.com"
```

To persist environment variables across reboots, use System Properties or:

```powershell
[System.Environment]::SetEnvironmentVariable("ATLAS_UI", "react", "Machine")
[System.Environment]::SetEnvironmentVariable("CHATGPT_ENDPOINT", "https://...", "Machine")
# Repeat for each variable. Requires admin. Takes effect on new processes.
```

### Option B: .env File (Development)

Create a `.env` file in the project root (copy from `.env.example`):

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your values:

```env
# Flask
FLASK_SECRET_KEY=dev-secret-change-in-prod

# Azure AD SSO
AZURE_CLIENT_ID=<from-app-registration>
AZURE_CLIENT_SECRET=<from-app-registration>
AZURE_TENANT_ID=<from-app-registration>

# Azure OpenAI
CHATGPT_ENDPOINT=https://stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com/coreapi/openai/v1/deployments/mmc-tech-gpt-4o-mini-128k-2024-07-18/chat/completions
AZURE_OPENAI_API_KEY=<from-cts-team>

# Frontend mode
ATLAS_UI=react

# Exchange MCP (for CBA — omit for interactive auth)
# AZURE_CERT_THUMBPRINT=<thumbprint>
# AZURE_TENANT_DOMAIN=mmc.onmicrosoft.com
```

### Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FLASK_SECRET_KEY` | Yes (prod) | `dev-secret-change-in-prod` | Session signing key. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `AZURE_CLIENT_ID` | Yes | — | Azure AD app registration client ID |
| `AZURE_CLIENT_SECRET` | Yes | — | Azure AD app registration client secret |
| `AZURE_TENANT_ID` | Yes | — | Azure AD tenant ID (GUID) |
| `CHATGPT_ENDPOINT` | Yes | — | Full Azure OpenAI chat completions URL |
| `AZURE_OPENAI_API_KEY` | Yes | — | Azure OpenAI API key |
| `ATLAS_UI` | No | `classic` | Set to `react` to serve React SPA; `classic` serves Jinja2 templates |
| `API_VERSION` | No | `2023-05-15` | Azure OpenAI API version |
| `OPENAI_MODEL` | No | `mmc-tech-gpt-4o-mini-128k-2024-07-18` | Model deployment name |
| `CHAT_HOST` | No | `0.0.0.0` | Waitress bind address |
| `CHAT_PORT` | No | `5000` | Waitress listen port |
| `CHAT_DB_PATH` | No | `../chat.db` | SQLite database file path |
| `SESSION_FILE_DIR` | No | `C:\temp\flask-sessions` | Server-side session file directory |
| `AZURE_CERT_THUMBPRINT` | CBA only | — | Certificate thumbprint for unattended Exchange auth |
| `AZURE_TENANT_DOMAIN` | CBA only | — | Primary tenant domain for CBA |

## Running the Application

### Development Mode (Frontend Hot Reload)

```powershell
# Terminal 1: Start Flask backend with HTTPS
$env:ATLAS_UI = "react"
uv run python start.py

# Terminal 2: Start Vite dev server (hot reload, optional)
cd frontend
npm run dev
```

Vite dev server runs on `http://localhost:5173` and proxies API requests (`/api/*`, `/auth/*`, `/chat/*`) to Flask on port 5050.

### Production Mode

`start.py` runs Flask with HTTPS using the server's TLS certificates on port 5050:

```powershell
$env:ATLAS_UI = "react"
uv run python start.py
```

This requires the TLS certificate and key in the project root:
- `usdf11v1784.mercer.com-chaincert-combined.crt`
- `usdf11v1784.mercer.com-private.key`

Flask serves the pre-built React SPA from `frontend_dist/`. No separate Node.js process is needed at runtime.

> **Note:** `start.py` uses Flask's built-in server with SSL. For higher concurrency, place behind IIS as a reverse proxy with TLS termination and use `uv run python -m chat_app.app` (Waitress, plain HTTP) as the backend.

### Running as a Windows Service

To run Atlas as a Windows service, use [NSSM](https://nssm.cc/):

```powershell
# Install NSSM
choco install nssm

# Create service
nssm install AtlasExchangeMCP "D:\xmcp\.venv\Scripts\python.exe" "start.py"
nssm set AtlasExchangeMCP AppDirectory "D:\xmcp"
nssm set AtlasExchangeMCP AppEnvironmentExtra "ATLAS_UI=react" "CHATGPT_ENDPOINT=https://..." "AZURE_CERT_THUMBPRINT=..."
nssm set AtlasExchangeMCP Description "Atlas Exchange Infrastructure Chat"
nssm set AtlasExchangeMCP Start SERVICE_AUTO_START

# Start
nssm start AtlasExchangeMCP
```

## Network Requirements

| Direction | Port | Destination | Purpose |
|-----------|------|-------------|---------|
| Inbound | 5050 | Atlas server | User access to chat UI (HTTPS) |
| Outbound | 443 | `login.microsoftonline.com` | Azure AD authentication |
| Outbound | 443 | `graph.microsoft.com` | Microsoft Graph (user profiles, photos) |
| Outbound | 443 | `outlook.office365.com` | Exchange Online PowerShell |
| Outbound | 443 | `stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com` | Azure OpenAI endpoint |
| Outbound | 443 | `secretsmanager.us-east-1.amazonaws.com` | AWS Secrets Manager (prod) |
| Outbound | 53 | DNS servers | DMARC/SPF/DKIM lookups |

### Reverse Proxy (Optional)

If placing Atlas behind IIS or Nginx as a reverse proxy:

**IIS with URL Rewrite:**
- Ensure WebSocket protocol is enabled
- Set `responseBufferLimit="0"` in the ARR configuration for SSE streaming
- Set `X-Accel-Buffering: no` header
- Configure the rewrite rule to proxy to `http://localhost:5000`

**Nginx:**
```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Required for SSE streaming
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
}
```

## Pre-Flight Verification

### 1. Verify Exchange Connectivity

```powershell
uv run python scripts/verify_exchange.py
```

Expected output:
```
Step 1: ExchangeClient created -- auth mode: interactive
Step 2: verify_connection() returned True
Step 3: Get-OrganizationConfig — Name field populated
Step 4: Second cmdlet completed — no orphaned sessions
ALL EXCHANGE CHECKS PASSED
```

### 2. Verify DNS Resolution

```powershell
uv run python scripts/verify_dns.py
```

### 3. Verify Unit Tests

```powershell
uv run pytest tests/ -v --ignore=tests/test_integration.py
```

All tests should pass. Integration tests (`test_integration.py`) require a live Exchange connection.

### 4. Verify Frontend Assets

```powershell
Get-ChildItem frontend_dist/   # Should contain index.html and assets/
```

### 5. Health Check

After starting the app:

```powershell
Invoke-RestMethod http://localhost:5000/api/health
```

Expected:
```json
{"status": "ok", "mcp_connected": true, "tools_count": 17}
```

## Troubleshooting

### Application Won't Start

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: No module named 'mcp'` | Dependencies not installed | Run `uv sync` |
| `ExchangeOnlineManagement not found` | PS module missing | Run `Install-Module ExchangeOnlineManagement -Force` |
| `MSAL error: invalid_client` | Wrong client ID or secret | Verify `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` |
| `Connection refused on port 5000` | App not running or port conflict | Check `CHAT_PORT`, verify no other process on port |
| `MCP init timeout (120s)` | Exchange auth failed at startup | Check Exchange credentials and network connectivity |
| `frontend_dist/ not found` | React build missing from repo | Run `git pull` or rebuild locally: `cd frontend && npm install && npm run build` |

### Exchange Tool Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Exchange error: Access denied` | Service account lacks RBAC role | Assign missing Exchange management role |
| `Exchange error: not found` | Invalid mailbox/DAG/database name | Verify the identity exists in Exchange |
| `TimeoutError: Command timed out after 60s` | Exchange server overloaded | Retry; consider increasing timeout |
| `Authentication failed (AADSTS...)` | Certificate expired or invalid | Rotate certificate, verify app registration |

### SSE Streaming Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Response arrives all at once | Proxy buffering SSE | Add `X-Accel-Buffering: no` header, disable proxy buffering; for IIS ARR set `responseBufferLimit="0"` |
| Response is blank | JavaScript error | Check browser console (F12); verify `ATLAS_UI=react` is set |
| Stop button doesn't appear | Stale frontend assets | Hard refresh (Ctrl+Shift+R) or rebuild frontend |

## Updating

```powershell
cd D:\xmcp
git pull origin master
uv sync  # Install any new Python dependencies

# Restart the application
nssm restart AtlasExchangeMCP  # If running as Windows service
```

The pre-built frontend assets update automatically with `git pull`. No npm or Node.js needed on the server.

### v1.3 Upgrade Notes

When upgrading from v1.2 to v1.3:

1. **Database migration is automatic** — `migrate_db()` runs on startup and adds the `feedback` table, `threads_fts` FTS5 index, and sync triggers to existing databases. No manual SQL required.
2. **App Role must be configured** — create the `Atlas.User` App Role in Azure AD (see Step 5 above) and assign your IT engineers group. Without this, all users will see "Access Denied" after login.
3. **No new environment variables required** — all v1.3 features use existing configuration. Optionally set `VITE_ADMIN_EMAIL` in the frontend build to customize the admin contact on the Access Denied page (defaults to `it-admin@mercer.com`).
4. **Frontend bundle updated** — the pre-built `frontend_dist/` includes all v1.3 features. Pulled automatically with `git pull`.

## Backup

### Database

The SQLite database contains all conversation threads and messages. Back it up regularly:

```powershell
# While application is running (WAL mode makes this safe)
Copy-Item chat.db "chat.db.backup.$(Get-Date -Format yyyyMMdd)"
```

### Session Files

Session files in `SESSION_FILE_DIR` are ephemeral and do not need backup. They are recreated on login.
