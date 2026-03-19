# Technology Stack

**Project:** Exchange Infrastructure MCP Server — Marsh McLennan Companies
**Researched:** 2026-03-19
**Researcher:** GSD Project Researcher

---

## Research Method & Confidence Note

Context7 MCP, WebSearch, and WebFetch tools were unavailable during this research session.
All findings are sourced from:

1. Project-owned documentation (`exchange-mcp-architecture.md`, `PROJECT.md`) — versions cited
   there were authored by the project owner with direct knowledge of the deployment environment.
   **Treat as HIGH confidence for pinned version floors.**
2. Training data (knowledge cutoff: August 2025) — used for ecosystem context, patterns, and
   recommendations where the project docs don't prescribe a choice. **Treat as MEDIUM confidence.**
   Version numbers from training data alone are flagged LOW confidence — verify before pinning.

No training-data version claim is presented as current without a flag. Where versions need
verification, the correct PyPI URL is provided.

---

## Recommended Stack

### Layer 1: MCP Server (Python)

| Technology | Min Version | Recommended Pin | Purpose | Why |
|------------|-------------|-----------------|---------|-----|
| Python | 3.11 | 3.12 | Runtime | 3.11 mandated by project; 3.12 offers free-threaded perf improvements and `asyncio` refinements. Do not use 3.13 yet — `pywinpty` and some WinRM libs lag. |
| `mcp` (Anthropic SDK) | 1.0.0 | ≥1.9.x | MCP protocol: tool registration, stdio transport, schema serialization | The `mcp` package is the official Anthropic Python SDK. 1.0.0 stable released late 2024; the architecture doc pins `>=1.0.0`. Verify current release at `https://pypi.org/project/mcp/` before pinning. |
| `anyio` | 4.x | ≥4.3.0 | Async runtime compatibility layer required by `mcp` | `mcp` SDK depends on `anyio`; pinning explicitly prevents transitive version drift on Windows. |
| `pydantic` | v2 | ≥2.5.0 | Data validation for tool input schemas | `mcp` SDK v1.x uses Pydantic v2 internally. Explicitly pinning avoids install-time resolution conflicts. Do NOT use Pydantic v1 — it is EOL. |

**Confidence:** MEDIUM. The `mcp>=1.0.0` floor is HIGH (project-authored). The recommendation
to verify current patch level before pinning is correct discipline — the package moves fast.

**What NOT to use:**
- `fastmcp` (third-party wrapper) — adds abstraction over the official SDK with no benefit for
  15 well-defined tools. The official `mcp` SDK is now mature enough that wrappers are unnecessary.
- `mcp` SDK versions below 1.0.0 — pre-1.0 had breaking protocol changes.

---

### Layer 2: Web Framework (Chat Application)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Flask** | ≥3.0 | HTTP server, routing, session management, Jinja2 templating | Project constraint specifies Flask/FastAPI + Jinja2. Flask is the correct choice here (see rationale below). |
| **Jinja2** | ≥3.1 | Server-side HTML templating | Bundled with Flask 3.x. No separate pin needed unless you need a Jinja2-only feature. |
| **Flask-Session** | ≥0.7 | Server-side session storage (filesystem or Redis) | Browser cookies cannot hold conversation history. Flask-Session stores it server-side. Required for multi-thread conversation history. |
| **Werkzeug** | ≥3.0 | WSGI utilities — ships with Flask 3.x | No separate pin. Locked to Flask version. |
| **Waitress** | ≥3.0 | WSGI production server for Windows | Gunicorn does NOT run on Windows. Waitress is the production WSGI server for Windows deployments. This is non-negotiable given the on-prem Windows constraint. |

**Flask vs FastAPI decision rationale:**

Choose **Flask** because:

1. **Jinja2 server-side rendering is idiomatic Flask.** FastAPI was designed for JSON API services.
   Using FastAPI with Jinja2/HTML responses (via `Jinja2Templates`) works but is non-standard
   and produces a mismatched mental model. The project is NOT building a React SPA — it's building
   an internal tool with HTML pages rendered server-side. Flask is the correct fit.

2. **Session management is simpler in Flask.** `flask.session` and `Flask-Session` are
   first-class. FastAPI requires `starlette` session middleware that is less battle-tested
   for this pattern.

