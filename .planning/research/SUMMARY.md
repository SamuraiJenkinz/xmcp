# Project Research Summary

**Project:** Exchange Infrastructure MCP Server — Marsh McLennan Companies (xmcp)
**Domain:** Enterprise MCP Server + Python Chat Application + Exchange Management Shell Integration
**Researched:** 2026-03-19
**Confidence:** HIGH (all four research areas draw primarily from project-owned architecture docs and official Microsoft/MCP documentation)

---

## Executive Summary

This project builds two cooperating systems on a single domain-joined Windows server: an MCP server that exposes 15 Exchange 2019 management tools to any MCP-compatible client, and a Python chat application that connects those tools to Azure OpenAI (gpt-4o-mini) behind an Azure AD / Entra ID SSO login. The primary user-facing value is replacing a 31,246-row Excel-driven governance process with live, natural-language queries to Exchange. The architecture is well-specified in existing project documentation — the build is principally an execution challenge, not a design challenge.

The recommended implementation approach follows a bottom-up dependency chain: Exchange client first, then MCP server, then chat app core, then UI polish. All four researchers agree on this ordering. The critical path dependency is the Exchange PowerShell subprocess layer — every one of the 15 tools depends on it, and its latency (2-4 seconds per call due to per-call PSSession creation) is the dominant user experience constraint that must be accepted as a design reality, not deferred as a later optimization problem.

The two highest-risk areas are Kerberos Constrained Delegation and the stdout/stderr discipline for the MCP stdio transport. KCD requires Active Directory team cooperation outside the Python code and should be planned as a v2 enhancement, with Basic Auth service account as the v1 fallback. stdout pollution can silently render the entire MCP server non-functional and must be addressed in the first line of scaffold code. Both risks are mitigable with known patterns; neither requires a change of direction.

---

## Key Findings

### Recommended Stack

The stack is almost entirely constrained by the deployment environment: domain-joined Windows Server, Exchange 2019, AWS Secrets Manager, and the MMC CTS Azure OpenAI gateway. These constraints eliminate Django, Gunicorn, uvicorn, and any Unix-only tooling. The official `mcp` Python SDK (not the third-party `fastmcp` wrapper) is the correct MCP protocol implementation. `boto3` is the only option for AWS Secrets Manager. `dnspython` is the only reasonable path for DMARC/SPF TXT lookups. `subprocess` + `asyncio` is the correct pattern for PowerShell process management on Windows — no library beyond stdlib is needed.

The only genuinely open stack decision is Flask vs FastAPI for the chat application, which is addressed in the Conflicts section below. All other decisions have a single correct answer given the constraints.

See `.planning/research/STACK.md` for the full dependency matrix with version floors and verification URLs.

**Core technologies:**
- Python 3.11/3.12: Runtime — 3.11 project-mandated floor; 3.13 not yet safe (pywinpty lag)
- `mcp >= 1.0.0`: MCP protocol — official Anthropic SDK, stdio transport for v1
- Flask 3.x + Waitress 3.x: Web framework — Windows-compatible WSGI stack (DISPUTED: see Conflicts)
- MSAL >= 1.28.0: Azure AD / Entra ID SSO — only Microsoft-maintained Python auth library for Entra ID
- `openai >= 1.30.0`: Azure OpenAI client — project-pinned floor; no alternative
- `dnspython >= 2.6.1`: DNS lookups — project-pinned; pure Python TXT record resolution
- `boto3 >= 1.34.0`: AWS Secrets Manager — project-specified secret source
- SQLite (stdlib): Conversation history — zero-ops, correct for <100 concurrent users
- `uv`: Package management — 10-100x faster than pip+venv, produces lockfiles
- PowerShell 5.1 (system): Exchange Management Shell host — built-in on Windows; Exchange 2019 requires PS 5.1

### Expected Features

The project has three distinct feature domains: MCP server tool exposure, enterprise chat UI, and Exchange management tooling. The 15 Exchange tools are fully specified in the architecture document and are not in question — they are the core deliverable.

See `.planning/research/FEATURES.md` for complete table stakes / differentiators / anti-features breakdown per domain.

