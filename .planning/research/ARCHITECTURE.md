# Architecture Patterns: Microsoft Graph Colleague Lookup Integration

**Project:** Exchange Infrastructure MCP Server — v1.1 Colleague Lookup milestone
**Researched:** 2026-03-24
**Scope:** Integration of Microsoft Graph API (user search + profile + photo) into the existing MCP server + Flask chat app

---

## Executive Summary

The Graph colleague lookup feature slots cleanly into the existing architecture. The pattern mirrors how Exchange tools already work: a new peer client module (`graph_client.py`) is called from the MCP server; new MCP tools surface data to the AI; a Flask photo proxy route handles binary image serving. Token acquisition reuses the existing MSAL `ConfidentialClientApplication` pattern from `auth.py`, using `acquire_token_for_client` (client credentials flow) rather than on-behalf-of, because the Graph calls are app-level lookups against the directory, not delegated user actions.

The one structural addition is a photo proxy route in `app.py` — the browser cannot call Graph directly because the bearer token is server-side only, and Graph does not support CORS for `$value` endpoints. Profile card rendering lives entirely in `app.js` as a new branch of the SSE `tool` event handler, keeping the server contract (JSON tool events over SSE) unchanged.

---

## Existing Architecture (What Is Already Built)

```
Browser (MMC internal / VPN)
    |
    | HTTPS + SSE
    v
+------------------------------------------+
|  chat_app/app.py  — Flask / Waitress      |
|  Blueprints: auth_bp, chat_bp,            |
|              conversations_bp             |
|  Routes:                                  |
|    GET  /                                 |
|    GET  /chat                             |
|    POST /chat/stream  (SSE)               |
|    GET  /api/health                       |
|    /auth/* (MSAL auth code flow)          |
|    /api/threads/* (conversation CRUD)     |
|  State:                                   |
|    SQLite (chat.db) — threads + messages  |
|    Filesystem sessions (flask-session)    |
|    MCP background thread + asyncio loop   |
+------------------+-----------------------+
                   |
                   | JSON-RPC 2.0 over stdio pipe
                   | (threading.Lock serialises calls)
                   v
+------------------------------------------+
|  exchange_mcp/server.py  — MCP server    |
|  Tools: 15 Exchange tools + ping          |
|  Dispatch: TOOL_DISPATCH dict             |
|  Error: _sanitize_error() strips PS trace|
+------------------+-----------------------+
                   |
                   | async Python calls
                   v
+------------------------------------------+
|  exchange_mcp/exchange_client.py          |
|  ExchangeClient — PowerShell subprocess   |
|  Auth: interactive or CBA (cert)          |
|  Per-call PSSession lifecycle             |
|  Retry with exponential backoff           |
+------------------------------------------+
                   |
                   | WinRM/PowerShell Remoting
                   v
         Exchange Management Shell
         (Exchange Online / on-prem)
```

### Key Constraints Already Established

- Flask is synchronous; async work dispatched via `run_coroutine_threadsafe` to a dedicated background loop in `mcp_client.py`.
- The MCP server subprocess uses stdio exclusively for JSON-RPC; stdout is reserved.
- MSAL `ConfidentialClientApplication` is created per-request from `auth.py` (`_build_msal_app()`). The `SerializableTokenCache` is persisted in the Flask session.
- Scopes currently acquired: `["User.Read"]` for delegated SSO login.
- Tool results flow as JSON text over MCP → `run_tool_loop()` in `openai_client.py` → SSE `tool` events → `app.js` `addToolPanel()`.

---

## Graph Integration: Target Architecture