3. **SSO / MSAL integration libraries are more mature for Flask.** `msal` + `Flask` has
   established patterns (`flask-dance`, direct MSAL usage) that are well-documented.
   FastAPI MSAL integration requires more manual wiring.

4. **Windows deployment.** Both run under Waitress (WSGI) on Windows, but Flask's synchronous
   model is simpler to reason about on a domain-joined Windows server. FastAPI's async model
   provides benefits primarily when you have many concurrent I/O-bound requests — this
   internal tool will not be under that load.

**What NOT to use:**
- **Gunicorn** — Unix-only, will not run on Windows without WSL. Use Waitress.
- **uvicorn** — async ASGI server for FastAPI/Starlette. Not appropriate for Flask unless
  you add the `asgiref` shim, which adds unnecessary complexity.
- **Django** — wildly over-engineered for an internal single-purpose tool. No ORM needed.
  No admin interface needed. Adds 40+ packages of surface area.

**Confidence:** HIGH. Windows-specific WSGI constraint eliminates Gunicorn. Flask + Jinja2 +
Waitress is the correct triad for this deployment model.

---

### Layer 3: Azure AD / Entra ID SSO

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **msal** (Microsoft Authentication Library) | ≥1.28.0 | Azure AD / Entra ID OAuth 2.0 / OIDC token acquisition | Official Microsoft Python library. The only supported, Microsoft-maintained path for Entra ID SSO from Python. |
| **Flask-Login** | ≥0.6.3 | Session-based login state management after MSAL token validation | Separates "who is authenticated" from "how they authenticated." Integrates cleanly with MSAL for post-callback session establishment. |

**SSO flow for this deployment:**

```
Browser → Flask app → Redirect to Azure AD /authorize
         → User authenticates with MMC Entra ID (MFA, existing SSO session)
         → Azure AD redirects back with auth code
         → Flask app calls MSAL /token endpoint (auth code exchange)
         → MSAL returns access token + ID token
         → Flask-Login establishes session
         → Subsequent requests: validate session, no re-auth
```

**Key MSAL configuration for MMC:**
- Flow: Authorization Code Flow (NOT Client Credentials — requires user identity for
  Kerberos delegation chain to work)
- Scopes: `openid`, `profile`, `email`, plus `User.Read` from Microsoft Graph for
  display name and UPN
- Token cache: in-memory per session (Flask-Session stores the MSAL token cache
  alongside conversation history)
- Tenant: MMC's Entra ID tenant — `AZURE_TENANT_ID` env var
- Client: Registered app in MMC Entra ID — `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET`

**What NOT to use:**
- `flask-azure-ad` — third-party, unmaintained, do not use.
- `authlib` — capable library but adds a dependency layer over MSAL with no benefit
  when MSAL itself is straightforward and Microsoft-maintained.
- `python-jose` for manual JWT validation — unnecessary when MSAL handles token
  validation internally.

**Confidence:** HIGH for MSAL as the correct library. MEDIUM for Flask-Login version — verify
at `https://pypi.org/project/Flask-Login/`.

---

### Layer 4: Kerberos Constrained Delegation (KCD)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pyspnego** | ≥0.10.0 | SPNEGO/Kerberos negotiation for WinRM connections | Provides Kerberos authentication context for PowerShell remote sessions from Python. Preferred over `winkerberos` for its cross-platform surface. |
| **pywinrm** | ≥0.4.3 | WinRM protocol client | Used to establish PSSession equivalent from Python to Exchange Management Shell. Integrates with pyspnego for Kerberos. |
| **gss-ntlmssp** (system package) | OS-level | NTLM/Kerberos GSS-API provider | Required on Windows — installed via the domain join. Not a pip package. |

**KCD flow for this deployment:**

```
Colleague authenticates → Azure AD issues token with UPN
Flask app calls Exchange tools → Needs to impersonate colleague in Exchange
Kerberos Constrained Delegation:
  Service account (svc-exchange-mcp) is delegated to impersonate
  any user to the Exchange PowerShell SPN
  AD: Service account configured with KCD to HTTP/exchprod01.marsh.com
  At call time: S4U2Proxy extension — service account requests ticket
  on behalf of colleague's UPN
```

