# Phase 26: Message Trace Tool - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

MCP tool for Exchange Online message trace via Get-MessageTraceV2. Users ask conversational delivery tracking questions ("did my email arrive?") and receive structured trace results — without PowerShell access. This phase adds one new tool (`get_message_trace`) with RBAC verification, PII-safe output, and system prompt disambiguation from the existing `check_mail_flow` tool.

</domain>

<decisions>
## Implementation Decisions

### Result output format
- Result structure: Claude's discretion (flat list vs grouped by status)
- Result cap for broad queries: Claude's discretion (sensible cap with summary)
- Fields per result: sender, recipient, timestamp, delivery status, Exchange MessageTraceId, truncated subject snippet, message size in KB
- Empty state behavior: Claude's discretion

### PII & subject handling
- Subject lines truncated to 30 characters in trace output
- Email addresses shown in full (no masking) — admin tool, admins need full addresses
- Trace queries logged for audit purposes (who searched for what sender/recipient/date)

### Query input handling
- Default date range when user doesn't specify: last 24 hours
- At least one filter required: sender OR recipient — no open org-wide scans
- Ambiguous sender input (e.g., "John" without domain): reject with guidance asking for full or partial email address
- Maximum date range: 10 days (aligned with Get-MessageTraceV2 real-time trace limits)

### Tool disambiguation
- System prompt uses intent-based rules: "delivery tracking / did it arrive" -> get_message_trace; "routing / where does mail go" -> check_mail_flow
- When AI is unsure which tool fits: ask the user to clarify ("specific email delivery, or mail routing in general?")
- Tool description includes 2-3 example queries to help AI pattern-match (e.g., "did john@example.com's email arrive?")
- System prompt includes explicit negative guidance: "Do NOT use check_mail_flow when the user asks about a specific email delivery"

### Claude's Discretion
- Result list structure (flat vs grouped by status)
- Result cap number for broad queries
- Empty state messaging and suggestions
- Exact audit log format and location

</decisions>

<specifics>
## Specific Ideas

- Subject truncation at 30 chars keeps it tight — enough to recognize the thread, not enough to leak sensitive content
- Require sender OR recipient prevents accidental full-org scans that could be slow or noisy
- Intent-based disambiguation in system prompt rather than keyword triggers — more robust for natural language queries
- Negative guidance ("do NOT use check_mail_flow for delivery questions") explicitly prevents the most likely tool confusion

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 26-message-trace-tool*
*Context gathered: 2026-04-06*
