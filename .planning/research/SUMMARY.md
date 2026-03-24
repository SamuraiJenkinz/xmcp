# Project Research Summary

**Project:** Exchange Infrastructure MCP Server — v1.1 Colleague Lookup Milestone
**Domain:** MCP Server + Enterprise Chat App — Microsoft Graph API Integration
**Researched:** 2026-03-24
**Confidence:** HIGH

---

## Executive Summary

The v1.1 milestone adds Microsoft Graph colleague lookup to an existing, shipped system. V1.0 delivered 15 Exchange management tools plus a Flask chat app with Azure AD SSO, conversation history, and inline tool panels. The new feature is well-scoped: two new MCP tools (`search_colleagues`, `get_colleague_profile`), one new module (`graph_client.py`), one new Flask route (`/api/photo/<user_id>`), and frontend profile card rendering. All four research files agree on the architecture and approach — there are no significant conflicts between researchers.

The recommended implementation uses `msal` + `requests` directly for Graph API calls, deliberately avoiding the `msgraph-sdk` package. This keeps the dependency footprint at zero new packages (requests is already a transitive dependency of msal). The key structural constraint is that the Graph client must be a module-level singleton with its own `ConfidentialClientApplication` instance, completely isolated from the existing user auth flow in `auth.py`. Mixing the two token flows causes subtle, hard-to-diagnose bugs that only appear after both flows have run at least once.

The critical prerequisite is Azure AD app registration: `User.Read.All` and `ProfilePhoto.Read.All` Application permissions must have admin consent granted before any Graph code can be tested. This is an infrastructure dependency that blocks the entire feature and must be secured before code is written. The photo proxy pattern — serving binary JPEG from Graph through a Flask route — keeps the bearer token server-side, prevents CORS issues, and is the correct architecture for this codebase. The highest-risk pitfall unique to this milestone is the two-MSAL-instance separation; get that wrong and SSO breaks in subtle ways.

---

## Key Findings

### Recommended Stack (v1.1 delta only)

All four research files agree: zero new packages are needed. The existing stack handles the Graph integration.

**Core technologies for this milestone:**
- `msal` (>=1.35.1, already pinned): Client credentials flow for Graph — `acquire_token_for_client(["https://graph.microsoft.com/.default"])`. The scope string is exact; substitutions fail silently.
- `requests` (>=2.32, already a transitive dep of msal): Direct REST calls to Graph API. The `msgraph-sdk` alternative was evaluated and rejected — it adds 7+ new transitive packages for two REST endpoints.
- Flask (existing): One new `GET /api/photo/<user_id>` route added inline in `app.py`, not a new blueprint.
- `httpx` (already installed as openai SDK dep): Available as async alternative for `graph_client.py` method signatures; synchronous `requests` is simpler for the photo proxy route specifically.

**What NOT to add:**
- `msgraph-sdk`: 7 new transitive packages (kiota stack, azure-identity, httpx) for two REST endpoints. STACK.md and ARCHITECTURE.md are in full agreement.
- `cachetools`: An in-memory dict with TTL timestamps is sufficient for photo caching at this scale. Add only if the dict implementation grows complex.

**Confidence:** HIGH — verified against official Microsoft Learn docs (2026-03-24) and the project lockfile confirming `requests` is already present.

### Expected Features

The v1.1 feature set is defined in PROJECT.md and confirmed by FEATURES.md domain research. There is no ambiguity about scope.

**Must have (table stakes — v1.1 launch requirements):**
- `search_colleagues` MCP tool — name/partial name search, up to 10 results
- `get_colleague_profile` MCP tool — detailed profile by user ID
- Photo proxy route — `/api/photo/<user_id>` returning JPEG or placeholder on 404
- Profile card rendering inline in chat — photo + name + title + department + email
- Graceful photo fallback — initials avatar or SVG placeholder when no photo exists
- Empty state for no-results queries — explicit message, not blank space
- `@login_required` on photo proxy route — personal data protection requirement

**Should have (add if time permits — low complexity, high value):**
- Operating company badge derived from `companyName` AAD field (Mercer, Marsh, Oliver Wyman, Guy Carpenter)
- Office location on card — render only when populated (many AAD records are null)
- Copy email to clipboard button — existing clipboard pattern already in codebase
- Single vs multi-result card layout differentiation (larger card for one confident match)

**Defer to post-v1.1:**
- Manager field (separate Graph call, adds complexity)
- Combined name + department search (`$search` + `$filter` combo — tricky to test)
- Phone numbers on card (validate population rate in MMC AAD first)
- Usage analytics for colleague lookup queries

