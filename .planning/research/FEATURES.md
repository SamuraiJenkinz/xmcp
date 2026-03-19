# Feature Landscape

**Domain:** MCP Server for Infrastructure Management + Enterprise Internal Chat Application
**Project:** Exchange Infrastructure MCP Server (Exchange Management Shell + Azure OpenAI + Python Chat App)
**Researched:** 2026-03-19
**Confidence:** HIGH — Project has a fully specified architecture document; feature analysis drawn from that spec plus domain knowledge of MCP, enterprise chat, and Exchange tooling.

---

## Overview: Three Feature Domains

This project has three distinct feature domains, each with its own table stakes / differentiator / anti-feature profile:

1. **MCP Server — Infrastructure Tool Exposure**
2. **Enterprise Internal Chat Application**
3. **Exchange Management Tooling (domain-specific)**

They are analyzed separately, then cross-cutting dependencies are mapped.

---

## Domain 1: MCP Server — Infrastructure Tool Exposure

### Table Stakes

Features users (in this case, the AI model and chat app) expect. Missing these makes the MCP server unusable or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Tool registry with JSON schemas | MCP protocol requirement — model cannot discover or call tools without it | Low | `list_tools()` in server.py. Already spec'd. |
| Structured JSON responses | AI model needs machine-parseable output, not raw PowerShell text | Low | `ConvertTo-Json` piped from PS cmdlets. |
| Error wrapping / graceful failures | A failed PS command must not crash the server or return unstructured error text to the model | Medium | Try/except with structured error dict returned as TextContent. |
| Tool input validation | Bad input (wrong mailbox format, missing params) must fail fast with clear message | Low | JSON schema constraints in tool definitions. |
| Authentication to backend system | Server must authenticate to Exchange; without this, zero tools work | Medium | Kerberos + Basic Auth fallback, already designed. |
| Read-only scope enforcement | Any infrastructure tool server that can mutate state without controls is a security incident waiting to happen | Low | Enforced at RBAC level (View-Only roles). Design constraint. |
| Timeout handling | Exchange cmdlets can hang; unhandled hangs block the chat app indefinitely | Medium | asyncio subprocess timeout, kill on overrun. |
| Per-call session lifecycle | Session leak in a long-running server causes Exchange server resource exhaustion | Medium | Per-call PSSession creation/destruction. Already spec'd. |

### Differentiators

Features that go beyond basic MCP compliance and make the server valuable and trustworthy.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Pass-through user identity (Kerberos Constrained Delegation) | Exchange sees the actual colleague's identity — per-user audit trail, RBAC respected per-person, not a single shared service account's permissions | High | This is unusual for chat-to-tool pipelines. Most use a single service account. Requires domain-joined host and KCD setup. |
| Tool-level audit logging | Record every tool invocation with caller identity, parameters, timestamp, and result summary | Medium | Protects the team in security reviews. Not required by MCP protocol. |
| Interpreted responses (not raw data) | The AI layer translates raw Exchange JSON into prose — "3 delegates" not `[{"AccessRights":["FullAccess"]...}]` | Low (AI does it) | The value is in the system prompt and tool description quality, not extra code. |
| Multi-category coverage (mailbox + DAG + mail flow + security + hybrid) | Most PowerShell-to-AI wrappers cover one domain; 15 tools across 5 categories makes this a genuine operational assistant | Medium | Already spec'd and justified in architecture doc. |
| DNS-based security checks without PowerShell | DMARC/SPF lookups via dnspython are faster, more portable, and do not require Exchange session auth | Low | Elegant bypass of PS session overhead for DNS checks. |
| Structured queue backlog alerting | `get_transport_queues` flags backlogs >100 — the tool interprets rather than just reports | Low | Thresholds can be made configurable in v2. |
| Candidate future tool catalog | The server's extensibility model is documented and clear — new tools follow a 4-step pattern | Low (design) | Reduces friction for future CTS engineers to extend the server. |

### Anti-Features