```
Browser (MMC internal / VPN)
    |
    | HTTPS + SSE
    v
+------------------------------------------+
|  chat_app/app.py  — Flask / Waitress      |
|  (modified)                               |
|  NEW route:                               |
|    GET  /api/photo/<user_id>              |  <-- photo proxy
|    (login_required, proxies Graph binary) |
+------------------+-----------------------+
                   |
                   | JSON-RPC 2.0 over stdio pipe
                   v
+------------------------------------------+
|  exchange_mcp/server.py  — MCP server    |
|  (modified — add 2 new tools)             |
|  NEW tools in TOOL_DEFINITIONS:           |
|    search_colleagues                      |
|    get_colleague_profile                  |
|  TOOL_DISPATCH entries point to           |
|    graph_client.GraphClient methods       |
+------------------+-----------------------+
                   |          |
      async Python calls      | async Python calls
                   |          |
                   v          v
+------------------------------------------+    +------------------------------------------+
|  exchange_mcp/exchange_client.py          |    |  exchange_mcp/graph_client.py  (NEW)      |
|  (unchanged)                             |    |  GraphClient                              |
+------------------------------------------+    |  Auth: MSAL client credentials            |
                                                |    acquire_token_for_client(              |
                                                |      ["https://graph.microsoft.com/.def"] |
                                                |    )                                      |
                                                |  Methods:                                 |
                                                |    search_users(query) -> list[dict]      |
                                                |    get_user_profile(user_id) -> dict      |
                                                |    get_user_photo_bytes(user_id) -> bytes |
                                                +------------------------------------------+
                                                                   |
                                                                   | HTTPS REST (requests)
                                                                   v
                                                     graph.microsoft.com/v1.0
                                                     /users?$search=...
                                                     /users/{id}?$select=...
                                                     /users/{id}/photo/96x96/$value
```

---

## Component-by-Component Integration Points

### 1. graph_client.py (NEW — peer to exchange_client.py)

**Location:** `exchange_mcp/graph_client.py`

**Responsibility:** All Microsoft Graph API calls. No Exchange, no PowerShell. Parallel design to `exchange_client.py`.

**Auth model:** App-only (client credentials flow). Uses the same `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` environment variables already present in the system. Acquires a token with scope `https://graph.microsoft.com/.default` — this is the app-only scope that bundles all consented application permissions.

**Why client credentials, not on-behalf-of:** The Graph calls are directory lookups (find a colleague by name), not actions that need to respect the logged-in user's own Graph permissions. The service runs as the registered application identity. This is simpler and avoids OBO complexity. The logged-in user is already authenticated via Azure AD; their identity is used for access control to the chat app, not for Graph authorization.

**Token caching inside GraphClient:** MSAL `SerializableTokenCache` in memory, module-level. App tokens (client credentials) are long-lived (typically 1 hour) and can be safely cached at the module level — they are not user-specific. This is distinct from the per-user token cache in the Flask session used for SSO.

**Key methods:**

```
search_users(query: str, top: int = 10) -> list[dict]
  GET /v1.0/users?$search="displayName:{query}"
              &$select=id,displayName,jobTitle,department,mail,userPrincipalName
              &$top={top}
  Headers: ConsistencyLevel: eventual
  Required permission: User.Read.All (application)

get_user_profile(user_id: str) -> dict
  GET /v1.0/users/{user_id}
              ?$select=id,displayName,jobTitle,department,
                       mail,userPrincipalName,officeLocation,
                       businessPhones,mobilePhone,manager
  Required permission: User.Read.All (application)

get_user_photo_bytes(user_id: str, size: str = "96x96") -> bytes
  GET /v1.0/users/{user_id}/photos/{size}/$value
  Returns: raw image bytes (jpeg)
  Returns: None if 404 (user has no photo)
  Required permission: ProfilePhoto.Read.All (application)
```

**Error handling:** `RuntimeError` on Graph API errors, matching the exchange_client convention so `server.py`'s `_sanitize_error()` can process them uniformly. 404 from photo endpoint returns `None` rather than raising — the tool result should gracefully indicate no photo available.

**No PowerShell dependency:** Pure Python + `requests` library (or `httpx` for async). This is a REST client, not a subprocess runner.

**Async vs sync:** The MCP server's `handle_call_tool` is async. `graph_client.py` should expose async methods (using `httpx.AsyncClient`) to avoid blocking the event loop. This mirrors the async pattern in `exchange_client.py`.

---

### 2. exchange_mcp/tools.py (MODIFIED — add 2 tools)

**Add to TOOL_DEFINITIONS:**

```python
Tool(
    name="search_colleagues",
    description=(
        "Search for MMC colleagues by name or partial name. Returns a list of matching "
        "people with their job title, department, and email address. "
        "Use when asked to find a person: 'Who is Jane Smith?', 'Find colleagues in IT', "
        "'Search for John in Finance'. Returns up to 10 results."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Name or partial name to search for."
            }
        },
        "required": ["query"]
    }
),
Tool(
    name="get_colleague_profile",
    description=(
        "Get detailed profile information for a specific colleague by their user ID "
        "or email address. Returns name, title, department, office, phone numbers, "
        "and manager. Use after search_colleagues to get full details for a specific person."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's Azure AD object ID or email address (UPN)."
            }
        },
        "required": ["user_id"]
    }
)
```

