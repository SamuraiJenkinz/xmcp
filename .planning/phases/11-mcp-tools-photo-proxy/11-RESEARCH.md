# Phase 11: MCP Tools + Photo Proxy - Research

**Researched:** 2026-03-24
**Domain:** MCP tool registration, Microsoft Graph API, Flask photo proxy, in-memory caching, SVG generation
**Confidence:** HIGH

---

## Summary

Phase 11 wires the verified Graph client (Phase 10) into two MCP tool registrations and adds a Flask photo proxy route. The codebase already contains all required building blocks: `graph_client.py` has `search_users()` and `get_user_photo_bytes()`, `exchange_mcp/tools.py` has the TOOL_DEFINITIONS/TOOL_DISPATCH pattern, and `auth.py` has the `@login_required` decorator. Three gaps need filling:

1. `graph_client.py` has no `get_user_profile()` function — it must be added to fetch user detail fields plus manager name via `$expand=manager`.
2. `exchange_mcp/tools.py` needs two new tool definitions appended to `TOOL_DEFINITIONS` and two async handler functions added to `TOOL_DISPATCH`.
3. `chat_app/app.py` needs a `/api/photo/<user_id>` route with `@login_required`, photo caching, and SVG placeholder generation.

The architectural constraint is significant: `exchange_mcp` runs as a subprocess and currently has no cross-imports with `chat_app`. However, because both packages live in the same `uv` project (single `pyproject.toml`), the subprocess CAN import `chat_app.graph_client` — `uv run python -m exchange_mcp.server` puts both packages on the Python path.

**Primary recommendation:** Import `chat_app.graph_client` functions directly from the new tool handlers in `exchange_mcp/tools.py`. This avoids duplicating Graph API code and matches the "two REST endpoints, already have both deps" v1.1 decision.

---

## Standard Stack

### Already in pyproject.toml (no new deps needed)
| Library | Version | Purpose | Role in Phase 11 |
|---------|---------|---------|-----------------|
| `mcp` | >=1.0.0 | MCP server SDK | Tool registration via `mcp.types.Tool` |
| `msal` | >=1.35.1 | Azure AD auth | Already used in `graph_client.py` |
| `requests` | (transitive) | HTTP client | Already used in `graph_client.py` |
| `flask` | >=3.0 | Web framework | Photo proxy route |

**No new dependencies required for this phase.**

### Stdlib used in Phase 11
| Module | Purpose |
|--------|---------|
| `time` | TTL cache expiry check |
| `hashlib` or `hash()` | Cache key from user_id |
| `threading.Lock` | Thread-safe cache access (Flask is multi-threaded) |

---

## Architecture Patterns

### Pattern 1: MCP Tool Definition (existing pattern — follow exactly)

```python
# Source: exchange_mcp/tools.py TOOL_DEFINITIONS list
types.Tool(
    name="search_colleagues",
    description=(
        "Search for colleagues by name or email address. "
        "Use for name lookups: 'Find John Smith', 'Who is alice@company.com?'. "
        "Returns up to 10 results with name, job title, department, and email. "
        "Does NOT return detailed profile or photo — use get_colleague_profile for that."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Name or email address to search for.",
            }
        },
        "required": ["query"],
    },
),
```

### Pattern 2: MCP Tool Handler (existing async pattern)

All existing handlers follow the signature `async def _handler(arguments: dict, client: ExchangeClient | None) -> dict`. The new Graph handlers will receive `client` (the ExchangeClient) but will ignore it — Graph access goes through `chat_app.graph_client` functions instead.

```python
# Source: exchange_mcp/tools.py handler pattern
async def _search_colleagues_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    query = arguments.get("query", "").strip()
    if not query:
        return {"message": "No query provided."}

    # graph_client functions are synchronous — use asyncio.to_thread
    import asyncio
    from chat_app.graph_client import is_graph_enabled, search_users

    if not is_graph_enabled():
        return {"message": "Colleague search is not available (Graph not configured)."}

    results = await asyncio.to_thread(search_users, query)
    ...
```

**Critical:** `graph_client.py` is synchronous (`requests` + `time.sleep`). Calling it directly from an `async def` handler blocks the event loop. Use `asyncio.to_thread()` to run it in a thread pool.

### Pattern 3: TOOL_DISPATCH Registration (existing pattern)