Features to deliberately NOT build in MCP server v1. Common mistakes in infrastructure tool server projects.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Write operations (create/modify/delete) in v1 | A single misunderstood query could mutate production state. "Disable the shared mailbox" is ambiguous; natural language is lossy | Separate write-capable server behind explicit approval gates, dedicated service account, mandatory confirmation prompts |
| Persistent PSSession pool | Session pooling increases performance but creates leak risk, complicates credential rotation, and obscures auth failures | Per-call sessions in v1; benchmark latency first; add pooling only if measured latency is unacceptable |
| Returning raw PowerShell output to the model | Raw PS output is inconsistent, noisy, and wastes context window tokens on formatting artifacts | Always pipe to `ConvertTo-Json`, parse in Python, return clean dict |
| Accepting free-form PowerShell input from the model | Allowing the model to construct arbitrary cmdlets bypasses all RBAC and safety design | Expose only the 15 defined tool schemas; model cannot deviate from them |
| Exchange Online-only tools via Graph API | Dual-path auth (Kerberos + OAuth to Graph) doubles complexity; hybrid on-prem focus is the stated v1 scope | Post-v1 extension, separate tool category with dedicated auth flow |
| Tool chaining / workflow orchestration inside the MCP server | The MCP server's job is single-tool execution; multi-step workflows belong in the AI model's reasoning layer | Let gpt-4o-mini orchestrate multiple tool calls naturally |
| Health check polling / proactive alerting inside the server | The MCP server is request/response, not an agent; embedding polling loops conflates concerns | Separate scheduled agent (already noted in architecture doc as integration point) |

---

## Domain 2: Enterprise Internal Chat Application

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| SSO authentication (Azure AD / Entra ID) | Corporate users will not use a separate login; IT will not approve a tool without corporate identity | Medium | MSAL Python library; already spec'd. |
| Conversation history persisting across sessions | Without this, every new browser session starts blank — unusable for any ongoing investigation | Medium | Database-backed (SQLite or Postgres); tied to user identity. |
| Multiple conversation threads | Engineers handle multiple investigations simultaneously; single-thread apps create context collision | Medium | Sidebar with named/dated threads. Already spec'd. |
| Tool visibility — show which tool was called and what it returned | Engineers and service desk staff need to audit what data the AI queried; "trust the AI" is not enterprise-acceptable | Medium | Collapsible tool call panel per message; shows tool name, params, raw result. |
| Loading / streaming indicator | LLM + PS execution takes 3-8 seconds; no feedback = perceived hang | Low | Streaming tokens or spinner with "Querying Exchange..." status. |
| Error messages visible to user | When a tool fails, user must understand why ("Mailbox not found" vs "PSSession timeout") | Low | Surface structured error from tool response in UI. |
| Basic copy/export response | Users need to paste results into ServiceNow tickets, emails, reports | Low | Copy-to-clipboard button per message. Already spec'd. |
| Mobile-responsive layout (minimum: readable on tablet) | Service desk staff may access from non-desktop devices | Low | Bootstrap or Tailwind grid; not a full mobile app. |
| Restricted to internal network / VPN | Internal tool with access to Exchange data must not be internet-accessible | Low | Nginx/Flask network binding; not a feature, a deployment requirement. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tool call collapsible panel with raw JSON | Engineers can verify AI interpretation against raw Exchange data; builds trust in the tool | Medium | Toggle show/hide raw result below AI response. |
| Conversation naming and search | When engineers have 20+ threads, finding "the DAG health investigation from Tuesday" requires search | Medium | Auto-name from first query; manual rename; search by keyword. |
| Export full conversation as PDF or Markdown | Provides audit trail for change management processes; enables sharing findings with stakeholders | Medium | Markdown is simpler and more useful than PDF for technical teams. |
| Contextual query suggestions | When the tool returns DAG health data, suggest "Check database copies?" — reduces expert knowledge required | Medium | Pre-defined suggestion sets per tool response type. |
| Conversation sharing via link or export | Senior stakeholders need to receive findings without using the tool themselves | Medium | Read-only share link with expiry. Useful for cross-operating-company sharing. |
| System prompt / persona configuration (admin only) | Allows CTS team to tune AI behavior (verbosity, tone, scope) without code changes | Medium | Admin settings page; stored in config DB. |
| Usage analytics (admin view) | CTS team needs to know which tools are being used, by whom, and how often — justifies continued investment | Medium | Query log aggregation; not user-facing. |
| Keyboard shortcuts | Power users (engineers) use tools heavily; mouse-heavy UIs slow them down | Low | `Ctrl+Enter` to send, `/` to focus input, `Esc` to cancel. |
| Dark mode | Engineers working in NOC environments or late shifts; table stakes for developer tools | Low | CSS variable theming; toggle in user settings. |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Chat-as-primary-interface for write operations | Natural language is ambiguous; "delete the shared mailbox" could be misinterpreted catastrophically | Write operations require dedicated, confirmation-gated UI (separate from conversational interface) |
| Per-user AI system prompt editing | Users modifying their own system prompts can override safety instructions and scope boundaries | Admin-only system prompt management; users can set display preferences only |
| Storing raw Exchange data in conversation history long-term | Mailbox content, delegate lists, and queue data is sensitive; long-term retention creates data governance risk | TTL on raw tool output in stored conversations (keep AI responses, expire raw JSON) |
| Public/unauthenticated access mode | Even read-only Exchange data (mailbox sizes, delegate lists) is sensitive corporate information | Hard gate on SSO; no bypass modes |
| Building a custom chat UI framework from scratch | Flask + Jinja2 + vanilla JS or a mature component library is sufficient; custom framework adds maintenance burden | Use proven UI patterns; invest effort in Exchange-specific features not in re-inventing message rendering |
| Embedded help documentation as a full knowledge base | Maintaining a separate docs system is expensive; the AI itself can answer "how do I query X" | Brief contextual help tooltips; let the AI explain its own capabilities |
| Real-time multi-user collaboration on same conversation thread | Adds WebSocket complexity; primary use case is individual engineers investigating their own issues | Share via export or link; real-time collaboration is not the core use case |

