---
phase: 07-chat-app-core
plan: 03
subsystem: api
tags: [openai, azure-openai, mmc-gateway, chat-completion, system-prompt]

# Dependency graph
requires:
  - phase: 07-01
    provides: Flask app scaffold with Config class (CHATGPT_ENDPOINT, AZURE_OPENAI_API_KEY, OPENAI_MODEL)
provides:
  - openai.OpenAI client wrapper with MMC gateway URL stripping
  - SYSTEM_PROMPT establishing Atlas as Exchange-only assistant with 6 guardrail rules
  - chat_completion() for basic completions (no tools)
  - _message_to_dict() converting SDK objects to plain JSON-serialisable dicts (includes tool_calls)
  - init_openai() / get_client() client lifecycle management
affects:
  - 07-04 (streaming chat route uses chat_completion)
  - 07-05 (tool-call loop extends chat_completion with tools parameter)
  - 07-06 (conversation persistence relies on _message_to_dict for serialisation)

# Tech tracking
tech-stack:
  added: [openai>=1.0 (already in deps), openai.OpenAI custom base_url pattern]
  patterns:
    - Strip /chat/completions suffix from gateway URL so SDK does not double-append
    - Use openai.OpenAI (not AzureOpenAI) for non-standard gateway endpoints
    - Dual auth header — api_key param + api-key default_header for MMC gateway
    - SDK message objects converted to plain dicts immediately; never stored as SDK types

key-files:
  created:
    - chat_app/openai_client.py
  modified: []

key-decisions:
  - "Use openai.OpenAI (not AzureOpenAI) — MMC gateway URL format does not match Azure SDK auto-routing"
  - "Strip /chat/completions suffix in _get_base_url() — SDK appends it automatically; double-append would 404"
  - "Set api-key default header alongside api_key param — MMC gateway may require header-based auth"
  - "SYSTEM_PROMPT has 6 numbered rules — Exchange-only guardrail, use tools for live data, never fabricate, concise output"
  - "build_system_message() accepts user_name param (unused in prompt body now) — reserved for future personalisation"
  - "_message_to_dict() handles tool_calls in preparation for 07-05 tool-call loop"

patterns-established:
  - "URL normalisation pattern: always strip known SDK-appended suffixes from gateway URLs before passing as base_url"
  - "Plain dict serialisation pattern: all SDK objects converted immediately at API boundary, never stored as SDK types"
  - "Client singleton pattern: global _client with init/get lifecycle, RuntimeError before init"

# Metrics
duration: 2min
completed: 2026-03-21
---

# Phase 7 Plan 03: Azure OpenAI Client Wrapper Summary

**openai.OpenAI client wrapper that strips /chat/completions from CHATGPT_ENDPOINT, sets Atlas Exchange-only system prompt, and converts SDK messages to plain dicts**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-21T19:05:44Z
- **Completed:** 2026-03-21T19:07:31Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `chat_app/openai_client.py` with full OpenAI client lifecycle (init, get, chat_completion)
- Implemented `_get_base_url()` that strips `/chat/completions` suffix from CHATGPT_ENDPOINT — prevents 404 from SDK double-appending the path
- Wrote `SYSTEM_PROMPT` with 6 guardrail rules establishing Atlas as Exchange-only assistant that uses tools for live data, never fabricates, and redirects off-topic questions
- Implemented `_message_to_dict()` that converts SDK `ChatCompletionMessage` to plain JSON-serialisable dicts including `tool_calls` structure (prepared for 07-05)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create openai_client.py with Azure OpenAI wrapper and system prompt** - `69707c1` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `chat_app/openai_client.py` - Azure OpenAI wrapper: _get_base_url, init_openai, get_client, _message_to_dict, chat_completion, build_system_message, SYSTEM_PROMPT

## Decisions Made

- **openai.OpenAI not AzureOpenAI**: MMC stg1 gateway URL ends in `/chat/completions` which does not match the Azure SDK's auto-routing pattern (`/openai/deployments/{model}/chat/completions`). Using standard `openai.OpenAI` with `base_url` gives full control over URL construction.
- **Strip /chat/completions in _get_base_url()**: The SDK appends `/chat/completions` automatically. If the gateway URL already contains it, the result would be a double-appended 404. Stripping it in `_get_base_url()` makes the URL composition predictable regardless of how the env var is set.
- **api-key default header**: MMC gateway may accept either Bearer token (`api_key` param) or `api-key` header. Setting both costs nothing and avoids debugging auth failures at runtime.
- **_message_to_dict handles tool_calls**: Even though 07-03 only uses basic completions, the converter handles `tool_calls` upfront so the same function is reused unchanged in 07-05 without modification.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The 3 pre-existing integration test failures (`test_integration.py`) relate to Exchange PowerShell not being available in this environment and were failing before this plan.

## User Setup Required

None - no external service configuration required beyond what was established in 07-01 (CHATGPT_ENDPOINT and AZURE_OPENAI_API_KEY in environment/secrets).

## Next Phase Readiness

- `init_openai()` is ready to be called in `create_app()` once CHATGPT_ENDPOINT and AZURE_OPENAI_API_KEY are available at startup
- `chat_completion()` and `build_system_message()` are ready for the streaming route in 07-04
- `_message_to_dict()` is prepared for tool_calls that arrive in 07-05
- **Concern carried forward**: API_VERSION=2023-05-15 may not support `tools` parameter — verify with MMC CTS before 07-05

---
*Phase: 07-chat-app-core*
*Completed: 2026-03-21*