**Add to TOOL_DISPATCH:**

```python
"search_colleagues": handle_search_colleagues,
"get_colleague_profile": handle_get_colleague_profile,
```

**Handler signature (same pattern as Exchange tools):**

```python
async def handle_search_colleagues(
    arguments: dict, client: ExchangeClient | None
) -> Any:
    ...

async def handle_get_colleague_profile(
    arguments: dict, client: ExchangeClient | None
) -> Any:
    ...
```

The `client` parameter is the ExchangeClient (unused by Graph handlers). Graph handlers construct or receive a `GraphClient` instance independently. A module-level `_graph_client: GraphClient | None` in `server.py` follows the same pattern as `_exchange_client`.

---

### 3. exchange_mcp/server.py (MODIFIED — Graph client lifecycle)

**Add module-level reference:**

```python
_graph_client: GraphClient | None = None
```

**Initialize in `main()` before stdio opens** (same pattern as `_exchange_client`):

```python
graph_client = GraphClient()
_graph_client = graph_client
ok = await graph_client.verify_connection()
if not ok:
    logger.warning("Graph client connection check failed — colleague tools degraded")
```

**Pass to tool handlers** by making `_graph_client` accessible in the dispatch context. The simplest approach: add a second context parameter to the Graph tool handlers, or use a module-level singleton accessed directly. The latter is simpler and consistent with how `_exchange_client` is accessed.

**Tool count:** Changes from 15 to 17 (15 Exchange tools + ping + 2 Graph tools). Update the startup banner log message.

---

### 4. Photo Proxy Route in app.py (NEW ROUTE — NOT a blueprint)

**Why a proxy is required:** The Graph `photo/$value` endpoint returns raw binary (JPEG). Browser `<img src="...">` tags cannot call it directly because:
- The bearer token is server-side (never exposed to browser JS)
- Graph does not add CORS headers to `$value` binary endpoints
- The existing auth pattern keeps all Azure credentials on the server

**Route:**

```
GET /api/photo/<user_id>
```

**Location:** Inline route in `app.py` (not a separate blueprint). This is a single route; a blueprint would be overengineering. Add it after the existing `/api/health` route.

**Implementation:**

```python
@app.route("/api/photo/<user_id>")
@login_required
def user_photo(user_id: str):
    # Import graph_client module directly — not via MCP
    from exchange_mcp.graph_client import GraphClient
    client = GraphClient()  # module-level singleton preferred
    photo_bytes = asyncio.run_in_executor_equivalent(client.get_user_photo_bytes(user_id))
    if photo_bytes is None:
        # Return a 1x1 transparent GIF placeholder
        return Response(TRANSPARENT_GIF_BYTES, content_type="image/gif")
    return Response(
        photo_bytes,
        content_type="image/jpeg",
        headers={"Cache-Control": "max-age=3600"}
    )
```

**Note on async in Flask route:** The photo proxy calls `graph_client.get_user_photo_bytes()` which is async. Use the same `_async_run()` pattern from `mcp_client.py` — dispatch to the background MCP event loop via `run_coroutine_threadsafe`. This avoids creating a new event loop inside a Flask route handler, which is an existing solved problem in this codebase.

**Alternatively:** Make `get_user_photo_bytes` also available as a synchronous wrapper in `graph_client.py`, since photo fetching is a direct REST call (not subprocess), making a sync version using `requests` library straightforward. This is the simpler path — no asyncio bridge needed for the proxy route.

**Cache-Control header:** `max-age=3600` (1 hour) is appropriate. Profile photos change rarely. The browser will cache the image and not re-request it on every render within that window.

**Security:** Route is protected by `@login_required`. Only authenticated colleagues can fetch photos. The `user_id` path parameter is passed directly to Graph — validate it is a GUID or UPN format before passing, to prevent path injection into the Graph URL.

---

### 5. Profile Card Rendering in app.js (FRONTEND CHANGE)

**What the AI returns:** When `search_colleagues` or `get_colleague_profile` is called, the MCP tool result JSON contains colleague fields. The AI then writes a text response that describes the profile. The SSE stream delivers:
1. A `tool` event: `{"type": "tool", "name": "get_colleague_profile", "status": "success", "result": "{...json...}"}`
2. `text` events: the AI's prose description
3. A `done` event

