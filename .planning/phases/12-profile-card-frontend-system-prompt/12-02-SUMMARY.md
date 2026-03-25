---
phase: 12-profile-card-frontend-system-prompt
plan: 02
subsystem: ai
tags: [openai, system-prompt, tool-routing, colleague-lookup, atlas]

# Dependency graph
requires:
  - phase: 11-mcp-tools-photo-proxy
    provides: search_colleagues and get_colleague_profile MCP tools
  - phase: 12-profile-card-frontend-system-prompt/01
    provides: profile card DOM rendering in app.js and CSS
provides:
  - SYSTEM_PROMPT Colleague Lookup section with rules 7-10
  - Rule 1 scope expansion to include colleague lookups
  - Auto-chain guidance: single search result triggers get_colleague_profile immediately
  - Multi-result guidance: list and ask user before calling get_colleague_profile
  - Text duplication suppression: rule 10 prevents Atlas restating card fields
affects:
  - Any future plan modifying SYSTEM_PROMPT or adding new colleague tools

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "System prompt section per tool domain: ## Colleague Lookup section groups search_colleagues and get_colleague_profile rules"
    - "Tool chaining rule in prompt: single-result auto-chain prevents unnecessary user friction"
    - "UI deduplication rule in prompt: instruct model not to restate fields rendered by DOM"

key-files:
  created: []
  modified:
    - chat_app/openai_client.py

key-decisions:
  - "Rules numbered 7-10 as continuation of existing 1-6 for consistent reference in conversation"
  - "Rule 10 explicitly names the UI behavior (profile card auto-rendered) to justify the brevity instruction"
  - "Colleague Lookup section placed after rules 1-6 using ## heading to separate domain concerns"

patterns-established:
  - "Prompt section pattern: ## heading + tool descriptions + numbered rules for each tool domain"
  - "Deduplication contract: system prompt instructs model to defer to UI for structured data display"

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 12 Plan 02: System Prompt Colleague Lookup Rules Summary

**Atlas SYSTEM_PROMPT updated with Colleague Lookup section (rules 7-10): search/profile tool routing, single-result auto-chain, multi-result disambiguation, and UI deduplication contract**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-25T11:22:58Z
- **Completed:** 2026-03-25T11:24:25Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Updated SYSTEM_PROMPT rule 1 to expand scope to colleague lookups
- Added `## Colleague Lookup` section describing `search_colleagues` and `get_colleague_profile` tool usage
- Rule 7: single search result triggers immediate `get_colleague_profile` auto-chain without user confirmation
- Rule 8: multiple results presented as numbered list, user picks before `get_colleague_profile` is called
- Rule 9: prohibits speculative `get_colleague_profile` calls without a specific email/ID
- Rule 10: suppresses text duplication of card fields — Atlas responds with one brief sentence after profile card renders

## Task Commits

1. **Task 1: Update SYSTEM_PROMPT with Colleague Lookup section** - `bc8eee3` (feat — committed by plan 12-01 agent which included this file)

## Files Created/Modified

- `chat_app/openai_client.py` - SYSTEM_PROMPT expanded: rule 1 scope, ## Colleague Lookup section, rules 7-10

## Decisions Made

- Rules numbered 7-10 continuing from 1-6 for consistent prompt reference and predictable numbering
- Rule 10 explicitly mentions "the UI automatically renders a profile card" to give the model full context for why brevity is appropriate — without this, the model might duplicate card fields thinking it's being helpful
- Colleague Lookup placed as a named `##` section rather than inline with Exchange rules to keep domain concerns separated

## Deviations from Plan

None — the SYSTEM_PROMPT changes were already committed in plan 12-01 commit `bc8eee3` (the previous agent included `openai_client.py` in its app.js commit). The content matched the plan specification exactly. No additional work was required.

## Issues Encountered

The previous plan 12-01 agent included `chat_app/openai_client.py` in its commit `bc8eee3` (alongside `app.js`). This plan's task edit produced no diff because the content was already in place. The task is complete; the commit hash for this work is `bc8eee3`.

## Next Phase Readiness

- Phase 12 complete: profile card DOM (plan 01) and system prompt routing (plan 02) both done
- Atlas now has full colleague lookup flow: search → auto-chain on 1 result, list on multiple → profile card renders without text duplication
- No blockers for production use of colleague lookup feature

---
*Phase: 12-profile-card-frontend-system-prompt*
*Completed: 2026-03-25*