---

## Domain 3: Exchange Management Tooling (Domain-Specific Features)

### Table Stakes

Features engineers and service desk staff expect any Exchange management tool to provide. Missing these and users revert to direct PowerShell.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Mailbox lookup by identity (UPN, alias, display name) | Foundational operation — everything else is a refinement of this | Low | `get_mailbox_stats`, `search_mailboxes` cover this. |
| Shared mailbox delegation query | The #1 governance question for service desk — "who has access to this mailbox?" | Low | `get_shared_mailbox_owners` covers full access + send-as + send-on-behalf. |
| DAG health / replication status | Engineers check DAG health multiple times daily during incidents; no substitute | Medium | `get_dag_health` with `Test-ReplicationHealth` + queue lengths. |
| Mail flow tracing (sender → recipient path) | When email isn't arriving, first question is "what routing path did it take?" | Medium | `check_mail_flow` with connector resolution. |
| Transport queue depth visibility | Queue backlog is an early warning for mail flow outages; must be visible without shell access | Low | `get_transport_queues` with backlog threshold flagging. |
| SMTP connector inventory | Service desk escalations often involve "which connector does this route use?" — requires full connector view | Low | `get_smtp_connectors` with auth + TLS config. |
| Email security posture (DMARC/SPF/DKIM) | Security team and service desk regularly validate sending domain posture | Medium | `get_dmarc_status` (DNS), `get_dkim_config` (PS). |
| Hybrid migration batch status | With 80,000+ mailboxes in hybrid topology, migration progress queries are constant | Low | `get_migration_batches` with completion percentages. |
| Database copy status across DAG | "Which server hosts the active copy of this database?" is asked during failover planning | Low | `get_database_copies` with activation preferences. |

### Differentiators

Features that go beyond basic Exchange tooling and address the specific pain points identified in the project context.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| On-demand shared mailbox ownership (vs ExoNotes.xlsx batch exports) | Directly replaces the 31,246-row Excel process. Live data vs stale exports. | Low (tool exists) | `get_shared_mailbox_owners` is the killer feature for the CTS governance team. |
| Cross-operating-company query access | Service desk at Mercer can query Exchange data for Marsh mailboxes without needing Exchange RBAC | Medium | Enabled by the chat app access model + RBAC on the service account, not a new tool feature. |
| Natural language query → structured Exchange answer | Engineers can ask "are the DAGs healthy?" without knowing `Test-ReplicationHealth` syntax | Low (AI does it) | The value is in the system prompt quality and tool description fidelity. |
| Hybrid connector health validation with live endpoint test | `Test-MigrationServerAvailability` actively tests the Exchange Online endpoint — not just config inspection | Medium | `get_connector_status` is the differentiator vs passive config read tools. |
| Mobile device wipe history visibility | Security-relevant: knowing which devices have been wiped and when | Low | `check_mobile_devices` exposes wipe history alongside access state. |
| Queue backlog threshold alerting inline | Tool returns not just raw queue data but a flag when threshold exceeded — no interpretation required | Low | 100-message threshold. Make configurable in v2. |
| Future BPA integration | Running Exchange Best Practices Analyzer via the chat interface removes the need for on-server execution | High | Post-v1 candidate. Complex to implement reliably. |

### Anti-Features (Exchange Domain)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Mailbox content search and retrieval | Exposing mailbox message content via an AI chat interface creates e-discovery and privacy violations | Keep Mailbox Search role scoped to statistics only; never retrieve message bodies or subjects |
| Transport rule creation or modification | A misunderstood transport rule could silently drop or redirect mail for 80,000+ users | Write operations require a separate privileged account + explicit approval workflow |
| DAG failover or database activation | Failover is a high-stakes operation with blast radius across the DAG; natural language instructions are too imprecise | Separate remediation tools with mandatory confirmation gates, separate from conversational UI |
| Full mailbox content export (PST/eDiscovery) | Legal hold and eDiscovery are compliance functions with chain-of-custody requirements | Handled by dedicated eDiscovery tooling (Purview), not a general-purpose chat tool |
| Password reset or account unlock | These are identity operations, not Exchange operations; they belong in AD/IDAM tooling | Refer users to existing service desk identity tools |
| Querying cloud-only Exchange Online mailboxes via Graph | Dual auth model (Kerberos + OAuth) doubles implementation complexity for v1 | Post-v1: dedicated Graph API tool category with separate auth flow |