**Anti-features (do not build):**
- Presence/availability status — requires higher-sensitivity Graph scope, data is ephemeral
- Bulk export of colleague data — data exfiltration risk
- Photo caching in SQLite — binary blobs in DB create stale-photo problem
- Autocomplete/typeahead in chat input — high API cost, breaks conversational model
- Account status or license details — AD admin data, not appropriate for this tool

### Architecture Approach

The integration is additive and follows the existing patterns exactly. `graph_client.py` is a new peer module to `exchange_client.py` — same constructor pattern, same error conventions (`RuntimeError` on API failure), same `verify_connection()` startup check. The MCP server gets two new tool definitions in `tools.py` and a module-level `_graph_client` singleton initialized in `main()`, mirroring `_exchange_client`.

**New or modified files:**
1. `exchange_mcp/graph_client.py` (NEW) — complete Graph API client: user search, profile retrieval, photo bytes. Module-level `ConfidentialClientApplication` singleton. Must be isolated from `auth.py`'s user auth CCA.
2. `exchange_mcp/tools.py` (MODIFIED) — add `search_colleagues` and `get_colleague_profile` tool definitions with descriptions under 800 chars, and dispatch entries.
3. `exchange_mcp/server.py` (MODIFIED) — add `_graph_client` module-level reference, initialize in `main()`, update tool count banner from 15 to 17.
4. `chat_app/app.py` (MODIFIED) — add `GET /api/photo/<user_id>` route with `@login_required`. Use existing background asyncio loop for async Graph call, or synchronous `requests` for simplicity.
5. `chat_app/static/app.js` (MODIFIED) — add `addProfileCard()` function that fires on SSE `tool` events with `name === "search_colleagues"` or `"get_colleague_profile"`. Parses tool result JSON; constructs DOM elements (not innerHTML/markdown injection).
6. `chat_app/static/style.css` (MODIFIED) — profile card CSS: photo dimensions, layout, operating company badge colors.
7. `chat_app/openai_client.py` (MODIFIED) — expand Atlas system prompt to describe colleague lookup capabilities and when to call each tool.

**Token caching architecture — two separate flows, never share:**

| Token Purpose | Where Cached | Flow | Scope |
|---|---|---|---|
| SSO login (user identity) | Flask session per-user `SerializableTokenCache` | Auth code flow | `User.Read` |
| Graph API calls (app-level) | Module-level singleton in `graph_client.py` | Client credentials | `https://graph.microsoft.com/.default` |

**Data flow summary:** User query → Atlas selects `search_colleagues` → MCP JSON-RPC → `graph_client.search_users()` → Graph API → JSON results → SSE `tool` event → `addProfileCard()` builds DOM → `<img src="/api/photo/{id}">` → Flask proxy → Graph photo endpoint → JPEG bytes with `Cache-Control: max-age=3600`.

**Build order confirmed by ARCHITECTURE.md:**
1. `graph_client.py` (foundation — test in isolation before touching anything else)
2. `tools.py` + `server.py` (MCP integration)
3. `/api/photo/<user_id>` route (photo proxy)
4. `app.js` + `style.css` (profile card frontend)
5. System prompt update (tune after seeing real tool behavior)

### Critical Pitfalls

The v1.1 milestone has 10 documented pitfalls (Pitfalls 16–25). The five most critical:

1. **Wrong scope for client credentials (Pitfall 16)** — `acquire_token_for_client` must receive `["https://graph.microsoft.com/.default"]` exactly. Passing `["User.Read.All"]` issues a token that Graph rejects with 401. The error message does not indicate the scope is wrong. Prevention: use `.default` scope and decode the returned token to verify the `roles` claim contains permission names (not `scp`).

2. **Admin consent not granted for Application permissions (Pitfall 17)** — Adding `User.Read.All` and `ProfilePhoto.Read.All` in the Azure portal requires a tenant admin to separately click "Grant admin consent for [tenant]". Graph returns 403 `Authorization_RequestDenied` until this is done. Prevention: obtain admin consent before writing any Graph code; this is a day-1 infrastructure action.

3. **Two MSAL instances sharing state corrupts both token flows (Pitfall 18)** — The Graph `ConfidentialClientApplication` must be a completely separate instance from the user auth CCA in `auth.py`. Sharing the same instance or cache causes user SSO to silently break after Graph calls start. Prevention: `graph_client.py` owns its own module-level CCA with no shared state with `auth.py`.

4. **`$search` requires `ConsistencyLevel: eventual` header (Pitfall 19)** — Graph returns 400 `Bad Request` if this header is omitted on any user `$search` request. Must be re-sent on every paginated follow-up request. Prevention: add to the module's default headers dict on day one.

5. **Photo 404 must be absorbed by the proxy, never forwarded (Pitfall 20)** — In an 80,000-user tenant, a significant fraction will have no photo. If the proxy forwards the 404, every profile card without a photo shows a broken image icon. Prevention: proxy catches Graph 404 and returns a placeholder SVG/PNG with HTTP 200. Add `onerror` fallback in `<img>` tags as belt-and-suspenders.

