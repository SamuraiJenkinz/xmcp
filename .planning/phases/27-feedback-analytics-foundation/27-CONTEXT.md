# Phase 27: Feedback Analytics Foundation - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Two read-only MCP tools (`get_feedback_summary`, `get_low_rated_responses`) that query the existing SQLite feedback table through conversation. Users get aggregate stats, satisfaction trends, and detailed negative feedback review. No frontend changes. No write operations. Phase 28 adds tool correlation on top of this foundation.

</domain>

<decisions>
## Implementation Decisions

### Date range defaults
- Default window: last 7 days when no date specified
- Custom ranges supported via AI-parsed natural language (start_date/end_date parameters)
- Maximum lookback: 90-day cap to prevent slow queries
- Empty range: return structured response with zero counts and a "no feedback in this period" note

### Summary data shape
- Metrics selection: Claude's discretion based on research and best practices (vote counts, satisfaction rate, daily trend, comment count are candidates)
- Satisfaction rate: simple percentage only — let the AI characterize it conversationally
- Daily trend: include days with zero feedback as zero counts (complete picture)
- No automatic previous-period comparison — user can ask explicitly and AI calls twice

### Negative feedback detail
- Default limit: 10 most recent low-rated responses
- Entry context: Claude's discretion based on research (timestamp, thread name, comment text, AI response snippet are candidates)
- Scope: all thumbs-down entries, not just those with comments — flag which ones have comments
- No keyword filter on comments — keep the tool simple, let AI summarize patterns

### Privacy boundaries
- No user identity exposed in analytics output — fully anonymous
- Thread names: shown as-is (no truncation) — they provide context for understanding feedback
- Comment text: returned in full — users intentionally wrote these, full text is most actionable
- Access: all authenticated Atlas users (no extra RBAC gating) — data is aggregate and anonymous

### Claude's Discretion
- Exact metrics included in get_feedback_summary response
- Fields included per negative feedback entry in get_low_rated_responses
- ATLAS_DB_PATH configuration approach
- Read-only SQLite connection pattern
- Error handling for database unavailability

</decisions>

<specifics>
## Specific Ideas

- Success criteria requires "total votes, thumbs-up/down counts, and satisfaction rate percentage" for summary
- Success criteria requires "timestamped thumbs-down entries with comment text and thread names" for negative feedback
- Must match the proven MCP tool pattern established in Phase 26 (message trace)
- Backend-only milestone — zero frontend changes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 27-feedback-analytics-foundation*
*Context gathered: 2026-04-06*