**Profile card rendering approach:** The frontend detects Graph colleague tool results and renders them as structured profile cards inline with the AI text, in addition to the collapsible tool panel. This requires a new rendering branch in `app.js`.

**Recommended format: HTML injection via innerHTML** (not markdown). The existing `appendText()` function appends raw text characters from streaming deltas. Profile card HTML needs to be injected as a DOM element, not as streaming text. The best insertion point is inside `addToolPanel()` or as a companion `addProfileCard()` method called when the SSE `tool` event has `name === "search_colleagues"` or `name === "get_colleague_profile"`.

**Profile card structure (inserted above the AI text, below the tool panel):**

```
[collapsible tool panel — existing behavior]
[profile card div — new]
  <img src="/api/photo/{user_id}" onerror="this.src='/static/no-photo.svg'">
  <div class="profile-info">
    <div class="profile-name">{displayName}</div>
    <div class="profile-title">{jobTitle}</div>
    <div class="profile-dept">{department}</div>
    <div class="profile-email"><a href="mailto:{mail}">{mail}</a></div>
  </div>
[streaming AI text — existing behavior]
```

**For `search_colleagues` returning multiple people:** Render a card row for each result. Parse the JSON tool result, iterate over the results array, render one card per person.

**Why not markdown:** The existing `appendText()` builds a DOM text node (`document.createTextNode('')`), not an HTML element. The AI's streaming text content cannot contain raw HTML — it would appear as literal `<div>` tags. Profile cards must be constructed as DOM elements from the SSE `tool` event data (which arrives before the streaming text), not from the AI's text output.

**What the AI text response should say:** The system prompt should instruct Atlas to describe the colleague in conversational prose when Graph tools are invoked ("Jane Smith is a Senior Engineer in the IT department..."), supplementing the card rather than repeating its fields verbatim. The card provides the photo and structured layout; the text provides context.

---

## Data Flow: Colleague Lookup Turn

```
1. User types: "Find Jane Smith in IT"

2. POST /chat/stream
   browser -> Flask

3. run_tool_loop() — OpenAI tool-call loop
   Atlas model selects: search_colleagues({"query": "Jane Smith"})

4. call_mcp_tool("search_colleagues", {"query": "Jane Smith"})
   Flask thread -> MCP background event loop (via run_coroutine_threadsafe)

5. JSON-RPC over stdio pipe
   mcp_client.py -> exchange_mcp/server.py

6. handle_search_colleagues(arguments, _exchange_client)
   server.py -> graph_client.GraphClient.search_users("Jane Smith")

7. MSAL acquire_token_for_client(["https://graph.microsoft.com/.default"])
   Graph token cache hit (if not expired) or token fetch from Azure AD

8. GET https://graph.microsoft.com/v1.0/users
        ?$search="displayName:Jane Smith"
        &$select=id,displayName,jobTitle,department,mail,userPrincipalName
        &$top=10
        &ConsistencyLevel=eventual
   graph_client.py -> graph.microsoft.com

9. JSON response: [{id, displayName, jobTitle, department, mail}, ...]

10. server.py wraps result as TextContent JSON
    Returns: [{"id": "...", "displayName": "Jane Smith", ...}, ...]

11. call_mcp_tool returns result JSON string
    Appended to messages as role=tool

12. Atlas model generates text response + emits done

13. SSE stream to browser:
    data: {"type": "tool", "name": "search_colleagues", "status": "success",
           "result": "[{\"id\":\"...\", \"displayName\":\"Jane Smith\", ...}]"}
    data: {"type": "text", "delta": "I found Jane Smith..."}
    data: {"type": "done"}

14. app.js SSE handler:
    - "tool" event with name "search_colleagues":
        addToolPanel(...)         -- existing collapsible panel
        addProfileCard(result)    -- NEW: parse result JSON, render card(s)
                                     img src="/api/photo/{id}"
    - "text" events: appendText() -- existing streaming text

15. Browser requests /api/photo/{user_id}
    GET /api/photo/abc-123-def

16. Flask photo proxy:
    GraphClient.get_user_photo_bytes("abc-123-def", size="96x96")
    -> GET /v1.0/users/abc-123-def/photos/96x96/$value
    -> returns JPEG bytes
    Response(jpeg_bytes, content_type="image/jpeg", Cache-Control: max-age=3600)

17. Browser renders <img> with colleague photo
```

---

## Token Caching: Graph vs SSO

