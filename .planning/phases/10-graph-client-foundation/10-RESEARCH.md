# Phase 10: Graph Client Foundation - Research

**Researched:** 2026-03-24
**Domain:** Microsoft Graph API, MSAL Python (client credentials), requests
**Confidence:** HIGH

## Summary

Phase 10 builds a standalone `graph_client.py` module that authenticates to Microsoft Graph using MSAL client credentials flow, caches tokens at module level, and exposes two operations: user search and profile photo retrieval. All decisions are locked (same Azure AD app registration, `msal` + `requests` directly, no msgraph-sdk).

The standard pattern is: a module-level `ConfidentialClientApplication` singleton with its own in-memory `TokenCache`, calling `acquire_token_for_client(["https://graph.microsoft.com/.default"])` before each Graph request. MSAL handles cache automatically since v1.23 — it returns cached tokens and only hits the network when the token has less than 5 minutes remaining (`expires_on < now + 300`). No manual expiry tracking is needed.

The two Graph operations require specific patterns. User search uses `$search` with `ConsistencyLevel: eventual` header (mandatory — without it Graph returns 400). Profile photo retrieval returns `404 Not Found` when no photo exists; the client must catch this and return `None` silently.

**Primary recommendation:** Build `graph_client.py` as a module-level singleton with its own `ConfidentialClientApplication`. Call `acquire_token_for_client` on every request (MSAL cache makes this free on hits). Wrap all Graph calls in a `_graph_request()` helper that adds the Bearer token, handles retries (429/503), and enforces the 10-second timeout.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| msal | 1.34.0 (installed) | Token acquisition + caching for client credentials | Already a dependency; `acquire_token_for_client` is the canonical pattern for app-only auth |
| requests | 2.32.5 (installed) | HTTP calls to Graph REST API | Already a dependency; explicit over sdk |

### No Additional Dependencies

The architecture decision to use `msal` + `requests` directly (rejecting `msgraph-sdk`) is locked. This phase adds **zero** new packages.

**Installation:**
```bash
# Nothing to install — both deps already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure

```
chat_app/
├── graph_client.py    # New module — Graph singleton lives here
config.py              # Add GRAPH_* env vars (reuses AZURE_CLIENT_ID, TENANT_ID)
secrets.py             # Add GRAPH_* keys to secrets passthrough
```

`graph_client.py` belongs in `chat_app/` alongside `auth.py` and `config.py`. It is NOT inside `exchange_mcp/` — Graph features serve the chat app (UI for colleague lookup), not the MCP server.

### Pattern 1: Module-Level Singleton with Own CCA

**What:** One `ConfidentialClientApplication` instance created at import time, stored as a module-level `_cca` variable. The instance owns its own in-memory `TokenCache`.

**Why own CCA, not shared with auth.py:** `auth.py`'s CCA uses per-request `SerializableTokenCache` stored in Flask sessions (delegated/user auth). The Graph CCA uses app-only client credentials flow with an in-memory cache that lives for the process lifetime. These token types are fundamentally different — mixing them would be an antipattern and violates the roadmap success criteria explicitly.

**When to use:** Always for daemon/service patterns accessing Graph as the application, not on behalf of a user.

**Example:**
```python
# Source: Official MSAL Python docs + verified against msal 1.34.0 source
import msal
import requests
import logging

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]

_cca: msal.ConfidentialClientApplication | None = None
_graph_enabled: bool = False


def init_graph(client_id: str, client_secret: str, tenant_id: str) -> None:
    """Initialize Graph client. Call once at app startup after config is loaded."""
    global _cca, _graph_enabled
    if not all([client_id, client_secret, tenant_id]):
        logger.warning(
            "Graph features disabled: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, "
            "or AZURE_TENANT_ID missing."
        )
        return
    _cca = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        # token_cache defaults to in-memory TokenCache() — correct for module singleton
    )
    # Verify admin consent at startup by acquiring a token and decoding roles
    token_result = _cca.acquire_token_for_client(scopes=_GRAPH_SCOPES)
    if "error" in token_result:
        logger.error(
            "Graph token acquisition failed. Check admin consent for "
            "User.Read.All and ProfilePhoto.Read.All. "
            "Grant consent at: https://login.microsoftonline.com/%s/adminconsent"
            "?client_id=%s",
            tenant_id, client_id,
        )
        return
    # Decode JWT roles claim (no external jwt library needed — base64 decode)
    _verify_roles(token_result["access_token"], tenant_id, client_id)
    _graph_enabled = True
