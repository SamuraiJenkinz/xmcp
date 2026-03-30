---
phase: 17-sidebar-and-tool-panels
plan: 02
subsystem: ui
tags: [react, sidebar, fluent-ui, css-transitions, localstorage, typescript]

# Dependency graph
requires:
  - phase: 15-design-system
    provides: --atlas- CSS custom properties used for sidebar, text, and stroke tokens
  - phase: 14-functional-port
    provides: ThreadList component, Thread type, ThreadContext
provides:
  - groupThreadsByRecency pure utility bucketing Thread[] into Today/Yesterday/This Week/Older groups
  - ThreadList with recency-grouped rendering, collapse-aware layout, and toggle + Compose icons
  - AppLayout sidebar collapse state with localStorage persistence and data-collapsed attribute
  - CSS: sidebar width transition (260px to 56px, 200ms ease), thread group headings, new-chat button styles
affects:
  - phase: 17-sidebar-and-tool-panels (plan 03, which builds on the sidebar foundation)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - groupThreadsByRecency pure function with Sunday edge case (getDay()==0 maps to 7 days lookback)
    - Sidebar collapse driven by data-collapsed attribute + CSS attribute selector
    - localStorage persistence for UI state using direct get/set (not a hook)

key-files:
  created:
    - frontend/src/utils/groupThreadsByRecency.ts
  modified:
    - frontend/src/components/Sidebar/ThreadList.tsx
    - frontend/src/components/AppLayout.tsx
    - frontend/src/index.css

key-decisions:
  - "Icon names have no size suffix in @fluentui/react-icons v9 — ComposeRegular not Compose20Regular; PanelLeftContractRegular not PanelLeftContract20Regular"
  - "sunday-grouping: getDay()==0 passes 7 to getLocalMidnight() so This Week covers full preceding 7 days"
  - "new-chat-btn is now icon+text in header row (transparent bg) not full-width accent button"

patterns-established:
  - "Thread group heading: uppercase caption2, tertiary color, 0.5px letter-spacing"
  - "Sidebar collapse toggle: always-visible 32x32 btn at top; thread list hidden when collapsed"
  - "Collapsed-mode icon button: 40x40, auto-centred, same hover token as expanded controls"

# Metrics
duration: 18min
completed: 2026-03-30
---

# Phase 17 Plan 02: Sidebar Recency Grouping and Collapse Mode Summary

**Sidebar redesigned with Today/Yesterday/This Week/Older thread grouping, icon-only collapse to 56px with 200ms CSS transition, and localStorage persistence using Fluent 2 tokens throughout.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-30T11:37:06Z
- **Completed:** 2026-03-30T11:55:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `groupThreadsByRecency` pure utility with correct Sunday handling (getDay()===0 maps to 7 days for This Week)
- ThreadList now renders threads under recency group headings; accepts `collapsed` and `onToggleCollapse` props
- AppLayout owns sidebar collapse state persisted to `localStorage` under `atlas-sidebar-collapsed` key
- CSS transition shrinks sidebar from 260px to 56px in 200ms; collapsed mode shows only toggle + Compose icon

## Task Commits

Each task was committed atomically:

1. **Task 1: Create groupThreadsByRecency utility and update ThreadList** - `ab8ad8b` (feat)
2. **Task 2: Add sidebar collapse state to AppLayout and CSS** - `4774850` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `frontend/src/utils/groupThreadsByRecency.ts` - Pure function bucketing Thread[] by updated_at into Today/Yesterday/This Week/Older; Sunday edge case handled
- `frontend/src/components/Sidebar/ThreadList.tsx` - Grouped thread rendering with recency headings; collapse-aware with PanelLeft icons and ComposeRegular
- `frontend/src/components/AppLayout.tsx` - Sidebar collapse state with useState + localStorage; data-collapsed attribute on aside; toggle handler passed to ThreadList
- `frontend/src/index.css` - Sidebar collapse CSS transition, sidebar[data-collapsed] width override, thread-list-header, sidebar-toggle-btn, new-chat-btn (redesigned), new-chat-btn-collapsed, thread-group, thread-group-heading

## Decisions Made
- **Icon size suffix absent** — `@fluentui/react-icons` v9 exports `ComposeRegular` not `Compose20Regular`; `PanelLeftContractRegular`/`PanelLeftExpandRegular` not the `20Regular` variants from the plan spec. Used correct names.
- **new-chat-btn redesigned** — replaced accent-background full-width button with transparent icon+text header-row button matching Fluent 2 command bar pattern. Old `.new-chat-btn` accent styles removed entirely.
- **thread-list padding reset to 0** — header provides its own padding; thread group items use their own padding; removes double-padding from old flat list layout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected icon import names — no size suffix in @fluentui/react-icons v9**
- **Found during:** Task 1 (ThreadList.tsx authoring)
- **Issue:** Plan spec used `Compose20Regular`, `PanelLeftContract20Regular`, `PanelLeftExpand20Regular` — these don't exist in the installed package; icons have no size in their export name
- **Fix:** Used `ComposeRegular`, `PanelLeftContractRegular`, `PanelLeftExpandRegular` — verified against package chunk type definitions
- **Files modified:** frontend/src/components/Sidebar/ThreadList.tsx
- **Verification:** `npx tsc --noEmit` passes; `npm run build` succeeds
- **Committed in:** ab8ad8b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — incorrect icon names from plan spec)
**Impact on plan:** Minimal — icon functionality identical; only the export name differed. No scope creep.

## Issues Encountered
None beyond the icon name correction above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Sidebar recency grouping and collapse mode are complete; 17-03 (tool panel polish or remaining sidebar work) can build directly on this foundation
- `data-collapsed` attribute on `<aside>` is available for any CSS-driven layout adjustments needed in the chat pane
- `groupThreadsByRecency` is a tested pure function ready for unit tests if Phase 17/18 adds a test suite

---
*Phase: 17-sidebar-and-tool-panels*
*Completed: 2026-03-30*
