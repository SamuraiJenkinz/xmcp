---
phase: 26-message-trace-tool
plan: 01
subsystem: exchange
tags: [exchange-online, message-trace, powershell, get-messagetrace, mcp-tools]

# Dependency graph
requires:
  - phase: 05-mail-flow-and-security-tools
    provides: check_mail_flow handler pattern, _validate_upn, _escape_ps_single_quote helpers
  - phase: 01-exchange-client-foundation
    provides: run_cmdlet_with_retry (auto-appends ConvertTo-Json), ExchangeClient
provides:
  - get_message_trace MCP tool definition (18th tool)
  - _get_message_trace_handler with full input validation and result normalization
  - _truncate_subject helper for PII-safe subject output
affects:
  - 26-message-trace-tool (plan 02 — per-message feedback or follow-on work)
  - Any phase that needs email delivery tracking context

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Get-MessageTraceV2 (not deprecated Get-MessageTrace) for Exchange Online message tracking"
    - "Truncation detection via requesting result_size+1 from PowerShell"
    - "Inline datetime import pattern matching existing handler style"

key-files:
  created: []
  modified:
    - exchange_mcp/tools.py

key-decisions:
  - "Use Get-MessageTraceV2, not Get-MessageTrace (deprecated Sep 2025)"
  - "Do not append ConvertTo-Json to cmdlet — run_cmdlet_with_retry already does this internally"
  - "Request result_size+1 from PowerShell (capped at 5000) to detect truncation without over-fetching"
  - "Subject capped at 30 chars in output for PII reduction"
  - "Size returned as size_kb (float, 1 decimal) rather than raw bytes"

patterns-established:
  - "_truncate_subject(subject, max_len=30): reusable helper for any tool returning subject lines"
  - "RBAC checkpoint pattern: verified Atlas is in Organization Management (includes Message Tracking)"

# Metrics
duration: 15min
completed: 2026-04-06
---

# Phase 26 Plan 01: Message Trace Tool Handler Summary

**get_message_trace MCP tool backed by Get-MessageTraceV2 with sender/recipient validation, 10-day range enforcement, and PII-safe subject truncation**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-06T00:00:00Z
- **Completed:** 2026-04-06T00:15:00Z
- **Tasks:** 2 (Task 1: RBAC verification — human; Task 2: implementation — automated)
- **Files modified:** 1

## Accomplishments

- RBAC verified: Atlas service principal is in Organization Management role group, which includes Message Tracking — no changes needed
- get_message_trace tool definition added to TOOL_DEFINITIONS (18th tool, 6 input parameters)
- _get_message_trace_handler implemented with all validation rules: requires sender or recipient, rejects bare names, validates UPN format, enforces 10-day max range, defaults to last 24 hours
- _truncate_subject helper added (30 char limit, appends "...")
- Result normalization: size_bytes → size_kb, subject → subject_snippet, truncation detection
- Handler registered in TOOL_DISPATCH

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify RBAC role for Atlas service principal** - N/A (human verification, no commit)
2. **Task 2: Add tool definition, handler, and dispatch registration** - `9fef3d6` (feat)

**Plan metadata:** (pending — docs commit)

## Files Created/Modified

- `exchange_mcp/tools.py` - Added _truncate_subject helper, get_message_trace tool definition, _get_message_trace_handler, TOOL_DISPATCH entry

## Decisions Made

- Used Get-MessageTraceV2 not Get-MessageTrace — the V1 cmdlet was deprecated in Sep 2025; V2 has no -Page parameter so pagination is handled via -ResultSize
- Do not append ConvertTo-Json to the cmdlet string — run_cmdlet_with_retry in exchange_client.py already appends `| ConvertTo-Json -Depth 10` internally (line 233 of exchange_client.py); doubling it would break parsing
- Request min(result_size + 1, 5000) from PowerShell to detect truncation without over-fetching beyond API limits
- Size output as size_kb (float rounded to 1 decimal) matching the plan spec; _format_size helper not used here as caller needs a numeric field for sorting/filtering

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - RBAC was already in place. Atlas is in Organization Management which includes the Message Tracking role.

## Next Phase Readiness

- get_message_trace tool is implemented and registered; ready for live testing against Exchange Online
- Plan 02 (if it exists) can build on top of this handler
- CHATGPT_ENDPOINT env var still manually set (not in AWS Secrets Manager pipeline) — carried forward concern

---
*Phase: 26-message-trace-tool*
*Completed: 2026-04-06*