**Additional pitfall inherited from v1.0 (Pitfall 1):** stdout pollution kills the MCP protocol. `graph_client.py` must not introduce any `print()` statements or library output to stdout.

---

## Implications for Roadmap

This milestone is a clean, well-defined feature addition. The research supports a 3-phase implementation plan.

### Phase 1: Infrastructure Prerequisites + Graph Client Foundation

**Rationale:** Nothing else can be tested until Azure AD permissions are consented and the Graph client token acquisition is verified. Admin consent requires another person (a tenant admin) — this is outside the development team's control and must be started on day 1 to avoid blocking later phases.

**Delivers:** Working `graph_client.py` with verified token acquisition, user search, profile retrieval, and photo bytes retrieval (including 404 handling). Azure AD app registration updated with admin consent.

**Must do:**
- Obtain admin consent for `User.Read.All` and `ProfilePhoto.Read.All` Application permissions — blocker, get it before writing code
- Implement `graph_client.py` as a module-level singleton, fully isolated from `auth.py`
- Verify client credentials scope is `["https://graph.microsoft.com/.default"]` — decode the token to confirm `roles` claim
- Verify `ConsistencyLevel: eventual` header is in default request headers
- Test `search_users("test")`, `get_user_profile(known_id)`, `get_user_photo_bytes(known_id)` in isolation
- Test `get_user_photo_bytes()` with a user who has NO photo (verify returns `None`, not raises)

**Pitfalls to avoid:** P16 (wrong scope), P17 (missing admin consent), P18 (shared MSAL instance), P19 (missing ConsistencyLevel header), P25 (CCA not singleton)

**Research flag:** No further research needed — Graph API docs are authoritative and were verified 2026-03-24.

### Phase 2: MCP Server Integration + Photo Proxy

**Rationale:** Depends on Phase 1 `graph_client.py` being proven. Adding tools to the MCP server follows established patterns from v1.0 — lowest-risk phase.

**Delivers:** Two new MCP tools verified with `mcp dev` or direct MCP client. Photo proxy route live and tested in browser under authenticated and unauthenticated conditions.

**Must do:**
- Add tool definitions to `tools.py` with descriptions under 800 chars — write descriptions before implementing handlers
- Add `_graph_client` module-level reference in `server.py`, initialize in `main()`
- Add `/api/photo/<user_id>` route to `app.py` with `@login_required` — never skip this decorator
- Proxy absorbs Graph 404 and returns placeholder (200 response, not 404 forward)
- Validate `user_id` path parameter is GUID or UPN format before passing to Graph (path injection prevention)
- Use existing background asyncio loop for the photo proxy async call — do not call `asyncio.run()` inside Flask route
- Test: authenticated user with photo, authenticated user without photo, unauthenticated request (should be blocked)

**Pitfalls to avoid:** P20 (photo 404 forwarded to browser), P23 (photo binary in MCP tool result — return `photo_url` string, not base64 bytes), P24 (unauthenticated photo proxy)

### Phase 3: Profile Card Frontend + System Prompt

**Rationale:** Depends on Phase 2 tool results being correctly shaped. Frontend work is the most iterative and must come after the tool result JSON contract is established.

**Delivers:** Inline profile cards in chat with photo, name, title, department, email. Atlas system prompt updated to use colleague lookup tools correctly.

**Must do:**
- Add `addProfileCard()` in `app.js` triggered by SSE `tool` events — build as DOM elements (same pattern as existing `addToolPanel()`)
- Parse tool result JSON in `app.js` for card data (do not embed card data in Atlas text response — fragile)
- Each `<img>` must have `onerror="this.src='/static/no-photo.svg'"` as fallback
- Test multi-result rendering (search returning multiple cards)
- Update Atlas system prompt — describe when to call `search_colleagues` vs `get_colleague_profile`
- Test tool selection: "Find Jane Smith", "Who is Jane?", "Find people in Finance" — verify consistent tool selection

**Optional for this phase (time permitting):**
- Operating company badge from `companyName` field (validate field population with CTS first)
- Office location (render only if populated)
- Copy email to clipboard button (existing clipboard pattern)

**Pitfalls to avoid:** P6 (vague tool descriptions degrade LLM tool selection), P23 (no photo binary in tool results)

### Phase Ordering Rationale

- Phase 1 must come first because admin consent is a human dependency — starting it on day 1 eliminates the risk of being blocked mid-implementation.
- Phase 1 also proves `graph_client.py` in isolation before it touches the MCP server, following the same incremental pattern used for `exchange_client.py` in v1.0 development.
- Phase 2 before Phase 3 because the frontend card renderer must parse the actual tool result JSON shape — building the card renderer before knowing the exact JSON keys is wasted work.
- System prompt update goes last because prompt tuning requires seeing real model behavior with live tools, not guessing in advance.