**Must have (v1 — already in scope per PROJECT.md):**
- All 15 Exchange tools with JSON schemas and structured JSON responses
- Azure AD / Entra ID SSO with MSAL (no unauthenticated access, ever)
- Per-call PSSession with Kerberos auth + Basic Auth fallback
- Conversation history persisting across sessions (DB-backed, scoped to user identity)
- Multiple conversation threads with sidebar navigation
- Tool visibility — collapsible panel showing tool name, parameters, and raw result
- Copy/export per-response (clipboard minimum)
- Structured error messages visible to the user
- Loading indicator during tool execution (3-8 second wait is visible)

**Should have (v1 if time permits):**
- Conversation auto-naming from first query
- Queue backlog threshold configurable (not hardcoded 100)
- Keyboard shortcuts (Ctrl+Enter to send)
- Dark mode toggle

**Defer to post-v1:**
- Write operations (create/modify/delete) — requires separate privileged account and confirmation gates; explicit out-of-scope per PROJECT.md
- Exchange Online Graph API tools — separate auth flow, explicit out-of-scope per PROJECT.md
- Per-user Kerberos identity pass-through (full S4U2Proxy) — requires AD team engagement; v1 uses service account with app-level audit log
- PSSession pooling — benchmark first; add only if measured p50 latency > 4 seconds
- Conversation search, read-only share links, usage analytics, BPA integration

**Anti-features (deliberately excluded):**
- Accepting free-form PowerShell input from the model (bypasses RBAC)
- Returning raw PowerShell output to the model (noisy, wastes context tokens)
- Mailbox content retrieval (privacy/e-discovery violation)
- DAG failover or database activation via chat (blast radius too large for conversational UI)

### Architecture Approach

The system is four cooperating processes on a single server with no distributed deployment in v1. The architecture is cleanly layered: Chat App (app.py) — MCP Client (embedded in app.py) — MCP Server (server.py, stdio subprocess) — Exchange Client (exchange_client.py, direct Python calls) — PowerShell subprocess — Exchange Management Shell. Each layer has a single responsibility and a clear interface. The MCP server is explicitly stateless between calls. All conversation state lives in the chat app. The authoritative data source is Exchange itself.

See `.planning/research/ARCHITECTURE.md` for complete component boundaries, data flow diagrams, interface contracts, and anti-patterns.

**Major components:**
1. Chat Application (app.py) — HTTP server, Azure AD auth, Azure OpenAI tool-call loop, conversation persistence, SSE streaming
2. MCP Server (server.py) — Protocol boundary; 15 tool registrations, input schema validation, error mapping; stateless
3. Exchange Client (exchange_client.py) — Only component touching Exchange; PowerShell subprocess management, Kerberos auth, JSON parsing, DNS lookups
4. Azure OpenAI Integration (inside app.py) — Multi-turn chat completions loop with tool calling; format translation between MCP tools/list and OpenAI function schema

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for all 15 pitfalls with prevention checklists and phase warnings.

1. **stdout pollution breaks the MCP stdio transport** — Configure `logging.basicConfig(stream=sys.stderr)` as the first act in server.py; never use `print()` in MCP server code; suppress all library banners. A single rogue print() silently destroys the JSON-RPC stream and the entire server becomes non-functional with no clear error.

2. **PSSession 2-4 second overhead must be designed around, not ignored** — Document latency in tool descriptions; set explicit timeouts at every layer (PS open, cmdlet, MCP call, HTTP); always use try/finally for `Remove-PSSession`; cap ResultSize on listing cmdlets. The 18-session-per-user Exchange limit turns orphaned sessions into a production incident.

3. **Kerberos negative cache causes "working configuration looks broken"** — After any KCD/RBCD change, wait 15 minutes or run `klist purge` before retesting; verify SPNs separately from application code; prefer RBCD over traditional KCD; never use CredSSP (credential exposure on intermediate server, violates enterprise security policy).

4. **Azure AD token not validated server-side enables identity spoofing** — The MCP server or its gateway must independently validate JWT signature, issuer, audience, and expiry using MSAL; never trust a client-supplied UPN; configure tenant-specific (not `common`) MSAL authority.

