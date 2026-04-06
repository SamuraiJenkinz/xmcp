# Exchange Infrastructure MCP Server

## What This Is

A complete Exchange management system for Marsh McLennan — an MCP server exposing 17 tools (15 Exchange infrastructure + 2 colleague lookup) paired with a modern React 19 chat application built on Fluent UI v9 and Tailwind v4. Colleagues across Marsh, Mercer, Oliver Wyman, and Guy Carpenter can query Exchange health, mailbox governance, mail flow, hybrid configuration, and look up colleagues with inline profile cards — all through natural language, powered by MMC's corporate Azure OpenAI (gpt-4o-mini-128k). Features include Azure AD App Role access gating, per-message feedback (thumbs up/down with SQLite persistence), thread search (client-side title filter + FTS5 full-text), Markdown conversation export, motion entrance animations, Azure AD SSO, Microsoft Graph API integration, multi-thread conversation history with recency grouping, collapsible tool panels with status badges and elapsed time, syntax-highlighted JSON, copy-to-clipboard, keyboard shortcuts (Ctrl+K search), WCAG AA accessible focus management, and dark/light mode with Fluent 2 design tokens. No direct PowerShell access or cmdlet knowledge required.

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
- React 19 + Vite + Fluent UI v9 + Tailwind v4 frontend with hybrid SPA pattern (ATLAS_UI feature flag) — v1.2
- Microsoft Copilot aesthetic — message bubbles, entrance animations, Fluent 2 design system with 62 --atlas- tokens — v1.2
- Redesigned sidebar with recency grouping (Today/Yesterday/This Week/Older) and collapse mode — v1.2
- Redesigned tool panels with chevron toggle, status badges, elapsed time, syntax-highlighted JSON — v1.2
- Professional splash/login page with Fluent 2 aesthetic — v1.2
- Stop generation button, auto-resize textarea, welcome state with prompt chips — v1.2
- Profile cards and search result cards aligned with Fluent 2 component patterns — v1.2
- WCAG AA accessibility — focus rings, skip navigation, roving tabindex, logical tab order — v1.2
- Dark/light mode with three-tier Fluent 2 surface hierarchy and Segoe UI Variable typography — v1.2
- Fix: Tool events persisted to SQLite (historical messages retain tool panels) — v1.2
- Fix: Copy-to-clipboard on historical messages — v1.2
- Fix: 3 test regressions, dead code removal, schema description correction — v1.2
- Azure AD App Role access gating with role_required decorator, structured 401/403 JSON, AccessDenied Fluent 2 component — v1.3
- Per-message thumbs up/down feedback with SQLite persistence, toggle retraction, optional comment Popover, ARIA live region — v1.3
- Thread search — instant client-side title filter + SQLite FTS5 full-text search with debounce, snippets, Ctrl+K shortcut — v1.3
- Conversation export — client-side Markdown with tool panel data, slug-dated filenames, Fluent MenuButton — v1.3
- Motion entrance animations — m.div fade+slide on messages, sidebar CSS transition, feedback scale micro-interaction, MotionConfig reducedMotion — v1.3

### Active

- Message trace tool — search by sender/recipient/date range, return subject, delivery status, timestamps, routing path (Get-MessageTrace, Exchange Online, 10-day window)
- Feedback analytics MCP tools — query feedback data through conversation (volume, thumbs-down with comments, tool correlation)

### Out of Scope

### Out of Scope

- Write operations (mailbox modifications, transport rule changes, database operations) — requires separate privileged service account and approval gates
- Exchange Online-only queries via Microsoft Graph API — hybrid on-prem focus for v1
- Mobile app — browser-based internal tool only, desktop (1080p-1440p)
- Persistent PowerShell session pooling — per-call sessions, optimize later if latency is a concern
- Production Azure OpenAI endpoint — targets stg1 non-prod ingress
- Future tools (accepted domains, retention policies, ABPs, certificates, CAS VDirs, public folders, BPA) — extend after v1
- Pass-through user identity via Kerberos delegation — deferred to v2 (IDEN-01, IDEN-02)
- Typewriter/per-character animation — artificial latency, frustrates fast readers
- Real-time multi-user collaboration — IT engineers investigate solo
- Mobile responsive layout — desktop-only tool

