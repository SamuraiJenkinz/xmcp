---
phase: 02-mcp-server-scaffold
plan: 03
subsystem: testing
tags: [mcp, tool-descriptions, exchange, llm-tool-selection, pytest, quality-gates]

# Dependency graph
requires:
  - phase: 02-02
    provides: TOOL_DEFINITIONS list with 15 Exchange + ping tool objects in tools.py
provides:
  - Refined tool descriptions optimized for LLM tool-selection accuracy
  - 10 description quality regression tests in tests/test_tool_descriptions.py
  - All critical disambiguation pairs explicitly separated with does-NOT clauses
affects:
  - Phase 3-6 tool implementations (same TOOL_DEFINITIONS structure; descriptions guide LLM selection)
  - Future description edits (tests enforce quality constraints as regression guard)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tool description structure: what it returns + Use when triggers + quoted examples + Does NOT clause"
    - "Disambiguation via explicit cross-reference: each paired tool names the other in its does-NOT clause"
    - "Description quality enforced via regression test file (test_tool_descriptions.py)"

key-files:
  created:
    - tests/test_tool_descriptions.py
  modified:
    - exchange_mcp/tools.py

key-decisions:
  - "Does NOT clause cross-references sibling tool by name (e.g., 'use search_mailboxes for that') — makes disambiguation machine-readable"
  - "Quoted single-quote examples (e.g., 'Is DKIM enabled?') as convention for LLM-targeted trigger phrases"
  - "test_no_exchange_jargon catches 'PowerShell' in descriptions — descriptions are user-facing, not admin-facing"

patterns-established:
  - "Description structure: sentence 1 (returns what), sentence 2 (Use when + triggers), sentence 3+ (quoted examples), optional final sentence (Does NOT)"
  - "Disambiguation tests: test assertions verify specific phrases exist and cross-references are present"

# Metrics
duration: 4min
completed: 2026-03-19
---

# Phase 2 Plan 03: Tool Description Quality Summary

**15 Exchange tool descriptions rewritten with Use-when triggers, quoted example queries, and explicit Does-NOT disambiguation clauses; 10 regression tests enforce quality constraints**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-19T23:00:52Z
- **Completed:** 2026-03-19T23:05:23Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Rewrote all 15 Exchange tool descriptions with four-part structure: what the tool returns, "Use when" triggers, quoted example queries, and "Does NOT" disambiguation
- Explicitly disambiguated all 5 critical pairs: get_mailbox_stats/search_mailboxes, get_shared_mailbox_owners/search_mailboxes, get_dkim_config/get_dmarc_status, list_dag_members/get_dag_health, get_hybrid_config/get_connector_status
- Created tests/test_tool_descriptions.py with 10 tests as a regression guard on description quality
- All 56 non-integration tests pass (3 Exchange Online integration tests require live credentials and are pre-existing failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Refine tool descriptions for disambiguation and LLM accuracy** - `b012dbf` (feat)
2. **Task 2: Write description quality tests** - `198dba5` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `exchange_mcp/tools.py` - All 15 Exchange tool descriptions rewritten (300-477 chars each, all under 800 char limit)
- `tests/test_tool_descriptions.py` - 10 quality regression tests for description properties

## Decisions Made

- Does NOT clause cross-references sibling tool by name (e.g., "use search_mailboxes for that") — makes disambiguation machine-readable by both LLMs and tests
- Single-quoted example queries (e.g., `'Is DKIM enabled for contoso.com?'`) as the convention for natural-language trigger phrases — tests check for this pattern
- "PowerShell" is forbidden in tool descriptions because descriptions are user-facing; technical implementation details belong in code comments, not LLM-visible descriptions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed 'PowerShell' jargon from get_dmarc_status description**

- **Found during:** Task 2 (writing test_no_exchange_jargon)
- **Issue:** get_dmarc_status description contained "(no Exchange PowerShell required)" — the word "PowerShell" is in the forbidden jargon list the test enforces
- **Fix:** Replaced the parenthetical with "by querying DNS directly" which conveys the same information without the jargon
- **Files modified:** exchange_mcp/tools.py
- **Verification:** test_no_exchange_jargon passes; description still clearly distinguishes DNS-based DMARC check from Exchange-based DKIM check
- **Committed in:** 198dba5 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug caught by test during same execution)
**Impact on plan:** Fix required for test to pass; improved description quality.

## Issues Encountered

None — the jargon violation was caught and fixed within the same execution.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 complete: MCP server scaffold has all 16 tools registered with unambiguous descriptions and 23 total tests
- Phase 3 ready: tool stubs in TOOL_DISPATCH are ready to be replaced with real Exchange implementations
- No blockers

---
*Phase: 02-mcp-server-scaffold*
*Completed: 2026-03-19*
