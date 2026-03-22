# Roadmap: Exchange Infrastructure MCP Server

## Overview

This roadmap delivers a complete Exchange management system for Marsh McLennan: an MCP server exposing 15 Exchange infrastructure tools, paired with a Python chat application backed by Azure AD SSO and Azure OpenAI. The delivery follows a strict bottom-up dependency chain — Exchange client first (every tool depends on it), then the MCP protocol layer, then all 15 tools across three phases, then the chat orchestration layer, then the UI. Each phase produces a verifiable capability before the next phase begins.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Exchange Client Foundation** - Async PowerShell subprocess runner, interactive/CBA auth, DNS utilities, JSON output parsing
- [x] **Phase 2: MCP Server Scaffold** - stdio transport, tool registration infrastructure, stderr discipline, error handling
- [x] **Phase 3: Mailbox Tools** - get_mailbox_stats, search_mailboxes, get_shared_mailbox_owners
- [x] **Phase 4: DAG and Database Tools** - list_dag_members, get_dag_health, get_database_copies
- [x] **Phase 5: Mail Flow and Security Tools** - check_mail_flow, get_transport_queues, get_smtp_connectors, get_dkim_config, get_dmarc_status, check_mobile_devices
- [x] **Phase 6: Hybrid Tools** - get_hybrid_config, get_connector_status (get_migration_batches removed — out of MMC scope)
- [x] **Phase 7: Chat App Core** - Azure AD SSO, Azure OpenAI tool-calling loop, SSE streaming, context window management
- [x] **Phase 8: Conversation Persistence** - SQLite threads and messages, multi-thread sidebar navigation, conversation auto-naming
- [ ] **Phase 9: UI Polish** - Tool visibility panel, copy/export, loading indicators, keyboard shortcuts, dark mode

## Phase Details

### Phase 1: Exchange Client Foundation
**Goal**: A verified, tested Exchange client layer exists that proves the PowerShell subprocess pattern works against the real Exchange Online environment with certificate-based Azure AD authentication
**Depends on**: Nothing (first phase)
**Requirements**: EXCL-01, EXCL-02, EXCL-03, EXCL-04
**Success Criteria** (what must be TRUE):
  1. A PowerShell command against Exchange completes and returns structured JSON without hanging or orphaning a session
  2. The async subprocess runner handles timeout and clean session teardown via try/finally on every execution path
  3. A DNS TXT record lookup for a test domain returns parsed DMARC/SPF data without invoking PowerShell
  4. A single proof-of-concept cmdlet (Get-OrganizationConfig) returns a response with all expected fields populated via explicit Select-Object
  5. Certificate-based Azure AD app-only credentials authenticate successfully to Exchange Online
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold with uv, Python 3.11, and async PowerShell subprocess runner
- [x] 01-02-PLAN.md — DNS resolver utilities for DMARC/SPF with TTL cache
- [x] 01-03-PLAN.md — ExchangeClient class with interactive/CBA auth, retry logic, and verify_connection
- [x] 01-04-PLAN.md — End-to-end integration verification against live Exchange and DNS

### Phase 2: MCP Server Scaffold
**Goal**: A runnable MCP server exists that can be inspected with mcp dev, registers tools correctly over stdio, and applies error handling and logging discipline uniformly
**Depends on**: Phase 1
**Requirements**: MCPS-01, MCPS-02, MCPS-03, MCPS-04
**Success Criteria** (what must be TRUE):
  1. The MCP server starts and the mcp dev inspector can enumerate registered tools without errors
  2. Every failure path returns isError: true with a sanitized error message — no raw PowerShell tracebacks reach the client
  3. All logging goes to stderr; stdout contains only valid JSON-RPC messages with zero pollution
  4. Tool descriptions are under 800 characters each and produce correct tool selection when tested with a prompt
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Scaffold server.py with stderr-only logging, stdio transport, startup validation, and ping placeholder tool
- [x] 02-02-PLAN.md — Register all 15 Exchange tools with dispatch table, error wrapping template, and isError conventions
- [x] 02-03-PLAN.md — Refine and validate all tool descriptions for LLM tool-selection accuracy

