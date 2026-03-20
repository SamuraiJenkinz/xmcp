---
phase: 05-mail-flow-and-security-tools
plan: 04
subsystem: api
tags: [exchange, dkim, dns, cname, powershell, mcp, tools, email-security]

# Dependency graph
requires:
  - phase: 05-mail-flow-and-security-tools/05-03
    provides: get_smtp_connectors handler, established Phase 5 handler pattern
  - phase: 01-exchange-client-foundation/01-02
    provides: dns_utils.py with get_txt_records, TTL cache, clear_cache pattern
provides:
  - get_cname_record function in dns_utils.py with TTL-respecting cache and negative caching
  - _get_dkim_config_handler combining Exchange DKIM signing config with live DNS CNAME validation
  - Sentinel pattern for distinguishing DNS error (null) from NXDOMAIN/not-published (false)
  - Updated get_dkim_config tool schema with domain as optional parameter
  - tests/test_tools_security.py with 9 handler unit tests
affects: [05-mail-flow-and-security-tools/05-05, 06-hybrid-and-migration-tools]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CNAME:{name} cache key prefix — avoids collision with TXT record cache keys in shared _cache dict"
    - "Sentinel object pattern for DNS result tracking — object() sentinel distinguishes error (match=null) from NXDOMAIN (match=false)"
    - "dns_utils import at module level in tools.py — enables patch('exchange_mcp.tools.dns_utils.get_cname_record') in tests"

key-files:
  created:
    - tests/test_tools_security.py
  modified:
    - exchange_mcp/dns_utils.py
    - exchange_mcp/tools.py
    - tests/test_dns_utils.py
    - tests/test_server.py

key-decisions:
  - "CNAME cache key prefixed with 'CNAME:' to prevent collision with TXT cache entries in shared module-level _cache dict"
  - "Sentinel object() per-invocation in handler to track whether DNS call succeeded vs errored — avoids flag variable"
  - "sel1_match = None when DNS raises LookupError (unknown); sel1_match = False when DNS returns None (NXDOMAIN/not published)"
  - "sel1_match = False when expected CNAME set but DNS returns None — subscriber has not published expected record"
  - "test_call_tool_not_implemented_raises updated to use get_dmarc_status stub — get_dkim_config is now real"

patterns-established:
  - "DNS result sentinel: _SENTINEL = object(); sel_result = _SENTINEL; try: sel_result = await dns_utils.get_cname_record(...) except LookupError: pass; then check 'if sel_result is not _SENTINEL'"
  - "Three-state DNS match: True (published == expected), False (mismatch or not-published when expected set), None (DNS error / unknown)"

# Metrics
duration: 5min
completed: 2026-03-20
---

# Phase 5 Plan 04: get_dkim_config Handler Summary

**DKIM signing config tool combining Exchange Get-DkimSigningConfig with live DNS CNAME validation, returning three-state match (true/false/null) per selector using a sentinel pattern to distinguish DNS errors from unpublished records**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-20T18:55:11Z
- **Completed:** 2026-03-20T18:59:52Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added `get_cname_record()` to dns_utils.py following the exact get_txt_records pattern: TTL-respecting cache, negative caching (300s), LookupError on DNS failures, trailing dot stripped from CNAME target
- Implemented `_get_dkim_config_handler` combining Exchange DKIM signing config (Get-DkimSigningConfig) with per-domain DNS CNAME validation via get_cname_record
- Three-state DNS match semantics: True (published matches expected), False (mismatch or expected-but-not-published), None (DNS lookup errored — unknown state)
- get_dkim_config tool schema updated: domain now optional (required:[]), returns all domains when omitted
- TOOL_DISPATCH updated from stub to real handler (5 stubs remaining)
- 14 new tests: 5 CNAME unit tests + 9 handler tests; 162 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_cname_record to dns_utils.py and its unit tests** - `185f05c` (feat)
2. **Task 2: Add _get_dkim_config_handler to tools.py with unit tests** - `c83e2de` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `exchange_mcp/dns_utils.py` - Added get_cname_record() with CNAME:{name} cache key, trailing dot stripping, same error/cache pattern as get_txt_records; updated module docstring
- `exchange_mcp/tools.py` - Added dns_utils import; added _get_dkim_config_handler (sentinel pattern, three-state match); updated get_dkim_config schema (domain optional); TOOL_DISPATCH stub replaced with real handler
- `tests/test_dns_utils.py` - Added 5 CNAME tests (found, nxdomain, no_answer, dns_error, cache_hit); updated imports
- `tests/test_tools_security.py` - Created with 9 handler tests covering single domain match, CNAME mismatch, not published, all domains, domain not found, no client, DNS error graceful, Exchange error propagates, empty result
- `tests/test_server.py` - Updated test_call_tool_not_implemented_raises to use get_dmarc_status stub

## Decisions Made
- **CNAME cache key prefix:** Used `CNAME:{name}` to avoid key collision with TXT record cache entries. TXT cache uses bare domain names (e.g. `_dmarc.contoso.com`); without a prefix, a CNAME lookup for a name matching a TXT cache entry could return wrong data.
- **Sentinel pattern for DNS result tracking:** Used `_SENTINEL = object()` per invocation to distinguish "DNS raised LookupError" from "DNS returned None (NXDOMAIN)". This avoids a separate boolean flag and cleanly handles the three states without extra complexity.
- **Three-state match semantics:** `None` = DNS error (unknown state, don't claim failure); `False` = expected set but NXDOMAIN or mismatch; `True` = published matches expected. The plan specified this explicitly.
- **Expected-but-not-published = False:** When Exchange has a Selector1CNAME but DNS returns None (NXDOMAIN/NoAnswer), we know the record is missing from DNS — this is a definite failure state (False), not unknown.
- **dns_utils imported at module level:** `from exchange_mcp import dns_utils` at the top of tools.py enables `patch('exchange_mcp.tools.dns_utils.get_cname_record')` in unit tests without circular imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Sentinel object to distinguish DNS error from NXDOMAIN**
- **Found during:** Task 2 (running test_get_dkim_config_dns_error_graceful)
- **Issue:** Initial implementation used `sel1_published = None` as default and `sel1_result = await get_cname_record(...)` in try/except. When LookupError was raised, `sel1_published` stayed `None`. The match logic then applied `elif sel1_published is None and sel1_expected is not None: sel1_match = False` — incorrectly treating DNS error as "not published" (False instead of None).
- **Fix:** Added `_SENTINEL = object()` before DNS calls, initialized `sel1_result = _SENTINEL`, set `sel1_published` only when `sel1_result is not _SENTINEL`. DNS errors leave `sel1_published = None` and `sel1_match = None` as required.
- **Files modified:** exchange_mcp/tools.py
- **Verification:** test_get_dkim_config_dns_error_graceful passes; test_get_dkim_config_cname_not_published correctly returns False (NXDOMAIN path)
- **Committed in:** c83e2de (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential for correct three-state semantics. No scope creep.

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- get_dkim_config complete with full DNS validation; 5 stubs remaining: get_dmarc_status, check_mobile_devices, get_hybrid_config, get_migration_batches, get_connector_status
- 162 tests passing (3 pre-existing Exchange integration failures remain, unrelated to this phase)
- Plan 05-05 (get_dmarc_status — Phase 5 final plan) can proceed immediately

---
*Phase: 05-mail-flow-and-security-tools*
*Completed: 2026-03-20*
