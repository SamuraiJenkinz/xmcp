---
phase: 01-exchange-client-foundation
plan: 03
subsystem: exchange-client
tags: [exchange-online, powershell, cba, certificate-auth, asyncio, retry, json, pytest, mock]

# Dependency graph
requires:
  - phase: 01-01
    provides: run_ps() async subprocess runner + build_script() preamble helper

provides:
  - ExchangeClient class with certificate-based Azure AD auth (CBA) via Connect-ExchangeOnline
  - Per-call Connect/Disconnect lifecycle in PowerShell try/finally template
  - ConvertTo-Json -Depth 10 enforcement in all script executions
  - Exponential-backoff retry with non-retryable error classification (_is_retryable)
  - verify_connection() health-check that returns bool and never raises
  - 13 unit tests with fully mocked ps_runner (no live Exchange dependency)

affects:
  - 01-04 (MCP server scaffold — imports ExchangeClient for health check endpoint)
  - 01-05 (integration tests — exercises ExchangeClient against live Exchange)
  - Phase 3+ (all MCP tool implementations call run_cmdlet_with_retry)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-call Connect/Disconnect in PS try/finally — no session pooling, accept 2-4s latency"
    - "CBA via CertificateThumbPrint env var — no credentials embedded in code"
    - "ConvertTo-Json -Depth 10 hardcoded in script template — prevents truncation of nested Exchange objects"
    - "Non-retryable error classification: auth, AADSTS, object-not-found, invalid-input raise immediately"
    - "Transient error classification: throttling, connection-reset, network errors retry with 2**attempt backoff"

key-files:
  created:
    - exchange_mcp/exchange_client.py
    - tests/test_exchange_client.py
  modified: []

key-decisions:
  - "run_cmdlet() returns raw Python objects (dict/list), not strings — JSON parsing is ExchangeClient's responsibility, not the caller's"
  - "build_script() NOT called from _build_cmdlet_script() — run_ps() auto-prepends preamble; calling build_script() would duplicate it"
  - "Non-retryable patterns list (AADSTS, authentication failed, couldn't find the object, etc.) checked case-insensitively — prevents burning retry quota on permanent failures"
  - "verify_connection() swallows all exceptions and returns False — health checks must never raise"

patterns-established:
  - "All Exchange MCP tools call run_cmdlet_with_retry(), not run_cmdlet() directly"
  - "ExchangeClient is the single abstraction layer over ps_runner for Exchange operations"
  - "Script template: Import-Module → Connect-ExchangeOnline (CBA) → cmdlet | ConvertTo-Json -Depth 10 → Disconnect in finally"

# Metrics
duration: 3min
completed: 2026-03-19
---

# Phase 1 Plan 03: Exchange Client Summary

**ExchangeClient with CBA auth template, per-call Connect/Disconnect lifecycle, ConvertTo-Json -Depth 10 enforcement, and exponential-backoff retry with non-retryable error classification — 13 passing unit tests, no live Exchange dependency**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T20:08:50Z
- **Completed:** 2026-03-19T20:11:45Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- `ExchangeClient` class validates `AZURE_CERT_THUMBPRINT`, `AZURE_CLIENT_ID`, `AZURE_TENANT_DOMAIN` at construction — fail-fast before any PowerShell is spawned
- `_build_cmdlet_script()` composes the full PowerShell script: `Import-Module` → `Connect-ExchangeOnline` (CBA via env vars) → `$result = {cmdlet} | ConvertTo-Json -Depth 10` → `Disconnect-ExchangeOnline` in finally block
- `run_cmdlet_with_retry()` retries transient errors (throttling, network, connection reset) up to `max_retries` times with `2**attempt` second backoff; auth failures and object-not-found raise immediately without retrying
- `verify_connection()` runs `Get-OrganizationConfig | Select-Object Name`, returns `True`/`False`, never raises — safe to use in health-check contexts
- All 13 unit tests pass in 0.16s with mocked `ps_runner.run_ps` — no live PowerShell or Exchange connection required

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ExchangeClient class with CBA auth, retry, and verify_connection** - `92a64b5` (feat)
2. **Task 2: Write unit tests for ExchangeClient with mocked PS runner** - `6d4e93a` (test)

**Plan metadata:** (committed with this summary)

## Files Created/Modified

- `exchange_mcp/exchange_client.py` - ExchangeClient class: `_verify_env()`, `_build_cmdlet_script()`, `run_cmdlet()`, `run_cmdlet_with_retry()`, `verify_connection()`, `_is_retryable()` helper; `_PS_CONNECT_TEMPLATE` and `_PS_DISCONNECT` module constants
- `tests/test_exchange_client.py` - 13 unit tests: env var validation, script structure, success/error/timeout/empty output paths, throttling retry (3 calls), auth non-retry (1 call), not-found non-retry (1 call), exhaustion, verify_connection success/failure

## Decisions Made

- `run_cmdlet()` does NOT call `ps_runner.build_script()` in `_build_cmdlet_script()` — `run_ps()` already auto-prepends the preamble, and calling `build_script()` would duplicate `[Console]::OutputEncoding` and `$ErrorActionPreference = 'Stop'` in the executed script
- Retry classification uses a `_NON_RETRYABLE_PATTERNS` tuple checked case-insensitively — covers AADSTS error codes, "authentication failed", "couldn't find the object", "cannot bind parameter", and similar permanent-failure phrases
- Empty string output from `run_ps()` returns `[]` rather than raising `json.JSONDecodeError` — some Exchange cmdlets legitimately produce no output when a filter matches zero objects
- `verify_connection()` catches bare `Exception` (not just `RuntimeError`/`TimeoutError`) — health checks must be resilient to unexpected failure modes including `json.JSONDecodeError`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Case-insensitive match in test_retry_exhaustion**

- **Found during:** Task 2 (test run)
- **Issue:** `pytest.raises(match="connection reset")` uses `re.search` which is case-sensitive by default. The error message was "Connection reset by peer" (capital C), causing regex match failure.
- **Fix:** Changed match pattern to `"(?i)connection reset"` — inline case-insensitive flag
- **Files modified:** `tests/test_exchange_client.py`
- **Verification:** All 13 tests pass (was 12/13 before fix)
- **Committed in:** `6d4e93a` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test regex correction. No scope creep. All essential behaviour verified correctly.

## Issues Encountered

None beyond the minor regex case-sensitivity fix documented above.

## User Setup Required

None — no external service configuration required. The required environment variables (`AZURE_CERT_THUMBPRINT`, `AZURE_CLIENT_ID`, `AZURE_TENANT_DOMAIN`) are documented in `.env.example` from Plan 01-01.

## Next Phase Readiness

- `ExchangeClient` is ready for Plan 01-04 (MCP server scaffold) to import for the `/health` endpoint
- `run_cmdlet_with_retry()` is the stable entry point for all Phase 3+ MCP tool implementations
- Blockers from STATE.md still apply: throttling policy verification before Phase 3 load testing; Basic Auth for v1 (Kerberos deferred)
- No live Exchange validation yet — that belongs in Plan 01-05 (integration tests)

---
*Phase: 01-exchange-client-foundation*
*Completed: 2026-03-19*
