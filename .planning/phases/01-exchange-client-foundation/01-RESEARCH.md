# Phase 1: Exchange Client Foundation - Research

**Researched:** 2026-03-19
**Domain:** Exchange Online PowerShell (EXO V3 module), asyncio subprocess on Windows, dnspython DNS resolution, JSON parsing
**Confidence:** HIGH for subprocess/asyncio and DNS layers; MEDIUM for EXO auth (critical conflict between CONTEXT.md and current Microsoft guidance — see Open Questions)

---

## Summary

Phase 1 builds the foundational `exchange_client.py` module: an async PowerShell subprocess runner, Exchange Online authentication, DNS utilities for DMARC/SPF, and JSON parsing. Three distinct technical subsystems each have well-understood implementation patterns.

**Critical finding on authentication:** The CONTEXT.md decision to use Azure AD app-only auth with a **client secret** conflicts with current Microsoft guidance. As of March 2026, Microsoft's official documentation exclusively describes **certificate-based authentication (CBA)** for app-only Exchange Online PowerShell. Client secret flow is considered unsupported and requires a manual OAuth2 token fetch workaround. This must be resolved before planning locks implementation details.

**Critical finding on EXO module version:** ExchangeOnlineManagement v3.7.0+ introduced a WAM (Web Account Manager) window-handle bug that breaks `Connect-ExchangeOnline` in any subprocess/headless context. The module is currently at v3.9.0. For certificate-based app-only auth, the WAM issue likely does not apply (WAM is the interactive auth flow), but this must be verified. All subprocess invocations must use `-ShowBanner:$false` and `-SkipLoadingFormatData` to reduce startup latency.

**Standard approach:** Python asyncio subprocess (`create_subprocess_exec`) with `asyncio.wait_for` timeout on Windows ProactorEventLoop (the default in Python 3.11). Per-call PowerShell subprocess with explicit `Connect-ExchangeOnline` + work + `Disconnect-ExchangeOnline -Confirm:$false` in a single process invocation. DNS via `dns.asyncresolver` (dnspython 2.8.0) for TXT record lookups with TTL-respecting cache.

**Primary recommendation:** Implement the PowerShell subprocess as a single-script-per-call pattern where each Python invocation spawns a new `powershell.exe` process, runs `Connect-ExchangeOnline` using CBA (certificate thumbprint), executes the cmdlet, pipes output through `ConvertTo-Json -Depth 10`, and terminates. Use certificate-based auth (not client secret), with the certificate installed in the CurrentUser store and private-key permissions granted to the service account.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `dnspython` | 2.8.0 | DNS TXT record resolution (DMARC/SPF) | Official Python DNS library, async support, TTL-aware cache, no external deps |
| `ExchangeOnlineManagement` (PS) | 3.9.0 (PSGallery) | Exchange Online PowerShell module | Microsoft's only supported module for EXO PowerShell access |
| Python stdlib `asyncio` | (built-in, Python 3.11) | Async subprocess execution | No external dep; ProactorEventLoop is Windows default |
| Python stdlib `json` | (built-in) | Parse PowerShell JSON output | No depth limit; handles deeply nested structures from PS |
| Python stdlib `subprocess` / `asyncio.subprocess` | (built-in) | Spawn PowerShell processes | Only option for EXO cmdlets from Python |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mcp` | >=1.0.0 | MCP server (used in later phases) | Not needed in Phase 1 but defines project dependency set |
| `concurrent.futures.ThreadPoolExecutor` | (built-in) | Run async PS calls from Flask's sync context | Flask 3.x + asyncio: use `loop.run_in_executor()` to bridge sync/async |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Certificate-based auth (CBA) | Client secret + manual OAuth token fetch | CBA is officially supported; client secret workaround is unofficial, brittle, and may break with module updates |
| `dns.asyncresolver` (dnspython) | `aiodns` | dnspython has DMARC/SPF parsing support and TTL-aware cache; aiodns is lower-level |
| Per-call PowerShell subprocess | Persistent PSSession pool | Per-call is simpler, avoids session leaks, and aligns with CONTEXT.md decisions; ~2-4s latency is acceptable for v1 |
| dnspython TXT parsing | `checkdmarc` library | `checkdmarc` is higher-level but pulls in more deps; manual regex on TXT strings is straightforward for DMARC/SPF |

### Installation

```bash
# Python dependencies
uv add "dnspython>=2.8.0"
uv add "mcp>=1.0.0"

