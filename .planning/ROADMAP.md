# Roadmap: Exchange Infrastructure MCP Server (Atlas)

## Milestones

- ✅ **v1.0 MVP** - Phases 1-9 (shipped 2026-03-22)
- ✅ **v1.1 Colleague Lookup** - Phases 10-12 (shipped 2026-03-25)
- ✅ **v1.2 UI/UX Redesign** - Phases 13-20 (shipped 2026-03-30)
- ✅ **v1.3 Access Control, Feedback, Search, Export, Animations** - Phases 21-25 (shipped 2026-04-02)
- 🚧 **v1.4 Message Trace & Feedback Analytics** - Phases 26-28 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-9) - SHIPPED 2026-03-22</summary>

Delivered complete Exchange management system: 15-tool MCP server, Flask chat app with Azure AD SSO, SQLite conversation persistence, polished UI with tool panels and dark mode.

35 plans across 9 phases. See MILESTONES.md for full detail.

</details>

<details>
<summary>✅ v1.1 Colleague Lookup (Phases 10-12) - SHIPPED 2026-03-25</summary>

Delivered Microsoft Graph API integration, two new MCP tools (search_colleagues, get_colleague_profile), secure photo proxy, and inline profile cards.

9 plans across 3 phases. See MILESTONES.md for full detail.

</details>

<details>
<summary>✅ v1.2 UI/UX Redesign (Phases 13-20) - SHIPPED 2026-03-30</summary>

Delivered full frontend rewrite to React 19 + Fluent UI v9 + Tailwind v4 with Microsoft Copilot aesthetic, 62 --atlas- design tokens, WCAG AA accessibility, dark/light mode, and polished chat interactions.

22 plans across 8 phases. See MILESTONES.md for full detail.

</details>

<details>
<summary>✅ v1.3 Access Control, Feedback, Search, Export, Animations (Phases 21-25) - SHIPPED 2026-04-02</summary>

Delivered Azure AD App Role access gating, per-message thumbs up/down feedback with SQLite persistence, two-tier thread search (client-side + FTS5), Markdown conversation export, and motion entrance animations with prefers-reduced-motion compliance.

9 plans across 5 phases. See MILESTONES.md for full detail.

</details>

### 🚧 v1.4 Message Trace & Feedback Analytics (In Progress)

**Milestone Goal:** Add a message trace MCP tool for email delivery tracking (Get-MessageTraceV2) and three feedback analytics MCP tools that query the existing SQLite feedback table directly from the MCP server — bringing the total tool count from 17 to 21. Backend-only milestone with zero frontend changes.

- [x] **Phase 26: Message Trace Tool** - Exchange Online message trace via Get-MessageTraceV2 with RBAC verification, PII-safe subject handling, and system prompt disambiguation
- [ ] **Phase 27: Feedback Analytics Foundation** - Read-only SQLite access from MCP server for feedback summary and low-rated response queries
- [ ] **Phase 28: Tool Correlation & Analytics Completion** - Feedback-to-tool correlation logic and system prompt guidance for all analytics tools

## Phase Details

### Phase 26: Message Trace Tool
**Goal**: Users can track email delivery status through conversational queries — answering "did my email arrive?" without PowerShell access
**Depends on**: Nothing (first phase of v1.4; uses proven Exchange tool pattern)
**Requirements**: TRACE-01, TRACE-02, TRACE-03, TRACE-04, TRACE-05, TRACE-06, TRACE-07, TRACE-08, TRACE-09, TRACE-10, INFRA-01
**Success Criteria** (what must be TRUE):
  1. User asks "trace emails from john@example.com in the last 3 days" and receives delivery status, timestamps, and recipient for each matching message
  2. User can filter trace results by subject line keyword and the results narrow accordingly
  3. The AI correctly chooses `get_message_trace` for delivery tracking questions and `check_mail_flow` for routing topology questions — no tool confusion
  4. Broad queries (no sender/recipient, wide date range) return a capped result set with a summary instead of hanging or timing out
  5. Subject lines in trace results are stripped or truncated — no full PII-bearing subjects exposed in tool output
**Plans**: 2 plans

Plans:
- [x] 26-01-PLAN.md — RBAC verification and Get-MessageTraceV2 tool handler implementation
- [x] 26-02-PLAN.md — System prompt disambiguation and tool registration finalization

### Phase 27: Feedback Analytics Foundation
**Goal**: Users can query aggregate feedback data through conversation — vote counts, satisfaction trends, and detailed negative feedback review
**Depends on**: Phase 26 (sequential ordering; no code dependency but validates simpler pattern first)
**Requirements**: FBAN-01, FBAN-02, FBAN-03, FBAN-04, FBAN-07, FBAN-08, FBAN-10, INFRA-02
**Success Criteria** (what must be TRUE):
  1. User asks "how is Atlas feedback looking this week?" and receives total votes, thumbs-up/down counts, and satisfaction rate percentage
  2. User asks "show me the negative feedback with comments" and receives timestamped thumbs-down entries with comment text and thread names — no per-user identity exposed
  3. Daily trend data is included when querying feedback summaries, showing satisfaction movement over the requested date range
  4. The MCP server reads the SQLite database in read-only mode — no write operations possible from the analytics module
**Plans**: TBD

Plans:
- [ ] 27-01: ATLAS_DB_PATH plumbing and read-only SQLite connection pattern
- [ ] 27-02: get_feedback_summary and get_low_rated_responses tool handlers

### Phase 28: Tool Correlation & Analytics Completion
**Goal**: Users can identify which Exchange tools produce the worst user experience and the AI presents all analytics results conversationally
**Depends on**: Phase 27 (builds on SQLite access pattern and feedback_analytics.py module)
**Requirements**: FBAN-05, FBAN-06, FBAN-09, FBAN-11
**Success Criteria** (what must be TRUE):
  1. User asks "which Exchange tools get the most negative feedback?" and receives a per-tool satisfaction breakdown with vote counts
  2. User asks for the worst-rated tool queries and receives specific examples of low-rated interactions with the tool name and context
  3. The AI presents analytics results in natural conversational language (not raw JSON or table dumps) guided by system prompt rules
**Plans**: TBD

Plans:
- [ ] 28-01: get_feedback_by_tool handler with message-to-tool correlation logic
- [ ] 28-02: System prompt analytics guidance and tool registration

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-9. MVP | v1.0 | 35/35 | Complete | 2026-03-22 |
| 10-12. Colleague Lookup | v1.1 | 9/9 | Complete | 2026-03-25 |
| 13-20. UI/UX Redesign | v1.2 | 22/22 | Complete | 2026-03-30 |
| 21-25. Access Control, Feedback, Search, Export, Animations | v1.3 | 9/9 | Complete | 2026-04-02 |
| 26. Message Trace Tool | v1.4 | 2/2 | Complete | 2026-04-06 |
| 27. Feedback Analytics Foundation | v1.4 | 0/2 | Not started | - |
| 28. Tool Correlation & Analytics Completion | v1.4 | 0/2 | Not started | - |