**Critical AD configuration (not Python-level):**
- Service account `svc-exchange-mcp` must have KCD configured in AD:
  `msDS-AllowedToDelegateTo: http/exchprod01.marsh.com`
- `TRUSTED_TO_AUTH_FOR_DELEGATION` flag on service account
- Exchange PowerShell virtual directory must accept Kerberos
- MCP server host must be domain-joined (project constraint confirmed)

**Alternative (simpler for v1):**
For the initial demo deployment, the architecture doc notes that Basic Auth with a
service account (`EXCHANGE_USER` / `EXCHANGE_PASSWORD`) is the supported fallback.
True KCD (per-user identity pass-through) requires AD configuration that may not be
ready at demo time. The project should plan for Basic Auth in v1 with KCD as a v2
enhancement unless AD delegation is pre-configured.

**What NOT to use:**
- `winkerberos` — Windows-only, C extension, fragile installation. pyspnego abstracts
  this cleanly.
- Manually constructing SPNEGO tokens — use the library.
- Client Credentials flow on the Azure AD side as a substitute for KCD — this gives
  service account identity, not user identity, which defeats the audit trail goal.

**Confidence:** MEDIUM. The KCD component is the highest-risk area in this stack.
The AD configuration complexity is outside Python and depends on enterprise AD team
cooperation. The pyspnego + pywinrm combination is the standard Python pattern, but
version currency should be verified.

---

### Layer 5: Azure OpenAI Client

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **openai** | ≥1.30.0 | Azure OpenAI API client — chat completions with tool use | Project-pinned floor. `AzureOpenAI` class handles the endpoint routing, api-key header injection, and api-version query parameter. Official OpenAI Python SDK — no alternative. |
| **httpx** | ≥0.27.0 | Underlying HTTP transport for the openai SDK | `openai` ≥1.x uses `httpx` internally. Pin explicitly to avoid transitive regression. |

**API version note (IMPORTANT):**
The architecture doc pins `API_VERSION=2023-05-15`. This is the Azure OpenAI API version,
not the package version. As of 2025/2026, newer Azure OpenAI API versions exist
(`2024-02-01`, `2024-08-01-preview`, `2024-10-01-preview`). The MMC gateway may be
pinned to `2023-05-15` by the corporate endpoint configuration. Do NOT change
`API_VERSION` without confirming with the MMC CTS team — the gateway may not support
newer versions.

Tool use (function calling) is supported in `2023-05-15` — this is the MCP tool dispatch
mechanism.

**What NOT to use:**
- `azure-openai` (older Azure SDK package) — superseded by the `openai` package's
  `AzureOpenAI` class. The separate `azure-openai` package is deprecated.
- Direct `requests` / `httpx` calls to the Azure OpenAI endpoint — loses retry logic,
  streaming support, and type safety provided by the SDK.
- `langchain` or `llamaindex` — over-engineered for 15 fixed tools. The `openai` SDK's
  native tool use handles this exactly. Adding an orchestration framework hides the
  tool dispatch logic and makes debugging harder.
- `semantic-kernel` — Microsoft's Python orchestration SDK. Valid for some Azure AI
  scenarios but adds abstraction that conflicts with the clean MCP protocol boundary.

**Confidence:** HIGH. The `openai` SDK is the only correct client for Azure OpenAI.
Version floor of `>=1.30.0` is project-authored and confirmed correct.

---

### Layer 6: PowerShell Execution Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `subprocess` (stdlib) | Python 3.11+ stdlib | Launch PowerShell process, capture stdout/stderr | The architecture doc uses `subprocess` for `run_ps()`. No external library needed for process management on Windows. |
| `asyncio.create_subprocess_exec` | Python 3.11+ stdlib | Async wrapper for PowerShell subprocess | Prevents blocking the event loop during PSSession setup (~2-4s per call). Essential for responsiveness when multiple tool calls are in-flight. |
| PowerShell 5.1 | 5.1 (Windows built-in) | Exchange Management Shell host | Project-pinned. Exchange 2019 Management Shell runs on PS 5.1. PowerShell 7 can also run Exchange cmdlets via compatibility mode but is not required and adds testing surface. |