```python
# Source: exchange_mcp/tools.py lines 1859-1875
TOOL_DISPATCH: dict[str, Any] = {
    ...
    "search_colleagues": _search_colleagues_handler,
    "get_colleague_profile": _get_colleague_profile_handler,
}
```

### Pattern 4: Graph API — Manager Expansion

The Graph API supports `$expand=manager` on a user request to fetch the manager in a single call:

```
GET /v1.0/users/{id}?$select=displayName,jobTitle,...&$expand=manager($select=displayName)
```

Response shape:
```json
{
  "displayName": "Jane Smith",
  "jobTitle": "Engineer",
  "manager": {
    "displayName": "Bob Jones"
  }
}
```

If the user has no manager, `manager` is absent from the response. The `$expand=manager` approach avoids a second HTTP call.

**Note:** The existing `graph_client.py` has no `get_user_profile()` function. It must be added to `chat_app/graph_client.py` alongside `search_users()` and `get_user_photo_bytes()`.

### Pattern 5: Photo Proxy Route (Flask)

```python
# In chat_app/app.py create_app(), following existing route pattern
@app.route("/api/photo/<user_id>")
@login_required
def photo_proxy(user_id):
    from flask import Response
    from chat_app.graph_client import get_user_photo_bytes
    from chat_app._photo_cache import get_cached_photo  # or inline cache

    data = get_cached_photo(user_id)  # returns bytes or None
    if data is None:
        data = get_user_photo_bytes(user_id)  # returns bytes or None
        # cache result (even None = no photo)

    if data is None:
        svg = _generate_initials_svg(user_id)  # placeholder
        return Response(svg, status=200, mimetype="image/svg+xml")

    return Response(data, status=200, mimetype="image/jpeg")
```

### Pattern 6: In-Memory TTL Cache

Simple thread-safe dict cache for photo bytes:

```python
import threading
import time

_photo_cache: dict[str, tuple[bytes | None, float]] = {}  # {user_id: (data, expires_at)}
_cache_lock = threading.Lock()
_PHOTO_TTL = 3600  # 1 hour

def get_cached_photo(user_id: str) -> bytes | None | _MISS:
    with _cache_lock:
        entry = _photo_cache.get(user_id)
        if entry is None:
            return _MISS  # sentinel: not in cache
        data, expires_at = entry
        if time.time() > expires_at:
            del _photo_cache[user_id]
            return _MISS
        return data  # may be None (= user has no photo, cached)

def cache_photo(user_id: str, data: bytes | None) -> None:
    with _cache_lock:
        _photo_cache[user_id] = (data, time.time() + _PHOTO_TTL)
```

Use a sentinel object (`_MISS = object()`) to distinguish "not cached" from "cached as None (no photo)".

### Pattern 7: SVG Initials Placeholder

Generated server-side from `user_id`. Since user_id is a GUID (not a name), initials must come from the display name in the profile, or fall back to a "?" if no name is available. **Better approach:** accept display name hint (or derive it from cache), or just return a generic colored icon.

Since the photo proxy receives only `user_id`, and the proxy does not have the user's name at call time, two options exist:

1. Generate a generic colored placeholder based on `user_id` hash (deterministic color, no initials)
2. Accept an optional `display_name` query param from the caller

**Recommendation:** Use option 1. Hash `user_id` to pick a color from a fixed palette. Render "?" or a silhouette character. The CONTEXT.md specifies "initials" but the proxy route only receives a GUID — you cannot reliably get initials without another Graph call. Avoid the extra Graph call for placeholder generation.

Alternative: during `get_colleague_profile`, return `photo_url` + the name; the frontend can pass `?name=Jane+Smith` to the proxy and the proxy renders initials from the first letters. This keeps the proxy stateless.

### Pattern 8: Photo URL Construction

The `photo_url` returned by `get_colleague_profile` should be a URL that the browser can call directly. Since the photo proxy requires `@login_required`, the URL format is:

```python
photo_url = f"/api/photo/{user_id}"
```

This is a relative URL — safe for same-origin use. The tool returns this string; the LLM relays it; the UI renders `<img src="/api/photo/...">`.

### Pattern 9: `get_user_photo_bytes` vs 96x96

The existing `get_user_photo_bytes` in `graph_client.py` uses `/users/{id}/photo/$value` (no size). The CONTEXT.md specifies `/photos/96x96/$value` for the proxy. Two approaches:

1. Add a second function `get_user_photo_96(user_id)` that hits `/photos/96x96/$value`
2. Add a `size` parameter to `get_user_photo_bytes`

**Recommendation:** Add `get_user_photo_96()` as a new function in `graph_client.py` specifically for the proxy route. Keeps the existing function unchanged (no risk to Phase 10 tests).

### Recommended Project Structure Changes

```
chat_app/
├── app.py              # ADD: /api/photo/<user_id> route + cache + SVG
├── graph_client.py     # ADD: get_user_profile(), get_user_photo_96()
└── ...

exchange_mcp/
├── tools.py            # ADD: search_colleagues + get_colleague_profile
│                       #      Tool definitions + handler functions + TOOL_DISPATCH entries
└── server.py           # MINOR: update tool count comment (15 → 17)
```

### Anti-Patterns to Avoid

- **Blocking the MCP event loop:** Calling synchronous `graph_client` functions directly in `async def` handlers without `asyncio.to_thread()`. This stalls all MCP tool calls.
- **Returning photo bytes in tool result:** Tool must return `photo_url` string. Binary data in LLM context violates PROF-05 and would massively inflate tokens.
- **Returning 404 from photo proxy:** Must return HTTP 200 with placeholder when no photo. The frontend treats any non-200 as broken image.
- **Importing `chat_app.graph_client` at module level in `exchange_mcp/tools.py`:** Prefer importing inside the handler function or at function call time to avoid import-time Config dependency (Config reads `os.environ` at class definition time, which is fine, but keeping the import local is cleaner).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token caching for Graph API | Custom cache | MSAL built-in | `_cca.acquire_token_for_client()` checks its own cache — call it per request |
| Photo byte caching | Redis/disk cache | In-memory dict + TTL | Single-process Flask app, no persistence needed, TTL dict is sufficient |
| SVG rendering library | `reportlab`, `cairosvg` | Inline f-string SVG | SVG is a text format, a simple colored circle with text is 5 lines of Python |
| Thread safety for cache | Full locking framework | `threading.Lock()` | Single lock around cache dict reads/writes is enough |
| Manager lookup | Second HTTP request | `$expand=manager` | Graph API handles in one request |

---

## Common Pitfalls

### Pitfall 1: Cross-package import at module scope in exchange_mcp

**What goes wrong:** `from chat_app.graph_client import ...` at the top of `exchange_mcp/tools.py` triggers Config class evaluation, which reads `os.environ` immediately. In some test environments or if the subprocess starts before environment variables are set, this silently uses empty strings.

**Why it happens:** Python evaluates class-level assignments at import time. `Config.AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")` runs when `chat_app.config` is first imported.

**How to avoid:** Import `chat_app.graph_client` inside the handler function, not at module scope in `exchange_mcp/tools.py`. Or import the specific function only (not the Config object).

**Warning signs:** `init_graph()` logs "missing config vars" in the MCP server stderr despite env vars being set in the parent Flask process.

### Pitfall 2: asyncio.to_thread not awaited

**What goes wrong:** The handler returns a coroutine object instead of the result.

**How to avoid:** Always `await asyncio.to_thread(sync_fn, arg)`.

### Pitfall 3: Missing `asyncio` import in tools.py

**What goes wrong:** `asyncio.to_thread` raises `NameError`.

**How to avoid:** `import asyncio` at the top of `exchange_mcp/tools.py` (not currently imported there).

### Pitfall 4: Cache stores None without sentinel distinction

**What goes wrong:** A user with no photo has `None` cached. On cache hit, the code interprets `None` as "cache miss" and calls Graph API again on every request.

**How to avoid:** Use a sentinel object (e.g., `_MISS = object()`) to distinguish "not cached" from "cached as no-photo (None)".

### Pitfall 5: login_required redirects API calls to login page

**What goes wrong:** The existing `login_required` decorator redirects to `url_for("index")` on failure. For `/api/photo/` requests made via `<img src>` tags from the browser, the redirect returns an HTML page that the browser renders as a broken image.

**Why it happens:** The `@login_required` decorator always redirects; it doesn't detect XHR vs. browser navigation.

**How to avoid:** For the photo proxy, check `session.get("user")` and return 401 with empty body if not set (or let the redirect happen — a 302 to the login page will cause the browser to navigate away, which is acceptable behavior for an unauthenticated direct URL hit). The CONTEXT.md success criterion says "401/302-to-login", so the existing redirect behavior of `login_required` satisfies the requirement.

