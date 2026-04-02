# Phase 23: Thread Search - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can find threads instantly by typing in the sidebar search box. Client-side title filtering provides immediate results; backend FTS5 search across message content provides deeper discovery when title alone isn't enough. Ctrl+K focuses the search. Creating, deleting, or organizing threads are separate concerns.

</domain>

<decisions>
## Implementation Decisions

### Search input & interaction
- Ctrl+K behavior: Claude's discretion — focus existing sidebar input or command palette overlay, whichever fits the sidebar layout best
- Placeholder text: Claude's discretion
- Escape key behavior: Claude's discretion — clear+restore or blur, whichever feels most natural
- Clear button visible per roadmap success criteria

### Result presentation
- FTS5 snippet display style: Claude's discretion — subtitle line, expandable preview, or similar, based on sidebar width and Fluent 2 patterns
- Match highlighting within snippets: Claude's discretion — bold, accent color, or none, based on existing design tokens
- Result count badge placement: Claude's discretion — per-thread, top of results, or both, whichever is least cluttered
- Title matches vs content matches grouping: Claude's discretion — unified list or two sections, based on scanning speed

### Empty & edge states
- No-match empty state style: Claude's discretion — simple text or illustration+text, matching existing sidebar style
- FTS5-specific empty state: Claude's discretion — may differentiate from title-filter empty state or use shared message
- Loading indicator during FTS5 request: Claude's discretion — spinner in input, skeleton rows, or similar Fluent 2 pattern
- Min-character hint for FTS5: Claude's discretion — silent activation or subtle hint at 1 character

### Filtering vs searching feel
- Unified experience: Claude's discretion — single input with title filter + FTS5 combined, or two explicit modes
- Search state on navigation: Claude's discretion — persist search results or clear on thread selection
- Active thread visibility during filter: Claude's discretion — pinned/always visible or filtered equally
- FTS5 message scope: Claude's discretion — both user and assistant messages, or user-only

### Claude's Discretion
All implementation decisions for this phase are at Claude's discretion. The user trusts Claude to make the best choices based on:
- Existing sidebar component structure and Fluent 2 patterns
- Atlas design token system (--atlas-* tokens)
- What feels natural and least complex for IT engineers finding past conversations
- Consistency with the Copilot aesthetic established in v1.2

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The user trusts Claude's judgment across all areas for this phase.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-thread-search*
*Context gathered: 2026-04-02*