**PSSession pattern (per-call, no pooling):**
```python
# Per architecture doc decision — no session pooling in v1
script = f"""
$session = New-PSSession -ConfigurationName Microsoft.Exchange \
    -ConnectionUri 'http://exchprod01.marsh.com/PowerShell/' \
    -Authentication Kerberos
Invoke-Command -Session $session -ScriptBlock {{ {ps_commands} }}
Remove-PSSession $session
"""
proc = await asyncio.create_subprocess_exec(
    "powershell.exe", "-NonInteractive", "-Command", script,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
stdout, stderr = await proc.communicate()
```

**What NOT to use:**
- `python-pptx` / `python-docx` — unrelated
- `paramiko` — SSH, not WinRM
- `pypsrp` — PowerShell Remoting Protocol over PSRP. Valid alternative to subprocess
  but heavier. The architecture doc's choice of `subprocess` is simpler and correct
  for this single-host, domain-joined Windows deployment.

**Confidence:** HIGH. `subprocess` + `asyncio` is the correct pattern on Windows.
No library needed beyond stdlib for this layer.

---

### Layer 7: DNS / Email Security Lookups

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **dnspython** | ≥2.6.1 | DMARC, SPF record resolution for `get_dmarc_status` | Project-pinned. `dns.resolver.resolve()` for TXT record lookups. Pure Python, no system DNS library dependency. Handles SERVFAIL, NXDOMAIN gracefully. |

**Pattern:**
```python
import dns.resolver

def get_dmarc_status(domain: str) -> dict:
    try:
        answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
        dmarc_record = next(
            (str(r) for r in answers if "v=DMARC1" in str(r)), None
        )
    except dns.exception.DNSException as e:
        return {"error": str(e)}
```

**What NOT to use:**
- `socket.getaddrinfo` — no TXT record support
- `subprocess` + `nslookup` / `Resolve-DnsName` — fragile, platform-dependent parsing

**Confidence:** HIGH. `dnspython>=2.6.1` is project-authored and correct.

---

### Layer 8: Data Persistence (Conversation History)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **SQLite** (stdlib `sqlite3`) | Python 3.11+ stdlib | Conversation thread storage, message history, user preferences | No external database server needed for an internal single-server deployment. SQLite on local disk is sufficient for the expected load (<100 concurrent users). Zero ops overhead. |
| **Flask-Session** (filesystem or SQLite backend) | ≥0.7 | In-process session state | Use `SESSION_TYPE="sqlalchemy"` with SQLite backend to colocate session and conversation data. |

**Schema sketch:**
```
threads(id, user_upn, title, created_at, updated_at)
messages(id, thread_id, role, content, tool_name, tool_result, timestamp)
```

**What NOT to use:**
- **PostgreSQL / MySQL** — operational overhead is not justified for this scale.
  An internal tool used by one team does not need a separate database server.
- **Redis** for conversation history — acceptable for session caching but adds
  infrastructure dependency. SQLite is simpler for the v1 deployment.
- **In-memory dict** for conversation history — data lost on server restart.
  Users expect history to persist (project requirement).

**Confidence:** HIGH. SQLite is the correct choice for this scale and deployment model.

---

### Layer 9: Secret Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **boto3** | ≥1.34.0 | AWS Secrets Manager client — fetch `AZURE_OPENAI_API_KEY` at startup | Architecture doc specifies secrets sourced from AWS Secrets Manager (`/mmc/cts/azure-openai/api-key`). `boto3` is the only AWS SDK for Python. |
| **python-dotenv** | ≥1.0.0 | `.env` file loader for local development | Never in production — only for local dev. In production, env vars are sourced from Secrets Manager via `boto3`. Pin `python-dotenv` as a dev-only dependency. |

**Startup pattern:**
```python
import boto3, os

def load_secrets():
    if os.getenv("ENVIRONMENT") == "production":
        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret = client.get_secret_value(SecretId="/mmc/cts/azure-openai/api-key")
        os.environ["AZURE_OPENAI_API_KEY"] = secret["SecretString"]
    # else: already set via .env or CI/CD environment
```

**What NOT to use:**
- Hardcoded API keys — explicitly forbidden by project constraints.
- `keyring` — Windows Credential Manager integration; acceptable for local dev but
  not the pattern for a multi-user server deployment.
