# Roadmap: Exchange Infrastructure MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-9 (shipped 2026-03-22)
- 🚧 **v1.1 Colleague Lookup** — Phases 10-12 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9) — SHIPPED 2026-03-22</summary>

### Phase 1: Exchange Client Foundation
**Goal**: Working async PowerShell runner that can execute Exchange cmdlets and return structured data
**Plans**: 4 plans (complete)

Plans:
- [x] 01-01: Async subprocess runner with per-call PSSession lifecycle
- [x] 01-02: Exchange Online auth (interactive + CBA) and connection management
- [x] 01-03: Base error handling, stderr discipline, structured return types
- [x] 01-04: -EncodedCommand UTF-16LE encoding to prevent cp1252 corruption

### Phase 2: MCP Server Scaffold
**Goal**: MCP server over stdio with tool registration, dispatch, and LLM-optimized schemas
**Plans**: 3 plans (complete)

Plans:
- [x] 02-01: MCP server skeleton with stdio transport and JSON-RPC
- [x] 02-02: Tool registration framework and dispatch table
- [x] 02-03: Error handling, startup banner, and stderr discipline

### Phase 3: Mailbox Tools
**Goal**: Mailbox governance tools — list, inspect, shared mailbox permissions, quota
**Plans**: 3 plans (complete)

Plans:
- [x] 03-01: get_mailbox_info, list_mailboxes tools
- [x] 03-02: get_mailbox_permissions, get_shared_mailbox_members tools
- [x] 03-03: get_mailbox_statistics (quota, size, item count)

### Phase 4: DAG and Database Tools
**Goal**: DAG health and mailbox database tools for Exchange availability monitoring
**Plans**: 3 plans (complete)

Plans:
- [x] 04-01: get_dag_health, list_dag_members tools
- [x] 04-02: get_database_copies, list_mailbox_databases tools
- [x] 04-03: get_server_health (Exchange server component status)

### Phase 5: Mail Flow and Security Tools
**Goal**: Mail flow tracing, transport rules, and DNS security lookups (DMARC/SPF/DKIM)
**Plans**: 5 plans (complete)

Plans:
- [x] 05-01: trace_message_tracking_log tool
- [x] 05-02: get_transport_rules, get_accepted_domains tools
- [x] 05-03: get_dmarc_record, get_spf_record tools
- [x] 05-04: get_dkim_record tool
- [x] 05-05: ping_exchange tool for connectivity checks

### Phase 6: Hybrid Tools
**Goal**: Hybrid connector and migration endpoint monitoring
**Plans**: 2 plans (complete)

Plans:
- [x] 06-01: get_inbound_connectors, get_outbound_connectors tools
- [x] 06-02: get_migration_endpoints tool (removed get_migration_batches — MMC not using)

### Phase 7: Chat App Core
**Goal**: Flask chat application with Azure AD SSO, Azure OpenAI tool-calling loop, and SSE streaming
**Plans**: 6 plans (complete)

Plans:
- [x] 07-01: Flask app skeleton, Waitress WSGI, HTTPS startup
- [x] 07-02: Azure AD/Entra ID SSO with MSAL auth code flow
- [x] 07-03: MCP client (async subprocess, JSON-RPC over stdio)
- [x] 07-04: Azure OpenAI tool-calling loop with SSE streaming
- [x] 07-05: Chat UI (message rendering, tool panels, keyboard shortcuts)
- [x] 07-06: Tool visibility panels with JSON highlighting and copy-to-clipboard

### Phase 8: Conversation Persistence
**Goal**: SQLite conversation history with multi-thread sidebar and auto-naming
**Plans**: 3 plans (complete)

Plans:
- [x] 08-01: SQLite schema, auto-bootstrap, conversation CRUD
- [x] 08-02: Multi-thread sidebar navigation and thread switching
- [x] 08-03: Auto-naming threads from first user message

### Phase 9: UI Polish
**Goal**: Dark mode, loading indicators, copy-to-clipboard on all responses, and production deployment
**Plans**: 4 plans (complete)

Plans:
- [x] 09-01: Dark mode toggle with CSS variables
- [x] 09-02: Loading indicators and streaming feedback
- [x] 09-03: Copy-to-clipboard on AI responses
- [x] 09-04: Production hardening, start.py HTTPS startup, deployment to usdf11v1784

</details>

---

### 🚧 v1.1 Colleague Lookup (In Progress)

**Milestone Goal:** Enable colleague search and profile display via Microsoft Graph API, rendered as inline profile cards in the chat UI.

---

