---
phase: 19-accessibility-sweep
plan: 01
subsystem: ui
tags: [accessibility, wcag, focus-rings, css-tokens, fluent2, skip-navigation, keyboard]

# Dependency graph
requires:
  - phase: 15-design-system
    provides: --atlas-accent token contrast-verified against dark surfaces
  - phase: 16-chat-experience-redesign
    provides: AppLayout, MessageList, Header, ChatInput component structure

provides:
  - Global Fluent 2 double-ring :focus-visible rule covering all interactive elements
  - Focus ring CSS tokens (--atlas-stroke-focus-inner/outer) in :root and dark theme
  - Windows High Contrast forced-colors fallback
  - SkipLink component targeting #chat-messages for WCAG 2.4.1 bypass-blocks
  - outline:none removed from .chat-input and .thread-item-name-input
  - aria-label on Header theme toggle button

affects:
  - 19-02 (ARIA roles and semantic HTML phase - if any)
  - future component additions (must not add outline:none overrides)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Global :focus-visible outside @layer for document-level specificity over component styles"
    - "Fluent 2 double-ring: 2px solid inner outline + 4px box-shadow outer ring"
    - "Dark mode focus: white inner ring + --atlas-accent outer (contrast-verified)"
    - "Skip link pattern: position:absolute top:-9999px, revealed on :focus-visible"

key-files:
  created:
    - frontend/src/components/SkipLink.tsx
  modified:
    - frontend/src/index.css
    - frontend/src/components/AppLayout.tsx
    - frontend/src/components/ChatPane/MessageList.tsx
    - frontend/src/components/ChatPane/Header.tsx

key-decisions:
  - "Global :focus-visible placed outside @layer so it has natural cascade precedence over layered component styles"
  - "Dark mode outer ring uses --atlas-accent (#115ea3) not #000000 — Phase 15 verified against dark surfaces"
  - "tabIndex={-1} on #chat-messages allows programmatic focus from skip link without entering chat in natural tab order"
  - "thread-list padding:2px prevents overflow:auto clipping of 4px box-shadow focus ring on thread items"

patterns-established:
  - "Focus ring pattern: outline 2px solid inner + box-shadow 0 0 0 4px outer"
  - "No component-level outline overrides — global rule is the single source of truth"
  - "Skip link is always first child of app-container, targets #chat-messages"

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 19 Plan 01: Focus Rings and Skip Navigation Summary

**Fluent 2 double-ring :focus-visible system with CSS tokens, forced-colors fallback, and WCAG 2.4.1 skip navigation targeting #chat-messages**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T13:35:01Z
- **Completed:** 2026-03-30T13:37:37Z
- **Tasks:** 2
- **Files modified:** 5 (1 created)

## Accomplishments

- Global `:focus-visible` double-ring rule (2px inner outline + 4px outer box-shadow) covers all interactive elements — buttons, links, inputs, textareas, summary elements, prompt chips — via a single CSS block outside `@layer`
- Focus ring tokens `--atlas-stroke-focus-inner/outer` defined for light (white/#000) and dark (white/--atlas-accent) modes with Phase 15 contrast compliance
- Windows High Contrast Mode fallback: `box-shadow: none` with `outline: 2px solid ButtonText` preserved
- `outline: none` removed from `.chat-input` and `.thread-item-name-input` — both now show focus rings
- `SkipLink` component mounted as first focusable element in `app-container`; skip link targets `#chat-messages` with `tabIndex={-1}` on the chat container
- Theme toggle button in `Header.tsx` has dynamic `aria-label` describing the switch direction

## Task Commits

Each task was committed atomically:

1. **Task 1: Focus ring tokens, global :focus-visible rule, and outline:none cleanup** - `9da29e7` (feat)
2. **Task 2: SkipLink component and wiring into AppLayout + MessageList** - `e446a44` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `frontend/src/index.css` - Focus ring tokens in :root and [data-theme="dark"], global :focus-visible block, forced-colors media query, skip-link CSS, outline:none removals, thread-list padding
- `frontend/src/components/SkipLink.tsx` - New: skip navigation anchor targeting #chat-messages
- `frontend/src/components/AppLayout.tsx` - SkipLink imported and mounted as first child of app-container
- `frontend/src/components/ChatPane/MessageList.tsx` - id="chat-messages" and tabIndex={-1} on both render paths
- `frontend/src/components/ChatPane/Header.tsx` - aria-label added to theme toggle button

## Decisions Made

- **Global :focus-visible outside @layer**: CSS Cascade Layers have lower specificity than unlayered styles. Placing the rule outside `@layer base` and `@layer components` ensures it applies unless explicitly overridden per-element — no need to repeat it in each component layer.
- **Dark mode outer ring = --atlas-accent**: Black outer ring (#000000) has insufficient contrast against dark surfaces (#292929, #1f1f1f). --atlas-accent (#115ea3) was contrast-verified in Phase 15 for use on dark backgrounds.
- **tabIndex={-1} on #chat-messages**: The skip link target must be focusable programmatically (`href="#chat-messages"` with JS focus). `tabIndex={-1}` makes it receivable without entering the chat container in the natural tab sequence.
- **thread-list padding:2px**: The sidebar uses `overflow-y: auto` which clips the 4px box-shadow of the outer focus ring. A 2px padding on `.thread-list` creates the visual clearance needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Focus ring CSS foundation is complete and active for all interactive elements
- Any new components added must NOT include `outline: none` or `outline: 0` CSS/inline styles — the global rule handles focus indicators
- Phase 19-02 (if planned: ARIA roles, landmark regions, color contrast audit) can proceed immediately
- Build passes cleanly at 288ms with no TypeScript or Vite errors

---
*Phase: 19-accessibility-sweep*
*Completed: 2026-03-30*
