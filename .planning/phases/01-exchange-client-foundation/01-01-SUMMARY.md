---
phase: 01-exchange-client-foundation
plan: 01
subsystem: infra
tags: [uv, python, asyncio, powershell, subprocess, pytest, pytest-asyncio, windows]

# Dependency graph
requires: []
provides:
  - uv-managed Python 3.11 project scaffold with all declared dependencies
  - Async PowerShell subprocess runner (run_ps) with timeout enforcement and UTF-8 output
  - build_script() helper for preamble composition
  - ProactorEventLoop confirmed on Windows
  - pytest + pytest-asyncio test harness in place

affects:
  - 01-02 (DNS resolver — imports exchange_mcp package, uses uv)
  - 01-03 (Exchange client — calls run_ps() for all Exchange operations)
  - 01-04 (MCP server — depends on exchange_mcp package structure)
  - all subsequent plans (all use uv venv and pytest harness)

# Tech tracking
tech-stack:
  added:
    - uv 0.10.11 (project/dependency manager)
    - Python 3.11.15 (cpython via uv)
    - dnspython 2.8.0
    - mcp 1.26.0
    - flask 3.1.3
    - waitress 3.0.2
    - pytest 9.0.2
    - pytest-asyncio 1.3.0
  patterns:
    - "-EncodedCommand (Base64 UTF-16LE) for Unicode-safe PowerShell argument delivery"
    - "Auto-prepend preamble in run_ps() to guarantee UTF-8 stdout encoding"
    - "asyncio.wait_for wrapping proc.communicate() for timeout-safe subprocess"
    - "proc.kill() + await proc.wait() for clean timeout recovery"

key-files:
  created:
    - exchange_mcp/__init__.py
    - exchange_mcp/ps_runner.py
    - tests/__init__.py
    - tests/test_ps_runner.py
    - pyproject.toml
    - .python-version
    - .env.example
    - uv.lock
  modified: []

key-decisions:
  - "Use -EncodedCommand (Base64 UTF-16LE) not -Command to prevent cp1252 corruption of non-ASCII script args"
  - "Auto-prepend _PS_PREAMBLE inside run_ps() so all callers get UTF-8 stdout by default"
  - "proc.communicate() not proc.wait() to prevent pipe-buffer deadlock on large output"
  - "proc.kill() then await proc.wait() on timeout to reap zombie before raising"

patterns-established:
  - "run_ps(script, timeout) is the single entry point for all PowerShell execution"
  - "build_script(body) for preamble + body composition and inspection"
  - "All Exchange operations flow through run_ps; JSON parsing is caller's responsibility"

# Metrics
duration: 37min
completed: 2026-03-19
---

# Phase 1 Plan 01: Project Scaffold and Async PowerShell Runner Summary

**uv-managed Python 3.11 project with async PowerShell subprocess runner using -EncodedCommand + auto-preamble for correct UTF-8 output on Windows**

## Performance

- **Duration:** 37 min
- **Started:** 2026-03-19T19:26:32Z
- **Completed:** 2026-03-19T20:04:24Z
- **Tasks:** 2 completed
- **Files modified:** 8

## Accomplishments

- Python 3.11 project scaffolded via uv with all declared dependencies (dnspython, mcp, flask, waitress) installed into venv, uv.lock committed
- `run_ps()` async function spawns `powershell.exe` via `-EncodedCommand`, enforces timeouts with kill/wait recovery, and captures UTF-8 stdout correctly on all Windows locales
- All 5 unit tests pass: echo, error exit, timeout (~3-4s not 30s), script building, and UTF-8 non-ASCII characters

## Task Commits

Each task was committed atomically:

1. **Task 1: Create project scaffold with uv, dependencies, and env var documentation** - `149cc2c` (feat)
2. **Task 2: Implement async PowerShell subprocess runner with timeout and error handling** - `2eacaf5` (feat)

**Plan metadata:** (committed with this summary)

## Files Created/Modified

- `pyproject.toml` - Project config: name=exchange-mcp, requires-python>=3.11, all runtime and dev deps
- `.python-version` - Pins Python 3.11 for uv
- `.env.example` - Documents AZURE_CERT_THUMBPRINT, AZURE_CLIENT_ID, AZURE_TENANT_DOMAIN
- `exchange_mcp/__init__.py` - Package init with module docstring
- `tests/__init__.py` - Empty test package init
- `exchange_mcp/ps_runner.py` - Async PowerShell runner: run_ps(), build_script(), _encode_command()
- `tests/test_ps_runner.py` - 5 unit tests for ps_runner using pytest-asyncio
- `uv.lock` - Locked dependency graph (46 packages)

