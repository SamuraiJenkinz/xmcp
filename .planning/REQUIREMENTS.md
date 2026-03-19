# Requirements: Exchange Infrastructure MCP Server

**Defined:** 2026-03-19
**Core Value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data

## v1 Requirements

Requirements for initial working demo. Each maps to roadmap phases.

### Exchange Client

- [ ] **EXCL-01**: Async PowerShell subprocess runner using asyncio.create_subprocess_exec with per-call PSSession lifecycle (create + destroy each invocation)
- [ ] **EXCL-02**: Basic Auth service account authentication to Exchange (Kerberos pass-through deferred to v2)
- [ ] **EXCL-03**: DNS resolver for DMARC/SPF/DKIM lookups via dnspython (no PowerShell dependency)
- [ ] **EXCL-04**: Structured JSON output parsing with ConvertTo-Json -Depth 10 and explicit Select-Object field selection per tool

### MCP Server Infrastructure

- [ ] **MCPS-01**: Tool registration via official mcp SDK with stdio transport
- [ ] **MCPS-02**: Structured error handling — isError: true on all failure paths with sanitized error messages
- [ ] **MCPS-03**: Tool descriptions optimized for LLM tool selection (<800 characters each)
- [ ] **MCPS-04**: All logging to stderr only — zero stdout pollution in server.py

### Mailbox Tools

- [ ] **MBOX-01**: get_mailbox_stats — returns size, quota, last logon, database placement for a single mailbox
- [ ] **MBOX-02**: search_mailboxes — filters mailboxes by database, type, or display name
- [ ] **MBOX-03**: get_shared_mailbox_owners — returns full access, send-as, and send-on-behalf delegates

### DAG / Database Tools

- [ ] **DAGD-01**: list_dag_members — lists DAG member servers with operational status and active database count
- [ ] **DAGD-02**: get_dag_health — full replication health report including copy/replay queue lengths and content index
- [ ] **DAGD-03**: get_database_copies — returns all copies of a database across DAG members with activation preferences

### Mail Flow Tools

- [ ] **FLOW-01**: check_mail_flow — traces routing path between sender and recipient, connector resolution, TLS requirements
- [ ] **FLOW-02**: get_transport_queues — returns queue depths across all transport servers, flags backlogs over threshold
- [ ] **FLOW-03**: get_smtp_connectors — full inventory of send and receive connectors with auth and TLS configuration

### Security Tools

- [ ] **SECU-01**: get_dkim_config — DKIM signing configuration per domain, selector names, CNAME records
- [ ] **SECU-02**: get_dmarc_status — live DNS lookup of DMARC, SPF records with parsed policy values
- [ ] **SECU-03**: check_mobile_devices — ActiveSync device partnerships, access state, last sync, wipe history

### Hybrid Tools

- [ ] **HYBR-01**: get_hybrid_config — full hybrid topology: org relationships, federation trust, connector mapping
- [ ] **HYBR-02**: get_migration_batches — active and historical migration batch status with completion percentages
- [ ] **HYBR-03**: get_connector_status — validates hybrid connector health with live Exchange Online endpoint test

### Chat Application

- [ ] **CHAT-01**: Azure AD / Entra ID SSO via MSAL auth code flow (corporate identity login)
- [ ] **CHAT-02**: Azure OpenAI tool-calling loop — detect tool_calls, route to MCP server, append results, second completion call
- [ ] **CHAT-03**: SSE streaming of final AI response to browser in real-time
- [ ] **CHAT-04**: Context window management — tiktoken token counting, conversation pruning within 128K token limit

### User Interface

- [ ] **UIUX-01**: Conversation history persisting across sessions (SQLite-backed, scoped to authenticated user)
- [ ] **UIUX-02**: Multiple conversation threads with sidebar navigation (create, switch, delete)
- [ ] **UIUX-03**: Tool visibility panel — collapsible panel showing tool name, parameters, and raw Exchange result
- [ ] **UIUX-04**: Copy/export responses for reports or tickets
- [ ] **UIUX-05**: Conversation auto-naming from first query text
- [ ] **UIUX-06**: Loading indicators — "Querying Exchange..." status during tool execution (2-4s expected)
- [ ] **UIUX-07**: Keyboard shortcuts (Ctrl+Enter to send, Esc to cancel)
- [ ] **UIUX-08**: Dark mode toggle

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Identity & Security

