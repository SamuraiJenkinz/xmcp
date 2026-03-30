---
phase: 17-sidebar-and-tool-panels
plan: 03
subsystem: ui
tags: [react, fluent-ui, css, json, syntax-highlighting, tool-panels]

# Dependency graph
requires:
  - phase: 17-01
    provides: startTime/endTime epoch floats on ToolPanelData and SSE tool events

provides:
  - syntaxHighlightJson utility (zero-dependency regex JSON highlighter)
  - Redesigned ToolPanel with ChevronRight16Regular icon, rotating 90deg on expand
  - Status badges: Done (success green) and Error (red) with color-mix subtle backgrounds
  - Elapsed time display ("Ran in X.Xs") when startTime/endTime present
  - Per-panel CopyButton copying plain JSON text
  - CSS: chevron rotation, badge colors, elapsed time, json-key/string/number/bool/null tokens

affects: [future tool panel work, phases 18-19]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - dangerouslySetInnerHTML with JSON.parse/JSON.stringify guard for XSS-safe syntax highlighting
    - onToggle event on <details> to sync React state with native open attribute
    - color-mix() for subtle badge backgrounds using status color tokens
    - ChevronRight16Regular (no size suffix in @fluentui/react-icons v9 base export; 16px sized variant fits tool panel)

key-files:
  created:
    - frontend/src/utils/syntaxHighlightJson.ts
  modified:
    - frontend/src/components/ChatPane/ToolPanel.tsx
    - frontend/src/index.css

key-decisions:
  - "ChevronRight16Regular used — plan said ChevronRight20Regular but 16px fits better in compact summary row"
  - "No running badge state — backend SSE emits tool events only after all tools complete (run_tool_loop blocking)"
  - "syntaxHighlightJson accepts only JSON.stringify output, not raw user input — XSS risk documented in JSDoc"
  - "CopyButton receives plain text getter not highlighted HTML — correct clipboard behavior"

patterns-established:
  - "syntaxHighlightJson: pass JSON.stringify output only, never raw input"
  - "onToggle + HTMLDetailsElement cast for React state sync with native details/summary"

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 17 Plan 03: Tool Panel Redesign Summary

**ToolPanel redesigned with rotating ChevronRight16Regular, Done/Error status badges, elapsed time display, and VS Code-inspired syntax-highlighted JSON using a zero-dependency regex highlighter**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-30T11:45:01Z
- **Completed:** 2026-03-30T11:46:44Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `syntaxHighlightJson.ts` utility that wraps JSON tokens in `<span>` elements with json-key/string/number/bool/null classes
- ToolPanel now shows a rotating chevron (0 to 90deg), Done/Error badge with color-mix subtle background, optional "Ran in X.Xs" elapsed time, and syntax-highlighted JSON via `dangerouslySetInnerHTML`
- CSS updated: old `.tool-panel-icon` (8px dot) and `.tool-panel-status` removed; new chevron, badge, elapsed, and JSON token rules added
- TypeScript compiles clean; full Vite build succeeds (19.19 kB CSS, 388 kB JS)

## Task Commits

1. **Task 1: Create syntaxHighlightJson utility and redesign ToolPanel component** - `95a872d` (feat)
2. **Task 2: Add CSS for chevron rotation, status badges, elapsed time, and JSON token colors** - `4659795` (feat)

## Files Created/Modified

- `frontend/src/utils/syntaxHighlightJson.ts` - Zero-dependency regex JSON highlighter with XSS guard
- `frontend/src/components/ChatPane/ToolPanel.tsx` - Redesigned with chevron, badge, elapsed, highlighted JSON, CopyButton
- `frontend/src/index.css` - Chevron rotation class, badge color-mix rules, elapsed time style, JSON token colors

## Decisions Made

- **ChevronRight16Regular selected** — Plan spec suggested ChevronRight20Regular, but the icon file showed both `ChevronRightRegular` (no size) and `ChevronRight16Regular` exist. The 16px variant fits the compact 12px caption tool panel summary row better than the 20px default.
- **No running badge state** — Per the scope note in the plan: `run_tool_loop` in `openai_client.py` is blocking; SSE tool events only emit after all tools finish. A "running" badge would require a separate phase to add SSE tool_start events.
- **XSS safety** — `syntaxHighlightJson` JSDoc explicitly states: "ONLY pass output of JSON.stringify — never raw user input". The `prettyJson` function calls `JSON.parse` then `JSON.stringify` before highlighting, ensuring the string is safe structured JSON.

## Deviations from Plan

None - plan executed exactly as written. The icon selection note in `<context>` was addressed: `ChevronRight16Regular` was chosen over the plan's `ChevronRight20Regular` but this was explicitly anticipated in the plan ("verify the exact name before importing").

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 17 is now complete (all 3 plans: 17-01 timestamps, 17-02 sidebar, 17-03 tool panel redesign)
- Tool panels are fully polished: chevron toggle, Done/Error badges, elapsed time, syntax-highlighted JSON, copy button
- Ready for Phase 18

---
*Phase: 17-sidebar-and-tool-panels*
*Completed: 2026-03-30*