5. **Exchange .NET objects truncated at ConvertTo-Json depth 2 produces silent data loss** — Always use `Select-Object` to explicitly name output fields; use `ConvertTo-Json -Depth 10` for nested objects; convert ProxyAddressCollection explicitly; define and test output schema per tool before implementation.

---

## Implications for Roadmap

### Phase 1: Infrastructure Foundation and Exchange Client

**Rationale:** Zero application code can be tested without proving the Exchange connection works. The PSSession pattern, Kerberos auth, JSON output parsing, and timeout handling are the foundation every tool depends on. Infrastructure setup (CredSSP prohibition, WinRM port, SPN verification, service account RBAC roles) must be completed and documented before any application code is written.

**Delivers:**
- Verified service account with correct Exchange RBAC roles (View-Only Management role group minimum)
- Working PowerShell subprocess runner: `asyncio.create_subprocess_exec` + `ProactorEventLoop` validation
- Single proof-of-concept tool (`Get-ExchangeServer` or `Get-MailboxStatistics`) with JSON output
- DNS utility functions via `dnspython`
- Infrastructure checklist: WinRM port, SPNs, service account delegation, Exchange PS VDir auth

**Addresses:** Per-call PSSession lifecycle (table stakes), timeout handling (table stakes), Kerberos auth (table stakes)

**Avoids:** CredSSP (Pitfall 8), WinRM port mismatch (Pitfall 14), Kerberos negative cache trap (Pitfall 3)

**Research flag:** Needs active infrastructure validation with MMC AD team. The KCD / RBCD configuration cannot be verified from code alone. Document the Basic Auth fallback path for v1 before spending time on KCD.

---

### Phase 2: MCP Server — All 15 Tools

**Rationale:** The MCP server is the protocol boundary between the chat app and Exchange. The chat app cannot enumerate tools until the server exists. Building all 15 tools before integrating the chat app allows the server to be tested in isolation with `mcp dev` or the MCP Inspector — catching output schema bugs and error handling gaps before they are obscured by the OpenAI layer.

**Delivers:**
- `server.py` with all 15 tools registered using the official `mcp` SDK
- Explicit output schemas per tool (verified with `Select-Object` and `ConvertTo-Json -Depth 10`)
- Error handling pattern applied uniformly: `isError: true` on all failure paths, sanitized error messages
- All tool descriptions written and tested for LLM tool-selection accuracy (<800 characters each)
- MCP server validated end-to-end with a test MCP client before chat app integration

**Addresses:** All 15 Exchange tools (must-have), structured JSON responses (table stakes), error wrapping (table stakes)

**Avoids:** stdout pollution (Pitfall 1 — configure stderr logging at server scaffold), .NET object serialization (Pitfall 5 — define output schemas before implementation), vague tool descriptions (Pitfall 6 — write descriptions before implementation), isError flag omission (Pitfall 10 — template first tool with error pattern)

**Research flag:** Well-documented patterns; `mcp` SDK documentation is current (verified 2026-03-19). No additional research phase needed. The 15 tool specifications are already fully documented in the architecture doc.

---

### Phase 3: Chat Application Core — Auth, OpenAI, MCP Client

**Rationale:** The chat app is the orchestration layer. It depends on the MCP server (Phase 2) for tool enumeration and the Exchange client (Phase 1) for all data. Building the full auth + OpenAI + MCP client integration in one phase ensures the end-to-end tool-calling loop is validated before UI polish begins.

**Delivers:**
- Flask/FastAPI skeleton with Waitress production server (never the dev server)
- Azure AD / Entra ID SSO: MSAL auth code flow, `/auth/login`, `/auth/callback`, `SerializableTokenCache` with persistent backend
- Azure OpenAI integration: connectivity to MMC stg1 endpoint, chat completions without tool calling (connectivity validation)
- MCP client integration: spawn `server.py` on app startup, `tools/list`, inject tools into OpenAI requests in OpenAI function schema format
- Tool-calling loop: detect `tool_calls` in response, route to MCP server, append assistant + tool result messages in correct order, make second completion call
- SSE streaming of final response to browser
- Context window management: `tiktoken` token counting before each API call, conversation pruning strategy (summarize older turns, hard cap on tool result size)
- Conditional Access claims challenge handler (`interaction_required` → interactive re-auth with claims)

