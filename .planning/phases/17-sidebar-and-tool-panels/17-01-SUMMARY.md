---
phase: 17-sidebar-and-tool-panels
plan: 01
subsystem: api
tags: [sse, tool-events, timestamps, python, typescript]

# Dependency graph
requires:
  - phase: 14-functional-port
    provides: SSE pipeline, useStreamingMessage hook, ToolPanelData type, run_tool_loop
  - phase: 16-chat-experience-redesign
    provides: final message bubble and tool panel rendering baseline
provides:
  - start_time/end_time epoch floats in all tool SSE events
  - ToolPanelData.startTime/endTime optional fields (camelCase)
  - SSEEvent tool union carries start_time/end_time (snake_case)
  - useStreamingMessage maps snake_case SSE fields to camelCase ToolPanelData
affects:
  - 17-02 (sidebar recency grouping — no dependency)
  - 17-03 (elapsed time display on tool panels — depends directly on these fields)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "snake_case SSE JSON → camelCase TypeScript DTO mapping at SSE parse boundary"
    - "time.time() wrap-around call_mcp_tool for start/end timestamps"

key-files:
  created: []
  modified:
    - chat_app/openai_client.py
    - chat_app/chat.py
    - frontend/src/types/index.ts
    - frontend/src/hooks/useStreamingMessage.ts

key-decisions:
  - "Use .get() in chat.py SSE yield for start_time/end_time — backward compat with any tool_events dict that predates timestamps"
  - "startTime/endTime optional on ToolPanelData — historical messages loaded via parseHistoricalMessages correctly omit them"
  - "Timestamps captured as epoch float seconds (time.time()) not milliseconds — consistent with Python convention"

patterns-established:
  - "SSE timestamp pattern: capture start_ts before try block, emit end_time=time.time() in both success and error branches"

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 17 Plan 01: Tool SSE Timestamps Summary

**Backend captures epoch float start/end times around every call_mcp_tool invocation and emits them in SSE tool events; frontend types and SSE parser thread them through to ToolPanelData.startTime/endTime**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T00:16:13Z
- **Completed:** 2026-03-30T00:17:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Backend run_tool_loop captures wall-clock start/end epoch floats around both call_mcp_tool call sites (modern tool_calls path and legacy function_call path)
- chat.py SSE yield passes start_time/end_time through with .get() for backward compatibility
- ToolPanelData interface gains optional startTime/endTime fields; SSEEvent tool union gains optional start_time/end_time
- useStreamingMessage maps snake_case SSE JSON fields to camelCase ToolPanelData at the parse boundary

## Task Commits

Each task was committed atomically:

1. **Task 1: Add time.time() timestamps to run_tool_loop and SSE passthrough** - `e4f832b` (feat)
2. **Task 2: Update frontend types and SSE parser for timestamp fields** - `7b14051` (feat)

## Files Created/Modified

- `chat_app/openai_client.py` - import time added; both call_mcp_tool sites wrapped with start_ts=time.time(), start_time/end_time added to all 4 tool_events.append() dicts
- `chat_app/chat.py` - SSE yield block adds start_time/end_time passthrough via .get()
- `frontend/src/types/index.ts` - ToolPanelData gains startTime?/endTime?; SSEEvent tool member gains start_time?/end_time?
- `frontend/src/hooks/useStreamingMessage.ts` - onTool call maps event.start_time→startTime, event.end_time→endTime

## Decisions Made

- `.get()` used in chat.py SSE yield so historical tool_event dicts that lack timestamps do not KeyError
- Timestamps are epoch float seconds (`time.time()`) not milliseconds — consistent with Python convention; frontend stores as-is for 17-03 to format
- Fields are optional on both the SSE type and ToolPanelData so parseHistoricalMessages (which reconstructs tools from RawMessage) remains untouched

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 17-01 data foundation complete: backend SSE tool events now carry start_time/end_time
- 17-03 (elapsed time display) can read ToolPanelData.startTime and .endTime directly
- 17-02 (sidebar recency grouping) has no dependency on this plan

---
*Phase: 17-sidebar-and-tool-panels*
*Completed: 2026-03-30*
