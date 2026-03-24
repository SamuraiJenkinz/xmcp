# Technology Stack

**Project:** Exchange Infrastructure MCP Server — Marsh McLennan Companies
**Researched:** 2026-03-19 (original) | Updated: 2026-03-24 (Graph milestone additions)
**Researcher:** GSD Project Researcher

---

## Research Method & Confidence Note

Context7 MCP, WebSearch, and WebFetch tools were unavailable during the original (2026-03-19)
research session.

The 2026-03-24 update used WebSearch and WebFetch to verify Graph API library versions and
permissions. Sources include:

1. Project-owned documentation (`exchange-mcp-architecture.md`, `PROJECT.md`) — HIGH confidence.
2. PyPI official pages (WebFetch verified) — HIGH confidence for current versions.
3. Microsoft Graph official documentation (Microsoft Learn, WebFetch verified) — HIGH confidence
   for API endpoints and required permissions.
4. Training data (knowledge cutoff: August 2025) — MEDIUM confidence for ecosystem context.
   Version numbers from training data alone are flagged LOW confidence.

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
| **Flask-Session** | ≥0.8 | Server-side session storage (filesystem or Redis) | Browser cookies cannot hold conversation history. Flask-Session stores it server-side. Required for multi-thread conversation history. |
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
| **msal** (Microsoft Authentication Library) | ≥1.35.1 | Azure AD / Entra ID OAuth 2.0 / OIDC token acquisition | Official Microsoft Python library. The only supported, Microsoft-maintained path for Entra ID SSO from Python. Current stable: 1.35.1 (released 2026-03-04, verified on PyPI). |
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

**Confidence:** HIGH for MSAL as the correct library. Current pinned version is 1.35.1
(verified against PyPI 2026-03-24).

---

### Layer 3a: Microsoft Graph API Client (NEW — Graph Milestone)

**Decision: Use `msal` + `requests` directly. Do NOT add `msgraph-sdk`.**

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **msal** | ≥1.35.1 (already pinned) | Token acquisition via client credentials flow | `ConfidentialClientApplication.acquire_token_for_client()` is the correct pattern for application-identity Graph calls. No new package needed. |
| **requests** | ≥2.32 (transitive via msal) | HTTP client for Graph REST calls | `requests` is already installed as a transitive dependency of `msal` (verified in the project lockfile: msal 1.35.1 pulls requests 2.32.5). Zero new install cost. |

**Rationale for NOT using `msgraph-sdk`:**

The official Microsoft Graph Python SDK (`msgraph-sdk`, current v1.55.0 as of 2026-02-20) is a
large package. It introduces these dependencies that are not otherwise in this project:

- `azure-identity` — Microsoft's Azure credential library (duplicates MSAL's role)
- `microsoft-kiota-abstractions`, `microsoft-kiota-authentication-azure`,
  `microsoft-kiota-http`, `microsoft-kiota-serialization-json`,
  `microsoft-kiota-serialization-text` — five Kiota packages for the generated client
- `httpx` — a second HTTP client (the project already has the requests-based MSAL path)

For **two Graph endpoints** (`GET /users?$search=...` and `GET /users/{id}/photo/$value`),
the `msgraph-sdk` dependency tree is engineering overhead with no benefit. The Graph API is
a straightforward JSON REST API. Raw `requests` calls are clearer, simpler to debug, and
require no additional packages.

**How it works in practice:**