```

### Pattern 2: Token Acquisition — MSAL Cache Handles Everything

**What:** Call `_cca.acquire_token_for_client(scopes=_GRAPH_SCOPES)` before EVERY Graph request. Since MSAL Python 1.23, this automatically returns the cached token if it has >5 minutes remaining, or fetches a new one if it is expired or within 5 minutes of expiry.

**CRITICAL VERIFIED FINDING:** MSAL's `TokenCache.search()` at line 1562 in `msal/token_cache.py` contains `if expires_in < 5*60: continue` — tokens with less than 5 minutes remaining are treated as expired and bypassed. A fresh token is requested automatically. The caller never needs to check expiry manually.

**What this means:** No need to store `expires_on` in a module variable and check it. Just call `acquire_token_for_client` — if it succeeds, use the token. If it fails, the client secret has expired or consent was revoked.

```python
# Source: Verified against msal 1.34.0 source code
def _get_token() -> str | None:
    """Return a valid Graph access token, or None if unavailable."""
    if _cca is None:
        return None
    result = _cca.acquire_token_for_client(scopes=_GRAPH_SCOPES)
    if "access_token" in result:
        return result["access_token"]
    # Token refresh failure — client secret expired or consent revoked
    logger.error(
        "Graph token acquisition failed: %s — %s",
        result.get("error"),
        result.get("error_description"),
    )
    return None
```

### Pattern 3: User Search with `$search` and `ConsistencyLevel: eventual`

**What:** `GET /v1.0/users?$search="displayName:{term}" OR "mail:{term}"&$select=...&$top=25&$filter=accountEnabled eq true`

**CRITICAL:** The `ConsistencyLevel: eventual` header is REQUIRED for `$search` on directory objects. Without it, Graph returns `400 Bad Request`. This is per official Microsoft Graph documentation (updated 2026-03-07).

**Search behavior:** For users, `$search` on `displayName` uses tokenized matching (not substring). `$search` on `mail` uses `startsWith` behavior (not full-text). This means searching "john" finds "John Smith" (displayName token match) and "johnd@..." (mail prefix match). It does NOT find "dejohn" in a display name.

**Combining `$search` and `$filter`:** Supported. Graph applies them as logical AND. `$filter=accountEnabled eq true` can be combined with `$search`.

**Note on excluding service accounts / room mailboxes:** There is no single Graph filter property that reliably identifies all service accounts and room mailboxes. The pragmatic approach is `accountEnabled eq true` (filters disabled accounts) and relying on the fact that room/resource mailboxes typically have `userType` set or are not in the user directory. For v1.0, `accountEnabled eq true` is the standard filter for active people. More complex exclusions (userType, mailboxSettings) require additional filtering that can be added in the next phase when profile cards are built.

```python
# Source: Official Graph docs (learn.microsoft.com/en-us/graph/search-query-parameter)
def search_users(term: str) -> list[dict]:
    """Search users by displayName or mail. Returns up to 25 results."""
    token = _get_token()
    if not token:
        return []
    url = f"{_GRAPH_BASE}/users"
    params = {
        "$search": f'"displayName:{term}" OR "mail:{term}"',
        "$select": "id,displayName,mail,jobTitle,department",
        "$filter": "accountEnabled eq true",
        "$top": "25",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "ConsistencyLevel": "eventual",  # REQUIRED for $search on directory objects
    }
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json().get("value", [])
```

### Pattern 4: Profile Photo — Handle 404 Silently

**What:** `GET /v1.0/users/{user_id}/photo/$value` returns raw binary (JPEG/PNG) on success, `404 Not Found` when no photo exists.

**CRITICAL:** Per official Microsoft Graph documentation: "If no photo exists, the operation returns `404 Not Found`." The client MUST treat 404 as a normal condition and return `None` — not raise an exception. This is the roadmap success criterion.

```python
# Source: Official Graph profilephoto docs (learn.microsoft.com/en-us/graph/api/profilephoto-get)
def get_user_photo_bytes(user_id: str) -> bytes | None:
    """Return profile photo bytes, or None if no photo exists."""
    token = _get_token()
    if not token:
        return None
    url = f"{_GRAPH_BASE}/users/{user_id}/photo/$value"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        return None  # Missing photo is normal — no logging
    resp.raise_for_status()
    return resp.content
