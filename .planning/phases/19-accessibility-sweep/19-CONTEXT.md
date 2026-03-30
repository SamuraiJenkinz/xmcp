# Phase 19: Accessibility Sweep - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Keyboard navigation and WCAG AA focus rings verified across all redesigned React components (Phases 13-18). The full UI must be operable without a mouse. Scope is limited to keyboard operability and visible focus indicators -- screen reader optimization, color contrast auditing, and ARIA live regions for streaming are out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Focus ring style
- Use Fluent 2 double-ring focus indicator pattern: 2px inner ring (white/black depending on theme) + 2px outer ring (--atlas-stroke-focus or brand color) with 1px offset
- Dark mode: inner white (#fff), outer --atlas-accent-primary; Light mode: inner white (#fff), outer black (#000) -- matches Microsoft's webDarkTheme/webLightTheme focus visible spec
- Apply via `:focus-visible` only (not `:focus`) to avoid showing rings on mouse click
- Use CSS outline (not box-shadow) for focus rings -- outlines respect border-radius in modern browsers and don't affect layout
- No animation on focus ring appearance -- instant visibility is more accessible

### Keyboard interaction patterns
- Tab/Shift+Tab: Navigate between all interactive elements in logical order
- Enter/Space: Activate buttons, toggle tool panels, select thread items
- Arrow Up/Down: Navigate within sidebar thread list (roving tabindex pattern) -- thread list acts as a single tab stop, arrows move within
- Escape: Close expanded tool panels, cancel thread rename, exit sidebar focus back to chat pane
- Home/End: Jump to first/last thread in sidebar list when focused within
- No custom global keyboard shortcuts beyond what already exists (Enter to send, Shift+Enter for newline, Escape to cancel stream)

### Skip navigation
- Include a single "Skip to chat" link as the first focusable element in the DOM
- Visible only on focus (visually hidden by default, slides into view at top-left on Tab)
- Target: the chat message container (main content area), not the input -- user can Tab from there to input
- Styled with --atlas-accent-primary background, white text, z-index above header

### Focus management on state changes
- Thread deleted: Focus moves to the next thread in the list; if last thread deleted, focus moves to "New Chat" button
- Thread created: Focus moves to the input textarea (ready to type)
- Sidebar collapse: Focus stays on the collapse/expand toggle button
- Sidebar expand: Focus stays on the expand toggle button (don't auto-jump into sidebar content)
- Tool panel expand/collapse: Focus stays on the toggle (chevron summary element)
- Streaming complete: Do not move focus -- user may be reading; input is already focusable when ready
- Prompt chip click: Focus moves to input textarea after chip sends message (same as thread creation)

### Claude's Discretion
- Exact outline-offset pixel values (1px recommended, adjust if clipping occurs on specific components)
- Whether to add `scroll-margin` on focus targets to prevent focused elements being obscured behind sticky headers
- Tab order micro-adjustments within message bubbles (copy button, timestamp -- or skip these as mouse-only hover actions)
- Whether roving tabindex in thread list uses `aria-activedescendant` or moves actual DOM focus

</decisions>

<specifics>
## Specific Ideas

- Fluent 2's focus indicator is the reference -- Microsoft's own components use the double-ring pattern consistently
- The existing `--atlas-` token system should provide the focus ring colors (add `--atlas-stroke-focus` if not already present)
- `:focus-visible` has full browser support in all modern browsers -- no polyfill needed
- Hover actions (copy button, timestamp) are currently mouse-only overlays -- these should remain mouse-only for this phase since they're non-essential (copy is also available via keyboard shortcut Ctrl+C on selected text)

</specifics>

<deferred>
## Deferred Ideas

- Screen reader optimization (ARIA live regions for streaming messages, role="log" on chat container) -- separate accessibility phase
- Color contrast audit beyond focus rings (WCAG AA contrast on all text/background combinations) -- separate audit
- Reduced motion preferences beyond the existing `prefers-reduced-motion` media query on message animations -- already partially handled in Phase 16

</deferred>

---

*Phase: 19-accessibility-sweep*
*Context gathered: 2026-03-30*