**Uses:** Flask 3.x + Waitress (or FastAPI — see Conflicts), MSAL, `openai` SDK, `mcp` ClientSession + stdio_client, `tiktoken`

**Implements:** Chat Application (app.py) component, Azure OpenAI Integration component, MCP Client component

**Avoids:** Dev server in production (Pitfall 15 — use Waitress from day one), MSAL cache not persisted (Pitfall 7 — SerializableTokenCache in this phase), Azure AD token not validated (Pitfall 4 — validate before any protected endpoint is reachable), Messages array mis-ordering (Pitfall 9 — implement helper function and test with two consecutive tool calls), Context growth (Pitfall 11 — implement token counting before first end-to-end test), Conditional Access (Pitfall 13)

**Research flag:** Flask vs FastAPI choice must be resolved before this phase begins. See Conflicts section below.

---

### Phase 4: Conversation Persistence and UI

**Rationale:** Persistence and UI are the only layers with no upward dependencies. They make the tool usable, not functional. This phase can begin only after the end-to-end tool-calling loop is verified in Phase 3.

**Delivers:**
- SQLite conversation storage (threads + messages schema with tool call metadata)
- Multi-conversation thread sidebar with navigation
- Collapsible tool call panel (tool name, parameters, raw Exchange result) per message
- Response copy-to-clipboard
- Error messages surfaced to user from structured tool error responses
- Loading indicator / "Querying Exchange..." status during tool execution
- Mobile-responsive layout (Bootstrap or Tailwind; not a custom framework)

**Addresses:** Conversation history (must-have), multiple threads (must-have), tool visibility (must-have), copy/export (must-have), error messages to user (must-have), loading indicator (must-have)

**Avoids:** Building a custom chat UI framework (anti-feature), storing raw Exchange data without TTL (anti-feature — implement data retention policy in this phase)

**Research flag:** Standard patterns. Flask + Jinja2 + SQLite + vanilla JS or a minimal JS library is well-documented. No research phase needed.

---

### Phase 5: Polish and v1 Hardening

**Rationale:** Post-integration polish that improves adoption without gating core functionality.

**Delivers:**
- Conversation auto-naming from first query text
- Configurable queue backlog threshold (remove hardcoded 100)
- Keyboard shortcuts (Ctrl+Enter, Esc to cancel)
- Dark mode toggle
- Production deployment checklist: AWS Secrets Manager integration, Waitress thread tuning (`threads=8`), SQLite WAL mode, audit log review
- Exchange cmdlet throttling validation against the service account's throttling policy

**Research flag:** No additional research needed for polish items. Throttling policy check (`Get-ThrottlingPolicy`) is a one-time infrastructure verification.

---

### Phase Ordering Rationale

- Infrastructure first because Phases 2-4 all depend on a proven Exchange connection
- MCP server before chat app because the chat app cannot enumerate tools until the server exists, and the server is easier to debug in isolation
- Auth + OpenAI + MCP client in one phase because they form an inseparable loop: auth provides user identity needed to scope conversations; the OpenAI loop needs tools from the MCP client; the MCP client calls the server built in Phase 2
- UI last because it adds no new integrations — all dependencies are resolved by Phase 3
- The 2-4 second PSSession latency is a Phase 1 discovery that shapes every subsequent phase (timeout values, loading indicators, UX copy) — discovering it late is expensive

### Research Flags

Phases likely needing deeper research or active validation during planning:
- **Phase 1:** Kerberos/RBCD configuration requires hands-on validation with the MMC Active Directory team. Cannot be resolved from code alone. Document the Basic Auth fallback path before KCD is attempted.
- **Phase 3:** The Flask vs FastAPI decision (see Conflicts below) must be resolved before this phase begins. Wrong choice here causes a rewrite.