Two separate MSAL token concerns in this system:

| Token Purpose | Where Cached | Flow | Scope | Lifetime |
|---------------|-------------|------|-------|----------|
| SSO login (user identity) | Flask filesystem session, per-user `SerializableTokenCache` | Auth code flow | `User.Read` | 1h access / longer refresh |
| Graph API calls (app-level) | Module-level singleton in `graph_client.py`, `SerializableTokenCache` | Client credentials | `https://graph.microsoft.com/.default` | 1 hour |

**Key design rule:** Do NOT reuse the SSO user token for Graph API calls. They serve different purposes and have different scopes. The SSO token is a delegated token scoped to `User.Read` for the logged-in user's own profile. The Graph search token is an application token with `User.Read.All` to search the entire directory. Mixing them is architecturally incorrect and would require OBO flow complexity with no benefit.

**Module-level token cache in GraphClient:** Since `graph_client.py` is imported by `server.py` (the MCP subprocess), and the MCP subprocess is a single long-lived process, the module-level token cache persists for the lifetime of the MCP server process. This is appropriate — client credential tokens can be shared across all tool calls in the same process.

---

## Required Azure AD App Registration Changes

The existing app registration (AZURE_CLIENT_ID) needs two new **application permissions** (not delegated — these are app-only calls):

| Permission | Type | Purpose |
|------------|------|---------|
| `User.Read.All` | Application | Search users, get profile details |
| `ProfilePhoto.Read.All` | Application | Fetch user photos |

**Admin consent required:** Application permissions always require tenant admin consent. This is a one-time action in the Azure portal (App Registrations -> API permissions -> Grant admin consent).

**No new client secret needed:** The existing `AZURE_CLIENT_SECRET` is reused. The same app identity acquires both SSO tokens (delegated) and Graph app tokens (application).

---

## New vs Modified Files

| File | Status | What Changes |
|------|--------|-------------|
| `exchange_mcp/graph_client.py` | NEW | Complete Graph API client — search, profile, photo |
| `exchange_mcp/tools.py` | MODIFIED | Add `search_colleagues` and `get_colleague_profile` tool definitions and dispatch entries |
| `exchange_mcp/server.py` | MODIFIED | Add `_graph_client` module-level reference, initialize in `main()`, pass to Graph handlers; update tool count in banner |
| `chat_app/app.py` | MODIFIED | Add `GET /api/photo/<user_id>` route |
| `chat_app/static/app.js` | MODIFIED | Add `addProfileCard()` function, handle Graph tool events in SSE handler |
| `chat_app/static/style.css` | MODIFIED | Profile card CSS (photo dimensions, layout, responsive) |
| `chat_app/openai_client.py` | MODIFIED | Update SYSTEM_PROMPT to include colleague lookup guidance for Atlas |

**No new blueprints, no new Python packages beyond `httpx` (or `requests`) for the Graph REST client.**

---

## Suggested Build Order

Dependencies determine sequence.

### Step 1: graph_client.py (foundation, no UI dependency)
Build and test in isolation before touching any other file. Verify:
- Token acquisition with `acquire_token_for_client` succeeds
- `search_users("test name")` returns expected shape
- `get_user_profile(known_id)` returns full profile dict
- `get_user_photo_bytes(known_id)` returns JPEG bytes
- 404 from photo endpoint returns `None` gracefully

### Step 2: MCP server integration (tools.py + server.py)
Add tool definitions and dispatch entries. Test with `mcp dev exchange_mcp/server.py` or direct MCP client. Verify the AI model selects `search_colleagues` and `get_colleague_profile` appropriately.

### Step 3: Photo proxy route (app.py)
Add the `/api/photo/<user_id>` route. Test by hitting it directly in a browser after login. Verify Cache-Control header, 404 handling (placeholder GIF), and `@login_required` gate.

### Step 4: Profile card frontend (app.js + style.css)
Add the card rendering logic. Test by sending a message that triggers the Graph tools and verifying the card renders with the proxied photo URL.

### Step 5: System prompt update (openai_client.py)
Expand the Atlas system prompt to describe colleague lookup capabilities and instruct the model on when to use `search_colleagues` vs `get_colleague_profile`.

---

## Architecture Patterns to Follow

### Pattern: Graph client mirrors exchange_client structure
Same constructor pattern, same error conventions (raise `RuntimeError` on API errors), same `verify_connection()` method for startup health check. This keeps `server.py` consistent — it initializes both clients the same way and passes both to handlers.

