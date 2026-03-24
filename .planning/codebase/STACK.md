# Technology Stack

**Analysis Date:** 2026-03-24

## Languages

**Primary:**
- Python 3.11 - Backend server, MCP server, tooling

**Secondary:**
- TypeScript/JavaScript - Frontend templates and static assets (Jinja2 templates in `chat_app/templates/`)
- PowerShell - Exchange Online cmdlet invocation via subprocess

## Runtime

**Environment:**
- Python 3.11+ with asyncio for async operations

**Package Manager:**
- uv - Deterministic Python package management (lockfile: `uv.lock`)

## Frameworks

**Core:**
- Flask 3.0+ - Web framework for chat application in `chat_app/app.py`
- Model Context Protocol (MCP) 1.0+ - Standard protocol for tool integration
  - MCP server: `exchange_mcp/server.py` (stdio transport)
  - MCP client: `chat_app/mcp_client.py` (subprocess-based stdio client)

**Session Management:**
- Flask-Session 0.8+ - Server-side session storage (filesystem-based)

**Testing:**
- pytest 9.0.2+ - Test runner
- pytest-asyncio 1.3+ - Async test support

## Key Dependencies

**Critical:**
- openai 2.29+ - OpenAI SDK for Azure OpenAI integration (`chat_app/openai_client.py`)
- msal 1.35.1+ - Microsoft Authentication Library for Azure AD/Entra ID SSO (`chat_app/auth.py`)
- tiktoken 0.12+ - Token counting for context management (`chat_app/context_mgr.py`)
- dnspython 2.8+ - DNS resolution for DMARC/SPF lookups (`exchange_mcp/dns_utils.py`)

**Infrastructure:**
- boto3 1.42.73+ - AWS SDK for Secrets Manager integration (`chat_app/secrets.py`)
- python-dotenv 1.2.2+ - Environment variable loading from .env files

**Server:**
- waitress 3.0+ - WSGI server (production HTTP server)

## Configuration

**Environment:**
- Loaded via `chat_app/config.py` using environment variables
- Secrets support: AWS Secrets Manager (primary) with .env fallback
- Configuration file: `.env.example` documents all required environment variables

**Build:**
- `pyproject.toml` - Project metadata and dependencies (PEP 621 format)
- `uv.lock` - Deterministic lock file for reproducible builds

## Platform Requirements

**Development:**
- Windows 11 Pro (native PowerShell for Exchange cmdlet execution)
- Python 3.11+ virtual environment
- Exchange Online PowerShell module (`ExchangeOnlineManagement`)

**Production:**
- Windows Server with PowerShell 5.1+ (for Exchange Online cmdlet execution via `ps_runner.py`)
- Linux/macOS: Limited to MCP tools only (no Exchange Online cmdlet support without PowerShell)
- Azure environment: Entra ID (Azure AD) and Azure OpenAI access
- AWS environment: Secrets Manager access for credential storage

**Key System Dependencies:**
- `dnspython` requires system DNS resolver (uses `dns.asyncresolver` and `dns.resolver`)
- Flask requires network access for OAuth callbacks
- Exchange Online cmdlets require Windows PowerShell 5.1+ (Windows-only)

---

*Stack analysis: 2026-03-24*
