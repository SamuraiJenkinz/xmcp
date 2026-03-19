# Phase 3: Mailbox Tools - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Three MCP tools for querying Exchange mailbox data: get_mailbox_stats (single mailbox details), search_mailboxes (filtered mailbox listing), and get_shared_mailbox_owners (delegate permissions). These tools are called by the LLM on behalf of users through the chat interface. Creating or modifying mailboxes is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Output schema shape
- Human-friendly snake_case field names (total_size, item_count, last_logon) — not Exchange-native PascalCase
- Sizes pre-converted to sensible units (e.g., "2.4 GB") — no raw bytes
- Include quota thresholds alongside current usage (issue_warning_quota, prohibit_send_quota, prohibit_send_receive_quota) so the LLM can calculate and report percentage used
- Light nesting for related fields (e.g., quotas as a nested object) — not completely flat, not deeply nested

### Search behavior
- Default ResultSize cap: 100 results when user doesn't specify a limit
- Wildcard support on display name filter (e.g., 'john*' matches 'John Smith') — use Exchange's native -Anr or wildcard capability
- Empty results return {results: [], count: 0, message: "No mailboxes matched the filter"} — include explanatory message
- Truncation flag when ResultSize cap is hit: {truncated: true, count: 100, message: "Results capped at 100"} — LLM can tell user to narrow search

### Permission output format
- Delegates grouped by permission type: full_access: [...], send_as: [...], send_on_behalf: [...]
- Include both inherited and directly-assigned permissions, with inherited flagged (inherited: true, via_group: "IT-Team")
- Each delegate entry includes both display_name and identity (UPN)
- Include summary counts per permission type (full_access_count: 3, etc.)

### Error & edge cases
- Specific error messages that echo the input: "No mailbox found for 'john.smth@company.com'. Check the email address and try again."
- Validate UPN format (contains @, valid domain structure) before calling Exchange — fail fast with clean message instead of waiting for Exchange timeout
- get_shared_mailbox_owners returns delegates regardless of mailbox type (works on regular mailboxes too, not just shared)
- Distinct error types: differentiate "mailbox not found" vs "Exchange unreachable" vs "timeout" — LLM can give appropriate guidance per error type

### Claude's Discretion
- Exact field list per tool beyond what's specified in success criteria
- PowerShell cmdlet parameter choices and Select-Object schema
- Internal retry behavior for transient Exchange errors (already decided in Phase 1)
- Exact UPN validation regex pattern

</decisions>

<specifics>
## Specific Ideas

- Tools are consumed by an LLM, not displayed raw to users — optimize field names and structure for LLM comprehension and natural language relay
- Quota inclusion enables the common admin question "is this mailbox almost full?" to be answered in a single tool call
- Wildcard search + truncation flag together support the pattern: broad search first, then narrow if too many results

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-mailbox-tools*
*Context gathered: 2026-03-19*
