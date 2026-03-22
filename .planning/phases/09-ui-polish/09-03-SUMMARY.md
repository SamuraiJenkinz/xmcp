---
phase: 09-ui-polish
plan: "03"
subsystem: ui
tags: [javascript, css, sse, abortcontroller, animation, streaming, ux]

# Dependency graph
requires:
  - phase: 09-01
    provides: addToolPanel, finalize, streaming cursor, tool panel rendering
  - phase: 09-02
    provides: copyText utility, copy buttons, finalize method with .finalized class

provides:
  - Bouncing dots loading indicator that appears immediately on message send
  - removeDots() cleanup triggered on first tool/text SSE event
  - Esc key cancels active stream via AbortController.abort()
  - markInterrupted() method leaving [response cancelled] marker in place of cursor
  - .thinking-dots CSS with staggered bounce-dot @keyframes animation
  - .interrupted-marker CSS for grey italic cancelled state

affects:
  - 09-04
  - Any future streaming modifications touching doSend, readSSEStream, createAssistantMessage

# Tech tracking
tech-stack:
  added: []
  patterns:
    - AbortController pattern for cancellable fetch requests
    - Idempotent removeDots() with dotsRemoved flag to prevent double-remove
    - AbortError vs network error discrimination in catch handlers
    - Animated loading indicator lifecycle tied to SSE event arrival

key-files:
  created: []
  modified:
    - chat_app/static/app.js
    - chat_app/static/style.css

key-decisions:
  - "dotsEl inserted with insertBefore(dotsEl, textNode) so dots precede streaming text in DOM order"
  - "removeDots() called idempotently — safe to call multiple times (done, error, tool, text handlers all call it)"
  - "AbortError distinguished in both fetch catch and pump().catch() — marks interrupted not error state"
  - "currentAbortController cleared in done, error, AbortError paths — no stale reference leak"
  - "Document-level Escape handler (not inputEl) — works even when focus is in message area"
  - "pump() checks signal.aborted before reader.read() to handle abort between chunk reads"

patterns-established:
  - "AbortController lifecycle: create in doSend, null on done/error/abort, abort on Escape"
  - "Dots lifecycle: insert in createAssistantMessage, remove on first content SSE event"

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 9 Plan 03: Bouncing Dots and Esc-to-Cancel Summary

**Animated three-dot loading indicator with AbortController-backed Esc cancellation, leaving partial streamed text visible with [response cancelled] marker**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-22T12:30:41Z
- **Completed:** 2026-03-22T12:32:53Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Bouncing dots appear immediately when doSend() creates the assistant message — fills the 2-4s gap before first SSE event
- Dots are removed on the first `tool` or `text` SSE event (and also on `done`, `error`, and abort paths)
- Pressing Escape during streaming calls `currentAbortController.abort()`, triggering AbortError in fetch/pump catch
- Partial streamed text remains in the DOM; `markInterrupted()` replaces the cursor with grey italic `[response cancelled]`
- Ctrl+Enter handler and all pre-existing copy functionality from 09-02 preserved

## Task Commits

Each task was committed atomically:

1. **Task 1: Add bouncing dots indicator and AbortController Esc-to-cancel** - `ce8c3ac` (feat)

**Plan metadata:** committed with task (single-task plan)

## Files Created/Modified

- `chat_app/static/app.js` - currentAbortController variable, dots lifecycle in createAssistantMessage, signal parameter in readSSEStream, AbortController in doSend, Esc keydown handler
- `chat_app/static/style.css` - .thinking-dots with bounce-dot @keyframes, .interrupted-marker

## Decisions Made

- `dotsEl` inserted with `insertBefore(dotsEl, textNode)` — dots precede streaming text in DOM so they display at the top of the assistant bubble before any text arrives
- `removeDots()` is idempotent via `dotsRemoved` flag — safe to call from multiple code paths (tool, text, done, error, abort) without double-remove errors
- AbortError discriminated from general errors in both `fetch.catch()` and `pump().catch()` — AbortError routes to `markInterrupted()`, other errors route to `markError()`
- Document-level Escape listener rather than inputEl — ensures cancellation works regardless of which element has focus
- `pump()` checks `signal.aborted` at the top of each recursive call — catches abort that happens between chunk reads before the next `reader.read()` resolves with AbortError

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 09-04 can proceed — streaming infrastructure complete (dots, cancel, copy, tool panels all in place)
- All four streaming UX requirements (UIUX-06 bouncing dots, UIUX-07 Esc cancel) implemented and committed

---
*Phase: 09-ui-polish*
*Completed: 2026-03-22*
