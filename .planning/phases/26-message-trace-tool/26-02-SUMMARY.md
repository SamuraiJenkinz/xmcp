---
phase: 26-message-trace-tool
plan: 02
subsystem: ai-routing
tags: [openai, system-prompt, disambiguation, exchange, mcp, tool-routing]

# Dependency graph
requires:
  - phase: 26-01
    provides: get_message_trace tool registered in TOOL_DEFINITIONS and TOOL_DISPATCH
provides:
  - System prompt disambiguation section guiding AI to choose get_message_trace vs check_mail_flow
  - Intent-based routing rules (15-18) with negative guidance and clarification prompt
  - Accurate tool count (18) in server.py docstring
affects: [future-phases-adding-tools, 27-message-feedback, 28-analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Intent-based disambiguation in system prompt: positive examples + negative guidance rule"
    - "Sequential rule numbering across SYSTEM_PROMPT sections for LLM clarity"

key-files:
  created: []
  modified:
    - chat_app/openai_client.py
    - exchange_mcp/server.py

key-decisions:
  - "Placed disambiguation section after Colleague Lookup (last section) so rule numbering is sequential and unambiguous"
  - "Used explicit negative rule (Do NOT use check_mail_flow) rather than relying on positive rules alone"
  - "Added clarification prompt text for ambiguous queries rather than forcing a default"

patterns-established:
  - "Tool disambiguation: each ambiguous pair gets ## heading, usage examples, positive rule, negative rule, clarification prompt"

# Metrics
duration: 8min
completed: 2026-04-06
---

# Phase 26 Plan 02: Message Trace Tool Summary

**System prompt disambiguation added for get_message_trace vs check_mail_flow with intent rules, negative guidance, and ambiguity clarification; server.py docstring updated to 18 tools**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-06T17:27:00Z
- **Completed:** 2026-04-06T17:35:12Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added "## Message Trace vs Mail Flow" disambiguation section to SYSTEM_PROMPT with usage examples for both tools
- Added four sequential rules (15-18): delivery routing, topology routing, explicit negative guidance, ambiguity clarification prompt
- Updated server.py docstring from "17 tools (14 Exchange...)" to "18 tools (15 Exchange...)"
- Confirmed TOOL_DEFINITIONS and TOOL_DISPATCH both have 18 entries including get_message_trace

## Task Commits

Each task was committed atomically:

1. **Task 1: Add system prompt disambiguation section** - `e8f88aa` (feat)
2. **Task 2: Update server.py tool count and verify end-to-end** - `22b93e3` (chore)

**Plan metadata:** committed with this SUMMARY

## Files Created/Modified
- `chat_app/openai_client.py` - Added ## Message Trace vs Mail Flow section with rules 15-18 to SYSTEM_PROMPT
- `exchange_mcp/server.py` - Updated docstring tool count from 17 to 18, breakdown from 14 Exchange to 15 Exchange

## Decisions Made
- Appended disambiguation section after rule 14 (end of Colleague Lookup) so rule numbering stays sequential (15-18)
- Used explicit negative rule ("Do NOT use check_mail_flow when...") as the most reliable way to prevent misrouting given surface-level similarity of the two tools
- Adjusted docstring wording from "18 registered\ntools" to "18 tools" on a single line to satisfy grep-based verification

## Deviations from Plan

None - plan executed exactly as written.

The verification step `grep -c "18 tools"` required the phrase to appear on a single line. The initial edit produced "18 registered\n tools" spanning two lines (grep returns 0). Fixed immediately by rewording to "18 tools\n(15 Exchange...)" — not a deviation, just precision in satisfying the verification criterion.

## Issues Encountered
- Minor: TOOL_DEFINITIONS contains MCP `Tool` objects (not plain dicts), so `t['function']['name']` raises TypeError. Used `t.name` attribute instead. This did not affect production code, only the verification script.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AI disambiguation rules are live; get_message_trace queries will be routed correctly away from check_mail_flow
- Tool count is accurate across all references (server.py docstring, TOOL_DEFINITIONS, TOOL_DISPATCH)
- Ready for Phase 27: per-message feedback

---
*Phase: 26-message-trace-tool*
*Completed: 2026-04-06*
