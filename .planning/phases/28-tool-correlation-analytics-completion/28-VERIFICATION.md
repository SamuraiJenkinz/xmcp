---
phase: 28-tool-correlation-analytics-completion
verified: 2026-04-06T23:58:28Z
status: passed
score: 3/3 must-haves verified
---

# Phase 28: Tool Correlation Analytics Completion — Verification Report

**Phase Goal:** Users can identify which Exchange tools produce the worst user experience and the AI presents all analytics results conversationally
**Verified:** 2026-04-06T23:58:28Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User asks "which Exchange tools get the most negative feedback?" and receives a per-tool satisfaction breakdown with vote counts | VERIFIED | `_get_feedback_by_tool_handler` breakdown mode aggregates per-tool up_votes/down_votes/satisfaction_pct; fan-out loop `for tname in tool_names:` attributes one vote to all tools in multi-tool turns; sorted worst-first; registered as tool 21 in TOOL_DISPATCH |
| 2 | User asks for the worst-rated tool queries and receives specific examples of low-rated interactions with tool name and context | VERIFIED | Drill-down mode (with `tool_name`) returns `timestamp`, `comment`, `thread_name` entries for thumbs-down votes attributed to that tool; `limit` param defaults 10 max 50; `_find_tool_names` correctly resolves `tool_calls` and legacy `function_call` formats |
| 3 | The AI presents analytics results in natural conversational language (not raw JSON or table dumps) guided by system prompt rules | VERIFIED | Rules 23-26 in SYSTEM_PROMPT: rule 23 routes per-tool queries to `get_feedback_by_tool`; rule 24 routes drill-down; rule 25 instructs lead-with-finding, flag low-confidence, suggest actions, no raw JSON/table dumps; rule 26 covers empty-list fallback |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `exchange_mcp/feedback_analytics.py` | `_find_tool_names`, `_aggregate_by_tool`, `_get_feedback_by_tool_handler` | VERIFIED | All three present; 534 lines; no stubs; exported; `TOOL_FEEDBACK_SQL` constant also present |
| `exchange_mcp/tools.py` | `get_feedback_by_tool` Tool definition and TOOL_DISPATCH entry | VERIFIED | Appears at line 512 (Tool definition) and line 2285 (TOOL_DISPATCH); import at line 26; 3 occurrences confirmed |
| `exchange_mcp/server.py` | Updated docstring "21 tools" | VERIFIED | Line 13: "enumerates all 21 tools" |
| `tests/test_server.py` | Assertion for 21 tools; test passes | VERIFIED | `test_list_tools_returns_all_21` passes; `assert len(tools) == 21` at line 155; all 13 tests pass |
| `chat_app/openai_client.py` | SYSTEM_PROMPT with rules 23-26 and `get_feedback_by_tool` in tool list | VERIFIED | Lines 101-114; `get_feedback_by_tool` in tool list with fan-out note; rules 23, 24, 25, 26 all present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `exchange_mcp/tools.py` | `exchange_mcp/feedback_analytics.py` | `from exchange_mcp.feedback_analytics import _get_feedback_by_tool_handler` | WIRED | Import at line 26; used in TOOL_DISPATCH at line 2285 |
| `exchange_mcp/tools.py` | `TOOL_DISPATCH` | `"get_feedback_by_tool": _get_feedback_by_tool_handler` | WIRED | Dispatch entry confirmed at line 2285 |
| `exchange_mcp/feedback_analytics.py` | `messages_json` parsing | `_find_tool_names` called per feedback row | WIRED | `messages_cache` by `thread_id`; `_find_tool_names(messages, row["assistant_message_idx"])` called in both modes |
| `chat_app/openai_client.py` | SYSTEM_PROMPT | Rules 23-26 in Feedback Analytics section | WIRED | Lines 111-114; all four rules present; `low_confidence` guidance confirmed; anti-raw-dump rule confirmed |

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| FBAN-05: `get_feedback_by_tool` correlates feedback votes with Exchange tool invoked | SATISFIED | `_find_tool_names` parses `messages_json` to extract `tool_calls`/`function_call` names; handler fans vote to each correlated tool |
| FBAN-06: `get_feedback_by_tool` includes top-N worst-rated tool queries | SATISFIED | Drill-down mode with `tool_name` returns thumbs-down examples; `limit` param (default 10, max 50); breakdown sorted worst satisfaction first |
| FBAN-09: Tool correlation parses `messages_json` to match `assistant_message_idx` with tool names from `tool_calls` | SATISFIED | `_find_tool_names` walks message list to locate content-bearing assistant message by ordinal, then walks backward to find preceding `tool_calls` or `function_call` |
| FBAN-11: System prompt guidance for presenting analytics results conversationally | SATISFIED | Rules 23-26 in SYSTEM_PROMPT; rule 25 explicitly prohibits raw JSON/table dumps; instructs conversational executive-summary presentation |

Note: REQUIREMENTS.md tracking still shows FBAN-05, FBAN-06, FBAN-09, FBAN-11 as unchecked `[ ]`. The implementations are complete and verified — the checklist was not updated post-implementation.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None | — | — | No stubs, TODO comments, placeholder content, or empty handlers found in any modified file |

### Human Verification Required

None. All success criteria are verifiable programmatically:
- Tool registration and dispatch confirmed by passing test suite (13/13 tests)
- `_find_tool_names` logic verified with unit assertions covering tool_calls, function_call, multi-tool fan-out, and no-tool cases
- SYSTEM_PROMPT content verified by import and string assertion
- Low-confidence flagging (`total < 5`) confirmed in source
- Worst-first sorting confirmed via `_sort_key` tuple `(int(low_confidence), satisfaction_pct)`
- `asyncio.to_thread` usage confirmed — non-blocking DB I/O pattern consistent with existing handlers

## Summary

Phase 28 goal is fully achieved. The `get_feedback_by_tool` handler is implemented with:

- **Fan-out attribution**: one vote counts toward all tools called in a multi-tool turn (`for tname in tool_names:`)
- **Low-confidence flagging**: `total_votes < 5` sets `low_confidence=True`; these tools sort last
- **Breakdown mode** (no `tool_name`): returns all tools with satisfaction percentages sorted worst-first
- **Drill-down mode** (with `tool_name`): returns thumbs-down examples for the named tool
- **Legacy format support**: both `tool_calls` and `function_call` message formats handled
- **Corrupt-row safety**: `json.JSONDecodeError` caught and skipped silently
- **Cache efficiency**: `messages_json` parsed once per thread per query

The AI is guided by four new system prompt rules to route per-tool queries correctly, present results conversationally with actionable findings, flag low-confidence data, and handle the empty-results case explicitly.

All 13 `test_server.py` tests pass including `test_list_tools_returns_all_21`.

---

_Verified: 2026-04-06T23:58:28Z_
_Verifier: Claude (gsd-verifier)_