Phases with standard patterns (can proceed without additional research):
- **Phase 2:** MCP SDK patterns are well-documented and verified. All 15 tools are fully specified in the architecture document.
- **Phase 4:** Flask + Jinja2 + SQLite patterns are mature and well-documented.
- **Phase 5:** Polish and hardening items have no novel technical dependencies.

---

## Conflicts Between Researchers

### PRIMARY CONFLICT: Flask vs FastAPI for the Chat Application

This is the most important unresolved question in the research. The two researchers reached opposite conclusions.

**Stack researcher recommendation: Flask 3.x + Waitress**

Rationale:
- Jinja2 server-side rendering is idiomatic Flask; FastAPI is designed for JSON API services
- `flask.session` and `Flask-Session` are first-class; FastAPI starlette session middleware is less battle-tested for this pattern
- MSAL + Flask integration (`flask-dance`, direct MSAL usage) has established, well-documented patterns
- The internal tool load (not many concurrent users) means Flask's synchronous model is simpler and sufficient
- Both run under Waitress on Windows; FastAPI's async benefits only materialize under high concurrency

**Architecture researcher recommendation: FastAPI**

Rationale:
- `asyncio.create_subprocess_exec` for PowerShell calls requires an async context. In Flask (synchronous), calling `asyncio.run()` inside a route handler that is already in a synchronous thread raises `RuntimeError` on Python 3.10+
- FastAPI is async-native; the PowerShell subprocess calls can be awaited directly without workarounds
- The architecture doc states: "Flask's dev server does not use asyncio — PowerShell subprocess calls must be run via `asyncio.run()` or in a thread pool if the web framework is synchronous (Flask). FastAPI is async-native and is the preferred choice for this reason."

**Synthesis and recommendation:**

Both researchers are correct about their respective concerns. The async/sync mismatch is a real pitfall (documented as Pitfall 6 in PITFALLS.md and Anti-Pattern 6 in ARCHITECTURE.md). The workaround for Flask is to use `concurrent.futures.ThreadPoolExecutor` with `loop.run_in_executor()`, which is documented and functional but adds indirection. The Jinja2 + session management ergonomics favor Flask.

**Decision required before Phase 3.** The recommended resolution is:

Option A (Flask + thread executor): Stay with Flask for the superior Jinja2/session/MSAL ergonomics. Run async PowerShell calls in a thread pool via `asyncio.get_event_loop().run_in_executor()`. This is the workaround described in Anti-Pattern 6. More boilerplate, but all the Flask ecosystem benefits remain.

Option B (FastAPI + Jinja2Templates): Use FastAPI with `Jinja2Templates` for HTML rendering. The async mismatch problem disappears. Jinja2 integration with FastAPI is non-standard but functional. MSAL wiring requires more manual work. Session management requires Starlette SessionMiddleware.

Neither option is wrong. The choice should be made by the person who will maintain the code. **If this team is more familiar with Flask, choose Option A. If async Python is preferred, choose Option B.** Flag this as an open decision for the roadmapper and document the chosen path in Phase 3 plan.

---

## Areas of Agreement Across All Researchers

All four research files agree on the following without qualification:

| Decision | Agreement |
|----------|-----------|
| Waitress as WSGI/ASGI server | Unanimous — Gunicorn is Unix-only; this is non-negotiable |
| Per-call PSSession, no pooling in v1 | Unanimous — accept the latency; benchmark before adding pooling |
| Basic Auth fallback for v1, KCD for v2 | Unanimous — KCD requires AD team cooperation outside the code |
| SQLite for conversation history | Unanimous — correct for <100 concurrent users; zero ops overhead |
| Official `mcp` SDK, not `fastmcp` | Unanimous — official SDK is now mature; wrapper adds no value |
| `openai` SDK direct, no LangChain/LlamaIndex | Unanimous — 15 fixed tools do not need an orchestration framework |
| No write operations in v1 | Unanimous — explicit out-of-scope in PROJECT.md |
| No Exchange Online Graph API tools in v1 | Unanimous — explicit out-of-scope in PROJECT.md |
| All logging to stderr in server.py | Unanimous — stdout pollution kills the MCP stdio transport |
| `isError: true` on all execution failures | Unanimous — omitting it causes LLM to treat errors as valid data |
| `ConvertTo-Json -Depth 10` + explicit Select-Object | Unanimous — default depth 2 produces silent data loss |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core technology choices are project-specified or forced by Windows deployment constraint. Only Flask/FastAPI and version currency for fast-moving packages (mcp SDK, uv) carry MEDIUM confidence. Verify all PyPI versions before pinning. |
| Features | HIGH | 15 Exchange tools are fully specified in the architecture document. Chat app feature set is well-understood enterprise tooling. Anti-features are clearly motivated by the 80K+ mailbox environment. |
| Architecture | HIGH | Component boundaries, interfaces, and data flows are verified against official MCP, Azure OpenAI, and MSAL documentation (2026-03-19). asyncio subprocess behavior on Windows is MEDIUM (behavior is documented and consistent but environment-specific). |
| Pitfalls | HIGH | All 15 pitfalls sourced from official documentation. The Kerberos and MSAL pitfalls are validated against current Microsoft identity platform documentation. |

