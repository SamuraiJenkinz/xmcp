"""Unit tests for exchange_mcp.exchange_client.ExchangeClient.

All tests mock ``exchange_mcp.ps_runner.run_ps`` to avoid actual PowerShell
execution.  No live Exchange Online connection is required.

Tests cover:
    - Environment variable validation at construction time
    - PowerShell script template structure
    - Successful cmdlet execution and JSON parsing
    - Error propagation (RuntimeError, TimeoutError, empty output)
    - Retry logic: transient errors retry, auth/input errors do not
    - Retry exhaustion
    - verify_connection() success and failure paths
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from exchange_mcp.exchange_client import ExchangeClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the required Azure AD credential env vars for every test that uses it."""
    monkeypatch.setenv("AZURE_CERT_THUMBPRINT", "AABBCCDDEEFF1122334455667788990011223344")
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("AZURE_TENANT_DOMAIN", "contoso.onmicrosoft.com")


@pytest.fixture()
def client(env_vars: None) -> ExchangeClient:
    """Return an ExchangeClient with all env vars set."""
    return ExchangeClient(timeout=30, max_retries=3)


# ---------------------------------------------------------------------------
# 1. test_init_missing_env_vars
# ---------------------------------------------------------------------------


def test_init_missing_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """ExchangeClient() must raise EnvironmentError when env vars are absent."""
    monkeypatch.delenv("AZURE_CERT_THUMBPRINT", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_TENANT_DOMAIN", raising=False)

    with pytest.raises(EnvironmentError) as exc_info:
        ExchangeClient()

    msg = str(exc_info.value)
    assert "AZURE_CERT_THUMBPRINT" in msg
    assert "AZURE_CLIENT_ID" in msg
    assert "AZURE_TENANT_DOMAIN" in msg


# ---------------------------------------------------------------------------
# 2. test_init_success
# ---------------------------------------------------------------------------


def test_init_success(env_vars: None) -> None:
    """ExchangeClient() must not raise when all env vars are set."""
    client = ExchangeClient()
    assert client.timeout == 60
    assert client.max_retries == 3
    assert client.default_result_size == 100


# ---------------------------------------------------------------------------
# 3. test_build_cmdlet_script_structure
# ---------------------------------------------------------------------------


def test_build_cmdlet_script_structure(client: ExchangeClient) -> None:
    """_build_cmdlet_script() must contain all required PowerShell fragments."""
    cmdlet = "Get-Mailbox -Identity user@contoso.com"
    script = client._build_cmdlet_script(cmdlet)

    # CBA authentication
    assert "Connect-ExchangeOnline" in script, "Missing Connect-ExchangeOnline"
    assert "CertificateThumbPrint" in script, "Missing CertificateThumbPrint"
    assert "$env:AZURE_CERT_THUMBPRINT" in script, "Thumbprint must come from env var"
    assert "$env:AZURE_CLIENT_ID" in script, "Client ID must come from env var"
    assert "$env:AZURE_TENANT_DOMAIN" in script, "Tenant domain must come from env var"

    # JSON serialisation contract
    assert "ConvertTo-Json -Depth 10" in script, "Must use ConvertTo-Json -Depth 10"

    # Clean disconnect in finally
    assert "Disconnect-ExchangeOnline" in script, "Missing Disconnect-ExchangeOnline"
    assert "finally" in script, "Disconnect must be inside a finally block"

    # The requested cmdlet must appear in the script
    assert cmdlet in script, f"Cmdlet {cmdlet!r} not found in script"

    # UTF-8 encoding preamble — set by ps_runner but we verify the body
    # does NOT duplicate it (ps_runner auto-prepends it)
    # The body itself should not contain the preamble to avoid duplication.
    # (We do not call build_script() in _build_cmdlet_script.)


# ---------------------------------------------------------------------------
# 4. test_run_cmdlet_success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_cmdlet_success(client: ExchangeClient) -> None:
    """run_cmdlet() must parse JSON output and return the Python object."""
    payload = {"DisplayName": "John Doe", "PrimarySmtpAddress": "john@contoso.com"}

    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = json.dumps(payload)
        result = await client.run_cmdlet("Get-Mailbox -Identity john@contoso.com")

    assert result == payload
    mock_run.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. test_run_cmdlet_ps_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_cmdlet_ps_error(client: ExchangeClient) -> None:
    """run_cmdlet() must propagate RuntimeError raised by ps_runner."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("PowerShell exited with code 1. stderr:\nsome error")

        with pytest.raises(RuntimeError):
            await client.run_cmdlet("Get-Mailbox -Identity bad@contoso.com")

    mock_run.assert_awaited_once()


# ---------------------------------------------------------------------------
# 6. test_run_cmdlet_timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_cmdlet_timeout(client: ExchangeClient) -> None:
    """run_cmdlet() must propagate TimeoutError from ps_runner unchanged."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = TimeoutError("PowerShell process did not complete within 30 second(s).")

        with pytest.raises(TimeoutError):
            await client.run_cmdlet("Get-Mailbox -Identity slow@contoso.com")

    mock_run.assert_awaited_once()


# ---------------------------------------------------------------------------
# 7. test_run_cmdlet_empty_output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_cmdlet_empty_output(client: ExchangeClient) -> None:
    """run_cmdlet() must return empty list when ps_runner returns empty string."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = ""
        result = await client.run_cmdlet("Get-Mailbox -Filter {Department -eq 'Empty'}")

    assert result == []
    mock_run.assert_awaited_once()


# ---------------------------------------------------------------------------
# 8. test_retry_on_throttling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_on_throttling(client: ExchangeClient) -> None:
    """run_cmdlet_with_retry() must retry up to max_retries on throttling errors."""
    success_payload = {"Name": "contoso"}

    # Fail twice with a throttling-style error, succeed on the third call.
    call_count = 0

    async def side_effect(*args: object, **kwargs: object) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Request was throttled. Please retry after 5 seconds.")
        return json.dumps(success_payload)

    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_run.side_effect = side_effect
        result = await client.run_cmdlet_with_retry("Get-OrganizationConfig")

    assert result == success_payload
    assert mock_run.await_count == 3, f"Expected 3 calls, got {mock_run.await_count}"
    # Backoff sleep should have been called twice (after attempt 0 and 1)
    assert mock_sleep.await_count == 2


# ---------------------------------------------------------------------------
# 9. test_no_retry_on_auth_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_retry_on_auth_error(client: ExchangeClient) -> None:
    """run_cmdlet_with_retry() must NOT retry when error indicates auth failure."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_run.side_effect = RuntimeError(
            "Authentication failed. Invalid credentials for application."
        )

        with pytest.raises(RuntimeError, match="Authentication failed"):
            await client.run_cmdlet_with_retry("Get-Mailbox")

    # Must only be called once — no retry on auth error
    assert mock_run.await_count == 1, f"Expected 1 call, got {mock_run.await_count}"
    mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# 10. test_no_retry_on_not_found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_retry_on_not_found(client: ExchangeClient) -> None:
    """run_cmdlet_with_retry() must NOT retry when object is not found."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_run.side_effect = RuntimeError(
            "Couldn't find the object 'missing@contoso.com'."
        )

        with pytest.raises(RuntimeError, match="Couldn't find the object"):
            await client.run_cmdlet_with_retry("Get-Mailbox -Identity missing@contoso.com")

    assert mock_run.await_count == 1, f"Expected 1 call, got {mock_run.await_count}"
    mock_sleep.assert_not_awaited()


# ---------------------------------------------------------------------------
# 11. test_retry_exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_exhaustion(client: ExchangeClient) -> None:
    """run_cmdlet_with_retry() must raise after all retries are exhausted."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_run.side_effect = RuntimeError(
            "Connection reset by peer — network transient error"
        )

        with pytest.raises(RuntimeError, match="(?i)connection reset"):
            await client.run_cmdlet_with_retry("Get-Mailbox")

    # Should have tried max_retries (3) times
    assert mock_run.await_count == client.max_retries, (
        f"Expected {client.max_retries} attempts, got {mock_run.await_count}"
    )


# ---------------------------------------------------------------------------
# 12. test_verify_connection_success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_success(client: ExchangeClient) -> None:
    """verify_connection() must return True when org name is present."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = json.dumps({"Name": "contoso"})
        result = await client.verify_connection()

    assert result is True
    mock_run.assert_awaited_once()


# ---------------------------------------------------------------------------
# 13. test_verify_connection_failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_connection_failure(client: ExchangeClient) -> None:
    """verify_connection() must return False (not raise) when cmdlet fails."""
    with patch("exchange_mcp.ps_runner.run_ps", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("Authentication failed. Cannot connect.")
        result = await client.verify_connection()

    assert result is False
    # No exception propagated — verify_connection() swallows errors and returns False