### Pattern: Photo proxy as a thin pass-through
The proxy should not transform the image. Fetch from Graph, return bytes. Do not base64-encode, resize, or reformat. Let the browser handle display via CSS constraints (`object-fit: cover; width: 64px; height: 64px`).

### Pattern: Profile card data from tool result JSON, not from AI text
The SSE `tool` event carries the raw JSON result from `search_colleagues` / `get_colleague_profile`. Parse this in `app.js` to build the profile card DOM. Do not ask the AI to embed structured card data in its text response — that path is fragile (the model may format it differently, may abbreviate, may omit fields).

### Pattern: Graceful photo degradation
Every `<img>` in a profile card should have `onerror="this.src='/static/no-photo.svg'"`. Not all colleagues have photos in Azure AD. The 404 case from the proxy (which returns a placeholder GIF) plus the `onerror` fallback ensures a consistent UI regardless of photo availability.

### Pattern: App registration permissions as a prerequisite
The photo proxy and search tools will return 403 errors until `User.Read.All` and `ProfilePhoto.Read.All` application permissions are granted admin consent in the Azure portal. This is an infrastructure prerequisite, not a code prerequisite — document it as a deployment requirement in the phase plan.

---

## Anti-Patterns to Avoid

### Anti-Pattern: Fetching photos in the MCP tool result
Do not return photo bytes from the MCP tool. MCP results are text (JSON). Embedding base64-encoded photos in tool result JSON would bloat the OpenAI context window (a 96x96 JPEG is ~3-8 KB of base64, multiplied by every search result). The photo proxy pattern correctly separates the binary channel (HTTP response) from the data channel (tool result JSON).

### Anti-Pattern: Calling Graph from app.js directly
The bearer token is server-side. Exposing it to the browser is a security violation. All Graph calls go through the server-side proxy.

### Anti-Pattern: Reusing the SSO user token for Graph directory calls
The delegated `User.Read` token only allows reading the currently logged-in user's own profile. Directory-wide colleague search requires `User.Read.All` with application permissions. Using the wrong token will produce 403 errors.

### Anti-Pattern: New blueprint for the photo proxy
One route does not warrant a blueprint. Adding a blueprint increases import complexity and registration overhead for no architectural benefit. The `/api/photo/<user_id>` route belongs inline in `app.py` alongside the existing `/api/health` route.

### Anti-Pattern: Blocking Flask request thread on async Graph call
`graph_client.get_user_photo_bytes()` is async. Do not call `asyncio.run()` inside the Flask route handler — this creates a new event loop in a thread that may already have one (the MCP background loop). Use `run_coroutine_threadsafe(_mcp_loop)` (reusing the existing background loop from `mcp_client.py`) or provide a synchronous `requests`-based implementation for the photo proxy specifically.

---

## Confidence Assessment

| Area | Confidence | Source |
|------|------------|--------|
| Graph `/users?$search` with `ConsistencyLevel: eventual` | HIGH | Official MS Learn docs verified 2026-03-24 |
| Graph `profilephoto-get` endpoint, 96x96 size | HIGH | Official MS Learn docs verified 2026-03-24 |
| `ProfilePhoto.Read.All` required permission for app-only photo access | HIGH | Official MS Learn docs verified 2026-03-24 |
| MSAL `acquire_token_for_client` for client credentials | HIGH | Official MSAL Python docs, established pattern |
| Module-level token cache in MCP subprocess being safe | HIGH | Client credential tokens are not user-specific; safe to share process-wide |
| Photo proxy pattern (Flask route serving binary from Graph) | HIGH | Standard pattern; no library-specific risk |
| `ConsistencyLevel: eventual` required for `$search` on `/users` | HIGH | Official Graph docs state this explicitly |
| Profile card as DOM injection (not markdown) | HIGH | Consistent with existing `addToolPanel()` DOM builder pattern in app.js |

---

## Sources

- Microsoft Graph List Users: https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0 (verified 2026-03-24)
- Microsoft Graph Get profilePhoto: https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0 (verified 2026-03-24)
- Microsoft Graph Get User: https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0 (verified 2026-03-24)
- MSAL Python client credentials: https://learn.microsoft.com/en-us/entra/msal/python/ (established pattern, consistent with auth.py)
- Existing auth.py and mcp_client.py in this codebase — MSAL and asyncio bridge patterns verified by reading source
