# Phase 8: Conversation Persistence - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Store conversation threads and messages in SQLite so colleagues can return the next day and find their previous conversations intact. Provide sidebar navigation to create, switch between, and delete threads. Auto-name conversations from the first query. Conversation history is scoped to the authenticated user.

</domain>

<decisions>
## Implementation Decisions

### Sidebar & thread display
- Always-visible left panel sidebar alongside the chat area
- Threads ordered by most recent message first (no date grouping)
- Thread entries show name only — no timestamps, no message previews
- Active thread indicated by highlighted row background

### Thread lifecycle
- Explicit "New Chat" button at top of sidebar to create threads
- Delete requires confirmation dialog before removing
- After deletion, select the next thread in the list
- Claude's Discretion: what to show on initial app load (last active thread vs empty state)

### Auto-naming style
- Auto-name from truncated first message (~30 chars)
- Users can click thread name in sidebar to rename inline
- Fallback name when auto-naming fails: timestamp format ("Chat — Mar 21, 2:30 PM")

### Message storage scope
- Store full tool call metadata per message: tool name, parameters, and raw Exchange result
- System prompt is global (code/config), not stored per thread
- Loading a previous thread sends full message history with same context window pruning as live chat
- No thread count limit — let threads accumulate

### Claude's Discretion
- Initial app load behavior (last active thread vs blank new chat)
- Sidebar width and responsive behavior
- Delete confirmation dialog styling
- SQLite schema details and migration approach

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-conversation-persistence*
*Context gathered: 2026-03-21*