- Azure Key Vault SDK — the architecture doc specifies AWS Secrets Manager, not AKV.
  The server runs in an AWS-hosted or AWS-connected environment.

**Confidence:** HIGH for boto3 as the correct choice given the AWS Secrets Manager spec.

---

### Layer 10: Development & Tooling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **uv** | ≥0.4.0 | Python package manager and virtualenv | Significantly faster than pip+venv for dependency resolution on Windows. Produces deterministic lockfiles. Recommended for all 2025/2026 Python projects. |
| **pytest** | ≥8.0 | Unit and integration test runner | Standard. `pytest-asyncio` plugin required for async tool handler tests. |
| **pytest-asyncio** | ≥0.23 | Async test support | Required to test `async def` tool handlers without manually running `asyncio.run()`. |
| **ruff** | ≥0.4.0 | Linting and formatting | Replaces flake8 + black + isort. Extremely fast, single config in `pyproject.toml`. |
| **mypy** | ≥1.10 | Static type checking | MCP tool schemas use Pydantic v2 models — mypy catches type mismatches before runtime. |
| **python-dateutil** | ≥2.9.0 | Date parsing for Exchange timestamp fields | Exchange returns dates in various formats. `dateutil.parser.parse()` handles them all. |

**What NOT to use:**
- **pip + requirements.txt** for dependency management — use `uv` + `pyproject.toml`.
  `requirements.txt` is not reproducible without pinning every transitive dependency.
- **poetry** — valid but slower than uv; less traction in 2025/2026 ecosystem.
- **black** separately — ruff now includes a black-compatible formatter.

**Confidence:** MEDIUM. uv adoption trajectory and ruff are solid as of training cutoff
(Aug 2025). Verify uv version at `https://pypi.org/project/uv/`.

---

## Full Dependency Matrix

### Production Dependencies (install order matters for Windows)

```toml
[project]
name = "exchange-mcp"
requires-python = ">=3.11"
dependencies = [
    # MCP protocol
    "mcp>=1.0.0",
    "anyio>=4.3.0",
    "pydantic>=2.5.0",

    # Web framework (chat app)
    "flask>=3.0.0",
    "flask-session>=0.7.0",
    "flask-login>=0.6.3",
    "waitress>=3.0.0",

    # Azure AD / Entra ID SSO
    "msal>=1.28.0",

    # Azure OpenAI
    "openai>=1.30.0",
    "httpx>=0.27.0",

    # DNS lookups
    "dnspython>=2.6.1",

    # Secret management
    "boto3>=1.34.0",

    # Utilities
    "python-dateutil>=2.9.0",
]
```

### Development-Only Dependencies

```toml
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "python-dotenv>=1.0.0",
]
```

### System-Level (not pip — Windows/AD environment)

| Component | Version | Install Method |
|-----------|---------|----------------|
| Python | 3.11 or 3.12 | python.org installer or `winget install Python.Python.3.12` |
| PowerShell | 5.1 (built-in) | Windows built-in; Exchange 2019 uses Windows PS 5.1 |
| Exchange Management Tools | Exchange 2019 build | Installed on management server |
| Active Directory (for KCD) | Windows Server AD | Enterprise AD team configuration |
| AWS CLI / credentials | Latest | For boto3 access to Secrets Manager |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Web framework | Flask 3.x | FastAPI | FastAPI is for JSON APIs, not server-rendered HTML. Jinja2 is non-idiomatic with FastAPI. Flask-Session is more mature. |
| WSGI server | Waitress | Gunicorn | Gunicorn is Unix-only. The deployment is Windows. |
| Session storage | SQLite / Flask-Session | Redis | Redis adds infrastructure dependency. SQLite has zero ops overhead for this scale. |
| Auth library | msal | authlib | msal is Microsoft-maintained, Entra ID-native. authlib is generic and adds a wrapper layer with no benefit. |
| MCP SDK | `mcp` (official) | `fastmcp` | `fastmcp` is a third-party wrapper over the official SDK. Use the official SDK — it is now mature. |
| Orchestration | openai SDK direct | langchain | langchain adds abstraction that hides tool dispatch. 15 fixed tools do not need an orchestration framework. |
| DNS lookups | dnspython | subprocess+nslookup | dnspython is pure Python, structured, handles all DNS exceptions cleanly. |
| Package manager | uv | pip+venv | uv is 10-100x faster resolution, produces lockfiles, is the 2025/2026 standard. |
| Database | SQLite | PostgreSQL | PostgreSQL is over-engineered for an internal single-server tool. SQLite is correct for this scale. |
| Kerberos | pyspnego + pywinrm | winkerberos | winkerberos is a C extension with fragile Windows installation. pyspnego is pure Python SPNEGO. |