### Research Flags

No phases need deeper research. All four research files are based on official Microsoft documentation verified 2026-03-24. The architecture follows existing codebase patterns throughout.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Graph client):** Official MSAL Python docs and Graph REST docs cover the entire implementation.
- **Phase 2 (MCP + proxy):** Mirrors existing `exchange_client.py` and existing Flask routes in `app.py`.
- **Phase 3 (frontend):** Mirrors existing `addToolPanel()` DOM builder pattern in `app.js`.

---

## Conflicts and Agreements Between Research Files

**No conflicts identified.** All four researchers agree on:
- Zero new packages required
- `graph_client.py` as a module-level singleton, isolated from `auth.py`
- Photo proxy as an inline Flask route (not a blueprint), with `@login_required`
- Profile card DOM injection from SSE tool event data (not from AI text output)
- Admin consent as a day-1 prerequisite before writing code

**One minor discrepancy in implementation detail (resolved):** STACK.md favors synchronous `requests` for the photo proxy route. ARCHITECTURE.md notes both synchronous and async approaches but recommends synchronous for the proxy specifically. Recommendation: use synchronous `requests` for the photo proxy to avoid the asyncio bridge; use async methods in `graph_client.py` for the search and profile calls that go through the MCP server's async `handle_call_tool`.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new packages — verified msal and requests are already present in lockfile. msgraph-sdk evaluated and rejected with clear rationale. |
| Features | HIGH | Table stakes verified against official Graph API docs. Differentiators from domain knowledge — `companyName` population rate in MMC AAD is unverified (see Gaps). |
| Architecture | HIGH | Integration points verified against existing codebase source (auth.py, mcp_client.py, app.js patterns reviewed). All design decisions have clear rationale. |
| Pitfalls | HIGH | 10 v1.1-specific pitfalls, all sourced from official Microsoft documentation. Pitfalls are specific and testable. |

**Overall confidence: HIGH**

### Gaps to Address

- **`companyName` population rate in MMC AAD:** The operating company badge depends on this field being consistently populated across 80,000 users. Validate with CTS team before building the badge. If unreliable, derive operating company from the mail domain pattern instead.

- **Phone number population rate in MMC AAD:** FEATURES.md recommends validating `businessPhones`/`mobilePhone` population before adding phone numbers to profile cards. Many enterprise AAD tenants have low mobile phone population — validate before committing to this feature.

- **Graph throttling headroom at MMC tenant scale:** Pitfall 21 documents that an 80K+ user tenant is "L" tier with 8,000 RU per 10 seconds. A burst of 10 search results each triggering a photo fetch costs 20+ RU. For v1.1 with a small internal user base, throttling is unlikely but the retry-after handler should be implemented before any load testing.

---

## Sources

### Primary (HIGH confidence — verified 2026-03-24)
- Microsoft Graph List Users: https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0
- Microsoft Graph Get profilePhoto: https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0
- Microsoft Graph Get User: https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0
- Microsoft Graph advanced query capabilities ($search, ConsistencyLevel): https://learn.microsoft.com/en-us/graph/aad-advanced-queries
- Microsoft Graph throttling guidance: https://learn.microsoft.com/en-us/graph/throttling
- Microsoft Graph service-specific throttling limits: https://learn.microsoft.com/en-us/graph/throttling-limits
- MSAL Python acquiring tokens: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- Microsoft Entra: Get access without a user (client credentials): https://learn.microsoft.com/en-us/graph/auth-v2-service
- Microsoft Entra: Grant tenant-wide admin consent: https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent
- PyPI: msal 1.35.1 (verified on PyPI 2026-03-24)

### Secondary (MEDIUM confidence)
- Operating company badge pattern: derived from project context (MMC 4-company structure, AAD `companyName` field). Requires validation that `companyName` is consistently populated in MMC AAD.
- Card layout for single vs multi-result: enterprise search UX convention (ClearBox Consulting, search UX best practices).
- Initials fallback for missing photos: industry standard pattern (Primer, shadcn — not Graph-specific documentation).

### Project sources (HIGH confidence — this codebase)
- `chat_app/auth.py` — verified MSAL pattern, `SerializableTokenCache` per-user in Flask session
- `chat_app/mcp_client.py` — verified asyncio bridge pattern (`run_coroutine_threadsafe`)
- `chat_app/static/app.js` — verified `addToolPanel()` DOM builder pattern
- `exchange_mcp/server.py` — verified module-level `_exchange_client` singleton pattern

---

*Research completed: 2026-03-24*
*Ready for roadmap: yes*
