---
phase: 28-tool-correlation-analytics-completion
plan: 01
subsystem: analytics
tags: [sqlite, feedback, tool-correlation, mcp, python, asyncio]

# Dependency graph
requires:
  - phase: 27-feedback-analytics-foundation
    provides: feedback_analytics.py with _get_feedback_summary_handler and _get_low_rated_responses_handler, SQLite read pattern, asyncio.to_thread I/O pattern
provides:
  - _find_tool_names: correlates content-bearing assistant messages to preceding tool_calls or legacy function_call entries
  - TOOL_FEEDBACK_SQL: joins feedback, messages, and threads tables for correlation queries
  - _get_feedback_by_tool_handler: breakdown mode (per-tool satisfaction, sorted worst-first, low-confidence flagged) and drill-down mode (thumbs-down examples for a specific tool)
  - get_feedback_by_tool Tool definition with inputSchema registered as tool 21
affects: [future analytics phases, any phase adding new Exchange tools]

# Tech tracking
tech-stack:
  added: [json (stdlib, added to existing imports)]
  patterns:
    - Fan-out vote attribution: single feedback row votes assigned to all tools in multi-tool assistant turns
    - messages_json cache: dict keyed by thread_id prevents redundant JSON parsing within a single query
    - Low-confidence flagging: tools with total_votes < 5 are flagged and sorted last
    - Two-mode handler: same endpoint serves breakdown (no filter) and drill-down (with tool_name)

key-files:
  created: []
  modified:
    - exchange_mcp/feedback_analytics.py
    - exchange_mcp/tools.py
    - exchange_mcp/server.py
    - tests/test_server.py

key-decisions:
  - "Fan-out attribution: multi-tool messages assign the vote to each tool independently — preserves per-tool accuracy"
  - "Low-confidence threshold at < 5 total votes — flagged and sorted last rather than excluded"
  - "messages_json cache keyed by thread_id — single dict for the entire query avoids O(n) reparsing"
  - "Two-mode design in one handler (breakdown vs drill-down) — reduces tool count, simpler API surface"

patterns-established:
  - "Correlation pattern: walk backward from content-bearing assistant message to find nearest preceding tool call, stop at user boundary"
  - "Sort key tuple (low_confidence_int, satisfaction_pct) puts confident bad tools before uncertain tools"

# Metrics
duration: 3min
completed: 2026-04-06
---

# Phase 28 Plan 01: Tool Correlation Analytics Summary

**Per-tool satisfaction analytics with fan-out vote attribution: `_find_tool_names` walks backward through message history to correlate feedback with Exchange tool calls (tool_calls and legacy function_call formats), powering a `get_feedback_by_tool` breakdown registered as tool 21**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-06T23:49:44Z
- **Completed:** 2026-04-06T23:52:19Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented `_find_tool_names` with correct backward-walk correlation for both modern `tool_calls` and legacy `function_call` message formats, stopping at user-role boundaries
- Implemented `_get_feedback_by_tool_handler` supporting breakdown mode (per-tool vote counts, satisfaction_pct, low_confidence flag, sorted worst-first with low-confidence last) and drill-down mode (thumbs-down examples for a named tool)
- Registered `get_feedback_by_tool` as tool 21 in TOOL_DEFINITIONS and TOOL_DISPATCH; all 13 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement _find_tool_names and _get_feedback_by_tool_handler** - `8ee079f` (feat)
2. **Task 2: Register get_feedback_by_tool in tools.py, update server.py and test_server.py** - `140498a` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `exchange_mcp/feedback_analytics.py` - Added `json` import, `TOOL_FEEDBACK_SQL`, `_find_tool_names`, `_get_feedback_by_tool_handler`
- `exchange_mcp/tools.py` - Added `_get_feedback_by_tool_handler` import, Tool definition, TOOL_DISPATCH entry; updated docstring to 21 tools
- `exchange_mcp/server.py` - Updated docstring from "20 tools" to "21 tools (3 feedback analytics)"
- `tests/test_server.py` - Renamed test to `test_list_tools_returns_all_21`, updated assertion from 20 to 21

## Decisions Made

- Fan-out attribution: multi-tool messages assign the vote to each tool independently. Rationale: preserves per-tool accuracy since each tool in a turn contributed to the response.
- Low-confidence threshold at < 5 total votes: flagged and sorted last rather than excluded. Rationale: still surfaced but clearly marked so users don't draw conclusions from thin data.
- messages_json cache keyed by thread_id: single dict for the entire handler invocation. Rationale: feedback rows for the same thread share the same messages blob — caching avoids O(n) redundant JSON parsing.
- Two-mode design (breakdown vs drill-down) in one handler. Rationale: reduces tool count and keeps the API surface minimal — the `tool_name` parameter acts as the mode switch.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `get_feedback_by_tool` is fully implemented and registered as tool 21
- Ready for plan 28-02 (remaining phase 28 plans)
- No blockers

---
*Phase: 28-tool-correlation-analytics-completion*
*Completed: 2026-04-06*
