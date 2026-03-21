---
phase: 06-hybrid-tools
plan: 01
subsystem: hybrid-tools
tags: [exchange, powershell, hybrid, federation, mcp-tools, pytest]

# Dependency graph
requires:
  - phase: 05-mail-flow-and-security-tools
    provides: check_mobile_devices handler pattern, independent error handling pattern, tool stub infrastructure
provides:
  - get_migration_batches removed from TOOL_DEFINITIONS and TOOL_DISPATCH (out of scope for MMC)
  - _get_hybrid_config_handler assembling 5 Exchange cmdlets into single hybrid topology response
  - Tool count updated from 16/15 to 15/14 across tools.py, server.py, test_server.py
  - 7 unit tests for get_hybrid_config in tests/test_tools_hybrid.py
affects: [06-02-PLAN, 07-conversation-api, STATE.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Multi-section independent error handling: each sub-call in a composite handler catches RuntimeError independently, returning {error: str} for that section without failing the whole handler"
    - "FederationTrust certificate projection: X509Certificate2 objects projected to scalar strings (Thumbprint, Subject, NotAfter.ToString('o')) via PowerShell calculated properties"
    - "MultiValuedProperty to string array: ForEach-Object { $_.ToString() } in PowerShell calculated properties for DomainNames, TargetAddressDomains, AddressSpaces, SmartHosts"
    - "_normalize() helper: converts single-dict Exchange responses to one-element list, passes list as-is, passes error dict as-is"

key-files:
  created:
    - tests/test_tools_hybrid.py
  modified:
    - exchange_mcp/tools.py
    - exchange_mcp/server.py
    - tests/test_server.py

key-decisions:
  - "get_migration_batches removed: out of MMC scope — MMC does not use migration batches"
  - "get_hybrid_config returns 5-section composite: org relationships, federation trust, intra-org connectors, availability address spaces, hybrid send connectors"
  - "Independent section error handling: partial Exchange failure returns error key for that section only, not a full RuntimeError — LLM receives available data plus explicit error markers"
  - "FederationTrust X509Certificate2 fields projected to scalar strings in PowerShell — avoids serialization failures with raw .NET objects"
  - "CloudServicesMailEnabled filter in PowerShell (Where-Object) not Python — reduces data transferred for hybrid send connector query"

patterns-established:
  - "Composite handler pattern: multiple cmdlets per handler, each wrapped in try/except RuntimeError, result assembled into structured dict"
  - "test_call_tool_not_implemented_raises tracks the last remaining stub — update to next stub when each handler is implemented"

# Metrics
duration: 12min
completed: 2026-03-20
---

# Phase 6 Plan 01: Remove get_migration_batches and Implement get_hybrid_config Summary

**get_migration_batches removed and get_hybrid_config implemented: 5-cmdlet composite handler returning full Exchange hybrid topology (org relationships, federation trust, intra-org connectors, availability address spaces, hybrid send connectors) with per-section independent error handling**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-20T23:07:53Z
- **Completed:** 2026-03-20T23:20:00Z
- **Tasks:** 2
- **Files modified:** 4 (tools.py, server.py, test_server.py, new test_tools_hybrid.py)

## Accomplishments

- Removed get_migration_batches from TOOL_DEFINITIONS and TOOL_DISPATCH (MMC out of scope); updated all count references from 16/15 to 15/14
- Implemented _get_hybrid_config_handler with 5 sequential Exchange cmdlets, each independently error-handled so partial Exchange failures return {"error": "..."} for that section without propagating
- FederationTrust X509Certificate2 fields projected to scalar strings (Thumbprint, Subject, NotAfter ISO-8601) via PowerShell calculated properties
- MultiValuedProperty fields (DomainNames, TargetAddressDomains, AddressSpaces, SmartHosts) projected with ForEach-Object ToString()
- Created tests/test_tools_hybrid.py with 7 unit tests covering full topology, multiple relationships, partial failure, total failure, empty results, no-client guard, and single-dict normalization
- 189 tests passing (up from 182), 3 pre-existing integration test failures unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove get_migration_batches and update all tool count references** - `455c698` (chore)
2. **Task 2: Implement _get_hybrid_config_handler and unit tests** - `e41f890` (feat)

**Plan metadata:** (committed with SUMMARY.md and STATE.md)

## Files Created/Modified

- `exchange_mcp/tools.py` - Removed get_migration_batches Tool definition and dispatch entry; updated module docstring counts; added _get_hybrid_config_handler (Phase 6 section); updated TOOL_DISPATCH to point to real handler
- `exchange_mcp/server.py` - Updated module docstring and handle_list_tools docstring: 16/15 -> 15/14
- `tests/test_server.py` - Renamed test_list_tools_returns_all_16 -> test_list_tools_returns_all_15; updated assertion to len==15; updated test_call_tool_not_implemented_raises to use get_connector_status stub
- `tests/test_tools_hybrid.py` - New: 7 unit tests for _get_hybrid_config_handler

## Decisions Made

- **get_migration_batches removed:** MMC does not use migration batches; removing reduces tool surface area and avoids maintaining a dead stub
- **Per-section independent error handling:** A failure in federation trust (e.g., not configured) should not prevent org relationship or intra-org connector data from being returned — LLM receives whatever is available
- **FederationTrust certificates projected in PowerShell:** Raw X509Certificate2 objects from Exchange cannot be JSON-serialized; projecting to Thumbprint/Subject/NotAfter strings at the PowerShell layer avoids serialization failures
- **Where-Object filter in PowerShell for hybrid send connectors:** Filter CloudServicesMailEnabled at the cmdlet level to avoid transferring all send connectors over the PS pipe

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- get_hybrid_config is fully implemented and tested; 06-02 (get_connector_status) is the last remaining stub
- Tool count is 15 (14 Exchange + ping); get_connector_status is the only stub remaining
- After 06-02 completes, Phase 6 will be complete and the MCP server will have all tools implemented

---
*Phase: 06-hybrid-tools*
*Completed: 2026-03-20*
