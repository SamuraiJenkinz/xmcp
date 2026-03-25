# Exchange Infrastructure MCP Server

## What This Is

A complete Exchange management system for Marsh McLennan — an MCP server exposing 17 tools (15 Exchange infrastructure + 2 colleague lookup) paired with a polished Python chat application. Colleagues across Marsh, Mercer, Oliver Wyman, and Guy Carpenter can query Exchange health, mailbox governance, mail flow, hybrid configuration, and look up colleagues with inline profile cards — all through natural language, powered by MMC's corporate Azure OpenAI (gpt-4o-mini-128k). Features include Azure AD SSO, Microsoft Graph API integration, multi-thread conversation history, collapsible tool visibility panels, copy-to-clipboard, keyboard shortcuts, and dark mode. No direct PowerShell access or cmdlet knowledge required.

## Core Value

Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data — eliminating the access dependency on Exchange engineers and the knowledge dependency on PowerShell expertise.

## Requirements

### Validated

- MCP server with 15 Exchange management tools (mailbox, DAG, mail flow, security, hybrid) — v1.0
- Python chat application with Azure AD/Entra ID SSO authentication — v1.0
- Polished internal tool UI with conversation history persisting across sessions — v1.0
- Multiple conversation threads with sidebar navigation — v1.0
- Tool visibility — show which Exchange tool was invoked and what data was returned — v1.0
- Export/share — copy or export responses for reports or tickets — v1.0
- Azure OpenAI integration via MMC corporate endpoint (gpt-4o-mini-128k) — v1.0
- Async PowerShell execution layer with per-call PSSession lifecycle — v1.0
- DNS-based security lookups (DMARC/SPF/DKIM) via dnspython — v1.0
- All operations read-only in v1 — v1.0
- Microsoft Graph API client with MSAL client credentials, token caching, auto-refresh — v1.1
- Azure AD app permissions: User.Read.All, ProfilePhoto.Read.All with admin consent — v1.1
- MCP tools: search_colleagues and get_colleague_profile (17 tools total) — v1.1
- Colleague search by name with ConsistencyLevel: eventual header — v1.1
- Secure photo proxy route with TTL cache and SVG placeholder fallback — v1.1
- Inline profile card DOM rendering (photo, name, title, department, email) — v1.1
- System prompt colleague lookup routing with auto-chain and deduplication — v1.1

### Active

(No active requirements — next milestone not yet defined)

### Out of Scope

- Write operations (mailbox modifications, transport rule changes, database operations) — requires separate privileged service account and approval gates
- Exchange Online-only queries via Microsoft Graph API — hybrid on-prem focus for v1
- Mobile app — browser-based internal tool only
- Persistent PowerShell session pooling — per-call sessions for v1, optimize later if latency is a concern
- Production Azure OpenAI endpoint — v1 targets stg1 non-prod ingress
- Future tools (accepted domains, retention policies, ABPs, certificates, CAS VDirs, public folders, BPA) — extend after v1
- Pass-through user identity via Kerberos delegation — deferred to v2 (IDEN-01, IDEN-02)

## Context

- **Current state:** v1.1 Colleague Lookup shipped 2026-03-25. ~20K LOC (Python + JS/CSS/HTML/SQL). 12 phases, 44 plans complete across 2 milestones.
- **Environment:** Hybrid Exchange (Exchange 2019 on-prem + Exchange Online), 80,000+ mailboxes, multiple DAGs, AWS-hosted mailbox servers
- **Organization:** Marsh McLennan Companies (MMC) — Colleague Tech Services (CTS) team
- **Strategic alignment:** Supports One Marsh 2026 infrastructure consolidation and MMC Corporate AI Platform initiatives
- **Existing pain point:** Shared mailbox governance (31,246 rows in ExoNotes.xlsx) currently requires batch exports — this enables on-demand live queries
- **AI backend:** MMC-approved Azure OpenAI deployment at Dallas non-prod ingress (stg1), gpt-4o-mini-128k model, API version 2023-05-15
- **Architecture doc:** `exchange-mcp-architecture.md` in project root — comprehensive reference for all tool schemas, data flows, and security model
- **Known tech debt:** Tool events not persisted to SQLite (historical messages lose tool panels); copy button not on historical messages; CHATGPT_ENDPOINT not in secrets pipeline; v1.1 test regressions (description phrasing, tool count assertion); get_user_photo_bytes() dead code; get_colleague_profile user_id schema description misleading

## Constraints

- **Tech stack:** Python 3.11+ (MCP server + chat app), PowerShell 5.1+ (Exchange cmdlets), Flask 3.x + Waitress + Jinja2 (frontend)
- **Deployment:** On-premises domain-joined Windows server — required for Kerberos authentication to Exchange
- **AI endpoint:** Must use MMC corporate Azure OpenAI gateway only — no external AI services
- **Security:** API keys sourced from AWS Secrets Manager at runtime — never hardcoded or committed. Service account credentials via Kerberos or Windows Credential Manager
- **RBAC:** Minimum Exchange roles: View-Only Recipients, View-Only Configuration, Mailbox Search, Database Copies
- **Network:** MCP server must run on same subnet as Exchange management servers. Chat app restricted to MMC internal network/VPN
- **Authentication:** Azure AD/Entra ID SSO for chat app, Kerberos Constrained Delegation for pass-through identity to Exchange (v2)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Flask 3.x + Waitress over FastAPI | Sync Flask with run_in_executor for async PS; Waitress for production Windows WSGI | Good — working in production |
| Pass-through user identity over service account | Per-user audit trail, respects existing Exchange RBAC | Pending — deferred to v2 (Kerberos delegation) |
| Azure AD/Entra ID SSO | Corporate identity standard at MMC, required for pass-through identity chain | Good — MSAL auth code flow working |
| All 15 tools in v1 (14 Exchange + ping) | Tools are well-scoped and documented, incremental delivery doesn't reduce complexity | Good — all tools verified |
| Per-call PSSession (no pooling) | Eliminates session leak risk, fresh auth per call, simpler implementation | Good — accept 2-4s latency |
| -EncodedCommand over -Command | Prevents cp1252 corruption on Windows; Base64 UTF-16LE encoding | Good — correctness improvement |
| openai.OpenAI (not AzureOpenAI) | MMC gateway URL format incompatible with Azure SDK auto-routing | Good — working with gateway |
| SQLite for conversation persistence | Zero ops, correct for <100 concurrent users, auto-bootstrap | Good — working cleanly |
| get_migration_batches removed | MMC does not use migration batches; confirmed during Phase 6 research | Good — scope correctly reduced |
| msal + requests over msgraph-sdk | 7 new transitive packages for two REST endpoints; already have both deps | Good — minimal dependency footprint |
| photo_url proxy indirection | Binary photo data must never enter LLM context; proxy absorbs 404s with SVG placeholder | Good — clean separation |
| asyncio.to_thread for sync graph calls | graph_client uses sync requests; MCP server is async; to_thread keeps event loop non-blocking | Good — no blocking |
| Lazy graph_client imports in handlers | Avoids Config evaluation at module import time; fails gracefully if Azure creds missing | Good — startup resilience |
| System prompt rules 7-10 for colleague lookup | Auto-chain on single result, disambiguate on multiple, suppress text duplication of card fields | Good — reliable tool routing |

---
*Last updated: 2026-03-25 after v1.1 milestone*
