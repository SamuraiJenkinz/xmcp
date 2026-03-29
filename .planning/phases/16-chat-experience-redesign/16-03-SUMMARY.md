---
phase: 16-chat-experience-redesign
plan: 03
subsystem: ui
tags: [react, css, hover-overlay, clipboard, intl, relative-time, typescript]

requires:
  - phase: 16-01
    provides: message bubble geometry (.message, .user-message, .assistant-message) and position:relative base
  - phase: 16-02
    provides: glassmorphism input bar, stop button, welcome state — all part of chat experience pass

provides:
  - Hover-revealed copy button on every message (opacity transition, top-right overlay)
  - Hover-revealed timestamp at bottom edge of every message
  - Intl.RelativeTimeFormat for <24h timestamps; toLocaleString absolute format for older
  - Icon-only CopyButton (clipboard emoji / checkmark feedback, aria-label)
  - formatTimestamp shared utility in frontend/src/utils/
  - CSS classes: .message-hover-actions, .message-timestamp-overlay

affects:
  - 17-sidebar-improvements (uses .thread-actions pattern — same 150ms opacity transition)
  - Any future message component additions (must include .message-hover-actions pattern)

tech-stack:
  added: []
  patterns:
    - "Hover overlay pattern: opacity 0 → 1 on .parent:hover .child via CSS transition, matching thread-actions"
    - "Lazy getText: CopyButton getText prop is a callback, evaluated at click time not render time"
    - "contentRef pattern: useRef + useEffect to track latest prop for stale-closure-safe clipboard copy"
    - "Conditional hover actions: gated on !isStreaming — streaming messages show no overlays until finalized"
    - "Timestamp display-layer only: no changes to RawMessage or StreamingMessageState types"

key-files:
  created:
    - frontend/src/utils/formatTimestamp.ts
  modified:
    - frontend/src/index.css
    - frontend/src/components/shared/CopyButton.tsx
    - frontend/src/components/ChatPane/UserMessage.tsx
    - frontend/src/components/ChatPane/AssistantMessage.tsx

key-decisions:
  - "formatTimestamp extracted to shared utils/ rather than inlined in each component — single source of truth"
  - "Clipboard emoji (U+1F4CB) chosen over Unicode copy symbol U+2398 for rendering reliability in Segoe UI Variable"
  - "Checkmark U+2713 for copied state — compact and universally recognisable"
  - "CopyButton hidden during streaming (gated on !isStreaming) — streaming content is in flux, copy would capture partial text"
  - "Timestamp overlay not shown during streaming — timestamp is only meaningful on finalised messages"

patterns-established:
  - "Message hover overlay: absolute-positioned div.message-hover-actions at top:-4px right:4px, opacity 0→1 in 150ms"
  - "Timestamp overlay: absolute-positioned div.message-timestamp-overlay at bottom:-20px, left-aligned on assistant messages"
  - "Icon-only button: .copy-btn uses font-size caption2 (10px) with compact padding 4px 6px"

duration: 12min
completed: 2026-03-29
---

# Phase 16 Plan 03: Message Hover Actions Summary

**Hover-revealed copy button and relative timestamp overlay on all message bubbles using CSS opacity transitions and Intl.RelativeTimeFormat**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-29T23:13:57Z
- **Completed:** 2026-03-29T23:26:00Z
- **Tasks:** 2
- **Files modified:** 5 (4 modified, 1 created)

## Accomplishments

- Both UserMessage and AssistantMessage now reveal a compact copy button (top-right) and timestamp (bottom edge) on hover
- CopyButton refactored from text "Copy"/"Copied!" to icon-only with clipboard emoji and checkmark feedback
- `formatTimestamp` utility provides relative format ("2 minutes ago") for recent messages and absolute format ("Mar 29, 3:42 PM") for older ones
- Hover transitions are 150ms opacity — matching the existing `.thread-actions` pattern established in Phase 15

## Task Commits

1. **Task 1: Hover action overlay CSS and icon-only CopyButton** - `74f8307` (feat)
2. **Task 2: Hover overlays and timestamp rendering in UserMessage and AssistantMessage** - `4cce16b` (feat)

## Files Created/Modified

- `frontend/src/utils/formatTimestamp.ts` - Shared timestamp formatter (Intl.RelativeTimeFormat + toLocaleString)
- `frontend/src/index.css` - Added .message-hover-actions, .message-timestamp-overlay; updated .copy-btn to icon-only
- `frontend/src/components/shared/CopyButton.tsx` - Icon-only clipboard/checkmark with aria-label
- `frontend/src/components/ChatPane/UserMessage.tsx` - Added hover overlay with CopyButton + timestamp
- `frontend/src/components/ChatPane/AssistantMessage.tsx` - Moved CopyButton to hover overlay, added timestamp, gated on !isStreaming

## Decisions Made

- `formatTimestamp` extracted to `frontend/src/utils/formatTimestamp.ts` rather than inline — avoids duplication across components and makes it testable
- Clipboard emoji (U+1F4CB `📋`) chosen over `\u2398` (HELM SYMBOL) because it renders reliably in Segoe UI Variable; `\u2398` has inconsistent rendering across Windows/macOS fonts
- Hover actions hidden during streaming (`!isStreaming` gate) — copying partial streamed text would capture incomplete content; timestamp is only meaningful on finalised messages
- `right: auto; left: 4px` override for `.assistant-message .message-timestamp-overlay` — left-aligned timestamps are more natural for left-aligned message bubbles

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 16 (Chat Experience Redesign) is now complete — all 3 plans executed
- Phase 17 (Sidebar Improvements) can begin; thread recency grouping and created_at column prerequisite should be verified first (see STATE.md blocker)
- Hover overlay pattern is reusable for any future interactive message actions (reactions, edit, etc.)

---
*Phase: 16-chat-experience-redesign*
*Completed: 2026-03-29*
