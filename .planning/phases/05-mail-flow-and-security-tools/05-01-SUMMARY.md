---
phase: 05-mail-flow-and-security-tools
plan: 01
subsystem: mail-flow
tags: [exchange, connectors, routing, smtp, get-accepteddomain, get-sendconnector, get-receiveconnector]

# Dependency graph
requires:
  - phase: 04-dag-and-database-tools
    provides: established handler pattern with ForEach-Object projection and run_cmdlet_with_retry
  - phase: 02-mcp-server-scaffold
    provides: _validate_upn helper, TOOL_DISPATCH stub pattern, _make_stub factory
provides:
  - _check_mail_flow_handler: config-based route analysis using accepted domains + send/receive connectors
  - AddressSpace matching logic: SMTP:domain;cost format, wildcard *, subdomain *.domain patterns
  - Internal routing detection via Get-AcceptedDomain accepted domains set
  - 10 unit tests in tests/test_tools_flow.py covering all routing paths and validation
affects:
  - 05-02 through 05-05: remaining Phase 5 handlers follow same pattern
  - future phases: routing_type internal/external/unroutable is the canonical routing classification

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Multi-call handler with three Exchange queries (accepted domains, send connectors, receive connectors)
    - ForEach-Object { $_.ToString() } projection for multi-valued Exchange ADMultiValuedProperty collections
    - AddressSpace string parsing: strip "SMTP:" prefix and ";cost" suffix before domain matching
    - Enabled-only connector filtering before domain matching
    - routing_type enum pattern (internal/external/unroutable) for LLM-friendly classification

key-files:
  created:
    - tests/test_tools_flow.py
  modified:
    - exchange_mcp/tools.py
    - tests/test_server.py

key-decisions:
  - "check_mail_flow is config-based route analysis only - no test messages sent, safe for production use"
  - "Internal routing check uses accepted domains set membership; wildcard/subdomain connectors not checked for internal"
  - "Matching connectors: only Enabled:True connectors qualify; first match per connector wins (break after match)"
  - "AddressSpace cost suffix (;1, ;5 etc) stripped before domain comparison; SMTP: prefix also stripped"
  - "routing_type=internal takes precedence over connector matching when recipient domain is accepted"
  - "test_call_tool_not_implemented_raises updated to get_transport_queues (next stub in phase 5)"

patterns-established:
  - "Phase 5 handler structure: validate -> 3-call Exchange sequence -> normalize -> classify -> return"
  - "AddressSpace parsing: addr.lower().split(';')[0].split(':',1)[-1].strip() extracts matchable domain"

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 5 Plan 01: check_mail_flow Handler Summary

**Config-based mail routing analysis using Get-AcceptedDomain, Get-SendConnector, and Get-ReceiveConnector with AddressSpace pattern matching (SMTP:domain;cost, wildcard *, *.domain)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T17:46:27Z
- **Completed:** 2026-03-20T17:49:22Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Implemented `_check_mail_flow_handler` with three-call Exchange query sequence (accepted domains, send connectors, receive connectors)
- AddressSpace matching handles SMTP:domain;cost format, wildcard `*`, and subdomain `*.domain` patterns via string parsing
- Internal routing detected when recipient domain is in accepted domains set; returns routing_type=internal with descriptive message
- External routing identifies matching send connector, TLS requirement, and next hop (smart host or DNS)
- Unroutable case (no matching enabled connector, non-accepted domain) reported clearly
- 10 unit tests added in tests/test_tools_flow.py; full suite now 138 passing (3 pre-existing integration failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _check_mail_flow_handler to tools.py** - `ff00d88` (feat)
2. **Task 2: Create unit tests for check_mail_flow in test_tools_flow.py** - `5a7764d` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `exchange_mcp/tools.py` - Added _check_mail_flow_handler (Phase 5 section), updated TOOL_DISPATCH entry from stub to real handler
- `tests/test_tools_flow.py` - New file: 10 unit tests for check_mail_flow covering all routing paths and validation
- `tests/test_server.py` - Updated test_call_tool_not_implemented_raises to use get_transport_queues stub

## Decisions Made
- **Config-based analysis only**: No test messages sent — reads connector configuration to determine routing path, safe for production environments
- **Internal check first**: Get-AcceptedDomain called first; if recipient domain is in accepted set, routing_type=internal regardless of connector matching
- **Enabled-only matching**: Connectors with Enabled:False are skipped in the matching loop
- **AddressSpace parsing**: `SMTP:*;1` → strip "SMTP:" → strip ";1" → match against recipient_domain; wildcard `*` matches everything, `*.domain` matches subdomain
- **test_call_tool_not_implemented_raises uses get_transport_queues**: check_mail_flow is now real, next stub in Phase 5 is get_transport_queues

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- check_mail_flow handler is complete and tested; ready for LLM routing queries
- 8 stubs remaining: get_transport_queues, get_smtp_connectors, get_dkim_config, get_dmarc_status, check_mobile_devices, get_hybrid_config, get_migration_batches, get_connector_status
- Phase 5 plans 02-05 implement the remaining mail flow and security handlers following the same pattern

---
*Phase: 05-mail-flow-and-security-tools*
*Completed: 2026-03-20*
