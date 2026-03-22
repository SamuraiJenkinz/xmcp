# Phase 9: UI Polish - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Polish the Atlas chat interface into a professional internal tool. Deliver: collapsible tool visibility panels showing Exchange data used per response, copy-to-clipboard on messages and tool data, loading/thinking indicators, keyboard shortcuts (Ctrl+Enter send, Esc cancel), and a dark mode toggle with session persistence. No new features or capabilities — this is UX refinement of the existing Phase 7+8 chat app.

</domain>

<decisions>
## Implementation Decisions

### Tool detail panel
- Collapsible panel shows tool name, parameters sent, AND raw Exchange JSON result — full transparency
- Default state: collapsed — click to expand, keeps chat flow clean
- Raw Exchange JSON displayed with syntax highlighting (colored key/value differentiation)
- Claude's discretion on placement (inline below chip vs grouped below message) and multi-tool handling

### Copy & export behavior
- Copy button appears on hover over assistant messages — not always visible, keeps UI uncluttered
- Copy captures AI answer text only — not tool data (colleagues paste into Teams/email)
- No separate export/download feature — plain text clipboard copy is sufficient
- Tool detail panel gets its own separate copy button for raw Exchange JSON — lets colleagues grab structured data for troubleshooting

### Loading & progress feedback
- Add animated dots indicator (three bouncing dots, iMessage-style) as a pre-tool thinking state — fills the gap between send and first tool chip/text event
- Existing tool chips ("Querying tool_name...") remain as-is for per-tool status
- Esc cancel keeps partial streamed text visible, marked as interrupted
- Esc cancel aborts fully — closes SSE connection to stop server-side processing and Exchange queries

### Dark mode
- Toggle in header bar — sun/moon icon next to user name and logout
- Auto-detect OS/browser prefers-color-scheme on first visit; user toggle overrides and persists
- True dark palette: #1a1a2e backgrounds, complementing existing #2563eb blue accent
- Smooth ~200ms crossfade transition on toggle — no jarring instant swap
- Preference persisted via localStorage across sessions

### Claude's Discretion
- Tool panel placement strategy (inline per-chip vs grouped per-message)
- Exact syntax highlighting approach (CSS-only vs lightweight library)
- Animated dots implementation details
- Dark mode color values for all UI elements (sidebar, messages, input, tool panels)
- "Interrupted" visual treatment for cancelled responses
- How copy confirmation is shown (tooltip, toast, etc.)

</decisions>

<specifics>
## Specific Ideas

- Tool panel: full transparency was emphasized — colleagues should see everything the AI saw from Exchange
- Copy on hover pattern keeps the UI clean for the corporate setting
- Separate copy on tool panel for Exchange JSON — troubleshooting use case is distinct from sharing AI answers
- True dark (#1a1a2e) matches the existing brand text color used in light mode — visual consistency
- System preference detection on first visit respects colleague workstation settings

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-ui-polish*
*Context gathered: 2026-03-21*