```python
# graph_client.py — the only new file needed
import msal
import requests

class GraphClient:
    """Application-identity Microsoft Graph client using client credentials flow.

    A single ConfidentialClientApplication is kept as a module-level singleton.
    MSAL's built-in in-memory token cache handles expiry and refresh automatically
    — acquire_token_for_client() returns a cached token until it is within 5 minutes
    of expiry, then silently refreshes.
    """
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    SCOPE = ["https://graph.microsoft.com/.default"]

    def __init__(self, client_id: str, client_secret: str, tenant_id: str) -> None:
        self._app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )

    def _get_token(self) -> str:
        result = self._app.acquire_token_for_client(scopes=self.SCOPE)
        if "access_token" not in result:
            raise RuntimeError(f"Graph token acquisition failed: {result.get('error_description')}")
        return result["access_token"]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def search_users(self, query: str, top: int = 10) -> list[dict]:
        """Search users by displayName, mail, or jobTitle using $search."""
        resp = requests.get(
            f"{self.GRAPH_BASE}/users",
            headers={**self._headers(), "ConsistencyLevel": "eventual"},
            params={
                "$search": f'"displayName:{query}" OR "mail:{query}"',
                "$select": "id,displayName,mail,jobTitle,department,officeLocation",
                "$top": top,
                "$count": "true",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_photo_bytes(self, user_id: str) -> bytes | None:
        """Fetch a user's profile photo as raw bytes. Returns None if no photo."""
        resp = requests.get(
            f"{self.GRAPH_BASE}/users/{user_id}/photos/96x96/$value",
            headers=self._headers(),
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content
```

**Critical note on `$search` and ConsistencyLevel:**

Graph's `$search` on user properties requires the `ConsistencyLevel: eventual` request header.
Without it, the API returns a 400 error. This is a documented requirement as of the Graph v1.0
REST API (verified via Microsoft Learn, 2026-03-24). The header must be on each individual
search request, not just on client initialization.

**Alternatives considered and rejected:**

| Option | Why Rejected |
|--------|-------------|
| `msgraph-sdk` v1.55.0 | Adds 7+ new transitive packages (kiota stack + azure-identity + httpx) for two REST endpoints. Over-engineered. |
| `msgraph-core` (older package) | Deprecated — superseded by `msgraph-sdk`. |
| `httpx` directly | `requests` is already a transitive dependency of `msal`. Using a second HTTP client for identical work adds confusion. |
| OData `$filter` instead of `$search` | `$filter` on displayName requires exact-match or startswith — not suitable for fuzzy colleague lookup. `$search` supports substring matching. |

**Confidence:** HIGH. The MSAL + requests direct pattern is the Microsoft-documented approach
for daemon/service applications calling Graph. Source:
https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-daemon-app-python-acquire-token

---

### Layer 3b: Azure AD App Registration Permissions (NEW — Graph Milestone)

These are Azure portal configuration changes, not Python packages. They must be added to the
existing MMC Entra ID app registration before `graph_client.py` will work.

| Permission | Type | Purpose | Why this, not alternatives |
|------------|------|---------|---------------------------|
| `User.Read.All` | Application (not Delegated) | Read all users' profiles (`/users?$search=...`) | Application permission required for client credentials flow. Delegated `User.ReadBasic.All` would require a logged-in user context — client credentials runs as the app identity, no user context. |
| `ProfilePhoto.Read.All` | Application | Read all users' profile photos (`/users/{id}/photo/$value`) | Least-privilege option for application-level photo access. `User.Read.All` alone does NOT grant photo read in all configurations. |

**Both permissions require admin consent.** They are Application permissions (not Delegated),
which means an Entra ID Global Administrator or Privileged Role Administrator must grant
tenant-wide consent. This is a one-time operation in the Azure portal.

**What NOT to request:**
- `Directory.Read.All` — much broader than needed; will trigger security review.
- `User.ReadWrite.All` — unnecessary write scope.
- `ProfilePhoto.ReadWrite.All` — unnecessary write scope.

**Confidence:** HIGH. Verified directly against Microsoft Graph permissions reference
(Microsoft Learn, WebFetch 2026-03-24).

---

### Layer 3c: Photo Proxy Route (NEW — Graph Milestone)

No new packages needed. The photo proxy is a standard Flask route in `app.py` or a new
`graph_bp` blueprint.

**Pattern:**

```python
# In app.py or a new graph blueprint
import base64
from flask import Response, abort

@app.route("/api/photo/<user_id>")
@login_required
def proxy_photo(user_id: str):
    """Proxy Graph profile photos through Flask to avoid CORS and to add auth."""
    graph = get_graph_client()  # module-level singleton
    photo_bytes = graph.get_photo_bytes(user_id)
    if photo_bytes is None:
        # Return a 1x1 transparent PNG placeholder, not a 404
        # (404 causes broken image icons in the UI)
        abort(404)
    return Response(photo_bytes, mimetype="image/jpeg")
```