- **IDEN-01**: Per-user Kerberos identity pass-through via Constrained Delegation (S4U2Proxy)
- **IDEN-02**: Per-user Exchange RBAC enforcement (Exchange sees actual colleague identity)

### Performance

- **PERF-01**: PSSession pooling with asyncio connection management (benchmark first — only if p50 > 4s)

### Exchange Online

- **EXOL-01**: Microsoft Graph API integration for cloud-only mailbox queries
- **EXOL-02**: Pure Exchange Online tools (cloud-only mailboxes, groups, transport rules)

### Chat Enhancements

- **ENHN-01**: Conversation search across all threads
- **ENHN-02**: Read-only share links for responses
- **ENHN-03**: Usage analytics dashboard (query patterns, tool usage, response times)

### Additional Tools

- **TOOL-01**: get_accepted_domains — full accepted domain inventory with domain type
- **TOOL-02**: get_retention_policies — MRM retention policy assignments per mailbox
- **TOOL-03**: get_address_book_policies — ABP assignments for operating company segmentation
- **TOOL-04**: get_exchange_certificates — certificate expiry monitoring across all Exchange servers
- **TOOL-05**: get_cas_virtual_directories — OWA, EWS, ActiveSync, Autodiscover URL validation
- **TOOL-06**: get_public_folder_stats — public folder size and hierarchy for migration planning
- **TOOL-07**: run_best_practices_analyzer — wrapper around Exchange BPA for health scoring

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Write operations (create/modify/delete mailboxes, transport rules, database ops) | Requires separate privileged service account and explicit approval gates — safety critical for 80K+ mailboxes |
| Free-form PowerShell input from the AI model | Bypasses RBAC and tool schema validation — unacceptable security risk |
| Mailbox content retrieval (reading emails, attachments) | Privacy violation, e-discovery compliance issue |
| DAG failover or database activation via chat | Blast radius too large for conversational UI — requires manual runbook |
| Raw PowerShell output returned to AI model | Wastes context tokens, noisy, unreliable for LLM interpretation |
| Mobile native app | Browser-based internal tool only — mobile-responsive web is sufficient |
| Production Azure OpenAI endpoint | v1 targets stg1 non-prod ingress; production cutover is a deployment task, not a code change |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXCL-01 | Phase 1 | Pending |
| EXCL-02 | Phase 1 | Pending |
| EXCL-03 | Phase 1 | Pending |
| EXCL-04 | Phase 1 | Pending |
| MCPS-01 | Phase 2 | Pending |
| MCPS-02 | Phase 2 | Pending |
| MCPS-03 | Phase 2 | Pending |
| MCPS-04 | Phase 2 | Pending |
| MBOX-01 | Phase 3 | Pending |
| MBOX-02 | Phase 3 | Pending |
| MBOX-03 | Phase 3 | Pending |
| DAGD-01 | Phase 4 | Pending |
| DAGD-02 | Phase 4 | Pending |
| DAGD-03 | Phase 4 | Pending |
| FLOW-01 | Phase 5 | Pending |
| FLOW-02 | Phase 5 | Pending |
| FLOW-03 | Phase 5 | Pending |
| SECU-01 | Phase 5 | Pending |
| SECU-02 | Phase 5 | Pending |
| SECU-03 | Phase 5 | Pending |
| HYBR-01 | Phase 6 | Pending |
| HYBR-02 | Phase 6 | Pending |
| HYBR-03 | Phase 6 | Pending |
| CHAT-01 | Phase 7 | Pending |
| CHAT-02 | Phase 7 | Pending |
| CHAT-03 | Phase 7 | Pending |
| CHAT-04 | Phase 7 | Pending |
| UIUX-01 | Phase 8 | Pending |
| UIUX-02 | Phase 8 | Pending |
| UIUX-03 | Phase 9 | Pending |
| UIUX-04 | Phase 9 | Pending |
| UIUX-05 | Phase 8 | Pending |
| UIUX-06 | Phase 9 | Pending |
| UIUX-07 | Phase 9 | Pending |
| UIUX-08 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0

---
*Requirements defined: 2026-03-19*
*Last updated: 2026-03-19 after roadmap creation*