### Pitfall 6: search_colleagues returns user IDs in result

**What goes wrong:** The search handler passes `graph_client.search_users()` results directly through, which includes `id` fields. The CONTEXT.md decision says search results must NOT include user ID.

**Why it happens:** `search_users()` in `graph_client.py` returns raw Graph API fields including `id`.

**How to avoid:** The handler must strip `id` from each result before returning. Map to `{name, jobTitle, department, email}` only.

### Pitfall 7: Empty string fields included in profile result

**What goes wrong:** Profile result contains `{"officeLocation": ""}` when the user has no office location. LLM may say "their office location is blank" rather than "no office location listed".

**How to avoid:** Omit keys where the value is falsy (`None`, `""`, `[]`). The CONTEXT.md decision is explicit: "Missing fields are omitted from the result (no null keys)."

### Pitfall 8: Photo proxy caches at wrong granularity

**What goes wrong:** Cache key is the raw user_id GUID. If the same user is requested before and after their photo is uploaded, the cached `None` persists until TTL expires.

**Why it happens:** This is expected TTL behavior.

**How to avoid:** This is acceptable and documented. 1-hour TTL means up to 1-hour delay for new photos to appear. Cache eviction is not required in v1.

---

## Code Examples

### search_colleagues handler (complete pattern)

```python
# Source: deduced from existing _ping_handler + graph_client.search_users patterns
import asyncio
from chat_app.graph_client import is_graph_enabled, search_users as _search_users

async def _search_colleagues_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    query = arguments.get("query", "").strip()
    if not query:
        return {"message": "Please provide a search query."}

    if not is_graph_enabled():
        return {"message": "Colleague search is not available — Graph not configured."}

    raw = await asyncio.to_thread(_search_users, query)

    if not raw:
        return {"message": f"No colleagues found matching '{query}'."}

    results = []
    for user in raw[:10]:  # enforce max 10 — Config.GRAPH_SEARCH_MAX_RESULTS may be 25
        entry: dict[str, Any] = {}
        if user.get("displayName"):
            entry["name"] = user["displayName"]
        if user.get("jobTitle"):
            entry["jobTitle"] = user["jobTitle"]
        if user.get("department"):
            entry["department"] = user["department"]
        if user.get("mail"):
            entry["email"] = user["mail"]
        # Deliberately exclude "id" — LLM must call get_colleague_profile to get details
        results.append(entry)

    return {"results": results, "count": len(results)}
```

### SVG initials placeholder (server-side generation)

```python
# Deterministic color from user_id hash; no external assets
_PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
    "#9c755f", "#bab0ac",
]

def _generate_placeholder_svg(user_id: str, initials: str = "?") -> str:
    color = _PALETTE[hash(user_id) % len(_PALETTE)]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">'
        f'<circle cx="48" cy="48" r="48" fill="{color}"/>'
        f'<text x="48" y="48" dominant-baseline="central" text-anchor="middle" '
        f'font-size="38" font-family="sans-serif" fill="white">{initials}</text>'
        f'</svg>'
    )
```

The `initials` parameter can be `"?"` if no name is available, or computed from a display name if available (e.g., "JS" from "Jane Smith"). Since the proxy only receives `user_id`, initials default to `"?"` unless the `display_name` query param is provided by the caller.

### get_user_profile function (to be added to graph_client.py)

```python
def get_user_profile(user_id: str) -> dict | None:
    """Fetch detailed profile for a user including manager display name.

    Uses $expand=manager to retrieve manager info in a single request.
    Returns None (not []) on error — callers can treat None as "unavailable".
    """
    if not _graph_enabled or not user_id:
        return None

    headers = _make_headers()
    if headers is None:
        return None

    url = f"{Config.GRAPH_BASE_URL}/users/{user_id}"
    params = {
        "$select": "id,displayName,mail,jobTitle,department,officeLocation,businessPhones",
        "$expand": "manager($select=displayName)",
    }

    try:
        resp = _graph_request_with_retry("GET", url, headers=headers, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Graph get_user_profile failed for user %r: %s", user_id, exc)
        return None
```

### get_user_photo_96 function (to be added to graph_client.py)

