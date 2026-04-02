---
phase: 25-motion-animations
plan: 02
subsystem: ui
tags: [motion, animation, react, framer-motion, LazyMotion, entrance-animation, micro-interaction]

# Dependency graph
requires:
  - phase: 25-01
    provides: LazyMotion + MotionConfig providers in App.tsx, feedback-scale-btn CSS class

provides:
  - m.div entrance animation on AssistantMessage (200ms ease-out, isNew + !isStreaming guard)
  - m.div entrance animation on UserMessage (150ms ease-out, isNew guard)
  - Historical message animation gate in MessageList (loadedCountRef snapshot on thread switch)
  - feedback-scale-btn class wired to both thumb buttons in FeedbackButtons

affects: [future chat UI changes, message rendering, feedback interaction]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wrapper pattern: const Wrapper = condition ? m.div : 'div' with spread motionProps for conditional animation"
    - "loadedCountRef gate: snapshot messages.length on activeThreadId change to distinguish historical vs new messages"

key-files:
  created: []
  modified:
    - frontend/src/components/ChatPane/AssistantMessage.tsx
    - frontend/src/components/ChatPane/UserMessage.tsx
    - frontend/src/components/ChatPane/MessageList.tsx
    - frontend/src/components/ChatPane/FeedbackButtons.tsx

key-decisions:
  - "Wrapper pattern (const Wrapper = m.div | 'div') chosen over ternary JSX duplication — single return path, same children"
  - "loadedCountRef.current set in useEffect([activeThreadId]) — fires after SET_MESSAGES populates messages array, capturing correct historical count"
  - "feedback-scale-btn applied via wrapper span inside PopoverTrigger (disableButtonEnhancement) — span receives ref for popover positioning, scale on :active is CSS-only with no motion import needed"

patterns-established:
  - "Conditional m.div pattern: import * as m from 'motion/react-m'; const Wrapper = condition ? m.div : 'div'; spread motionProps"
  - "Historical animation gate: useRef snapshot of messages.length on activeThreadId change, idx >= ref.current = isNew"

# Metrics
duration: 2min
completed: 2026-04-02
---

# Phase 25 Plan 02: Motion Animations — Component Wiring Summary

**m.div entrance animations wired into message components with thread-switch historical gate; feedback thumb buttons receive CSS scale class — all 6 ANIM requirements fulfilled**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-02T00:13:23Z
- **Completed:** 2026-04-02T00:15:34Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- AssistantMessage uses m.div with 200ms ease-out fade+slide when isNew=true and isStreaming=false; falls back to plain div otherwise (ANIM-01, ANIM-04)
- UserMessage uses m.div with 150ms ease-out fade+slide when isNew=true (ANIM-02)
- MessageList computes isNew per message via loadedCountRef — messages loaded on thread switch receive isNew=false and never animate (ANIM historical gate)
- FeedbackButtons wraps both ThumbLike and ThumbDislike buttons in span.feedback-scale-btn, activating the CSS :active scale(0.88) defined in Plan 01 (ANIM-06)
- Build passes, tsc clean, zero new errors

## Task Commits

1. **Task 1: Add m.div entrance animations to AssistantMessage and UserMessage** - `e1774c6` (feat)
2. **Task 2: Implement historical animation gate in MessageList and wire feedback-scale-btn** - `84c1252` (feat)

**Plan metadata:** _(docs commit below)_

## Files Created/Modified

- `frontend/src/components/ChatPane/AssistantMessage.tsx` - Added motion/react-m import, isNew prop, Wrapper/motionProps pattern for conditional 200ms entrance
- `frontend/src/components/ChatPane/UserMessage.tsx` - Added motion/react-m import, isNew prop, Wrapper/motionProps pattern for conditional 150ms entrance
- `frontend/src/components/ChatPane/MessageList.tsx` - Added loadedCountRef, useEffect on activeThreadId to snapshot historical count, isNew computed per message and passed to both message components
- `frontend/src/components/ChatPane/FeedbackButtons.tsx` - Both thumb buttons wrapped in span.feedback-scale-btn

## Decisions Made

- Wrapper pattern (`const Wrapper = condition ? m.div : 'div'`) chosen over duplicating JSX in ternary — single return path, same children, cleaner diff
- `loadedCountRef` updated in `useEffect([activeThreadId])` rather than `useEffect([messages])` — fires once per thread switch after SET_MESSAGES, not on every message append
- `feedback-scale-btn` applied via wrapper span inside PopoverTrigger with `disableButtonEnhancement` — span correctly receives the ref for popover anchor positioning while the CSS :active transform fires on press

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 ANIM requirements complete (ANIM-01 through ANIM-06)
- Phase 25 is the final phase in v1.3; project is ready for human testing
- Blocker remains: Atlas.User App Role must be created in Entra admin center for Phase 21 access control to function end-to-end

---
*Phase: 25-motion-animations*
*Completed: 2026-04-02*