```

### Pattern 5: Retry with Exponential Backoff and Retry-After

**What:** Wrap Graph calls in a retry loop for 429 (Too Many Requests) and 503 (Service Unavailable). Respect `Retry-After` response header if present.

```python
import time

def _graph_request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict,
    params: dict | None = None,
    max_retries: int = 3,
    timeout: int = 10,
) -> requests.Response:
    """Execute a Graph API request with exponential backoff retry."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.request(
                method, url, headers=headers, params=params, timeout=timeout
            )
            if resp.status_code in (429, 503):
                retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                logger.warning(
                    "Graph API %s (attempt %d/%d). Waiting %ds.",
                    resp.status_code, attempt + 1, max_retries, retry_after,
                )
                time.sleep(retry_after)
                continue
            return resp
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning("Graph request timed out (attempt %d). Retrying in %ds.", attempt + 1, wait)
            time.sleep(wait)
    raise last_exc or RuntimeError("Graph request failed after retries")
```

### Pattern 6: Admin Consent Verification at Startup

**What:** After acquiring the first token, decode the JWT payload (middle part, base64) to read the `roles` claim. Check for `User.Read.All` and `ProfilePhoto.Read.All`.

**Admin consent URL format** (from official Microsoft Entra docs, updated 2026-02-19):
```
https://login.microsoftonline.com/{tenant_id}/adminconsent?client_id={client_id}
```
This URL takes the tenant admin directly to the consent page for the specific application. No `redirect_uri` required.

```python
import base64
import json

def _verify_roles(access_token: str, tenant_id: str, client_id: str) -> None:
    """Decode JWT and verify required roles claim. Log warning if missing."""
    try:
        # JWT middle segment is the payload (base64url encoded)
        payload_b64 = access_token.split(".")[1]
        # Add padding if needed
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        roles = set(payload.get("roles", []))
        required = {"User.Read.All", "ProfilePhoto.Read.All"}
        missing = required - roles
        if missing:
            consent_url = (
                f"https://login.microsoftonline.com/{tenant_id}/adminconsent"
                f"?client_id={client_id}"
            )
            logger.error(
                "Graph admin consent incomplete. Missing roles: %s. "
                "Grant consent at: %s",
                ", ".join(missing),
                consent_url,
            )
    except Exception as exc:
        logger.warning("Could not verify Graph token roles: %s", exc)
```

### Anti-Patterns to Avoid

- **Sharing auth.py's CCA:** `auth.py` creates a new CCA per request with a per-session `SerializableTokenCache`. Graph needs a persistent in-memory cache at module level. Different lifetimes, different token types — do not share.
- **Manual token expiry tracking:** Do not store `token_expiry = time.time() + result["expires_in"]` and check it. MSAL does this internally with a 5-minute buffer. Re-calling `acquire_token_for_client` is idempotent and cheap on cache hits.
- **Raising exceptions on 404 for photos:** Missing profile photos are normal in large organizations. 404 must return `None`, not raise.
- **Forgetting `ConsistencyLevel: eventual`:** `$search` on `/users` will return 400 without this header. It must appear on every search request.
- **Using `msgraph-sdk`:** Rejected decision — do not add this dependency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token caching + auto-refresh | Custom `expires_on` tracking | `msal.acquire_token_for_client()` | MSAL has a verified 5-minute buffer; caches by client_id+scopes+tenant |
| JWT decode for roles verification | PyJWT or similar | `base64.urlsafe_b64decode` on middle segment | JWT payload is just base64url; no signature verification needed for log messages |
| HTTP retries with backoff | Custom retry loop | Use the pattern above with `time.sleep` | Consistent with `exchange_client.py`'s existing retry pattern in the codebase |

**Key insight:** MSAL's `acquire_token_for_client` does everything needed for token lifecycle. The only "manual" work needed is calling it and checking for `"access_token"` in the result.

## Common Pitfalls

### Pitfall 1: Missing ConsistencyLevel Header on Search

**What goes wrong:** `GET /users?$search=...` returns `400 Bad Request` with error message about advanced queries.
**Why it happens:** Graph's `$search` on directory objects (users, groups) requires the client to opt into eventual consistency.
**How to avoid:** Always include `ConsistencyLevel: eventual` header for any request with `$search`. Centralize header construction in `_make_headers()`.
**Warning signs:** 400 response with body mentioning "ConsistencyLevel" or "advanced queries".

### Pitfall 2: Admin Consent Not Granted Before Testing

**What goes wrong:** `acquire_token_for_client` succeeds (returns an access token) but Graph API calls return `403 Forbidden`. The token exists but has no roles.
**Why it happens:** A token can be issued for an app even without admin consent — it just won't have the `roles` claim. Graph enforces permissions at the API level, not during token issuance.
**How to avoid:** Verify roles at startup using the JWT decode pattern. Log clearly and disable Graph features if roles are missing.
**Warning signs:** 403 on Graph calls despite valid access token; `roles` claim is empty or missing in token payload.

### Pitfall 3: Token Acquisition "Succeeds" but Returns Error Dict

**What goes wrong:** Code checks `if result:` and proceeds, but `result` is `{"error": "invalid_client", "error_description": "..."}` — truthy but erroneous.
**Why it happens:** MSAL returns a dict always; errors are in the dict, not raised as exceptions.
**How to avoid:** Always check `if "access_token" in result`, never `if result`.
**Warning signs:** Graph calls fail with `None` bearer token or `Authorization: Bearer None`.

### Pitfall 4: Forgetting the Module is Not Reinitialized on Config Change

**What goes wrong:** Changing `AZURE_CLIENT_SECRET` in `.env` doesn't take effect until the process restarts.
**Why it happens:** `_cca` is set once at `init_graph()` call. Flask server must restart.
**How to avoid:** Document this clearly. The `init_graph()` startup warning covers the "secret missing" case; expired secrets log clearly on token failure.

### Pitfall 5: $search Tokenization Is Not Substring Search

**What goes wrong:** Searching "john" does not find "johnathan" if "johnathan" is a single token. Searching "son" does not find "Johnson".
**Why it happens:** Graph's `$search` uses word tokenization on `displayName` — it splits on spaces, casing changes, and symbols. It does NOT do substring matching.
**How to avoid:** Accept this behavior and document it. For the colleague lookup use case (people type a name fragment), prefix tokenization is usually sufficient. Searching "jon" finds users whose displayName contains a token starting with "jon".
**Warning signs:** Users report that search "misses" names that clearly contain the search term.

### Pitfall 6: Race Condition on Module Initialization

**What goes wrong:** If `init_graph()` is called concurrently (e.g., multiple threads at Flask startup), `_cca` could be set twice or not at all.
**Why it happens:** Flask's `create_app()` is single-threaded at startup, but this is worth noting.
**How to avoid:** Call `init_graph()` once in `create_app()` before the app serves requests (same pattern as `init_mcp()` and `init_openai()`). No thread-locking required given Flask's startup sequence.

## Code Examples

### Complete `_make_headers()` helper

```python
# Pattern that ensures ConsistencyLevel is always present for search
def _make_headers(*, search: bool = False) -> dict[str, str] | None:
    """Return request headers with Bearer token, or None if Graph is disabled."""
    token = _get_token()
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    if search:
        headers["ConsistencyLevel"] = "eventual"
    return headers
```

### Startup verification in `create_app()`

```python
# In chat_app/app.py, following the pattern of init_mcp() and init_openai()
from chat_app.graph_client import init_graph
from chat_app.config import Config

try:
    init_graph(
        client_id=Config.AZURE_CLIENT_ID,
        client_secret=Config.AZURE_CLIENT_SECRET,
        tenant_id=Config.AZURE_TENANT_ID,
    )
except Exception as exc:
    logger.error("Graph client initialization failed (degraded mode): %s", exc)
```

### Config additions needed

```python
# In chat_app/config.py — no new env vars needed for same-app-registration case
# AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID already exist
# Just add Graph-specific settings:
GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
GRAPH_SEARCH_MAX_RESULTS: int = 25
GRAPH_TIMEOUT: int = 10
```

### secrets.py additions needed

```python
# In chat_app/secrets.py load_secrets() keys list — no new secrets for same-app-registration
# AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID are already loaded
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual token expiry check | MSAL auto-cache since v1.23 | MSAL 1.23 (2022) | No custom expiry tracking needed |
| `adal` library (deprecated) | `msal` library | 2020 | adal is end-of-life; msal is the standard |
| Bearer token only for $search | Must add `ConsistencyLevel: eventual` | Graph v1.0 (2020+) | Without header, advanced queries fail |

**Deprecated/outdated:**
- `adal`: Microsoft retired the Azure ADAL libraries in June 2023. Already using MSAL correctly.

## Open Questions

1. **Excluding room mailboxes and service accounts from search**
   - What we know: `accountEnabled eq true` filters disabled accounts. Room mailboxes in Exchange Online appear in the user directory with `userType` = `Member` but have `accountEnabled = false` (when resource mailboxes are disabled accounts). However, some environments configure room mailboxes with enabled accounts.
   - What's unclear: Whether the customer's tenant has room/resource mailboxes as enabled accounts. A compound filter `accountEnabled eq true` may be sufficient; if not, `userPurpose ne 'room'` or checking `mailboxSettings.userPurpose` requires a separate Graph call.
   - Recommendation: Implement with `accountEnabled eq true` only for Phase 10. Add room/service exclusion in the Phase 11 profile card work if users report noise in results.

2. **Token cache persistence across restarts**
   - What we know: The in-memory `TokenCache` is lost on process restart, requiring a fresh token acquisition on each startup.
   - What's unclear: This is not a problem in practice — the first request after restart will fetch a new token (< 1 second). No persistent cache is needed for a long-running server.
   - Recommendation: No action needed. In-memory cache is correct.

## Sources

### Primary (HIGH confidence)

- Official MSAL Python docs — `acquire_token_for_client` behavior, token cache auto-refresh: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- MSAL Python 1.34.0 source code (`msal/token_cache.py` line 1562): `if expires_in < 5*60: continue` — verified 5-minute refresh buffer
- MSAL Python 1.34.0 source code (`msal/application.py` line 422): `self.token_cache = token_cache or TokenCache()` — default in-memory cache
- MSAL Python 1.34.0 source code (`msal/application.py`): `acquire_token_for_client` calls `_acquire_token_silent_with_error` which checks cache first
- Graph user list API docs: https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0 — ConsistencyLevel required for $search
- Graph $search docs: https://learn.microsoft.com/en-us/graph/search-query-parameter (updated 2026-03-07) — tokenization behavior, $search + $filter combining
- Graph advanced queries docs: https://learn.microsoft.com/en-us/graph/aad-advanced-queries (updated 2026-03-07) — ConsistencyLevel requirement
- Graph profilephoto-get docs: https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0 — 404 when no photo, `ProfilePhoto.Read.All` permission
- Admin consent URL format: https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent (updated 2026-02-19) — `https://login.microsoftonline.com/{tenant_id}/adminconsent?client_id={client_id}`

### Secondary (MEDIUM confidence)

- Existing codebase patterns: `exchange_client.py` retry logic with `asyncio.sleep(2 ** attempt)` — mirrored for synchronous Graph retries using `time.sleep`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from installed packages and pyproject.toml
- MSAL token caching: HIGH — verified directly from installed MSAL 1.34.0 source code
- Graph API patterns: HIGH — verified from official Microsoft Graph docs (updated 2026)
- ConsistencyLevel requirement: HIGH — multiple official sources confirm, updated 2026-03-07
- 404 on missing photo: HIGH — official profilephoto-get docs explicitly state this
- Admin consent URL: HIGH — official Entra docs confirm exact format
- Search tokenization behavior: HIGH — official $search docs describe tokenization algorithm
- Pitfalls: MEDIUM — combination of official docs and code inspection

**Research date:** 2026-03-24
**Valid until:** 2026-06-24 (Graph API patterns are stable; MSAL major version change would invalidate caching section)
