"""Unit tests for exchange_mcp.ps_runner.

These tests exercise run_ps() against a real powershell.exe subprocess.
They require a Windows environment with PowerShell available in PATH.
"""

import pytest
import pytest_asyncio  # noqa: F401 — ensures plugin is active

from exchange_mcp.ps_runner import build_script, run_ps, _PS_PREAMBLE


# ---------------------------------------------------------------------------
# pytest-asyncio mode — auto mode so every async test is recognised without
# decorating each one individually.
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_run_ps_echo():
    """run_ps should capture stdout and return it stripped."""
    result = await run_ps('Write-Output "hello"')
    assert "hello" in result, f"Expected 'hello' in output, got: {result!r}"


@pytest.mark.asyncio
async def test_run_ps_error_exit():
    """run_ps should raise RuntimeError when PowerShell exits non-zero."""
    with pytest.raises(RuntimeError) as exc_info:
        await run_ps("exit 1")
    # The error message must mention the exit code or stderr.
    assert exc_info.value.args[0]  # Non-empty message


@pytest.mark.asyncio
async def test_run_ps_timeout():
    """run_ps should raise TimeoutError and kill the process on timeout.

    Uses a very short timeout so the test completes in ~2-3 s rather than 30.
    """
    with pytest.raises(TimeoutError) as exc_info:
        await run_ps("Start-Sleep -Seconds 30", timeout=2)
    assert "2 second" in str(exc_info.value).lower() or "second" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_build_script():
    """build_script should prepend the UTF-8 preamble to the supplied body."""
    body = "Get-Date"
    combined = build_script(body)
    assert combined.startswith(_PS_PREAMBLE), (
        f"Expected script to start with preamble, got: {combined[:80]!r}"
    )
    assert combined.endswith(body), (
        f"Expected script to end with body, got: {combined[-80:]!r}"
    )
    # Verify encoding directive is present
    assert "[Console]::OutputEncoding" in combined
    assert "$ErrorActionPreference = 'Stop'" in combined


@pytest.mark.asyncio
async def test_run_ps_utf8():
    """run_ps should handle UTF-8 characters in PowerShell output."""
    result = await run_ps('Write-Output "café"')
    assert "café" in result, (
        f"Expected UTF-8 string 'café' in output, got: {result!r}"
    )