## Context

- **Current milestone:** v1.4 — Message Trace & Feedback Analytics
- **Current state:** ~75.7K LOC (Python + TypeScript/CSS/SQL). 25 phases, 76 plans complete across 4 milestones.
- **Tech stack:** Python 3.11 (Flask + Waitress backend), React 19 + Vite + TypeScript + Fluent UI v9 + Tailwind v4 + motion@12.38.0 (frontend), PowerShell 5.1+ (Exchange cmdlets)
- **Design reference:** `designux.md` in project root — comprehensive design brief with component inventory, design tokens, and user flows
- **Environment:** Hybrid Exchange (Exchange 2019 on-prem + Exchange Online), 80,000+ mailboxes, multiple DAGs, AWS-hosted mailbox servers
- **Organization:** Marsh McLennan Companies (MMC) — Colleague Tech Services (CTS) team
- **Strategic alignment:** Supports One Marsh 2026 infrastructure consolidation and MMC Corporate AI Platform initiatives
- **Existing pain point:** Shared mailbox governance (31,246 rows in ExoNotes.xlsx) currently requires batch exports — this enables on-demand live queries
- **AI backend:** MMC-approved Azure OpenAI deployment at Dallas non-prod ingress (stg1), gpt-4o-mini-128k model, API version 2023-05-15
- **Architecture doc:** `exchange-mcp-architecture.md` in project root — comprehensive reference for all tool schemas, data flows, and security model
- **Known tech debt:** Sidebar CSS transition lacks prefers-reduced-motion override (low severity); login_required returns 302 instead of 401 for API routes (mitigated by role_required); historical tool panels always show "Done" badge (error status not persisted); historical tool panels lose elapsed time; AuthContext.error field unused; CHATGPT_ENDPOINT not in secrets pipeline

## Constraints

- **Tech stack:** Python 3.11+ (MCP server + chat app), PowerShell 5.1+ (Exchange cmdlets), Flask 3.x + Waitress (backend), React 19 + Vite + TypeScript + Fluent UI v9 + Tailwind v4 (frontend)
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

| React 19 over Svelte 5 for v1.2 | Fluent UI v9 is React-only from Microsoft; official packages for Copilot aesthetic | Good — full Fluent 2 integration |
| Hybrid SPA pattern (ATLAS_UI flag) | Flask renders Jinja2 shell, React mounts on #app; no CORS, no cookie reconfiguration; safe dual-mode rollout | Good — zero regression path |
| 62 --atlas- semantic design tokens | Three-tier surface hierarchy matching Fluent 2 webDarkTheme; single source of truth for light/dark | Good — clean token foundation |
| Native details/summary for tool panels | Simpler than Fluent Accordion; fewer dependencies; consistent expand/collapse | Good — reliable cross-browser |
| SSE via fetch + ReadableStream | Not EventSource; AbortController in useRef for cancel support | Good — full streaming control |
| Migration order: scaffold → port → visual | Visual work before functional parity is the primary failure mode | Good — proven approach |

| App Roles over groupMembershipClaims for access gating | No overage problem at 80K+ users; decouples app from raw group GUIDs; manages access via group-to-role assignment in Entra ID | Good — role_required decorator on all routes |
| AuthStatus discriminated union over boolean flags | Exhaustive — compiler enforces all branches; extensible without adding new booleans | Good — clean 5-state discrimination |
| migrate_db() idempotent startup migration | Additive-only DDL on every startup; existing databases gain new tables automatically | Good — zero-ops deployment |
| FTS5 unicode61 tokenizer (not porter) | Porter over-stems Exchange technical terms (DAGHealth, etc.) | Good — accurate matching |
| motion@12.38.0 (not framer-motion) | Official successor; React 19 compatible; tree-shakeable with LazyMotion | Good — confirmed compat |
| Client-side Markdown export (not server-side) | Zero server round-trip; tool panel data available in client state | Good — instant download |
| loadedCountRef for historical message gate | Snapshot messages.length on thread switch; idx >= ref = isNew | Good — prevents disorienting animations |

---
*Last updated: 2026-04-06 after v1.4 milestone started*
