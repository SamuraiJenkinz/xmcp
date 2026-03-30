---
phase: 19-accessibility-sweep
plan: 02
subsystem: ui
tags: [accessibility, wcag, keyboard-navigation, aria, roving-tabindex, sidebar, fluent2]

# Dependency graph
requires:
  - phase: 19-01
    provides: Global :focus-visible focus ring rule active for all interactive elements
  - phase: 17-sidebar-polish
    provides: ThreadItem, ThreadList components with thread rename/delete functionality
  - phase: 15-design-system
    provides: Atlas token system, CSS component layer for sidebar styles

provides:
  - ThreadItem as button element with role=option, aria-selected, roving tabIndex
  - ThreadList with role=listbox, aria-label="Conversations", Arrow/Home/End keyboard navigation
  - Post-delete focus management routing to next thread or collapsed-aware new-chat button
  - button.thread-item CSS reset in index.css removing default button browser styling
  - Action items as span role=button tabIndex={-1} (mouse-only per CONTEXT decision)

affects:
  - Any future sidebar changes involving ThreadItem or ThreadList

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Roving tabindex: single tabIndex={0} on focused item, -1 on all others; arrow keys move focus"
    - "role=listbox wrapper with onKeyDown captures Arrow/Home/End; individual items are role=option"
    - "Collapsed-aware focus fallback: collapsed ? newChatBtnCollapsedRef : newChatBtnRef"
    - "focusAfterDeletion state deferred to useEffect to run after React reconciles thread list"
    - "span role=button tabIndex={-1} for mouse-only action items inside a button — avoids invalid nesting"

key-files:
  created: []
  modified:
    - frontend/src/components/Sidebar/ThreadItem.tsx
    - frontend/src/components/Sidebar/ThreadList.tsx
    - frontend/src/index.css

key-decisions:
  - "Thread action items use span role=button not nested button — button-in-button is invalid HTML"
  - "focusAfterDeletion deferred via useState+useEffect to ensure itemRefs are populated after reconciliation"
  - "Collapsed-aware new-chat button fallback: two refs (newChatBtnRef, newChatBtnCollapsedRef) selected at runtime"
  - "Input keydown stops propagation to prevent arrow keys and Enter bubbling to listbox handler during rename"

patterns-established:
  - "Roving tabindex: tabIndexValue prop on each item, itemRef callback populates itemRefs.current[]"
  - "Post-delete focus: setFocusAfterDeletion(index) in async handler, useEffect resolves focus after state update"
  - "Listbox wrapper: role=listbox + aria-label + onKeyDown — NOT on outer scrollable container"

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 19 Plan 02: Thread List Keyboard Navigation Summary

**Roving tabindex thread listbox with Arrow Up/Down/Home/End navigation, post-delete focus management, and span role=button action items replacing nested buttons**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T14:23:32Z
- **Completed:** 2026-03-30T14:25:22Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `ThreadItem` converted from `<div>` to `<button>` with `role="option"`, `aria-selected={isActive}`, and `tabIndex={tabIndexValue}` for roving tabindex — thread list is now a single Tab stop with Arrow Up/Down/Home/End navigation
- Action buttons (`✏️`, `🗑️`) converted from `<button>` to `<span role="button" tabIndex={-1}>` to avoid invalid button-inside-button HTML nesting; action items remain mouse-only per CONTEXT.md decision
- `ThreadList` implements roving tabindex with `itemRefs`, `focusedIndex`, `handleListKeyDown`, `flatThreads` derived from groups, and `role="listbox"` wrapper with `aria-label="Conversations"`
- Post-delete focus management via `focusAfterDeletion` state deferred to `useEffect` — focus routes to next thread or collapsed-aware new-chat button when list empties
- `button.thread-item` CSS reset added to `index.css` to strip browser default button styling (border, background, font, text-align, width)

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert ThreadItem div to button with roving tabindex props** - `ed39233` (feat)
2. **Task 2: Roving tabindex in ThreadList with focus management** - `8cb9061` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `frontend/src/components/Sidebar/ThreadItem.tsx` - Outer element is now `<button>` with `role="option"`, `aria-selected`, `tabIndex={tabIndexValue}`, `ref={itemRef}`, `onFocus={onFocusInList}`; action items are `<span role="button" tabIndex={-1}>`; input has `tabIndex={-1}` and stops propagation
- `frontend/src/components/Sidebar/ThreadList.tsx` - Roving tabindex state (`itemRefs`, `focusedIndex`, `focusAfterDeletion`), `handleListKeyDown` (Arrow/Home/End), `role="listbox"` wrapper, `newChatBtnRef`/`newChatBtnCollapsedRef`, updated `handleDelete` with collapsed-aware focus fallback
- `frontend/src/index.css` - `button.thread-item` CSS reset block added before `.thread-item` styles

## Decisions Made

- **span role=button for action items**: `<button>` inside `<button>` is invalid HTML (interactive content model). `<span role="button" tabIndex={-1}>` preserves click semantics while satisfying the content model constraint.
- **focusAfterDeletion deferred to useEffect**: `handleDelete` is async — itemRefs.current may not reflect the updated thread list until React reconciles. Deferring focus via `useState` + `useEffect` that depends on `threads` ensures refs are populated.
- **Collapsed-aware new-chat button fallback**: The sidebar renders two separate buttons — one for expanded state, one for collapsed. Two refs (`newChatBtnRef`, `newChatBtnCollapsedRef`) are selected at runtime using the `collapsed` prop.
- **Input keydown stops propagation**: Without `e.stopPropagation()` on the rename input's keydown, Arrow keys and Enter bubble up through the button to the listbox handler, triggering navigation during text editing.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 19 (Accessibility Sweep) is now complete — both plans executed
- Thread list is fully keyboard-operable: single Tab stop, roving tabindex, Arrow/Home/End navigation, Enter/Space selection, post-delete focus management
- Focus ring from Phase 19-01 is active on all thread item buttons automatically
- Build passes cleanly at 305ms with zero TypeScript or Vite errors
- No open blockers for production deployment

---
*Phase: 19-accessibility-sweep*
*Completed: 2026-03-30*