## Decisions Made

- `-EncodedCommand` (Base64 UTF-16LE) used instead of `-Command` to guarantee Unicode-safe argument passing on all Windows locales — prevents cp1252 corruption of non-ASCII script content
- `_PS_PREAMBLE` is automatically applied inside `run_ps()` rather than requiring callers to call `build_script()` — ensures every invocation gets UTF-8 stdout encoding regardless of caller discipline
- `build_script()` is retained as a pure composition function for callers that need to inspect or log the full script before execution
- `proc.communicate()` used throughout (not `proc.wait()`) to prevent pipe-buffer deadlock on large stdout/stderr output

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed uv binary manually (not in system PATH)**

- **Found during:** Task 1 (uv sync)
- **Issue:** `uv` was not installed on the system; PowerShell installer script failed due to missing Microsoft.PowerShell.Security module
- **Fix:** Downloaded `uv-x86_64-pc-windows-msvc.zip` directly from GitHub releases and extracted to `C:\Users\taylo\uv_install\`; used full path `C:\Users\taylo\uv_install\uv.exe` for all uv commands
- **Files modified:** None (binary installed outside project)
- **Verification:** `uv --version` returned 0.10.11; `uv sync` completed successfully
- **Committed in:** Not committed (external binary)

**2. [Rule 1 - Bug] Switched from -Command to -EncodedCommand for Unicode-safe PowerShell argument delivery**

- **Found during:** Task 2 (test_run_ps_utf8 failure)
- **Issue:** Initial implementation used `-Command script` which passes the script through the Windows system code page (cp1252). Non-ASCII characters in the script body were corrupted before PowerShell received them.
- **Fix:** Added `_encode_command()` helper that encodes scripts as Base64 UTF-16LE; switched to `-EncodedCommand` flag in `create_subprocess_exec` call
- **Files modified:** `exchange_mcp/ps_runner.py`
- **Verification:** test_run_ps_utf8 still failed — led to next fix
- **Committed in:** `2eacaf5` (combined with all Task 2 changes)

**3. [Rule 1 - Bug] Auto-applied preamble inside run_ps() to guarantee UTF-8 stdout encoding**

- **Found during:** Task 2 (test_run_ps_utf8 still failing after -EncodedCommand fix)
- **Issue:** Without the UTF-8 preamble, PowerShell writes stdout using the system code page (cp1252). `Write-Output "café"` produced byte `\x82` (cp1252 for é) instead of `\xc3\xa9` (UTF-8). `decode('utf-8', errors='replace')` then produced U+FFFD (replacement character) instead of é.
- **Fix:** Changed `run_ps()` to prepend `_PS_PREAMBLE` to every script before encoding, guaranteeing `[Console]::OutputEncoding = UTF8` runs before any output
- **Files modified:** `exchange_mcp/ps_runner.py`
- **Verification:** All 5 tests pass; `test_run_ps_utf8` confirms `café` returned correctly
- **Committed in:** `2eacaf5` (combined with all Task 2 changes)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs)
**Impact on plan:** All essential for correct UTF-8 operation on Windows. No scope creep. The -EncodedCommand + auto-preamble approach is strictly better than the plan's -Command approach and is the production-correct design.

## Issues Encountered

- PowerShell Security module not available in the bash→PowerShell calling context prevented using the official uv installer script; worked around with direct binary download from GitHub

## User Setup Required

None - no external service configuration required for this plan. Future plans will require the env vars documented in `.env.example`.

## Next Phase Readiness

- uv venv and pytest harness ready for Plan 02 (DNS resolver)
- `run_ps()` is the single entry point for all PowerShell execution in Plans 03+
- Exchange-specific imports (ExchangeOnlineManagement) deliberately excluded — belong in Plan 03 per plan design
- Blockers from STATE.md still apply: Basic Auth for v1 (Kerberos deferred), throttling policy verification before Plan 03 load testing

---
*Phase: 01-exchange-client-foundation*
*Completed: 2026-03-19*