**Why proxy through Flask:**
- The browser cannot call `https://graph.microsoft.com` directly — it has no Graph token.
- The Flask route adds the `Authorization: Bearer` header server-side.
- Avoids CORS issues with graph.microsoft.com.
- `@login_required` ensures only authenticated users can fetch photos.

**Caching consideration:** Profile photos rarely change. A 10-minute in-memory cache
(using `functools.lru_cache` keyed on `user_id`) or a simple `dict` with TTL timestamps
will eliminate redundant Graph API calls. Use `cachetools.TTLCache` if you want a
battle-tested TTL dict. `cachetools` is a zero-dependency pure-Python package at ~20KB.

| Tool | Add to deps? | Why |
|------|-------------|-----|
| `cachetools` | Optional | If photo proxy sees repeated requests for the same users; adds `TTLCache`. Pure Python, tiny. |
| In-memory dict with timestamp | Zero-cost alternative | Sufficient for an internal tool with <100 users. |

**Recommendation:** Start with an in-memory dict with TTL timestamps (no new package). Only
add `cachetools` if the dict implementation becomes complex.

---

### Layer 4: Kerberos Constrained Delegation (KCD)

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

### Layer 5: Azure OpenAI Client

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **openai** | ≥2.29.0 | Azure OpenAI API client — chat completions with tool use | Project-pinned floor. `AzureOpenAI` class handles the endpoint routing, api-key header injection, and api-version query parameter. Official OpenAI Python SDK — no alternative. |
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
Version floor of `>=2.29.0` is project-pinned (from pyproject.toml as of 2026-03-24).

---

### Layer 6: PowerShell Execution Layer

(See Layer 4 / KCD — they are the same implementation layer. No new packages.)

---

### Layer 7: DNS / Email Security Lookups

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **dnspython** | ≥2.8.0 | DMARC, SPF record resolution for `get_dmarc_status` | Project-pinned (pyproject.toml: `>=2.8.0`). `dns.resolver.resolve()` for TXT record lookups. Pure Python, no system DNS library dependency. Handles SERVFAIL, NXDOMAIN gracefully. |

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

**Confidence:** HIGH. `dnspython>=2.8.0` is project-pinned (pyproject.toml).

---

### Layer 8: Data Persistence (Conversation History)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **SQLite** (stdlib `sqlite3`) | Python 3.11+ stdlib | Conversation thread storage, message history, user preferences | No external database server needed for an internal single-server deployment. SQLite on local disk is sufficient for the expected load (<100 concurrent users). Zero ops overhead. |
| **Flask-Session** (filesystem backend) | ≥0.8.0 | In-process session state | `SESSION_TYPE="filesystem"` — confirmed in `config.py`. |

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
| **boto3** | ≥1.42.73 | AWS Secrets Manager client — fetch `AZURE_OPENAI_API_KEY` at startup | Project-pinned (pyproject.toml: `>=1.42.73`). `boto3` is the only AWS SDK for Python. |
| **python-dotenv** | ≥1.2.2 | `.env` file loader for local development | Project-pinned (pyproject.toml: `>=1.2.2`). Never in production — only for local dev. |

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
| **pytest** | ≥9.0.2 | Unit and integration test runner | Project-pinned (pyproject.toml). `pytest-asyncio` plugin required for async tool handler tests. |
| **pytest-asyncio** | ≥1.3.0 | Async test support | Project-pinned (pyproject.toml). Required to test `async def` tool handlers without manually running `asyncio.run()`. |
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

## Graph Milestone: Summary of Changes to pyproject.toml

**No new production packages needed.** The Graph API integration requires zero additions
to `[project.dependencies]` because:

1. `msal` is already pinned at `>=1.35.1` — provides `ConfidentialClientApplication`
   and `acquire_token_for_client()`.
2. `requests` is already installed as a transitive dependency of `msal` (confirmed:
   msal 1.35.1 depends on requests 2.32.5 in the project lockfile).

**What does change:**

