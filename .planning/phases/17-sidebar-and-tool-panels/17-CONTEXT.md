# Phase 17: Sidebar and Tool Panels - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Thread sidebar redesign with recency grouping, collapse mode, and polished states. Tool panels redesign with chevron expand, status badges, elapsed time, and syntax-highlighted JSON. One backend change: SSE tool events carry start/end timestamps.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User granted full discretion on all implementation choices for this phase. The following areas are flexible — Claude should make decisions during research and planning based on best practices, existing codebase patterns (Fluent 2 / --atlas- tokens / Copilot aesthetic), and the success criteria below.

**Sidebar recency grouping:**
- How threads are bucketed under Today / Yesterday / This Week / Older headings
- Empty group handling (hide vs show empty)
- Sort order within groups (newest first assumed)
- Visual treatment of group headings (typography, spacing, dividers)

**Sidebar collapse behavior:**
- Icon-only mode appearance and transition animation
- What triggers collapse/expand (icon click, drag, keyboard shortcut)
- localStorage persistence of collapsed state
- Content shown in collapsed mode (icons, truncated names, nothing)

**Tool panel presentation:**
- Chevron toggle style and animation
- Status badge appearance for running / done / error states
- Elapsed time format ("Ran in 1.2s") and placement
- Expand/collapse default state for new vs historical messages

**JSON display in tool panels:**
- Syntax highlighting color theme (Fluent-aligned dark mode)
- Truncation strategy for large payloads
- Per-panel copy button placement and style
- Font and sizing for JSON content

**Sidebar polish:**
- Active/hover state refinements
- Pencil-plus new-chat button placement and style
- Spacing and padding adjustments
- Thread item layout within groups

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Should maintain the Microsoft Copilot aesthetic established in Phases 15-16 and use --atlas- design tokens throughout.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 17-sidebar-and-tool-panels*
*Context gathered: 2026-03-29*
