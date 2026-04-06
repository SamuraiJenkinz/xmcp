---
phase: 28-tool-correlation-analytics-completion
plan: 02
subsystem: ai-prompting
tags: [system-prompt, feedback-analytics, get_feedback_by_tool, routing-rules, presentation-rules]

# Dependency graph
requires:
  - phase: 28-01
    provides: get_feedback_by_tool MCP tool handler (fan-out attribution, two-mode breakdown/drill-down)
  - phase: 27-01
    provides: feedback SQLite database and base feedback query tools
provides:
  - System prompt routing rules for get_feedback_by_tool (rules 23-24)
  - Analytics presentation rules — executive summary tone, low-confidence flagging, no raw dumps (rule 25)
  - Empty tools list fallback response (rule 26)
  - get_feedback_by_tool documented in Feedback Analytics tool list with fan-out attribution note
affects:
  - Any future phase adding new feedback or analytics tools to the system prompt

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Numbered imperative rules in SYSTEM_PROMPT sections for AI routing and presentation"
    - "Tool list + routing rules + presentation rules + empty-state fallback as 4-layer prompt structure"

key-files:
  created: []
  modified:
    - chat_app/openai_client.py

key-decisions:
  - "Rules 23-26 follow existing numbered imperative style of rules 1-22 for consistency"
  - "Rule 25 uses lettered sub-points (a-d) to group presentation concerns without adding more rule numbers"
  - "Fan-out attribution note placed in tool description so AI can explain multi-tool vote counting to users"

patterns-established:
  - "Feedback analytics section pattern: tool list → routing rules → presentation rules → empty-state rule"

# Metrics
duration: 1min
completed: 2026-04-06
---

# Phase 28 Plan 02: Tool Correlation Analytics Completion Summary

**System prompt extended with get_feedback_by_tool routing (rules 23-24), executive-summary presentation rules (rule 25), and empty-state fallback (rule 26) — completing FBAN-11**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-04-06T23:53:05Z
- **Completed:** 2026-04-06T23:55:35Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `get_feedback_by_tool` to the Feedback Analytics tool list with usage examples and fan-out attribution note
- Added rule 23: route per-tool satisfaction breakdown queries (no tool_name) → ranked worst-to-best list
- Added rule 24: route named-tool drill-down queries (with tool_name) → low-rated examples for that tool
- Added rule 25: presentation guidance — lead with actionable finding, flag low_confidence, suggest action, no raw JSON/table dumps
- Added rule 26: empty tools list fallback response text

## Task Commits

1. **Task 1: Add get_feedback_by_tool entry and rules 23-26 to SYSTEM_PROMPT** - `a194220` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `chat_app/openai_client.py` - SYSTEM_PROMPT Feedback Analytics section extended with tool entry and rules 23-26

## Decisions Made

- Rules 23-26 follow the existing numbered imperative style of rules 1-22 for consistency with the rest of the prompt
- Rule 25 uses lettered sub-points (a-d) to group the four presentation concerns without inflating the rule count
- Fan-out attribution note placed inline in the tool description so the AI can explain multi-tool vote counting if a user asks
- No separate rule for fan-out explanation — the tool description itself is sufficient for the AI to reference

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 28 complete (both plans 28-01 and 28-02 done)
- FBAN-11 fully resolved: `get_feedback_by_tool` handler exists (28-01), system prompt guides its use (28-02)
- v1.4 Feedback Analytics feature set is complete
- No blockers for next development cycle

---
*Phase: 28-tool-correlation-analytics-completion*
*Completed: 2026-04-06*
