# Phase 28: Tool Correlation & Analytics Completion - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can identify which Exchange tools produce the worst user experience and the AI presents all analytics results conversationally. Delivers `get_feedback_by_tool` MCP tool with message-to-tool correlation logic, plus system prompt guidance for conversational analytics presentation. Backend-only — zero frontend changes.

</domain>

<decisions>
## Implementation Decisions

### Correlation logic
- Multi-tool attribution strategy: Claude's discretion — choose the best approach for mapping feedback to tools when a message used multiple Exchange tools
- Tool call records are stored in SQLite already — no need to parse from message content
- Query-time vs write-time correlation: Claude's discretion — pick the approach that fits the existing architecture best
- Messages with no identifiable tool call: Claude's discretion — decide whether to exclude or bucket as "general"

### Per-tool breakdown
- Metrics to include: Claude's discretion — pick the most useful metrics based on available data
- Low-vote threshold filtering: Claude's discretion — choose a sensible minimum
- Default sort order: Claude's discretion — optimize for the "which tools have worst experience" use case
- Date range parameter: Claude's discretion — decide based on consistency with Phase 27 tools

### Low-rated examples
- Fields per example: Claude's discretion — pick fields that are most actionable without exposing PII
- Default result count: Claude's discretion — sensible default with optional limit parameter
- Tool name filter: Claude's discretion — decide whether to allow drilling into a specific tool
- Include original user query: Claude's discretion — balance PII considerations vs usefulness

### Conversational presentation
- Tone: Executive summary — concise, professional reporting style
- Actionable recommendations: Yes — AI should proactively suggest actions based on analytics data
- Low confidence flagging: Yes — explicitly note when data is sparse (e.g., "Limited data (3 votes) — trends may not be representative")
- System prompt scope: Claude's discretion — decide whether to add unified guidance for all three analytics tools or only the new tool

### Claude's Discretion
- Correlation strategy for multi-tool messages (attribute to all, last, or weighted)
- Query-time vs write-time correlation approach
- Handling of no-tool-identified feedback
- Per-tool metrics selection, thresholds, and sort order
- Date range parameter inclusion
- Low-rated example fields, count defaults, and filtering options
- Whether system prompt guidance covers all analytics tools or just the new one

</decisions>

<specifics>
## Specific Ideas

- Executive summary tone: "get_mailbox_info has 45% satisfaction across 22 interactions. Top complaint: slow response times."
- Flag low confidence explicitly when data is sparse
- AI should suggest actions, not just report numbers — e.g., "Consider reviewing get_transport_rules — it has the lowest satisfaction"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 28-tool-correlation-analytics-completion*
*Context gathered: 2026-04-06*
