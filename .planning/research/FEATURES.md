# Feature Landscape

**Domain:** MCP Server for Infrastructure Management + Enterprise Internal Chat Application
**Project:** Exchange Infrastructure MCP Server (Exchange Management Shell + Azure OpenAI + Python Chat App)
**Researched:** 2026-03-19 (original), updated 2026-03-24 (colleague lookup milestone), updated 2026-03-27 (UI/UX overhaul milestone)
**Confidence:** HIGH — Project has a fully specified architecture document; feature analysis drawn from that spec plus domain knowledge of MCP, enterprise chat, and Exchange tooling.

---

## Overview: Three Feature Domains

This project has three distinct feature domains, each with its own table stakes / differentiator / anti-feature profile:

1. **MCP Server — Infrastructure Tool Exposure**
2. **Enterprise Internal Chat Application**
3. **Exchange Management Tooling (domain-specific)**

They are analyzed separately, then cross-cutting dependencies are mapped.

Domain 4 (Colleague Lookup and Profile Display) was added in milestone v1.1 and is analyzed at the end.

Domain 5 (UI/UX Overhaul — Microsoft Copilot aesthetic) was added in milestone v1.2 and is analyzed in the final section.

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

## Domain 4: Colleague Lookup and Profile Display (v1.1 Milestone)

**Context:** Users ask the AI in natural language to look up colleagues. The AI calls MCP tools that query Microsoft Graph. Results render as inline profile cards in the chat UI — photo, name, title, department, email, office location. Azure AD has 80,000+ users across Marsh, Mercer, Oliver Wyman, and Guy Carpenter.

**Source confidence:** Table stakes verified against Microsoft Graph official documentation (profilephoto-get, user resource type, $search parameter docs — HIGH). Differentiators and anti-features from domain knowledge and enterprise UX research (MEDIUM).

### Table Stakes

Features users expect from any colleague lookup capability in an enterprise tool. Missing these makes the feature feel broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Search by name (partial match) | Users type first name, last name, or partial name — exact match only is unusable at 80K users | Low | Microsoft Graph `$search="displayName:term"` with `ConsistencyLevel: eventual` header. Returns up to 15 results by default. |
| Search by department | "Show me people in HR" is a common first query when the user doesn't know a specific name | Low | `$filter=department eq 'Human Resources'`. Must handle exact match; department values must match AAD strings exactly. |
| Display name prominently | First thing users scan for is the name — it orients all other data on the card | Low | Microsoft Graph `displayName` is a default-returned field. Always present. |
| Job title on profile card | Users need title to confirm they found the right person (John Smith the VP vs John Smith the analyst) | Low | `jobTitle` in Graph user resource. Must be $select'd explicitly. Often null for some user types — render gracefully. |
| Department on profile card | Confirms business unit context; particularly important at MMC where same name can exist across 4 operating companies | Low | `department` must be $select'd. May be null — render "Department not listed" rather than blank. |
| Email address on profile card | Primary action after finding someone is emailing them; must be clickable `mailto:` link | Low | `mail` is returned by default. Some accounts use `userPrincipalName` only — fall back to UPN if mail is null. |
| Profile photo or graceful fallback | Photos are the primary visual identifier; absence of a photo must not break the card layout | Medium | Microsoft Graph `GET /users/{id}/photo/$value` returns 404 when no photo exists. Server must proxy and return initials-based fallback (colored circle with initials) on 404. Photo sizes: 48x48, 96x96, 240x240 available. Use 96x96 for cards. |
| Multiple results for ambiguous queries | "Find Sarah" in an 80,000-person directory will return many matches; presenting only one is incorrect | Low | Return up to 10 results per query. Each result renders as a compact card. User scrolls to find the right Sarah. |
| Clear empty state for no results | When query returns zero results, user needs explicit feedback — not a blank space | Low | "No colleagues found matching '[term]'" message with suggestion to try a different search term. |
| Results scoped to MMC Azure AD only | The Azure AD tenant contains only MMC employees; no filtering required, but tool must not reach external directories | Low | Single tenant — Graph client credentials are scoped to MMC tenant. No cross-tenant queries. |

