"""Unit tests for exchange_mcp.exchange_client.ExchangeClient.

All tests mock ``exchange_mcp.ps_runner.run_ps`` to avoid actual PowerShell
execution.  No live Exchange Online connection is required.

Tests cover:
    - Auth mode auto-detection (interactive vs certificate)
    - Environment variable validation for certificate mode
    - PowerShell script template structure (both auth modes)
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
def env_vars_cba(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set Azure AD credential env vars for certificate-based auth tests."""
    monkeypatch.setenv("AZURE_CERT_THUMBPRINT", "AABBCCDDEEFF1122334455667788990011223344")
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("AZURE_TENANT_DOMAIN", "contoso.onmicrosoft.com")


@pytest.fixture()
def env_vars_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no cert env vars → interactive auth mode."""
    monkeypatch.delenv("AZURE_CERT_THUMBPRINT", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_TENANT_DOMAIN", raising=False)


@pytest.fixture()
def client(env_vars_interactive: None) -> ExchangeClient:
    """Return an ExchangeClient in interactive auth mode."""
    return ExchangeClient(timeout=30, max_retries=3)


@pytest.fixture()
def client_cba(env_vars_cba: None) -> ExchangeClient:
    """Return an ExchangeClient in certificate auth mode."""
    return ExchangeClient(timeout=30, max_retries=3)


# ---------------------------------------------------------------------------
# 1. test_init_interactive_no_env_vars
# ---------------------------------------------------------------------------


def test_init_interactive_no_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """ExchangeClient() uses interactive auth when no cert env vars are set."""
    monkeypatch.delenv("AZURE_CERT_THUMBPRINT", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_TENANT_DOMAIN", raising=False)

    client = ExchangeClient()
    assert client.auth_mode == "interactive"


# ---------------------------------------------------------------------------
# 1b. test_init_cba_missing_partial_env_vars
# ---------------------------------------------------------------------------


def test_init_cba_missing_partial_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """ExchangeClient() raises if AZURE_CERT_THUMBPRINT is set but other vars missing."""
    monkeypatch.setenv("AZURE_CERT_THUMBPRINT", "AABBCCDD")
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_TENANT_DOMAIN", raising=False)

    with pytest.raises(EnvironmentError) as exc_info:
        ExchangeClient()

    msg = str(exc_info.value)
    assert "AZURE_CLIENT_ID" in msg
    assert "AZURE_TENANT_DOMAIN" in msg


# ---------------------------------------------------------------------------
# 2. test_init_success_interactive
# ---------------------------------------------------------------------------


def test_init_success_interactive(env_vars_interactive: None) -> None:
    """ExchangeClient() works without any env vars in interactive mode."""
    client = ExchangeClient()
    assert client.timeout == 60
    assert client.max_retries == 3
    assert client.default_result_size == 100
    assert client.auth_mode == "interactive"


# ---------------------------------------------------------------------------
# 2b. test_init_success_cba
# ---------------------------------------------------------------------------


def test_init_success_cba(env_vars_cba: None) -> None:
    """ExchangeClient() auto-detects certificate mode when cert env vars are set."""
    client = ExchangeClient()
    assert client.auth_mode == "certificate"


# ---------------------------------------------------------------------------
# 3. test_build_cmdlet_script_interactive
# ---------------------------------------------------------------------------


def test_build_cmdlet_script_interactive(client: ExchangeClient) -> None:
    """_build_cmdlet_script() in interactive mode uses Connect-ExchangeOnline without CBA params."""
    cmdlet = "Get-Mailbox -Identity user@contoso.com"
    script = client._build_cmdlet_script(cmdlet)

    # Interactive auth — no CBA params
    assert "Connect-ExchangeOnline" in script, "Missing Connect-ExchangeOnline"
    assert "CertificateThumbPrint" not in script, "Interactive mode must NOT have CertificateThumbPrint"

    # JSON serialisation contract
    assert "ConvertTo-Json -Depth 10" in script, "Must use ConvertTo-Json -Depth 10"

    # Clean disconnect in finally
    assert "Disconnect-ExchangeOnline" in script, "Missing Disconnect-ExchangeOnline"
    assert "finally" in script, "Disconnect must be inside a finally block"

    # The requested cmdlet must appear in the script
    assert cmdlet in script, f"Cmdlet {cmdlet!r} not found in script"


# ---------------------------------------------------------------------------
# 3b. test_build_cmdlet_script_cba
# ---------------------------------------------------------------------------


def test_build_cmdlet_script_cba(client_cba: ExchangeClient) -> None:
    """_build_cmdlet_script() in certificate mode includes CBA params."""
    cmdlet = "Get-Mailbox -Identity user@contoso.com"
    script = client_cba._build_cmdlet_script(cmdlet)

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