---

## Version Verification Checklist

Before pinning versions in `pyproject.toml`, verify current releases:

| Package | Verify At | Training-Data Version | Flag |
|---------|-----------|----------------------|------|
| `mcp` | https://pypi.org/project/mcp/ | 1.x (exact patch unknown) | LOW — fast-moving |
| `flask` | https://pypi.org/project/flask/ | 3.0.x | MEDIUM |
| `msal` | https://pypi.org/project/msal/ | 1.28.x | MEDIUM |
| `openai` | https://pypi.org/project/openai/ | 1.30.x (floor) | HIGH (project-pinned) |
| `dnspython` | https://pypi.org/project/dnspython/ | 2.6.x (floor) | HIGH (project-pinned) |
| `waitress` | https://pypi.org/project/waitress/ | 3.0.x | MEDIUM |
| `uv` | https://pypi.org/project/uv/ | 0.4.x+ | LOW — fast-moving |
| `boto3` | https://pypi.org/project/boto3/ | 1.34.x | MEDIUM |
| `pyspnego` | https://pypi.org/project/pyspnego/ | 0.10.x | LOW — verify |
| `pywinrm` | https://pypi.org/project/pywinrm/ | 0.4.x | LOW — verify |

---

## Critical Stack Decisions with Risk Flags

### DECISION 1: Flask over FastAPI
**Risk:** LOW. Flask 3.x is stable, well-documented, Windows-compatible.
**Watch:** Flask 4.x may ship in 2026 — check for breaking changes before upgrading.

### DECISION 2: Waitress as WSGI server
**Risk:** LOW-MEDIUM. Waitress is single-threaded per worker by default. For production
with >20 concurrent users, configure `threads=8` parameter.
**Configuration:** `waitress.serve(app, host='0.0.0.0', port=5000, threads=8)`

### DECISION 3: Kerberos Constrained Delegation
**Risk:** HIGH. This is the most operationally complex component. True per-user
identity pass-through requires AD team configuration of:
- Service account with `msDS-AllowedToDelegateTo`
- `TRUSTED_TO_AUTH_FOR_DELEGATION` flag
- Exchange PowerShell VDir Kerberos auth enabled
**Mitigation:** Implement Basic Auth with service account for v1 demo. KCD is a v2
enhancement requiring AD team engagement.

### DECISION 4: SQLite for conversation history
**Risk:** LOW. SQLite has write serialization (one writer at a time). For <100
concurrent users, this is not a bottleneck.
**Migration path:** If scale requires it, swap SQLite for PostgreSQL with minimal
schema changes. The Flask-SQLAlchemy abstraction handles this.

### DECISION 5: Per-call PSSession (no pooling)
**Risk:** MEDIUM-HIGH for user experience. 2-4 seconds per tool call is noticeable.
**Watch:** If demo feedback is that latency is unacceptable, the session pool is the
first optimization target. A persistent session pool in v2 would use `asyncio.Queue`
to manage a fixed pool of 3-5 open PSSessions.

---

## Sources

- Project documentation: `C:/xmcp/exchange-mcp-architecture.md` (HIGH — project-authored)
- Project documentation: `C:/xmcp/.planning/PROJECT.md` (HIGH — project-authored)
- Training data (knowledge cutoff August 2025): Flask 3.x, MSAL, openai SDK, boto3,
  uv ecosystem patterns (MEDIUM — treat version numbers as floors, not current)
- Version verification: All packages require PyPI verification before pinning
  (URLs provided above)

**Note on tool availability:** Context7, WebSearch, and WebFetch were unavailable during
this research session. All version claims from training data are marked with appropriate
confidence levels. Verify all package versions at PyPI before production deployment.