# PowerShell module (run once in elevated PowerShell, or in the service account context)
Install-Module -Name ExchangeOnlineManagement -Force -Scope CurrentUser
```

---

## Architecture Patterns

### Recommended Project Structure

```
exchange_mcp/
├── exchange_client.py       # Phase 1: EXO client + DNS utilities
├── dns_utils.py             # DMARC/SPF resolver (may be separate module)
├── server.py                # Phase 2+: MCP tool registration
├── app.py                   # Phase 2+: Flask app + chat UI
├── pyproject.toml           # uv project config
├── uv.lock                  # uv lockfile
├── .python-version          # pins 3.11
└── .env.example             # documents required env vars
```

### Pattern 1: Per-Call PowerShell Subprocess (EXO V3 Module)

**What:** Each cmdlet invocation spawns a new `powershell.exe` process that runs a self-contained script: connect → execute → serialize → disconnect → exit. Python reads stdout as JSON.

**When to use:** All Exchange Online cmdlet calls in Phase 1.

**Key insight:** The EXO V3 module uses REST API connections internally (not WinRM). This means:
- No WinRM configuration needed
- `PowerShell.exe` on Windows 5.1 is fully supported
- `-SkipLoadingFormatData` cuts connection time significantly
- `Disconnect-ExchangeOnline -Confirm:$false` must be called to release the REST API session

**Template PowerShell script (built dynamically in Python):**

```powershell
# Source: Microsoft Learn - App-only auth / Connect-ExchangeOnline docs
$ErrorActionPreference = 'Stop'
try {
    Connect-ExchangeOnline `
        -CertificateThumbPrint $env:AZURE_CERT_THUMBPRINT `
        -AppID $env:AZURE_CLIENT_ID `
        -Organization $env:AZURE_TENANT_DOMAIN `
        -ShowBanner:$false `
        -SkipLoadingFormatData

    $result = Get-MailboxStatistics -Identity "user@domain.com" |
        Select-Object DisplayName, TotalItemSize, ItemCount, LastLogonTime |
        ConvertTo-Json -Depth 10

    Write-Output $result
}
catch {
    $errorObj = @{ error = $_.Exception.Message; type = $_.Exception.GetType().FullName }
    Write-Output ($errorObj | ConvertTo-Json)
    exit 1
}
finally {
    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
}
```

**Python async runner:**

```python
# Source: Python docs - asyncio subprocess, verified pattern
import asyncio
import json
import sys

async def run_ps(script: str, timeout: int = 60) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "powershell.exe", "-NonInteractive", "-NoProfile", "-Command", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()  # wait for kill to complete — do not skip
        raise

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", errors="replace").strip())

    return json.loads(stdout.decode("utf-8"))
```

### Pattern 2: Flask + asyncio Bridge (ProactorEventLoop)

**What:** Flask 3.x runs synchronously. PowerShell runner is async. Bridge with `run_in_executor` or a dedicated event loop thread.

**When to use:** When MCP tool handlers (Flask) need to call `run_ps()`.

**Example:**

```python
# Source: Python docs - run_in_executor / asyncio.get_event_loop
import asyncio
from concurrent.futures import ThreadPoolExecutor

# At startup: ensure ProactorEventLoop on Windows (it IS the default on Python 3.11)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Thread pool for blocking Exchange calls from Flask
_executor = ThreadPoolExecutor(max_workers=4)

def call_exchange_sync(script: str, timeout: int = 60) -> dict:
    """Blocking wrapper for use in Flask route handlers."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_ps(script, timeout))
    finally:
        loop.close()
```

### Pattern 3: DNS TXT Lookup with TTL Cache (dnspython)

**What:** Resolve `_dmarc.<domain>` and `<domain>` TXT records using `dns.asyncresolver`, parse the raw strings, cache with TTL.

**When to use:** `get_dmarc_status` and `get_spf_record` tools in later phases; DNS utilities built in Phase 1.

**Example:**

```python
# Source: dnspython 2.8.0 docs - dns.asyncresolver
import dns.asyncresolver
import dns.exception
import time
from functools import lru_cache

resolver = dns.asyncresolver.Resolver()
_dns_cache: dict[str, tuple[list[str], float]] = {}  # key -> (records, expiry)

async def resolve_txt(name: str) -> list[str]:
    """Resolve DNS TXT records with TTL-based cache."""
    now = time.monotonic()
    if name in _dns_cache:
        records, expiry = _dns_cache[name]
        if now < expiry:
            return records

    try:
        answer = await resolver.resolve(name, "TXT")
        records = [b"".join(rdata.strings).decode("utf-8") for rdata in answer]
        ttl = answer.rrset.ttl if answer.rrset else 300
        _dns_cache[name] = (records, now + ttl)
        return records
    except dns.exception.DNSException as e:
        raise LookupError(f"DNS lookup failed for {name}: {e}") from e
```

**DMARC/SPF parsing (do not hand-roll a full validator):**

```python
import re

def parse_dmarc(txt_record: str) -> dict:
    """Parse a DMARC TXT record string into structured dict."""
    # Source: RFC 7489 tag-value pairs
    tags = dict(item.split("=", 1) for item in re.split(r";\s*", txt_record.strip(";"))
                if "=" in item)
    return {
        "version": tags.get("v", ""),
        "policy": tags.get("p", "none"),
        "subdomain_policy": tags.get("sp", tags.get("p", "none")),
        "pct": int(tags.get("pct", 100)),
        "rua": tags.get("rua", ""),
        "ruf": tags.get("ruf", ""),
        "adkim": tags.get("adkim", "r"),
        "aspf": tags.get("aspf", "r"),
        "raw": txt_record,
    }

def parse_spf(txt_record: str) -> dict:
    """Parse an SPF TXT record string into structured dict."""
    # Source: RFC 7208
    mechanisms = []
    all_qualifier = None
    for token in txt_record.split():
        if token.lower() == "v=spf1":
            continue
        if token.lower() in ("+all", "-all", "~all", "?all", "all"):
            all_qualifier = token
        else:
            mechanisms.append(token)
    return {
        "version": "spf1",
        "mechanisms": mechanisms,
        "all": all_qualifier,
        "raw": txt_record,
    }
```

### Pattern 4: Startup Fail-Fast Verification

**What:** On `ExchangeClient.__init__`, immediately run a lightweight cmdlet to verify credentials before the MCP server accepts any tool calls.

**When to use:** Every time `ExchangeClient` is instantiated.

```python
async def verify_connection(self) -> bool:
    """Run Get-OrganizationConfig as a lightweight connectivity check."""
    script = """
    Connect-ExchangeOnline `
        -CertificateThumbPrint $env:AZURE_CERT_THUMBPRINT `
        -AppID $env:AZURE_CLIENT_ID `
        -Organization $env:AZURE_TENANT_DOMAIN `
        -ShowBanner:$false -SkipLoadingFormatData
    Get-OrganizationConfig | Select-Object Name | ConvertTo-Json -Depth 2
    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
    """
    result = await run_ps(script, timeout=30)
    return bool(result.get("Name"))
```

### Anti-Patterns to Avoid

- **Persistent PSSession across calls:** Session leaks, stale auth tokens, and hard-to-debug failures; per-call is required.
- **Capturing only stdout and ignoring stderr:** PowerShell sends non-terminating errors and warnings to stderr; log stderr even on success.
- **Using `proc.terminate()` without `await proc.wait()`:** On Windows, `terminate()` sends `TerminateProcess` which is synchronous, but the process object doesn't update until waited. Always `await proc.wait()` after kill.
- **Using `asyncio.wait_for` timeout on `proc.wait()` alone:** If stdout/stderr pipes are full and not drained, `proc.wait()` will deadlock. Always use `proc.communicate()` (which drains pipes), not `proc.wait()`.
- **Embedding credentials in the PowerShell script string:** Credentials must come from environment variables read inside PowerShell (`$env:VAR`), never interpolated from Python strings.
- **Using `-Depth 2` (the default) in `ConvertTo-Json`:** Exchange cmdlet outputs are frequently nested 3-5 levels deep. Default depth 2 collapses nested objects into `@{Key=Value}` strings. Always use `-Depth 10`.
- **Parsing raw `Get-PSSession` output to check EXO connection state:** EXO V3 uses REST API, not PSSessions. Use `Get-ConnectionInformation` instead.
- **Repeated `Connect-ExchangeOnline / Disconnect-ExchangeOnline` in a loop inside one PS process:** Microsoft documentation explicitly warns this causes memory leaks. Each subprocess must run only one connect-work-disconnect cycle.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DNS async resolution with TTL caching | Custom UDP socket + cache | `dns.asyncresolver` (dnspython) | Handles NXDOMAIN, SERVFAIL, retries, TTL, CNAME chasing, Windows registry resolver config |
| DMARC/SPF TXT record full validation | Custom RFC parser | Simple tag-split regex for Phase 1; `checkdmarc` for Phase 5+ | Full RFC 7208/7489 compliance is complex (macro expansion, DNS lookup limits, redirect chains) |
| OAuth2 token fetch for Exchange | Custom HTTP client + MSAL | Certificate-based auth through `Connect-ExchangeOnline` (handled by module) | The EXO module internally uses MSAL; reimplementing is fragile |
| PowerShell output encoding | Custom encoding detection | Always pass `-NonInteractive -NoProfile` and decode stdout as UTF-8 | PowerShell output encoding is environment-dependent; these flags stabilize it |
| Process timeout and kill | `threading.Timer` | `asyncio.wait_for` + `proc.kill()` + `await proc.wait()` | asyncio pattern is composable with the rest of the async stack |

**Key insight:** The Exchange Online management surface is entirely PowerShell-dependent for v1. There is no Python library that wraps EXO cmdlets directly — the subprocess pattern is the only viable approach without moving to Microsoft Graph API (a larger architectural change).

---

## Common Pitfalls

### Pitfall 1: WAM Window Handle Error (EXO Module 3.7+)

**What goes wrong:** `Connect-ExchangeOnline` throws `"A window handle must be configured"` in headless/subprocess context.

**Why it happens:** Module versions 3.7.0+ integrated WAM (Web Account Manager) for interactive authentication. When `GetConsoleWindow()` returns NULL (no visible console), authentication fails with this error.

**How to avoid:** For **app-only (certificate-based) auth**, WAM is not invoked — the certificate flow bypasses interactive auth entirely. The WAM issue affects interactive (`-UserPrincipalName`) connections, not CBA. Verify this during the proof-of-concept task by using `-CertificateThumbPrint` auth in a subprocess and confirming no WAM error. If it occurs, add `-DisableWAM` to the `Connect-ExchangeOnline` call.

**Warning signs:** Error text contains "window handle" or "WAM"; occurs only in subprocess, not in interactive PowerShell terminal.

### Pitfall 2: ConvertTo-Json Depth Truncation

**What goes wrong:** Nested Exchange objects appear as `@{Property=Value}` strings instead of JSON objects.

**Why it happens:** `ConvertTo-Json` default depth is 2. Exchange cmdlets return objects nested 3-6 levels deep (e.g., `MailboxStatistics.TotalItemSize` is a `ByteQuantifiedSize` object).

**How to avoid:** Always use `ConvertTo-Json -Depth 10` in every PowerShell script. Add a test that verifies `TotalItemSize` is an object with a `Value` key, not a string.

**Warning signs:** Python receives `"@{Value=...}"` strings as JSON values; `json.loads` succeeds but data is wrong.

### Pitfall 3: asyncio Subprocess Deadlock via Pipe Buffer Overflow

**What goes wrong:** `await proc.wait()` hangs indefinitely on large Exchange responses.

**Why it happens:** If stdout/stderr pipes fill before Python reads them, the subprocess blocks waiting to write more data. `proc.wait()` waits for the process to exit, but the process is blocked on the full pipe — classic deadlock.

**How to avoid:** Always use `await proc.communicate()` instead of `await proc.wait()`. `communicate()` drains both pipes concurrently while waiting.

**Warning signs:** Script hangs on large Get-Mailbox calls with hundreds of results; works fine for single-object responses.

### Pitfall 4: Certificate Private Key Permission Error (Non-Admin)

**What goes wrong:** `Connect-ExchangeOnline` with `-CertificateThumbPrint` fails with a `.NET` signing error when run as a non-admin service account.

**Why it happens:** The certificate's private key in the LocalMachine store requires explicit permission grants. Without them, only Administrators can use it.

**How to avoid:** Either:
1. Install the certificate in the **CurrentUser** store of the service account (no permission grant needed), OR
2. Install in LocalMachine store and grant the service account explicit Full Control on the private key via MMC → Certificate Manager → Manage Private Keys.

**Warning signs:** Works in admin PowerShell, fails in non-admin subprocess; error mentions `.NET Desktop` signing or `Could not use the certificate`.

### Pitfall 5: EXO Session Limit Exceeded

**What goes wrong:** `Connect-ExchangeOnline` fails with `"You have exceeded the maximum number of connections allowed: 3"`.

**Why it happens:** Each org/service account is limited to 3 concurrent EXO PowerShell connections. If previous subprocesses didn't properly disconnect (crash, kill, timeout), orphaned sessions accumulate.

**How to avoid:** The `try/finally` block in every PowerShell script must always call `Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue`. Use the `-SkipLoadingFormatData` flag to reduce connection overhead and time. For the proof-of-concept, verify session cleanup with `Get-ConnectionInformation` after each call.

**Warning signs:** Intermittent auth failures after a few hours; error message explicitly mentions "maximum connections".

### Pitfall 6: Client Secret Not Supported Natively

**What goes wrong:** Attempts to pass client secret to `Connect-ExchangeOnline` directly fail — there is no `-ClientSecret` parameter.

**Why it happens:** Microsoft's official app-only auth for EXO PowerShell is certificate-only. The `-AccessToken` workaround (manually fetching a token via `Invoke-RestMethod` against `login.microsoftonline.com/oauth2/v2.0/token`) works but is unsupported and may break with module updates.

**How to avoid:** Use certificate-based authentication. See Open Questions for resolution path.

**Warning signs:** Searching for `-ClientSecret` or `-AppSecret` parameters in `Connect-ExchangeOnline` docs; these do not exist.

### Pitfall 7: PowerShell stdout Encoding on Windows

**What goes wrong:** Non-ASCII characters (e.g., in display names) appear garbled in Python after decoding stdout.

**Why it happens:** PowerShell 5.1 defaults to the system code page (often CP1252 or OEM 437) for stdout encoding.

**How to avoid:** Set output encoding explicitly in the PowerShell script:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```
And decode in Python as `stdout.decode("utf-8")`. Alternatively, use PowerShell 7 which defaults to UTF-8.

---

## Code Examples

### Exchange Client Initialization

```python
# exchange_client.py - verified pattern for phase 1
import asyncio
import json
import os
import sys
from typing import Any

if sys.platform == "win32":
    # Python 3.11 default is already ProactorEventLoop on Windows
    # This is a belt-and-suspenders confirmation, not a change
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

_PS_PREAMBLE = """\
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
Import-Module ExchangeOnlineManagement -ErrorAction Stop
"""

_PS_CONNECT = """\
Connect-ExchangeOnline `
    -CertificateThumbPrint $env:AZURE_CERT_THUMBPRINT `
    -AppID $env:AZURE_CLIENT_ID `
    -Organization $env:AZURE_TENANT_DOMAIN `
    -ShowBanner:$false `
    -SkipLoadingFormatData
"""

_PS_DISCONNECT = """\
Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
"""


class ExchangeClient:
    def __init__(self, timeout: int = 60, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self._verify_env()

    def _verify_env(self):
        required = ["AZURE_CERT_THUMBPRINT", "AZURE_CLIENT_ID", "AZURE_TENANT_DOMAIN"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {missing}")

    async def run_cmdlet(self, cmdlet_script: str) -> Any:
        """Run a single Exchange Online cmdlet and return parsed JSON."""
        script = f"{_PS_PREAMBLE}\ntry {{\n{_PS_CONNECT}\n{cmdlet_script}\n}}\nfinally {{\n{_PS_DISCONNECT}\n}}"
        return await self._run_ps(script)

    async def _run_ps(self, script: str) -> Any:
        """Async subprocess runner with timeout and kill-on-timeout."""
        proc = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NonInteractive", "-NoProfile", "-Command", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"PowerShell call exceeded {self.timeout}s timeout")

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"PowerShell error (exit {proc.returncode}): {err}")

        raw = stdout.decode("utf-8", errors="replace").strip()
        if not raw:
            return {}
        return json.loads(raw)

    async def verify_connection(self) -> bool:
        """Lightweight connectivity check for health endpoint."""
        cmdlet = "Get-OrganizationConfig | Select-Object Name | ConvertTo-Json -Depth 2"
        result = await self.run_cmdlet(cmdlet)
        return bool(result.get("Name"))
```

### DNS DMARC/SPF Lookup

```python
# dns_utils.py - dnspython 2.8.0 async pattern
import asyncio
import time
import dns.asyncresolver
import dns.exception
import dns.rdatatype

_cache: dict[str, tuple[list[str], float]] = {}


async def get_txt_records(name: str) -> list[str]:
    """Return TXT record strings for `name`, respecting TTL cache."""
    now = time.monotonic()
    if name in _cache and now < _cache[name][1]:
        return _cache[name][0]

    try:
        answer = await dns.asyncresolver.resolve(name, dns.rdatatype.TXT)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        _cache[name] = ([], now + 300)  # cache miss for 5 min
        return []
    except dns.exception.DNSException as exc:
        raise LookupError(f"DNS lookup failed: {name} — {exc}") from exc

    records = [
        b"".join(rdata.strings).decode("utf-8")
        for rdata in answer
    ]
    ttl = answer.rrset.ttl if answer.rrset else 300
    _cache[name] = (records, now + ttl)
    return records


async def get_dmarc_record(domain: str) -> dict:
    """Fetch and parse DMARC record for domain."""
    records = await get_txt_records(f"_dmarc.{domain}")
    dmarc_records = [r for r in records if r.lower().startswith("v=dmarc1")]
    if not dmarc_records:
        return {"found": False, "domain": domain}
    return {"found": True, "domain": domain, **parse_dmarc(dmarc_records[0])}


async def get_spf_record(domain: str) -> dict:
    """Fetch and parse SPF record for domain."""
    records = await get_txt_records(domain)
    spf_records = [r for r in records if r.lower().startswith("v=spf1")]
    if not spf_records:
        return {"found": False, "domain": domain}
    return {"found": True, "domain": domain, **parse_spf(spf_records[0])}
```

### uv pyproject.toml Baseline

```toml
# Source: uv project docs - https://docs.astral.sh/uv/guides/projects/
[project]
name = "exchange-mcp"
version = "0.1.0"
description = "Exchange Online MCP server for Marsh McLennan"
requires-python = ">=3.11"
dependencies = [
    "dnspython>=2.8.0",
    "mcp>=1.0.0",
    "flask>=3.0",
    "waitress>=3.0",
]

[tool.uv]
python = "3.11"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `New-PSSession` + WinRM for EXO | `Connect-ExchangeOnline` (REST API, no WinRM) | EXO V3 module v3.0.0 (Sep 2022) | No WinRM config needed; more reliable; REST API timeout is 15 min |
| Basic Auth with `PSCredential` | Certificate-based (CBA) or Modern Auth | EXO -Credential deprecated June 2026 | ROPC/Basic is being blocked; CBA is only automation path |
| Remote PSSession (`Get-PSSession`) | `Get-ConnectionInformation` (EXO V3) | v3.0.0 (Sep 2022) | Session state is no longer in PSSession objects |
| `ConvertTo-Json` default depth (2) | Always explicit `-Depth 10` | N/A (always required) | Default depth 2 corrupts nested Exchange objects |

**Deprecated/outdated:**
- `-Credential` parameter on `Connect-ExchangeOnline`: Removed after June 2026. Do not use.
- `New-PSSession` / `Remove-PSSession` for Exchange Online: Replaced by `Connect-ExchangeOnline` / `Disconnect-ExchangeOnline`.
- `SelectorEventLoop` on Windows: Cannot run subprocesses. `ProactorEventLoop` is the default in Python 3.11 on Windows — no explicit policy set needed, but verification is worthwhile.
- `ExchangeOnlineManagement` v3.7.0 (specific): Has the WAM bug. v3.7.1 reportedly does not fix it. Current v3.9.0 may be fixed or still require `-DisableWAM` for interactive flows (does not affect CBA).

---

## Open Questions

### 1. Client Secret vs. Certificate Authentication (BLOCKING)

**What we know:** CONTEXT.md specifies Azure AD app-only auth with client secret. Microsoft's official documentation for Exchange Online PowerShell only supports certificate-based authentication (CBA) natively. Client secret auth requires a manual OAuth2 token fetch and passing the token via `-AccessToken` parameter — an unsupported workaround.

**What's unclear:** Whether the project owner has an Azure AD app registration with a certificate already, or only a client secret. The environment variables in CONTEXT.md (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`) suggest a client secret was intended.

**Recommendation:** The planner should flag this as a prerequisite. The decision path is:
- **Option A (recommended):** Create a self-signed certificate, attach it to the Azure AD app registration, install it in the CurrentUser certificate store on the Windows host, and use `AZURE_CERT_THUMBPRINT` + `AZURE_CLIENT_ID` + `AZURE_TENANT_DOMAIN` as environment variables. This is the Microsoft-supported path.
- **Option B (workaround):** Use the client secret + manual OAuth2 token fetch pattern (`Invoke-RestMethod` to `login.microsoftonline.com/oauth2/v2.0/token`, then `Connect-ExchangeOnline -AccessToken $token -Organization $org`). This works today but is officially unsupported and may break with future module updates.

**The planner should create a task for the certificate setup as a prerequisite to the subprocess runner task**, or explicitly document that client-secret workaround is the accepted approach.

### 2. WAM Issue with CBA in Subprocess

**What we know:** EXO module v3.7+ has a WAM window-handle issue in headless/subprocess contexts. CBA (certificate auth) may bypass WAM entirely since it doesn't require interactive prompts.

**What's unclear:** Whether the current v3.9.0 module still exhibits the WAM error specifically with `-CertificateThumbPrint` authentication in a subprocess.

**Recommendation:** The proof-of-concept task (01-05 in the roadmap) must explicitly test subprocess execution with CBA. If the WAM error occurs, add `-DisableWAM` to `Connect-ExchangeOnline`. Plan for this as a likely outcome and include it in the task's verification criteria.

### 3. Memory Leak on Repeated Connect/Disconnect

**What we know:** Microsoft docs explicitly warn that "frequent use of `Connect-ExchangeOnline` and `Disconnect-ExchangeOnline` in a single PowerShell session might lead to a memory leak."

**What's unclear:** Whether this applies to separate subprocess invocations (each with a new process) or only within a single persistent PowerShell session.

**Recommendation:** Per-call subprocesses (one process per cmdlet call) should be immune since each process is a fresh memory space. The warning likely applies to scripts that loop `Connect → Disconnect` many times within a single process. Verify with a soak test during implementation.

---

## Sources

### Primary (HIGH confidence)

- Microsoft Learn: App-only authentication in Exchange Online PowerShell — https://learn.microsoft.com/en-us/powershell/exchange/app-only-auth-powershell-v2?view=exchange-ps
- Microsoft Learn: About the Exchange Online PowerShell V3 module — https://learn.microsoft.com/en-us/powershell/exchange/exchange-online-powershell-v2?view=exchange-ps (updated 2026-02-27)
- Python docs: asyncio Subprocess — https://docs.python.org/3/library/asyncio-subprocess.html
- Python docs: asyncio Policies (Windows) — https://docs.python.org/3.11/library/asyncio-policy.html
- dnspython 2.8.0 on PyPI — https://pypi.org/project/dnspython/
- dnspython Resolver docs — https://dnspython.readthedocs.io/en/latest/resolver-class.html

### Secondary (MEDIUM confidence)

- Microsoft Tech Community: Deprecation of -Credential parameter — https://techcommunity.microsoft.com/blog/exchange/deprecation-of-the--credential-parameter-in-exchange-online-powershell/4494584
- David Homer blog: WAM window handle fix — https://david-homer.blogspot.com/2025/01/exchange-online-management-powershell.html (2025)
- David Homer blog: Connect via client secret — https://david-homer.blogspot.com/2023/09/connect-to-exchange-online-powershell.html
- Microsoft Q&A: CertificateThumbprint non-admin error — https://learn.microsoft.com/en-us/answers/questions/1397944/connect-exchangeonline-with-certificate-thumbprint
- uv project docs — https://docs.astral.sh/uv/guides/projects/

### Tertiary (LOW confidence)

- michev.info: Client secret workaround (blog, explicitly labeled unsupported) — https://michev.info/blog/post/2997/connecting-to-exchange-online-powershell-via-client-secret-flow
- Simon Willison TIL: subprocess timeout pattern — https://til.simonwillison.net/python/subprocess-time-limit

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — dnspython and asyncio subprocess are well-documented; EXO module version confirmed from PSGallery
- Architecture patterns: HIGH — subprocess runner pattern is standard Python; PowerShell script structure is from official Microsoft docs
- Authentication method: LOW-MEDIUM — CONTEXT.md specifies client secret, but Microsoft only officially supports certificates; client secret workaround is real but unsupported
- Pitfalls (WAM, depth, pipe deadlock, cert permissions): HIGH — sourced from official docs, active Microsoft Q&A threads, and PSGallery release notes

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (30 days) — exchange module may update; verify current module version before implementation