---

## Feature Dependencies

```
Authentication (SSO)
  → Conversation history (needs user identity to scope history)
  → Pass-through identity (needs authenticated user identity for KCD)
  → Tool audit logging (needs user identity to record)

Pass-through identity (Kerberos Constrained Delegation)
  → Per-user Exchange RBAC respected
  → Per-user audit trail in Exchange logs

MCP Tool Registry (list_tools)
  → All 15 Exchange tools (tools are registered, then callable)
  → Tool visibility in UI (UI reads tool call metadata from model response)

Tool visibility in UI
  → Conversation history (tool calls are part of the stored conversation)
  → Export/share (exported conversation must include tool call metadata)

Conversation history
  → Multiple conversation threads (threads are groups of history records)
  → Conversation search (search requires history to exist)
  → Export/share (exports from stored history)

Per-call PSSession lifecycle
  → All 15 Exchange tools (every tool uses PSSession)
  → Timeout handling (per-call timeout set when PSSession is created)

Error wrapping in MCP server
  → User-visible error messages in chat UI (structured error flows to UI)
```

---

## MVP Recommendation

For v1 as specified, prioritize in this order:

**Must-Have (v1 — already in scope per PROJECT.md):**
1. All 15 Exchange tools with JSON schemas and structured responses
2. Azure AD / Entra ID SSO for the chat app
3. Per-call PSSession with Kerberos auth + Basic Auth fallback
4. Conversation history persisting across sessions (DB-backed)
5. Multiple conversation threads with sidebar
6. Tool visibility — collapsible tool call panel showing tool name + params + raw result
7. Copy/export response (clipboard copy as minimum, full export as enhancement)
8. Error handling visible to user
9. Loading indicator during tool execution

**High Value, Low Complexity (add to v1 if time permits):**
- Conversation auto-naming from first query
- Queue backlog threshold configurable (not hardcoded 100)
- Keyboard shortcuts (`Ctrl+Enter` to send)
- Dark mode toggle

**Defer to Post-v1:**
- Write operations: requires separate privileged account + approval gates (explicit out-of-scope in PROJECT.md)
- Exchange Online Graph API tools: separate auth flow (explicit out-of-scope in PROJECT.md)
- Conversation search: useful but not blocking initial adoption
- Read-only share links: useful for stakeholder sharing but adds auth complexity
- System prompt / persona admin configuration
- Usage analytics dashboard
- BPA integration (high complexity, high value)
- PSSession pooling: benchmark latency first, add only if >4s p50 latency is confirmed

---

## Cross-Cutting Dependencies Summary

| Feature | Depends On | Enables |
|---------|------------|---------|
| SSO (Azure AD) | Corporate Entra ID tenant | Pass-through identity, conversation history scoping, tool audit logging |
| Kerberos Constrained Delegation | Domain-joined Windows host, KCD config in AD | Per-user Exchange RBAC, per-user audit trail |
| Per-call PSSession | Python asyncio, WinRM endpoint, service account | All 15 Exchange tools |
| Tool registry (list_tools) | MCP SDK | Tool dispatch, tool visibility in UI, model tool selection |
| Conversation DB | SSO user identity, chosen DB (SQLite/Postgres) | History persistence, multiple threads, export, search |
| Tool visibility in UI | MCP tool call metadata in model response | User trust, audit capability, export with tool traces |

---

## Sources

- C:\xmcp\exchange-mcp-architecture.md — Primary source. Authoritative specification for all 15 tools, auth model, component design, and extensibility. HIGH confidence.
- C:\xmcp\.planning\PROJECT.md — Project requirements, constraints, out-of-scope items, and key decisions. HIGH confidence.
- Domain knowledge: MCP protocol design patterns, enterprise chat application conventions, Exchange Management Shell capabilities. MEDIUM confidence (training data, knowledge cutoff August 2025 — MCP ecosystem was maturing rapidly through 2024-2025).
- Note: WebSearch and Context7 tools were not available in this research session. Feature categorizations for MCP server patterns and enterprise chat applications rely on domain knowledge rather than verified external sources. Recommend validating the MCP server table stakes list against current MCP specification documentation before finalizing.
