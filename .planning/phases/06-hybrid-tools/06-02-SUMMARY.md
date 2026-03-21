---
phase: 06-hybrid-tools
plan: "02"
subsystem: exchange-tools
tags: [exchange, hybrid, connectors, tls, certificates, powershell, mcp]

# Dependency graph
requires:
  - phase: 06-01
    provides: get_hybrid_config handler establishing hybrid tool pattern
  - phase: 05-mail-flow-and-security-tools
    provides: connector data patterns (SMTP connectors, TLS fields)
provides:
  - _get_connector_status_handler: hybrid send/receive connector health with per-connector boolean
  - _lookup_cert_for_fqdn: per-connector TLS certificate lookup via Get-ExchangeCertificate
  - _assess_connector_health: (healthy, error) tuple from connector + cert state
  - All 15 Exchange MCP tools fully implemented — zero stubs remain in TOOL_DISPATCH
affects: [07-http-layer, 08-conversation-persistence, 09-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Per-connector cert lookup via Get-ExchangeCertificate with graceful None fallback for Exchange Online
    - Three-criteria health assessment: Enabled + RequireTLS + cert.status == "Valid"
    - Hybrid send connector identification by CloudServicesMailEnabled eq true
    - Hybrid receive connector identification by TlsCertificateName non-empty
    - all_healthy boolean summarizing every connector's health for LLM consumption

key-files:
  created: []
  modified:
    - exchange_mcp/tools.py
    - tests/test_tools_hybrid.py
    - tests/test_server.py

key-decisions:
  - "get_connector_status identifies hybrid send connectors by CloudServicesMailEnabled eq true (not connector name)"
  - "get_connector_status identifies hybrid receive connectors by TlsCertificateName being non-empty"
  - "Per-connector TLS cert lookup via Get-ExchangeCertificate -DomainName with graceful None return on RuntimeError"
  - "Connector health is Enabled AND RequireTLS AND cert.status == Valid; None cert treated as healthy (Exchange Online)"
  - "all_healthy=True for empty connector list — no connectors is not an unhealthy state"
  - "test_call_tool_not_implemented_raises updated to use nonexistent_tool — zero stubs remain"

patterns-established:
  - "Per-entity helper lookup pattern: _lookup_cert_for_fqdn returns None on any failure, never raises"
  - "Health assessment decomposed to pure function _assess_connector_health (testable without mocks)"
  - "test_call_tool_not_implemented_raises uses nonexistent_tool name as final form — no stubs left to test"

# Metrics
duration: 38min
completed: 2026-03-21
---

# Phase 6 Plan 02: Connector Status Summary

**get_connector_status handler with per-connector TLS cert validation, completing all 15 Exchange MCP tools with zero stubs**

## Performance

- **Duration:** 38 min
- **Started:** 2026-03-21T02:01:45Z
- **Completed:** 2026-03-21T02:40:20Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented `_get_connector_status_handler` reporting hybrid send and receive connector health with per-connector `healthy` boolean and `error` message
- Added `_lookup_cert_for_fqdn` helper that queries `Get-ExchangeCertificate -DomainName` and gracefully returns `None` when the cmdlet is unavailable (Exchange Online environments)
- Added `_assess_connector_health` pure function: connector is healthy when Enabled + RequireTLS + cert status is "Valid" (or cert unavailable)
- Replaced the last remaining stub in `TOOL_DISPATCH` — all 15 Exchange + ping tools are now fully implemented
- Added 10 unit tests for the connector status handler and 1 direct test of `_assess_connector_health`
- Updated `test_call_tool_not_implemented_raises` to use `nonexistent_tool` — the test is now permanent and not tied to any real tool

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _get_connector_status_handler with helpers to tools.py** - `5ceb3f0` (feat)
2. **Task 2: Add unit tests for get_connector_status handler** - `34f8b54` (test)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `exchange_mcp/tools.py` - Added `_lookup_cert_for_fqdn`, `_assess_connector_health`, `_get_connector_status_handler`; replaced stub in `TOOL_DISPATCH`
- `tests/test_tools_hybrid.py` - Added 10 connector status unit tests + `_assess_connector_health` direct tests (17 total in file)
- `tests/test_server.py` - Updated `test_call_tool_not_implemented_raises` to use `nonexistent_tool`; updated docstring

## Decisions Made

- **Hybrid send connector identification:** `CloudServicesMailEnabled eq true` — matches the same filter used in `get_hybrid_config` hybrid send cmdlet; consistent across tools
- **Hybrid receive connector identification:** `TlsCertificateName` non-empty — the standard marker for TLS-configured receive connectors in hybrid deployments
- **Certificate lookup on RuntimeError returns None:** `Get-ExchangeCertificate` is on-premises only; in pure Exchange Online environments the cmdlet doesn't exist. Returning `None` allows health assessment to proceed without the cert check rather than failing the whole tool call
- **None cert = healthy:** When cert lookup is unavailable we cannot fully verify TLS but the connector is still enabled and TLS-configured — this is a valid operational state especially in cloud-first hybrid deployments
- **`all_healthy=True` for empty connector list:** No connectors is not an unhealthy state; the LLM should be informed there are no hybrid connectors rather than told things are broken
- **`_assess_connector_health` as pure function:** Separated from async handler to enable direct unit testing without mocking the Exchange client

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 15 Exchange MCP tools (14 Exchange + ping) are fully implemented with zero stubs
- Phase 6 Hybrid Tools is **complete** — both plans (06-01 get_hybrid_config, 06-02 get_connector_status) done
- Test suite: 199 unit tests passing (3 live integration tests require Exchange credentials — pre-existing, not new failures)
- Ready for Phase 7: HTTP Layer — Flask/FastAPI server wrapping the MCP server for REST access

---
*Phase: 06-hybrid-tools*
*Completed: 2026-03-21*
