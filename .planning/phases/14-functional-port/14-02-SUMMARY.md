---
phase: 14-functional-port
plan: 02
subsystem: ui
tags: [react, typescript, sse, streaming, hooks, fetch, readablestream, abortcontroller, raf-batching, tool-panels]

# Dependency graph
requires:
  - phase: 14-01
    provides: SSEEvent, ToolPanelData, DisplayMessage, RawMessage types from ../types

provides:
  - useStreamingMessage hook — SSE fetch+ReadableStream with rAF-batched text, AbortController cancel
  - parseHistoricalMessages utility — DEBT-01 fix parsing tool_calls from persisted messages_json

affects:
  - 14-03 (ChatWindow component will consume useStreamingMessage and parseHistoricalMessages)
  - 14-04 (MessageList rendering depends on DisplayMessage shape from parseHistoricalMessages)
  - 14-05 (Integration/smoke tests will exercise the streaming hook end-to-end)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Callbacks-in-ref pattern: options stored in optionsRef to prevent stale closure captures"
    - "rAF text batching: text deltas accumulated in pendingTextRef, flushed per animation frame"
    - "AbortController in useRef (not useState) — avoids re-render on assignment, stable reference"
    - "SSE buffer split on \\n\\n for event boundaries, TextDecoder { stream: true } for multi-byte"
    - "pendingToolPanels accumulator for multi-turn tool loops in historical message parsing"

key-files:
  created:
    - frontend/src/hooks/useStreamingMessage.ts
    - frontend/src/utils/parseHistoricalMessages.ts
  modified: []

key-decisions:
  - "AbortController in useRef confirmed as locked decision — not useState"
  - "options callbacks stored in optionsRef to avoid stale closures as context state updates"
  - "rAF batching flushes on tool events and done/error/cancel to ensure no text is dropped"
  - "parseHistoricalMessages look-ahead stops at next assistant message boundary to handle multi-turn loops correctly"

patterns-established:
  - "Hook signature: accept callbacks not contexts (keeps hook independently testable)"
  - "SSE pump loop: async/await IIFE with recursive pump() call, not EventSource"
  - "Historical parser: pendingToolPanels accumulates across assistant+tool pairs, resets on content flush"

# Metrics
duration: 12min
completed: 2026-03-28
---

# Phase 14 Plan 02: Streaming Hook and Historical Parser Summary

**SSE fetch+ReadableStream hook with rAF-batched text delivery and AbortController cancel, plus DEBT-01 tool_calls historical parser**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-28T00:00:00Z
- **Completed:** 2026-03-28T00:12:00Z
- **Tasks:** 2
- **Files modified:** 2 (both new)

## Accomplishments

- Ported `readSSEStream` from app.js into `useStreamingMessage` — a typed, testable React hook that delivers streaming tokens to callbacks rather than directly manipulating DOM
- Implemented rAF text batching: deltas accumulate in `pendingTextRef` and flush once per animation frame, preventing excessive re-renders during rapid token delivery
- Created `parseHistoricalMessages` (DEBT-01 fix): correctly pairs `tool_calls` with their `role:"tool"` results via `tool_call_id` and re-attaches them as `toolPanels` on the content-bearing assistant message
- Both files compile with zero TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create useStreamingMessage hook with SSE parsing and rAF batching** - `88163af` (feat)
2. **Task 2: Create parseHistoricalMessages utility (DEBT-01 frontend fix)** - `04e9761` (feat)

**Plan metadata:** `(pending)` (docs: complete streaming hook and historical parser plan)

## Files Created/Modified

- `frontend/src/hooks/useStreamingMessage.ts` — SSE hook with fetch+ReadableStream, AbortController cancel, rAF text batching, all event types handled (text/tool/thread_named/done/error)
- `frontend/src/utils/parseHistoricalMessages.ts` — Converts RawMessage[] (OpenAI format) to DisplayMessage[] with tool panels re-attached for historical rendering

## Decisions Made

- Options callbacks stored in `optionsRef` — the `onText`, `onTool`, etc. callbacks change identity each render as context state updates; reading them via ref prevents stale closures without requiring them in `useCallback` dependency arrays
- `flushPendingText` called before every non-text event (tool, done, error, cancel) — ensures no text delta is ever silently dropped when an event boundary arrives
- Historical parser look-ahead for tool results stops at the next `assistant` message — prevents cross-turn contamination when a tool result from one loop iteration matches a call from a different iteration

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `useStreamingMessage` and `parseHistoricalMessages` are ready for consumption by ChatWindow (14-03) and MessageList (14-04)
- Both exports are typed and compile cleanly against the types established in 14-01
- No blockers for continuing Phase 14

---
*Phase: 14-functional-port*
*Completed: 2026-03-28*