**Overall confidence: HIGH**

### Gaps to Address

- **Flask vs FastAPI choice:** Must be resolved before Phase 3 planning. See Conflicts section. Recommend the team make an explicit decision and document it in the Phase 3 plan.
- **KCD / RBCD AD configuration:** Cannot be validated without active engagement with the MMC Active Directory team. The Python code is straightforward; the risk is entirely in AD configuration and the Kerberos ticket acquisition chain. Plan for Basic Auth in v1 demo. Start KCD engagement early for v2.
- **MMC Azure OpenAI gateway API version lock:** The architecture doc pins `API_VERSION=2023-05-15`. Newer Azure OpenAI API versions exist. Verify with the MMC CTS team whether the gateway supports newer versions before attempting to upgrade. Do not change this without confirmation.
- **mcp SDK version currency:** The official `mcp` package moves fast. Verify the current release at https://pypi.org/project/mcp/ before pinning. The `>=1.0.0` floor is confirmed; the current patch is not.
- **Exchange throttling policy for the service account:** Verify the throttling policy before Phase 2 tool testing. An overly restrictive policy will cause intermittent failures that look like code bugs. Run `Get-ThrottlingPolicyAssociation` against the service account before integration testing.

---

## Sources

### Primary (HIGH confidence — project-authored or official documentation verified 2026-03-19)

- `C:\xmcp\exchange-mcp-architecture.md` — All 15 tool specifications, component design, auth model, extensibility patterns
- `C:\xmcp\.planning\PROJECT.md` — Project requirements, constraints, out-of-scope items, key decisions
- MCP Specification: https://modelcontextprotocol.io/docs/concepts/architecture
- MCP Tools: https://modelcontextprotocol.io/docs/concepts/tools
- MCP Python Server quickstart: https://modelcontextprotocol.io/docs/develop/build-server
- Azure OpenAI Function Calling: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/function-calling
- OAuth 2.0 OBO Flow: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- Azure AD Seamless SSO / Kerberos: https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-sso-how-it-works
- MSAL Python: https://learn.microsoft.com/en-us/entra/msal/python/
- Microsoft Docs: Making the second hop in PowerShell Remoting (CredSSP prohibition, RBCD)
- Microsoft Docs: Azure OpenAI Quotas and Limits (tool description 1024-char limit, 128 tool limit)

### Secondary (MEDIUM confidence — training data, knowledge cutoff August 2025)

- Flask 3.x documentation patterns (version numbers require PyPI verification)
- Waitress 3.x Windows deployment patterns
- `uv` package manager ecosystem trajectory
- MSAL SerializableTokenCache patterns for server-side web apps
- Exchange Management Shell throttling policy documentation

### Tertiary (LOW confidence — require verification before use)

- `pyspnego >= 0.10.0` and `pywinrm >= 0.4.3` version currency — verify at PyPI before pinning
- `mcp` SDK patch version — verify at https://pypi.org/project/mcp/
- `uv` current version — verify at https://pypi.org/project/uv/

---

*Research completed: 2026-03-19*
*Ready for roadmap: yes — pending Flask vs FastAPI decision*