### Differentiators

Features that elevate the colleague lookup experience beyond basic directory search.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Office location on profile card | At a global company with offices across 130+ countries, knowing where someone sits matters for meeting scheduling and escalation chains | Low | `officeLocation` must be $select'd. Null in many AAD records — render only if present, do not show empty label. |
| Business phone on card | Direct dial number is a common need when email is too slow for an incident | Low | `businessPhones` is an array — render first entry. Null for many users — render only if present. |
| Mobile phone on card | Mobile for out-of-hours or urgent contact | Low | `mobilePhone` — render only if present. Many users will not have this populated. |
| Operating company badge | At MMC, "Marsh", "Mercer", "Oliver Wyman", "Guy Carpenter" tell the user which business unit this person works in — critical context when names are common | Low | Derive from department, companyName, or mail domain pattern. `companyName` must be $select'd. Render as colored badge on card (e.g., Mercer = teal). |
| Copy email to clipboard button | Most common action after finding someone — eliminates manual selection and copy | Low | Clipboard API on the email address element. Already implemented pattern in the app for AI responses. |
| Search by both name and department simultaneously | "Find Sarah in Finance" is more precise than either query alone — filters the multi-result list meaningfully | Medium | Combine `$search="displayName:Sarah"` with `$filter=department eq 'Finance'`. Graph supports combining $search and $filter with ConsistencyLevel: eventual header. |
| Manager field on detailed profile | For escalation workflows: "who does this person report to?" is a common follow-up question | Medium | `manager` is a navigation property — requires separate Graph call `GET /users/{id}/manager`. Not in initial card; available on expand or separate tool call. |
| Profile card inline in chat response | Cards rendered directly in the conversation thread, not in a modal or new tab — keeps the user in context | Medium | Custom HTML rendering in AI message bubble. The AI message text introduces the results; cards appear below as structured elements, not as JSON. |
| Differentiated card layout for single vs multi-result | A single confident match gets a larger card with more detail; multiple matches get compact cards in a scrollable list | Medium | Single result: 96x96 photo, full fields. Multiple results: 48x48 photo, name + title + department + email only. |

### Anti-Features

Things to deliberately NOT build for colleague lookup. Common mistakes that create privacy, performance, or scope creep problems.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Presence/availability status ("Sarah is in a meeting") | Presence data from Graph requires `Presence.Read.All` permission — a higher-sensitivity scope. Presence is ephemeral, often stale, and creates an expectation of real-time monitoring that the tool cannot reliably deliver | Omit presence. If users need availability, direct them to Teams or Outlook calendar. |
| Full org chart rendering | Building a tree view of reporting lines requires recursive Graph calls (manager chain, direct reports list). High API cost, complex rendering, and rarely what users need from a chat tool | Expose manager as a single field on detailed profile. If users need full org chart, direct them to the M365 profile page. |
| Search across email content or calendar | Graph has APIs for mail and calendar; using them here creates a surveillance tool, not a directory tool. Privacy and data governance concerns are immediate | Scope the colleague lookup strictly to AAD user profile data only. Never query mailbox or calendar content. |
| Free-text notes or annotations on colleague profiles | Any user-editable annotation layer on top of AAD data creates a shadow HR system — legal exposure, GDPR complications, data quality problems | Read-only display of official AAD data only. Direct users to the appropriate HR system for updates. |
| Photo caching in the conversation database | Profile photos are binary blobs; storing them in SQLite adds significant size and creates a stale-photo problem (users update their photo but the cached version remains) | Proxy photos on demand via `/api/photo/<user_id>`. Add HTTP cache headers (Cache-Control: max-age=3600) for browser-level caching. No server-side photo storage. |
| Bulk export of colleague contact data | Exporting a directory of 80,000 names, emails, and phone numbers from a chat tool creates a data exfiltration risk — even internal | Return results per query only. No "export all search results" function. Maximum 10 results per search response. |
| Autocomplete / typeahead search in the chat input | Intercepting keystrokes in the chat input to suggest colleague names requires polling Graph on every keystroke — high API cost, complex UX state, and breaks the conversational model | Let users type complete natural language queries. The AI extracts name/department intent and calls the search tool. |
| Displaying user account status or license details | Account enabled/disabled status, license assignments, and group memberships are AD administration data — not appropriate for a general-purpose colleague lookup in a chat tool | Scope strictly to profile display fields: name, title, department, email, phone, location, photo. |