1. **New file: `exchange_mcp/graph_client.py`** — a `GraphClient` class using the
   pattern documented in Layer 3a above.
2. **New file: `exchange_mcp/graph_tools.py`** (or additions to `tools.py`) — two new
   MCP tool handlers: `search_colleagues` and `get_colleague_profile`.
3. **New route in `chat_app/app.py`** — `GET /api/photo/<user_id>` photo proxy.
4. **New config vars in `config.py`** — `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`,
   `GRAPH_TENANT_ID` (may reuse existing `AZURE_*` vars if the same app registration
   is used for both SSO and Graph application permissions — see note below).

**Same-app vs separate-app registration:**

The existing app registration uses the Authorization Code flow for SSO (delegated
permissions). The Graph client credentials pattern requires Application permissions
(`User.Read.All`, `ProfilePhoto.Read.All`). Both can live on the same app registration.

- **Same registration (recommended):** Add the Application permissions to the existing
  app registration. Simpler ops — one app to manage. The existing `AZURE_CLIENT_ID`,
  `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID` env vars can be reused.
- **Separate registration:** More security isolation, but adds operational complexity
  (two app registrations, two secrets to rotate).

**Recommendation:** Use the same app registration. Internal tools with low security
surface area do not need the additional isolation.

---

## Full Dependency Matrix (Post-Graph Milestone)

### Production Dependencies

```toml
[project]
name = "exchange-mcp"
requires-python = ">=3.11"
dependencies = [
    # MCP protocol
    "mcp>=1.0.0",

    # Web framework (chat app)
    "flask>=3.0",
    "flask-session>=0.8.0",
    "waitress>=3.0",

    # Azure AD / Entra ID SSO + Graph API client
    # NOTE: requests is NOT listed here — it is a transitive dep of msal.
    # If msal ever drops the requests dep, add requests>=2.32 explicitly.
    "msal>=1.35.1",

    # Azure OpenAI
    "openai>=2.29.0",
    "tiktoken>=0.12.0",

    # DNS lookups
    "dnspython>=2.8.0",

    # Secret management
    "boto3>=1.42.73",
    "python-dotenv>=1.2.2",
]
```

### Development-Only Dependencies

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
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
| Graph API client | msal + requests (direct) | `msgraph-sdk` | Adds 7 new transitive packages (kiota stack) for two REST endpoints. Over-engineered. |
| Graph API client | msal + requests (direct) | `msgraph-core` (deprecated) | Superseded by msgraph-sdk; do not use. |
| User search | `$search` with ConsistencyLevel header | `$filter=startsWith(displayName,'...')` | `$filter` with startsWith is exact-prefix only, not substring. `$search` supports proper substring match needed for colleague lookup. |
| Photo size | 96x96 via `/photos/96x96/$value` | Default `/photo/$value` | Default photo is the largest available (up to 648x648). A 96x96 thumbnail is sufficient for profile cards and avoids transmitting large binary payloads. |
| Photo caching | In-memory dict with TTL | `cachetools.TTLCache` | For <100 users, a plain dict is adequate. Only add cachetools if the TTL management code grows complex. |
| App registration | Reuse existing SSO app | Separate app registration | No meaningful security benefit for an internal tool. One registration is simpler to manage. |
| Web framework | Flask 3.x | FastAPI | FastAPI is for JSON APIs, not server-rendered HTML. Jinja2 is non-idiomatic with FastAPI. Flask-Session is more mature. |
| WSGI server | Waitress | Gunicorn | Gunicorn is Unix-only. The deployment is Windows. |
| Session storage | filesystem / Flask-Session | Redis | Redis adds infrastructure dependency. SQLite has zero ops overhead for this scale. |
| Auth library | msal | authlib | msal is Microsoft-maintained, Entra ID-native. authlib is generic and adds a wrapper layer with no benefit. |
| MCP SDK | `mcp` (official) | `fastmcp` | `fastmcp` is a third-party wrapper over the official SDK. Use the official SDK — it is now mature. |
| Orchestration | openai SDK direct | langchain | langchain adds abstraction that hides tool dispatch. 15 fixed tools do not need an orchestration framework. |
| DNS lookups | dnspython | subprocess+nslookup | dnspython is pure Python, structured, handles all DNS exceptions cleanly. |
| Package manager | uv | pip+venv | uv is 10-100x faster resolution, produces lockfiles, is the 2025/2026 standard. |
| Database | SQLite | PostgreSQL | PostgreSQL is over-engineered for an internal single-server tool. SQLite is correct for this scale. |