#### Phase 10: Graph Client Foundation
**Goal**: A verified, isolated Graph API client exists with confirmed admin consent, correct token acquisition, and all three core operations tested in isolation
**Depends on**: Phase 9 (v1.0 shipped — additive work)
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, SRCH-04
**Success Criteria** (what must be TRUE):
  1. Graph API token is acquired via client credentials using `["https://graph.microsoft.com/.default"]` scope and the decoded token's `roles` claim contains `User.Read.All` and `ProfilePhoto.Read.All`
  2. `graph_client.py` is a module-level singleton with its own `ConfidentialClientApplication` — it shares no state with `auth.py`'s user auth CCA
  3. Token is cached at module level and refreshed automatically before expiry — no 401 errors after the first successful call
  4. `search_users("test")` returns structured results with `ConsistencyLevel: eventual` header on every request
  5. `get_user_photo_bytes()` returns `None` (not an exception) when the target user has no photo
**Plans**: TBD

Plans:
- [ ] 10-01: Azure AD app permissions + admin consent verification (GRAPH-02)
- [ ] 10-02: graph_client.py — MSAL singleton, token acquisition, caching (GRAPH-01, GRAPH-03)
- [ ] 10-03: User search and profile methods with ConsistencyLevel header (SRCH-04)

---

#### Phase 11: MCP Tools + Photo Proxy
**Goal**: Two new MCP tools are registered and callable, and authenticated users can retrieve colleague photos through a secure Flask proxy that absorbs 404s
**Depends on**: Phase 10 (graph_client.py verified in isolation)
**Requirements**: MCP-01, MCP-02, SRCH-01, SRCH-02, SRCH-03, PROF-01, PROF-03, PROF-05
**Success Criteria** (what must be TRUE):
  1. `search_colleagues` tool is callable via MCP and returns up to 10 results each with name, job title, department, and email
  2. `get_colleague_profile` tool is callable via MCP and returns detailed profile fields plus a `photo_url` string — no binary photo data in the tool result
  3. Searching for a name with no matches returns a clear "no results" message, not an empty array or silence
  4. `GET /api/photo/<user_id>` returns the JPEG photo for an authenticated user who has a photo
  5. `GET /api/photo/<user_id>` returns a placeholder image with HTTP 200 (not 404) when the user has no photo
  6. `GET /api/photo/<user_id>` returns 401/302-to-login for unauthenticated requests
**Plans**: TBD

Plans:
- [ ] 11-01: MCP tool definitions in tools.py — search_colleagues and get_colleague_profile schemas (MCP-01, MCP-02)
- [ ] 11-02: Tool dispatch + server.py graph client singleton initialization (SRCH-01, SRCH-02, SRCH-03, PROF-01, PROF-05)
- [ ] 11-03: Photo proxy route in app.py with @login_required and 404 absorption (PROF-03)

---

#### Phase 12: Profile Card Frontend + System Prompt
**Goal**: Users see inline profile cards with photo, name, title, department, and email when they ask about colleagues, and Atlas consistently selects the right tool
**Depends on**: Phase 11 (tool result JSON shape confirmed)
**Requirements**: MCP-03, MCP-04, PROF-02, PROF-04
**Success Criteria** (what must be TRUE):
  1. Asking "look up Jane Smith" in the chat renders an inline profile card with photo, name, job title, department, and email — the card is built from DOM elements, not markdown
  2. Profile cards for users without photos display a fallback avatar (initials or SVG icon), not a broken image
  3. A search returning multiple results renders multiple profile cards in the same message
  4. Atlas reliably selects `search_colleagues` for name queries and `get_colleague_profile` for ID-specific lookups — verified with at least 5 representative phrasings
**Plans**: TBD

Plans:
- [ ] 12-01: addProfileCard() DOM builder in app.js triggered by SSE tool events (MCP-04, PROF-02, PROF-04)
- [ ] 12-02: Profile card CSS — photo layout, card structure, fallback avatar (PROF-02, PROF-04)
- [ ] 12-03: System prompt update for colleague lookup tool selection guidance (MCP-03)

---

## Progress

**Execution Order:** 10 → 11 → 12

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Exchange Client Foundation | v1.0 | 4/4 | Complete | 2026-03-19 |
| 2. MCP Server Scaffold | v1.0 | 3/3 | Complete | 2026-03-19 |
| 3. Mailbox Tools | v1.0 | 3/3 | Complete | 2026-03-20 |
| 4. DAG and Database Tools | v1.0 | 3/3 | Complete | 2026-03-20 |
| 5. Mail Flow and Security Tools | v1.0 | 5/5 | Complete | 2026-03-20 |
| 6. Hybrid Tools | v1.0 | 2/2 | Complete | 2026-03-20 |
| 7. Chat App Core | v1.0 | 6/6 | Complete | 2026-03-21 |
| 8. Conversation Persistence | v1.0 | 3/3 | Complete | 2026-03-22 |
| 9. UI Polish | v1.0 | 4/4 | Complete | 2026-03-22 |
| 10. Graph Client Foundation | v1.1 | 0/3 | Not started | - |
| 11. MCP Tools + Photo Proxy | v1.1 | 0/3 | Not started | - |
| 12. Profile Card Frontend + System Prompt | v1.1 | 0/3 | Not started | - |