---

## Domain 5: UI/UX Visual Overhaul — Microsoft Copilot Aesthetic (v1.2 Milestone)

**Context:** Atlas is functionally complete but visually dated. This milestone is a full UI/UX overhaul targeting Microsoft Copilot aesthetic for IT engineers and managers at Marsh McLennan. 80K employees, desktop-only (1080p–1440p), dark mode primary. All backend features stay; only visual and interaction patterns change.

**Research basis:** Microsoft 365 Copilot Chat, GitHub Copilot Chat, ChatGPT, Claude.ai, Microsoft Fluent 2 Design System. Patterns sourced from Microsoft Design documentation, Smashing Magazine AI UI patterns research, and community-verified UX practices.

**Source confidence:** Table stakes HIGH (all verified against documented Copilot/ChatGPT patterns). Differentiators MEDIUM (verified against multiple sources; specific values like animation timing LOW confidence). Anti-features HIGH (established enterprise UX guidance).

### Table Stakes

Features that users of modern enterprise AI chat expect to be present and correct. Missing or broken implementations make the product feel unfinished or unprofessional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Full-bleed, consistent dark mode | IT ops teams default to dark. Mismatched grays or light-mode bleed signals poor craft. | Low | Already exists; needs audit — surface hierarchy (#0f0f0f / #1a1a1a / #262626), no off-white elements |
| Unambiguous user vs. assistant role differentiation | Every major product (Copilot, ChatGPT, Claude) visually distinguishes who said what. | Low | Alignment differences, avatar/icon, background tint, or label — pick one consistent approach |
| Proper markdown rendering during streaming | Code blocks, bold, lists, headers in every IT response. Partial markdown during SSE must not break layout. | Low-Med | Already exists; audit for streaming edge cases — half-open bold tags, unclosed code fences |
| Syntax-highlighted code blocks | IT engineers read Exchange cmdlets and JSON. Plain-text code is unacceptable. | Low | Already exists; verify language auto-detection works correctly |
| Copy button on every code block | ChatGPT, Copilot: every code block has its own copy button. Engineers expect it. | Low | Already exists for full responses; ensure per-code-block copy is present |
| Auto-resize textarea input | Single-line inputs feel broken for multi-sentence prompts. | Low | Standard grow-on-newline behavior, max ~5 lines before scroll |
| Send on Enter, newline on Shift+Enter | Universal standard across all major chat products. Any other mapping creates friction. | Low | Verify current behavior matches; document the keyboard shortcut visibly |
| Streaming cursor / active generation signal | Users expect to see text arriving. A blinking cursor or shimmer signals the model is working. | Low | Already exists; ensure visual is crisp and not distracting |
| Stop generation button during streaming | ChatGPT, Copilot: replaces or augments send button while streaming. Engineers run long queries. | Low | Appears during SSE streaming, disappears when stream ends |
| Sidebar thread list with clear hierarchy | Persistent history with left-side navigation is expected. Copilot, ChatGPT, Claude all use this layout. | Low | Already exists; needs visual polish — spacing, active state, hover states |
| Thread rename and delete affordances | Users name threads by project or ticket. Cannot feel ephemeral. | Low | Already exists; ensure affordances are discoverable (hover reveal or always-visible icons) |
| New thread button — prominent and consistent | "New chat" must be immediately findable at the top of the sidebar. | Low | Already exists; verify placement and icon (pencil-plus is the Copilot/ChatGPT standard) |
| Welcome / empty state with prompt suggestions | Every modern product (Copilot, Gemini) shows prompt chips on an empty state to reduce blank-page anxiety. | Low | Already exists; needs visual refinement to match Fluent 2 card style |
| Loading / thinking state before streaming begins | Three-dot pulse or shimmer during the gap between send and first token. | Low | Already exists; audit visual quality against Copilot standard |
| Keyboard navigation and visible focus rings | Enterprise accessibility requirement. WCAG AA mandates 3:1 contrast on focus indicators. | Med | Focus styles, logical tab order, Esc to cancel |

### Differentiators

Features that separate "it works" from "it feels like Copilot."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tool call panel visual upgrade | GitHub Copilot, Claude show agentic steps with chevron icon, status badge, and timing. Engineers trust systems that show their work. | Med | Already exists functionally; add: chevron icon, status badge (running / done / error), elapsed time on header |
| Tool call elapsed time display | "Ran in 1.2s" on collapsed tool panels signals performance. Copilot does this for actions. | Low | Add elapsed time to each tool panel header — needs timing data from backend (start/end timestamps) |
| Smooth message entrance animation | Copilot uses subtle fade-in + translate-up for new messages. Reduces visual jank on SSE token arrival. | Low | CSS keyframe, 150–200ms duration, no bounce, opacity 0→1 + translateY 8px→0 |
| Sidebar thread recency grouping | ChatGPT groups threads: Today / Yesterday / This Week / Older. Reduces cognitive load with many sessions. | Low-Med | Frontend-only sort by `created_at` timestamp; no backend change if timestamps exist |
| Hover actions on messages | Copy, thumbs-up/down, timestamp appear on message hover. Copilot, ChatGPT pattern. | Low-Med | Ghost icons at message bottom-right edge, visible only on hover, opacity transition |
| Thumbs-up / thumbs-down feedback | IBM, Copilot, all enterprise tools capture response quality. Builds trust with IT stakeholders. Two taps max: icon click, then optional pre-defined category. | Low | Binary feedback; optional category on thumbs-down (Inaccurate / Not helpful / Off-topic). No open text required. |
| Sidebar collapse to icon-only | Copilot and GitHub Copilot allow hiding sidebar for focus mode — common on 1080p monitors. | Low-Med | Slide/shrink CSS transition; icon-only collapsed state shows new-chat button and first letter of thread name |
| Per-message timestamp on hover | ChatGPT shows send time on hover. Helps engineers correlate chat steps to Exchange event logs. | Low | Tooltip or fade-in text on message hover, format: "Today 14:32" |
| Inline profile card visual alignment with Fluent 2 | Already built; differentiation comes from Fluent-style card: subtle border-radius, correct spacing, avatar ring color. | Low | Audit existing card against Fluent 2 card component specifications |
| Accessible color contrast audit | Fluent 2 dark mode tokens are tuned for WCAG AA. Replacing ad-hoc grays with semantic tokens fixes contrast failures at once. | Med | One-time token system introduction; fixes multiple contrast issues simultaneously |

### Anti-Features

UI/UX patterns to deliberately NOT build. These are common complexity traps or signals of consumer-grade quality.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Typewriter / per-character animation | Looks clever, frustrates fast readers, adds artificial latency. Copilot streams tokens naturally — no typewriter. | Render tokens as they arrive via SSE. Natural streaming speed, no artificial per-character delay. |
| Message reaction emojis (emoji palette) | Consumer chat pattern. Enterprise AI tools (Copilot, ChatGPT Business) do not use emoji reactions. Undermines trust, looks like Slack misused. | Binary thumbs-up/down only. |
| "Bot is typing..." persistent ellipsis as primary loading | Signals low-end support bot (Intercom, Zendesk). Enterprise AI shows "Thinking..." or a named assistant with a spinner. | Use a "Thinking..." label with pulsing dots alongside the Atlas assistant name/avatar. |
| Onboarding wizard or product tour overlay | Enterprise IT engineers do not want guided tours. Copilot has none. Teams has none. | Welcome chips + clear affordances. Let the tool speak for itself. |
| Sound effects on send/receive | No modern enterprise chat uses audio. Immediately signals consumer-grade build. | Silence. |
| Floating chat bubble / widget style | Embedded support bot pattern. Full-page layout is the professional enterprise standard (Copilot, ChatGPT, Claude). | Full-page layout only. |
| Always-visible "Regenerate response" button under every message | Creates persistent visual clutter. Should appear only via hover actions or on the last message only. | Hover action pattern — appears on interaction, disappears when focus leaves. |
| Chat export as PDF or Word doc | High implementation cost (HTML → PDF rendering), low usage by IT engineers. They copy-paste or share links. | Copy-to-clipboard (already built) covers 95% of the use case. |
| Real-time multi-user collaboration on same thread | Wrong problem for this domain. IT engineers investigate solo. Multi-user adds WebSocket complexity for zero benefit. | Single-user sessions. Share via export only. |
| File attachment upload UI | Not applicable to Exchange query domain. Adds visual complexity with no functional use. | Text-only input. Keep the input area clean. |
| Model picker dropdown in the chat UI | Multiple model options confuse enterprise users and fragment the support surface. | Single model, single experience. Model selection stays in admin config. |
| Animated mesh gradient or particle background | Consumer AI marketing page aesthetic. Signals startup, not enterprise. Especially wrong in dark mode. | Flat neutral dark surface. Let content be the visual focus. |
| "Powered by OpenAI" or LLM branding watermark | IT engineers know the stack. A watermark signals demo build, not production tool. | Remove or restrict to auth splash page if legally required. |
| Chat persona / avatar customization by end users | Consumer ChatGPT feature. Enterprise users do not need to configure assistant identity. | Fixed Atlas branding and avatar. No customization for end users. |
| Paginated message history within a thread | Creates disorientation. Users expect continuous scroll to top within a thread. | Virtualized scroll list. All messages in one continuous view. |

### Feature Dependencies (UI/UX Overhaul)

```
Dark Mode Audit
    └── Requires: design token system (CSS custom properties for semantic colors)
    └── Enables: consistent dark mode across all components at once

Message Role Differentiation
    └── Depends on: existing message data model (role: user | assistant already present)
    └── No backend changes needed

Tool Call Panel Upgrade
    ├── Status badge (running/done/error) — needs: tool_status field in SSE events
    └── Elapsed time — needs: tool_start_time and tool_end_time in SSE events
         └── Backend change required: add timestamps to tool call events

Stop Generation Button
    └── Needs: SSE stream abort signal (fetch AbortController already standard in modern browsers)
    └── Backend: handle connection close gracefully

Sidebar Thread Recency Grouping
    └── Needs: thread.created_at timestamp (verify this exists in current schema)
    └── Frontend-only sort and group if timestamp exists

Message Entrance Animation
    └── CSS only — no dependencies

Hover Actions on Messages
    └── CSS + minimal JS — depends on: existing copy-to-clipboard implementation
    └── Thumbs feedback — new: needs feedback storage endpoint (POST /api/feedback)

Sidebar Collapse
    └── CSS transition + localStorage for persisted state
    └── No backend changes
```

### MVP Recommendation for UI/UX Overhaul

**Must ship (table stakes audit + fix — no new backend):**
1. Audit and fix dark mode color consistency — semantic token system, surface hierarchy
2. Message role visual differentiation — clear user vs. assistant distinction
3. Sidebar visual polish — spacing, active state, hover states, new-chat button placement
4. Auto-resize textarea — CSS + JS, no backend
5. Stop generation button — AbortController on existing SSE fetch
6. Message entrance animation — CSS keyframes only
7. Keyboard navigation and focus rings — accessibility + WCAG AA compliance

**Should ship (differentiators, low complexity):**
8. Tool call panel upgrade — chevron icon, status badge, elapsed time (requires backend timestamp addition)
9. Hover actions on messages — copy, per-message timestamp, thumbs feedback
10. Thread recency grouping in sidebar — Today / Yesterday / This Week / Older
11. Sidebar collapse — CSS transition, localStorage persistence

**Defer (high complexity, out of scope for visual overhaul):**
- Thread search (requires search backend or client-side index)
- Full token/design system migration (large scope, own milestone)
- Response word count or token indicator (low value for IT domain)

---

## Cross-Cutting Dependencies Summary

| Feature | Depends On | Enables |
|---------|------------|---------|
| SSO (Azure AD) | Corporate Entra ID tenant | Pass-through identity, conversation history scoping, tool audit logging, Graph client credentials |
| Graph API client (client credentials) | Azure AD app registration, User.Read.All + ProfilePhoto.Read.All permissions | search_colleagues, get_colleague_profile, photo proxy |
| Photo proxy route | Graph API client, Flask routing | Profile card photo display, token security (browser never sees Graph token) |
| Profile card rendering | search_colleagues/get_colleague_profile tool result, photo proxy | Inline colleague information in chat |
| Kerberos Constrained Delegation | Domain-joined Windows host, KCD config in AD | Per-user Exchange RBAC, per-user audit trail (v2) |
| Per-call PSSession | Python asyncio, WinRM endpoint, service account | All Exchange tools |
| Tool registry (list_tools) | MCP SDK | Tool dispatch, tool visibility in UI, model tool selection |
| Conversation DB | SSO user identity, SQLite | History persistence, multiple threads, export, search |
| Tool visibility in UI | MCP tool call metadata in model response | User trust, audit capability, export with tool traces |
| Design token system (CSS custom properties) | CSS refactor | Dark mode consistency, WCAG AA compliance, theme maintenance |
| Tool call timestamps | Backend SSE event changes | Tool elapsed time display, status badge accuracy |

---

## Sources

**Domain 5 — UI/UX Overhaul (verified 2026-03-27):**
- [The new UI for enterprise AI — Microsoft Design](https://microsoft.design/articles/the-new-ui-for-enterprise-ai/)
- [Creating a dynamic UX: guidance for generative AI applications — Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-cloud/dev/copilot/isv/ux-guidance)
- [Design Patterns For AI Interfaces — Smashing Magazine](https://www.smashingmagazine.com/2025/07/design-patterns-ai-interfaces/)
- [AI Chat UI Best Practices: Designing Better LLM Interfaces — DEV Community](https://dev.to/greedy_reader/ai-chat-ui-best-practices-designing-better-llm-interfaces-18jj)
- [Fluent 2 Design System — Color](https://fluent2.microsoft.design/color)
- [Designing dark mode — Microsoft Design](https://microsoft.design/articles/designing-dark-mode/)
- [AI UX Patterns — Citations — ShapeofAI.com](https://www.shapeof.ai/patterns/citations)
- [Comparing Conversational AI Tool User Interfaces 2025 — IntuitionLabs](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025)
- [AI Copilot UX 2025–26: Best Practices for Trustworthy Interfaces](https://www.letsgroto.com/blog/mastering-ai-copilot-design)
- [ChatGPT Sidebar Redesign: New Features Explained](https://www.ai-toolbox.co/chatgpt-management-and-productivity/chatgpt-sidebar-redesign-guide)
- [Where should AI sit in your UI — UX Collective](https://uxdesign.cc/where-should-ai-sit-in-your-ui-1710a258390e)
- [Beyond Chat: How AI is Transforming UI Design Patterns — Artium.AI](https://artium.ai/insights/beyond-chat-how-ai-is-transforming-ui-design-patterns)

**Domains 1–4 — original research (verified 2026-03-19 to 2026-03-24):**
- Microsoft Graph profilephoto GET API: https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0
- Microsoft Graph user resource type: https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0
- Microsoft Graph $search parameter: https://learn.microsoft.com/en-us/graph/search-query-parameter
- Microsoft Graph Toolkit Person-Card (archived, retirement 2026-08-28): https://learn.microsoft.com/en-us/graph/toolkit/components/person-card
