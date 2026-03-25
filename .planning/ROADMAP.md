# Roadmap: Exchange Infrastructure MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-9 (shipped 2026-03-22)
- ✅ **v1.1 Colleague Lookup** — Phases 10-12 (shipped 2026-03-25)

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

<details>
<summary>v1.1 Colleague Lookup (Phases 10-12) — SHIPPED 2026-03-25</summary>

- [x] Phase 10: Graph Client Foundation (4/4 plans) — completed 2026-03-24
- [x] Phase 11: MCP Tools + Photo Proxy (3/3 plans) — completed 2026-03-24
- [x] Phase 12: Profile Card Frontend + System Prompt (2/2 plans) — completed 2026-03-25

</details>

## Progress

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
| 10. Graph Client Foundation | v1.1 | 4/4 | Complete | 2026-03-24 |
| 11. MCP Tools + Photo Proxy | v1.1 | 3/3 | Complete | 2026-03-24 |
| 12. Profile Card Frontend + System Prompt | v1.1 | 2/2 | Complete | 2026-03-25 |
