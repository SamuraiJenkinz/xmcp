---
phase: 05-mail-flow-and-security-tools
plan: 03
subsystem: api
tags: [exchange, smtp, connectors, powershell, mcp, tools]

# Dependency graph
requires:
  - phase: 05-mail-flow-and-security-tools/05-02
    provides: get_transport_queues handler, partial-results pattern, two-step server discovery
provides:
  - _get_smtp_connectors_handler with connector_type filtering (send/receive/all)
  - Multi-valued property projection pattern for Bindings, RemoteIPRanges, AddressSpaces, SmartHosts, SourceTransportServers
  - Full send connector inventory (AddressSpaces, TLS, SmartHosts, MaxMessageSize, source servers)
  - Full receive connector inventory (Bindings, RemoteIPRanges, AuthMechanism, PermissionGroups, TLS)
affects: [06-hybrid-and-migration-tools, future phases needing connector context]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "connector_type filter pattern: send/receive/all with immediate validation before Exchange calls"
    - "MaxMessageSize string coercion: str() on ByteQuantifiedSize object to preserve human-readable format"
    - "Single dict normalization: [raw] if isinstance(raw, dict) and raw else []"

key-files:
  created: []
  modified:
    - exchange_mcp/tools.py
    - tests/test_tools_flow.py
    - tests/test_server.py

key-decisions:
  - "connector_type defaults to 'all' when not provided — backward compatible, most informative response"
  - "Invalid connector_type raises RuntimeError immediately before any Exchange call — fail fast pattern"
  - "MaxMessageSize serialized as str() — ByteQuantifiedSize objects serialize to human-readable '25 MB (26,214,400 bytes)'"
  - "Multi-valued Bindings and RemoteIPRanges use ForEach-Object { $_.ToString() } — same lesson as Phase 4 ActivationPreference"
  - "test_call_tool_not_implemented_raises updated to use get_dkim_config stub — get_smtp_connectors is now real"

patterns-established:
  - "connector_type filter: validate immediately, branch on ('send', 'all') and ('receive', 'all') to skip unneeded Exchange calls"
  - "MaxMessageSize as nullable string: str(val) if val else None preserves Exchange format without parsing"

# Metrics
duration: 2min
completed: 2026-03-20
---

# Phase 5 Plan 03: get_smtp_connectors Handler Summary

**Full SMTP connector inventory tool with send/receive filtering, multi-valued property projection, and 8 unit tests covering all filtering modes and edge cases**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-20T18:50:33Z
- **Completed:** 2026-03-20T18:52:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Implemented `_get_smtp_connectors_handler` with connector_type filtering (send/receive/all)
- Multi-valued Exchange properties (AddressSpaces, SmartHosts, SourceTransportServers, Bindings, RemoteIPRanges) projected to string arrays via ForEach-Object
- MaxMessageSize coerced to string preserving Exchange's human-readable format
- TOOL_DISPATCH updated from stub to real handler (6 stubs remaining)
- 8 unit tests covering all filter modes, edge cases, error paths, and single dict normalization

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _get_smtp_connectors_handler to tools.py** - `85f2cf4` (feat)
2. **Task 2: Add unit tests for get_smtp_connectors to test_tools_flow.py** - `5516859` (test)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `exchange_mcp/tools.py` - Added _get_smtp_connectors_handler (109 lines); TOOL_DISPATCH stub replaced with real handler
- `tests/test_tools_flow.py` - Added 8 get_smtp_connectors tests and import; fixed missing assert in exchange_error_propagates test for get_transport_queues
- `tests/test_server.py` - Updated test_call_tool_not_implemented_raises to use get_dkim_config stub

## Decisions Made
- connector_type defaults to "all" — returns both send and receive, most informative for LLM with no filter specified
- Invalid connector_type raises RuntimeError immediately before any Exchange call — fail fast, same pattern as other parameter validation
- MaxMessageSize serialized as `str(val) if val else None` — Exchange returns ByteQuantifiedSize objects that render as "25 MB (26,214,400 bytes)" when stringified; no need to parse
- Multi-valued Bindings and RemoteIPRanges projected via `ForEach-Object { $_.ToString() }` — same lesson learned in Phase 4 for ActivationPreference opaque serialization
- test_call_tool_not_implemented_raises updated to get_dkim_config — rolling forward as each tool becomes real

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - straightforward implementation following the established handler pattern.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- get_smtp_connectors complete; 6 stubs remaining: get_dkim_config, get_dmarc_status, check_mobile_devices, get_hybrid_config, get_migration_batches, get_connector_status
- 155 tests passing (3 pre-existing Exchange integration failures remain, unrelated to this phase)
- Plan 05-04 (get_dkim_config) can proceed immediately

---
*Phase: 05-mail-flow-and-security-tools*
*Completed: 2026-03-20*
