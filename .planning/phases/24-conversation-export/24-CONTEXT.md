# Phase 24: Conversation Export - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

IT engineers can download the active thread as a Markdown file for pasting into Jira/incident reports. The export includes all user and assistant turns plus tool call data from Exchange queries. The export button lives in the ChatPane header behind a Fluent Menu offering Markdown as a format choice. The downloaded filename includes the slugified thread name and date. Thread ownership is enforced — exporting another user's thread returns 404.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions are delegated to Claude based on research and best practices. The following areas are open:

**Markdown structure**
- How the .md file is organized — headings, turn separation, metadata header
- How tool call results and Exchange query data render (tables, code blocks, collapsible sections)
- Whether a YAML frontmatter or plain heading is used for thread metadata

**Export trigger & UX**
- Button placement and icon choice in the ChatPane header
- Fluent Menu design (single format for now per requirements, but menu structure)
- User feedback during export (toast, download indicator, or silent)
- Whether export is client-side Blob or server-side response (decision from STATE.md: Markdown client-side Blob, JSON server-side Response — hybrid per research resolution)

**Tool call data inclusion**
- How Exchange query results are formatted in Markdown — code blocks, tables, or structured sections
- Whether large tool outputs are truncated or included in full
- How tool call metadata (tool name, execution time) is presented

**Edge cases**
- Handling empty threads, very long conversations, mid-stream export attempts
- Filename collision handling
- Character encoding and special character escaping

</decisions>

<specifics>
## Specific Ideas

- Export is for pasting into Jira/incident reports — the Markdown should be clean and copy-pasteable, not heavily decorated
- Prior decision (STATE.md): Markdown export uses client-side Blob download; JSON uses server-side Response

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 24-conversation-export*
*Context gathered: 2026-04-02*