---

## Version Verification Checklist

Before pinning versions in `pyproject.toml`, verify current releases:

| Package | Verify At | Verified Version | Date Verified | Confidence |
|---------|-----------|-----------------|---------------|------------|
| `msal` | https://pypi.org/project/msal/ | 1.35.1 | 2026-03-24 | HIGH |
| `msgraph-sdk` | https://pypi.org/project/msgraph-sdk/ | 1.55.0 (NOT USED) | 2026-03-24 | HIGH |
| `requests` | transitive via msal | 2.32.5 | 2026-03-24 (lockfile) | HIGH |
| `mcp` | https://pypi.org/project/mcp/ | verify before pinning | — | LOW — fast-moving |
| `flask` | https://pypi.org/project/flask/ | 3.0.x | MEDIUM |
| `openai` | https://pypi.org/project/openai/ | 2.29.0 (floor, pyproject) | HIGH |
| `dnspython` | https://pypi.org/project/dnspython/ | 2.8.0 (floor, pyproject) | HIGH |
| `waitress` | https://pypi.org/project/waitress/ | 3.0.x | MEDIUM |
| `uv` | https://pypi.org/project/uv/ | verify before pinning | LOW — fast-moving |
| `boto3` | https://pypi.org/project/boto3/ | 1.42.73 (floor, pyproject) | HIGH |

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

### DECISION 6 (NEW): Graph Client Credentials — Same App Registration
**Risk:** LOW-MEDIUM. Admin consent is required for `User.Read.All` and
`ProfilePhoto.Read.All` as Application permissions. This is a one-time Azure portal
action that requires a Global Administrator or Privileged Role Administrator.
**Dependency:** The milestone is blocked until this admin consent is granted. The
Python code can be written and unit-tested before consent, but live Graph calls will
return 403 until the permissions are in place.
**Watch:** If the `$search` query returns unexpected results, verify the
`ConsistencyLevel: eventual` header is present and that the Entra directory has
replicated recent changes (replication can lag 30-60s).

### DECISION 7 (NEW): requests over httpx for Graph calls
**Risk:** VERY LOW. `requests` is synchronous and already installed. The Graph calls
in `search_colleagues` and `get_colleague_profile` are synchronous MCP tool handlers
(the MCP server's `handle_call_tool` awaits the async handler, but the Graph calls
themselves can be synchronous within the async handler without blocking issues for
this call volume).
**Watch:** If Graph calls are found to block the event loop under load, wrap them in
`asyncio.get_event_loop().run_in_executor(None, ...)` or switch to `httpx.AsyncClient`.
For an internal tool with <100 users, this is not an expected issue.

---

## Sources

- Project `pyproject.toml` (HIGH — project-authored, verified 2026-03-24)
- Project `uv.lock` (HIGH — lockfile, verified msal 1.35.1 + requests 2.32.5, 2026-03-24)
- Project `chat_app/auth.py`, `chat_app/config.py` (HIGH — confirmed MSAL auth code flow)
- PyPI: https://pypi.org/project/msgraph-sdk/ — v1.55.0 current, verified 2026-03-24
- PyPI: https://pypi.org/project/msal/ — v1.35.1 current, verified 2026-03-24
- Microsoft Learn: https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0
  (HIGH — official Graph API docs, photo endpoints, permissions, verified 2026-03-24)
- Microsoft Learn: https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0
  (HIGH — official Graph API docs, user search, $search ConsistencyLevel requirement, verified 2026-03-24)
- Microsoft Learn: https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-daemon-app-python-acquire-token
  (HIGH — official pattern for MSAL client credentials + Graph, verified 2026-03-24)
- Training data (knowledge cutoff August 2025): ecosystem context (MEDIUM)
