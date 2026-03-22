# Atlas Deployment Guide

This guide covers deploying the Exchange Infrastructure MCP Server and Atlas chat application on a Windows server within the MMC network.

## Architecture Overview

```
                                    ┌──────────────────────────┐
                                    │   Azure AD / Entra ID    │
                                    │   (SSO Authentication)   │
                                    └──────────┬───────────────┘
                                               │
  ┌──────────┐     HTTPS      ┌────────────────▼───────────────┐
  │ Browser  │◄──────────────►│  Flask + Waitress (port 5000)  │
  │ (User)   │   SSE stream   │  chat_app/app.py               │
  └──────────┘                │                                │
                              │  ┌─────────────────────────┐   │
                              │  │  Azure OpenAI (gpt-4o)  │   │
                              │  │  MMC stg1 endpoint      │   │
                              │  └─────────────────────────┘   │
                              │                                │
                              │  ┌─────────────────────────┐   │
                              │  │  MCP Server (stdio)     │   │
                              │  │  exchange_mcp/server.py  │   │
                              │  │  15 Exchange tools       │   │
                              │  └──────────┬──────────────┘   │
                              └─────────────┼──────────────────┘
                                            │
                              ┌─────────────▼──────────────────┐
                              │  PowerShell subprocess         │
                              │  Connect-ExchangeOnline        │
                              │  Per-call PSSession lifecycle  │
                              └─────────────┬──────────────────┘
                                            │
                              ┌─────────────▼──────────────────┐
                              │  Exchange Online / On-Prem     │
                              │  80,000+ mailboxes             │
                              └────────────────────────────────┘
```

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
3. Click **Grant admin consent for [organization]** if required by your tenant policy

### Step 5: Record Values

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

```bash
git clone https://github.com/SamuraiJenkinz/xmcp.git
cd xmcp

# Install all dependencies (creates .venv automatically)
uv sync
```

### Verify Python Environment

```bash
uv run python --version   # Should be 3.11+
uv run python -c "import mcp; print('MCP OK')"
uv run python -c "import flask; print('Flask OK')"
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

```bash
# Required — not in Secrets Manager
export CHATGPT_ENDPOINT="https://stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com/coreapi/openai/v1/deployments/mmc-tech-gpt-4o-mini-128k-2024-07-18/chat/completions"

# Optional — override defaults
export CHAT_PORT=5000
export CHAT_HOST=0.0.0.0
export CHAT_DB_PATH=/opt/atlas/data/chat.db
export SESSION_FILE_DIR=/opt/atlas/sessions

# For CBA Exchange auth (unattended)
export AZURE_CERT_THUMBPRINT="<certificate-thumbprint>"
export AZURE_CLIENT_ID="<app-client-id>"
export AZURE_TENANT_DOMAIN="mmc.onmicrosoft.com"
```

### Option B: .env File (Development)

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
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
| `API_VERSION` | No | `2023-05-15` | Azure OpenAI API version |
| `OPENAI_MODEL` | No | `mmc-tech-gpt-4o-mini-128k-2024-07-18` | Model deployment name |
| `CHAT_HOST` | No | `0.0.0.0` | Waitress bind address |
| `CHAT_PORT` | No | `5000` | Waitress listen port |
| `CHAT_DB_PATH` | No | `../chat.db` | SQLite database file path |
| `SESSION_FILE_DIR` | No | `/tmp/flask-sessions` | Server-side session file directory |
| `AZURE_CERT_THUMBPRINT` | CBA only | — | Certificate thumbprint for unattended Exchange auth |
| `AZURE_TENANT_DOMAIN` | CBA only | — | Primary tenant domain for CBA |

## Running the Application

### Development Mode

```bash
cd xmcp

# Interactive Exchange auth (browser popup on first tool call)
uv run python -m chat_app.app
```

The app will start on `http://localhost:5000`. The MCP server subprocess is spawned automatically.

### Production Mode

```bash
# With CBA Exchange auth (unattended)
export AZURE_CERT_THUMBPRINT="ABC123..."
export AZURE_CLIENT_ID="..."
export AZURE_TENANT_DOMAIN="mmc.onmicrosoft.com"

uv run python -m chat_app.app
```

Waitress serves the app on `0.0.0.0:5000` by default. No separate MCP server process is needed — it is spawned as a subprocess.

### Running as a Windows Service

To run Atlas as a Windows service, use [NSSM](https://nssm.cc/):

```powershell
# Install NSSM
choco install nssm

# Create service
nssm install AtlasExchangeMCP "C:\xmcp\.venv\Scripts\python.exe" "-m chat_app.app"
nssm set AtlasExchangeMCP AppDirectory "C:\xmcp"
nssm set AtlasExchangeMCP AppEnvironmentExtra "CHATGPT_ENDPOINT=https://..." "AZURE_CERT_THUMBPRINT=..."
nssm set AtlasExchangeMCP Description "Atlas Exchange Infrastructure Chat"
nssm set AtlasExchangeMCP Start SERVICE_AUTO_START

# Start
nssm start AtlasExchangeMCP
```

## Network Requirements

| Direction | Port | Destination | Purpose |
|-----------|------|-------------|---------|
| Inbound | 5000 (configurable) | Atlas server | User access to chat UI |
| Outbound | 443 | `login.microsoftonline.com` | Azure AD authentication |
| Outbound | 443 | `graph.microsoft.com` | Microsoft Graph (user profile) |
| Outbound | 443 | `outlook.office365.com` | Exchange Online PowerShell |
| Outbound | 443 | `stg1.mmc-dallas-int-non-prod-ingress.mgti.mmc.com` | Azure OpenAI endpoint |
| Outbound | 443 | `secretsmanager.us-east-1.amazonaws.com` | AWS Secrets Manager (prod) |
| Outbound | 53 | DNS servers | DMARC/SPF/DKIM lookups |

### Reverse Proxy (Optional)

If placing Atlas behind IIS or Nginx as a reverse proxy:

**IIS with URL Rewrite:**
- Ensure WebSocket protocol is enabled
- Set `X-Accel-Buffering: no` header for SSE to work
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

```bash
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

```bash
uv run python scripts/verify_dns.py
```

### 3. Verify Unit Tests

```bash
uv run pytest tests/ -v --ignore=tests/test_integration.py
```

All tests should pass. Integration tests (`test_integration.py`) require a live Exchange connection.

### 4. Health Check

After starting the app:

```bash
curl http://localhost:5000/api/health
```

Expected:
```json
{"status": "ok", "mcp_connected": true, "tools_count": 15}
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
| Response arrives all at once | Proxy buffering SSE | Add `X-Accel-Buffering: no` header, disable proxy buffering |
| Response is blank | JavaScript error | Check browser console; verify `app.js` loaded |
| "Connection refused" on chat | Flask session directory missing | Ensure `SESSION_FILE_DIR` directory exists |

## Updating

```bash
cd xmcp
git pull origin master
uv sync  # Install any new dependencies

# Restart the application
nssm restart AtlasExchangeMCP  # If running as Windows service
```

## Backup

### Database

The SQLite database contains all conversation threads and messages. Back it up regularly:

```bash
# While application is running (WAL mode makes this safe)
cp chat.db chat.db.backup.$(date +%Y%m%d)
```

### Session Files

Session files in `SESSION_FILE_DIR` are ephemeral and do not need backup. They are recreated on login.