```python
def get_user_photo_96(user_id: str) -> bytes | None:
    """Retrieve the 96x96 profile photo for a user as raw bytes.

    Uses /photos/96x96/$value endpoint — smaller payload than the default photo.
    Returns None silently on HTTP 404 (user has no photo).
    """
    if not _graph_enabled or not user_id:
        return None

    headers = _make_headers()
    if headers is None:
        return None

    url = f"{Config.GRAPH_BASE_URL}/users/{user_id}/photos/96x96/$value"

    try:
        resp = _graph_request_with_retry("GET", url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        logger.error("Graph get_user_photo_96 failed for user %r: %s", user_id, exc)
        return None
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| Passing binary photo data to LLM | Return `photo_url` string, serve bytes via proxy | PROF-05 compliance — binary never enters LLM context |
| Per-request Graph token | MSAL `acquire_token_for_client()` with internal cache | No extra code needed, MSAL handles refresh |
| Generic profile photo silhouette | SVG with initials or hash-colored circle | More personal feel per CONTEXT.md |

---

## Open Questions

1. **Initials in SVG placeholder when proxy only has user_id**
   - What we know: photo proxy route is `/api/photo/<user_id>`. The user_id is a GUID.
   - What's unclear: How to get the person's name to generate initials without a second Graph call in the proxy handler.
   - Recommendation: Accept optional `?name=First+Last` query param. The `get_colleague_profile` tool constructs `photo_url` and can embed the name. The photo handler splits on space and takes first letters. If absent, renders `"?"`.

2. **GRAPH_SEARCH_MAX_RESULTS is 25 in Config vs 10 per CONTEXT.md**
   - What we know: `Config.GRAPH_SEARCH_MAX_RESULTS = 25` but CONTEXT.md says max 10 results.
   - What's unclear: Should Config be changed to 10, or should the handler slice to 10?
   - Recommendation: The handler slices `raw[:10]` without changing Config (Config controls the Graph API call limit; the tool may apply a stricter cap). This is more flexible.

3. **Server startup validation with Graph tools**
   - What we know: `server.py` validates Exchange connectivity at startup. It does NOT validate Graph.
   - What's unclear: Should the startup validation also check `is_graph_enabled()`?
   - Recommendation: Log a warning at startup if Graph is disabled, but don't fail startup — the tool handlers already return graceful "not available" messages. No code change to `server.py` startup logic.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection: `chat_app/graph_client.py` — confirmed `search_users()` and `get_user_photo_bytes()` exist; `get_user_profile()` does NOT exist yet
- Direct codebase inspection: `exchange_mcp/tools.py` — confirmed TOOL_DEFINITIONS pattern, async handler signature `(arguments: dict, client: ExchangeClient | None) -> dict`
- Direct codebase inspection: `exchange_mcp/server.py` — confirmed `TOOL_DEFINITIONS` and `TOOL_DISPATCH` imported from tools.py; server startup pattern
- Direct codebase inspection: `chat_app/auth.py` — confirmed `login_required` decorator exists and redirects to `url_for("index")`
- Direct codebase inspection: `chat_app/app.py` — confirmed graph_client initialized at startup; blueprint registration pattern
- Direct codebase inspection: `chat_app/config.py` — confirmed `GRAPH_BASE_URL`, `GRAPH_SEARCH_MAX_RESULTS=25`, `GRAPH_TIMEOUT=10`
- Direct codebase inspection: `chat_app/mcp_client.py` — confirmed MCP server spawned as `uv run python -m exchange_mcp.server` with full env; both packages on Python path

### Secondary (MEDIUM confidence)

- Microsoft Graph API documentation (training knowledge, verified by existing code): `$expand=manager($select=displayName)` is the standard way to fetch manager in one call; `/photos/96x96/$value` is valid endpoint
- SVG specification (HIGH): SVG is a W3C text format; the circle + text pattern is universally supported in modern browsers

### Tertiary (LOW confidence)

- `asyncio.to_thread()` behavior with MSAL `time.sleep()` retry loops: blocking sleep inside `to_thread` is fine (thread pool, not event loop), but long retries (up to 8 seconds with 3 retries) will hold the thread pool thread. Acceptable for this use case.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all in pyproject.toml
- Architecture patterns: HIGH — patterns derived directly from existing codebase code
- Graph API $expand: MEDIUM — based on training knowledge, consistent with existing code patterns
- Pitfalls: HIGH — derived from direct code inspection (existing patterns, Config, TOOL_DISPATCH)

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable codebase — 30 days)