### Phase 3: Mailbox Tools
**Goal**: The three mailbox tools are fully implemented, return well-structured JSON, and pass end-to-end validation through the MCP server
**Depends on**: Phase 2
**Requirements**: MBOX-01, MBOX-02, MBOX-03
**Success Criteria** (what must be TRUE):
  1. get_mailbox_stats returns size, quota, last logon, and database placement for a given mailbox UPN
  2. search_mailboxes returns a filtered list when queried by database, type, or display name with ResultSize capped
  3. get_shared_mailbox_owners returns full access, send-as, and send-on-behalf delegates for a shared mailbox
  4. All three tools return isError: true with a useful message when given an invalid mailbox identity
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Implement get_mailbox_stats with shared helpers (_validate_upn, _format_size) and unit tests
- [x] 03-02-PLAN.md — Implement search_mailboxes with all filter modes, ResultSize cap, and truncation detection
- [x] 03-03-PLAN.md — Implement get_shared_mailbox_owners for all three delegate permission types

### Phase 4: DAG and Database Tools
**Goal**: The three DAG and database tools are fully implemented and return accurate replication health data through the MCP server
**Depends on**: Phase 3
**Requirements**: DAGD-01, DAGD-02, DAGD-03
**Success Criteria** (what must be TRUE):
  1. list_dag_members returns all member servers with operational status and active database count
  2. get_dag_health returns a full replication health report including copy/replay queue lengths and content index state per copy
  3. get_database_copies returns all copies of a named database across DAG members with activation preferences
  4. All three tools return isError: true with a useful message when the DAG or database name is not found
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Implement list_dag_members with DAG metadata, per-server enrichment (site, version), and active/passive database counts
- [x] 04-02-PLAN.md — Implement get_dag_health with per-server replication health and partial results for unreachable servers
- [x] 04-03-PLAN.md — Implement get_database_copies with authoritative activation preferences from Get-MailboxDatabase and database size

### Phase 5: Mail Flow and Security Tools
**Goal**: All six mail flow and security tools are implemented and return accurate data — the security tools combining live DNS lookups with Exchange PowerShell data where needed
**Depends on**: Phase 4
**Requirements**: FLOW-01, FLOW-02, FLOW-03, SECU-01, SECU-02, SECU-03
**Success Criteria** (what must be TRUE):
  1. check_mail_flow traces the routing path between a sender and recipient and identifies the connector and TLS requirement
  2. get_transport_queues returns queue depths across all transport servers and flags any queues over the backlog threshold
  3. get_smtp_connectors returns the full send and receive connector inventory with auth and TLS configuration
  4. get_dkim_config returns DKIM signing configuration and CNAME record data per domain
  5. get_dmarc_status returns a live-resolved DMARC and SPF policy without relying on PowerShell
  6. check_mobile_devices returns ActiveSync device partnerships with access state, last sync, and wipe history
**Plans**: 5 plans

Plans:
- [x] 05-01-PLAN.md — Implement check_mail_flow with config-based route inference and accepted domain detection
- [x] 05-02-PLAN.md — Implement get_transport_queues with per-server iteration and backlog threshold flagging
- [x] 05-03-PLAN.md — Implement get_smtp_connectors with send/receive filter and multi-valued property projection
- [x] 05-04-PLAN.md — Add get_cname_record to dns_utils and implement get_dkim_config with DNS CNAME validation
- [x] 05-05-PLAN.md — Implement get_dmarc_status (pure DNS) and check_mobile_devices (Exchange with wipe history)

### Phase 6: Hybrid Tools
**Goal**: All three hybrid tools are implemented and validate the live Exchange Online connector health — completing the full 15-tool MCP server
**Depends on**: Phase 5
**Requirements**: HYBR-01, HYBR-02, HYBR-03
**Success Criteria** (what must be TRUE):
  1. get_hybrid_config returns the full hybrid topology including org relationships, federation trust, and connector mapping
  2. get_migration_batches returns active and historical migration batch status with completion percentages
  3. get_connector_status reports hybrid connector health with a live test result against the Exchange Online endpoint
  4. All 15 tools enumerate correctly when queried via the MCP inspector — the server is fully complete
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md — Remove get_migration_batches (out of scope), implement get_hybrid_config with 5-cmdlet composite handler
- [x] 06-02-PLAN.md — Implement get_connector_status with TLS certificate validation and connector health assessment

