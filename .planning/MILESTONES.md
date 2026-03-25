# Project Milestones: Exchange Infrastructure MCP Server

## v1.1 Colleague Lookup (Shipped: 2026-03-25)

**Delivered:** Colleague search and profile display via Microsoft Graph API — users ask about a colleague by name, Atlas auto-chains search to profile lookup, and an inline profile card renders with photo, name, title, department, and email.

**Phases completed:** 10-12 (9 plans total)

**Key accomplishments:**

- Microsoft Graph API client with MSAL client credentials flow, module-level token caching, and automatic refresh
- Two new MCP tools (search_colleagues, get_colleague_profile) bringing the server total to 17
- Secure Flask photo proxy route (`/api/photo/<user_id>`) with TTL cache and SVG placeholder fallback for users without photos
- Inline profile card DOM rendering in chat UI — photo, name, job title, department, and email built from tool result JSON (not AI-generated markdown)
- System prompt colleague lookup rules: auto-chain on single result, disambiguation on multiple, text deduplication contract with UI

**Stats:**

- 60 files created/modified
- 8,118 lines added across Python/JS/CSS/HTML
- 3 phases, 9 plans
- 3 days from milestone start to ship (2026-03-23 → 2026-03-25)

**Git range:** `711547c` (milestone start) → `b7e2425` (phase 12 complete)

**What's next:** v1.2 — address carried tech debt (test regressions, schema descriptions), expanded profile fields (office, phone, manager), department search

---

## v1.0 MVP (Shipped: 2026-03-22)

**Delivered:** A complete Exchange management system — 15-tool MCP server paired with a polished Python chat application backed by Azure AD SSO and Azure OpenAI, enabling any authorized colleague to query Exchange infrastructure through natural language.

**Phases completed:** 1-9 (35 plans total)

**Key accomplishments:**

- Async PowerShell subprocess runner with per-call PSSession lifecycle and Exchange Online authentication (interactive + CBA)
- 15-tool MCP server over stdio with structured error handling, stderr discipline, and LLM-optimized tool descriptions
- Full Exchange tool suite: mailbox governance, DAG health, mail flow tracing, DNS security (DMARC/SPF/DKIM), and hybrid connector monitoring
- Python chat application with Azure AD SSO, Azure OpenAI tool-calling loop, and SSE streaming
- SQLite conversation persistence with multi-thread sidebar navigation and auto-naming
- Polished UI: collapsible tool panels with JSON highlighting, copy-to-clipboard, loading indicators, keyboard shortcuts, and dark mode

**Stats:**

- 138 files created/modified
- 12,016 lines of Python/JS/CSS/HTML/SQL
- 9 phases, 35 plans
- 4 days from project initialization to ship (2026-03-19 → 2026-03-22)

**Git range:** `27bb782` (project init) → `9f7e1bd` (milestone audit)

**What's next:** v1.1 — address tech debt (persist tool events, historical message UX), Kerberos identity pass-through, additional Exchange tools

---