### Phase 7: Chat App Core
**Goal**: A colleague can log in with their MMC identity, ask an Exchange question in natural language, watch the tool call resolve, and read an AI-composed answer — end-to-end
**Depends on**: Phase 6
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04
**Success Criteria** (what must be TRUE):
  1. A colleague navigates to the chat app, is redirected to Azure AD login, and arrives at the chat interface authenticated as themselves
  2. A natural language query that requires an Exchange tool causes the AI to invoke the correct MCP tool, receive the result, and produce a coherent answer in a single round-trip
  3. The AI response streams to the browser in real-time — partial text appears before the full response is ready
  4. A conversation that would exceed the 128K context window is pruned automatically without crashing or producing an error
  5. The Azure AD token is validated server-side before any protected endpoint is accessible
**Plans**: 6 plans

Plans:
- [x] 07-01-PLAN.md — Scaffold Flask app with Waitress, session management, and environment/secrets loading from AWS Secrets Manager
- [x] 07-02-PLAN.md — Implement Azure AD / Entra ID SSO via MSAL auth code flow with SerializableTokenCache and Conditional Access handler
- [x] 07-03-PLAN.md — Implement Azure OpenAI connectivity to MMC stg1 endpoint and basic chat completions without tool calling
- [x] 07-04-PLAN.md — Implement MCP client integration — spawn server.py on startup, tools/list, inject tools into OpenAI requests as function schemas
- [x] 07-05-PLAN.md — Implement tool-calling loop — detect tool_calls, route to MCP, append messages in correct order, second completion call
- [x] 07-06-PLAN.md — Implement SSE streaming of final response and tiktoken context window management with conversation pruning

### Phase 8: Conversation Persistence
**Goal**: A colleague can return to the app the next day and find their previous conversations intact, navigate between threads, and have new conversations named automatically
**Depends on**: Phase 7
**Requirements**: UIUX-01, UIUX-02, UIUX-05
**Success Criteria** (what must be TRUE):
  1. Conversations persist across browser sessions — closing and reopening the app shows all previous threads
  2. A colleague can create a new conversation thread, switch between existing threads, and delete a thread from the sidebar
  3. Conversations are automatically named from the first query text — no manual naming required
  4. Conversation history is scoped to the authenticated user — one colleague cannot see another's threads
**Plans**: 3 plans

Plans:
- [x] 08-01-PLAN.md — SQLite database layer (db.py, schema.sql) and thread CRUD API blueprint (conversations.py)
- [x] 08-02-PLAN.md — Migrate chat_stream from Flask session to SQLite with thread_id routing and auto-naming
- [x] 08-03-PLAN.md — Sidebar UI with thread list, create/switch/delete/rename, and thread_id integration

### Phase 9: UI Polish
**Goal**: The chat interface feels like a polished internal tool — colleagues can inspect what Exchange data was used, export answers for tickets, and work efficiently with keyboard and visual preferences
**Depends on**: Phase 8
**Requirements**: UIUX-03, UIUX-04, UIUX-06, UIUX-07, UIUX-08
**Success Criteria** (what must be TRUE):
  1. Every AI response that involved an Exchange tool shows a collapsible panel with the tool name, parameters sent, and raw Exchange result
  2. A colleague can copy any response to the clipboard or export it for a report or ticket in one action
  3. A "Querying Exchange..." loading indicator is visible during the 2-4 second tool execution window
  4. Pressing Ctrl+Enter sends a message and Esc cancels an in-progress response
  5. A dark mode toggle persists the colleague's visual preference across sessions
**Plans**: TBD

Plans:
- [ ] 09-01: Implement collapsible tool visibility panel per message with tool name, parameters, and raw result
- [ ] 09-02: Implement copy-to-clipboard and export response functionality
- [ ] 09-03: Implement loading indicator with "Querying Exchange..." status tied to tool execution state
- [ ] 09-04: Implement keyboard shortcuts (Ctrl+Enter to send, Esc to cancel) and dark mode toggle with session persistence

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Exchange Client Foundation | 4/4 | ✓ Complete | 2026-03-19 |
| 2. MCP Server Scaffold | 3/3 | ✓ Complete | 2026-03-19 |
| 3. Mailbox Tools | 3/3 | ✓ Complete | 2026-03-20 |
| 4. DAG and Database Tools | 3/3 | ✓ Complete | 2026-03-20 |
| 5. Mail Flow and Security Tools | 5/5 | ✓ Complete | 2026-03-20 |
| 6. Hybrid Tools | 2/2 | ✓ Complete | 2026-03-20 |
| 7. Chat App Core | 6/6 | ✓ Complete | 2026-03-21 |
| 8. Conversation Persistence | 3/3 | ✓ Complete | 2026-03-22 |
| 9. UI Polish | 0/4 | Not started | - |
