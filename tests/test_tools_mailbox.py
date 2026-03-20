"""Unit tests for mailbox tool handlers and shared helper functions.

All tests mock ExchangeClient — no live Exchange Online connection is needed.

Tests cover:
    - _validate_upn: valid UPN, invalid formats (no @, empty, no domain)
    - _escape_ps_single_quote: single quote doubling, no-op on clean strings
    - _format_size: GB, MB, KB, B, None, and zero cases
    - _get_mailbox_stats_handler: valid input with merged stats+quota response,
      invalid email rejection, not-found error interception, other Exchange errors
      propagating unchanged, null LastLogonTime, no client, list normalization
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exchange_mcp.tools import (
    _escape_ps_single_quote,
    _format_size,
    _get_mailbox_stats_handler,
    _validate_upn,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a mock ExchangeClient with an async run_cmdlet_with_retry."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# _validate_upn tests
# ---------------------------------------------------------------------------


def test_validate_upn_valid() -> None:
    """Valid UPN does not raise."""
    _validate_upn("user@domain.com")  # must not raise


def test_validate_upn_invalid_no_at() -> None:
    """String without @ raises RuntimeError with 'not a valid email address'."""
    with pytest.raises(RuntimeError, match="not a valid email address"):
        _validate_upn("notanemail")


def test_validate_upn_invalid_empty() -> None:
    """Empty string raises RuntimeError."""
    with pytest.raises(RuntimeError, match="not a valid email address"):
        _validate_upn("")


def test_validate_upn_invalid_no_domain() -> None:
    """Address missing domain part after @ raises RuntimeError."""
    with pytest.raises(RuntimeError, match="not a valid email address"):
        _validate_upn("user@")


# ---------------------------------------------------------------------------
# _escape_ps_single_quote tests
# ---------------------------------------------------------------------------


def test_escape_ps_single_quote() -> None:
    """Single quotes are doubled for PowerShell string safety."""
    assert _escape_ps_single_quote("O'Brien") == "O''Brien"


def test_escape_ps_single_quote_no_quotes() -> None:
    """Strings without single quotes are returned unchanged."""
    assert _escape_ps_single_quote("normal") == "normal"


# ---------------------------------------------------------------------------
# _format_size tests
# ---------------------------------------------------------------------------


def test_format_size_gb() -> None:
    """Byte count >= 1 GB renders with one decimal place in GB."""
    assert _format_size(2_578_497_536) == "2.4 GB"


def test_format_size_mb() -> None:
    """Byte count >= 1 MB and < 1 GB renders in MB."""
    assert _format_size(52_428_800) == "50.0 MB"


def test_format_size_kb() -> None:
    """Byte count >= 1 KB and < 1 MB renders in KB."""
    assert _format_size(1_024) == "1.0 KB"


def test_format_size_bytes() -> None:
    """Byte count < 1 KB renders as raw bytes."""
    assert _format_size(500) == "500 B"


def test_format_size_none() -> None:
    """None input returns None (handles missing Exchange data)."""
    assert _format_size(None) is None


def test_format_size_zero() -> None:
    """Zero bytes renders as '0 B'."""
    assert _format_size(0) == "0 B"


# ---------------------------------------------------------------------------
# _get_mailbox_stats_handler tests
# ---------------------------------------------------------------------------

_STATS_DICT = {
    "DisplayName": "Alice Smith",
    "ItemCount": 1234,
    "TotalItemSizeBytes": 2_578_497_536,
    "LastLogonTime": "/Date(1708000000000)/",
    "Database": "DB01",
}

_QUOTA_DICT = {
    "PrimarySmtpAddress": "alice@contoso.com",
    "RecipientTypeDetails": "UserMailbox",
    "ProhibitSendQuota": "49.5 GB",
    "ProhibitSendReceiveQuota": "50 GB",
    "IssueWarningQuota": "49 GB",
}


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_valid(mock_client: MagicMock) -> None:
    """Valid email returns merged stats and quota data with human-friendly size."""
    mock_client.run_cmdlet_with_retry.side_effect = [_STATS_DICT, _QUOTA_DICT]

    result = await _get_mailbox_stats_handler(
        {"email_address": "alice@contoso.com"}, mock_client
    )

    assert result["email_address"] == "alice@contoso.com"
    assert result["display_name"] == "Alice Smith"
    assert result["total_size"] == "2.4 GB"
    assert result["total_size_bytes"] == 2_578_497_536
    assert result["item_count"] == 1234
    assert result["database"] == "DB01"
    assert result["mailbox_type"] == "UserMailbox"
    assert result["last_logon"] == "/Date(1708000000000)/"
    quotas = result["quotas"]
    assert "issue_warning" in quotas
    assert "prohibit_send" in quotas
    assert "prohibit_send_receive" in quotas
    assert quotas["prohibit_send"] == "49.5 GB"


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_invalid_email(mock_client: MagicMock) -> None:
    """Invalid email raises RuntimeError before calling Exchange."""
    with pytest.raises(RuntimeError, match="not a valid email address"):
        await _get_mailbox_stats_handler(
            {"email_address": "not-an-email"}, mock_client
        )
    mock_client.run_cmdlet_with_retry.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_not_found(mock_client: MagicMock) -> None:
    """Exchange 'not found' error is intercepted and re-raised with friendly message."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError(
        "Couldn't find the object 'bad@domain.com'."
    )

    with pytest.raises(RuntimeError, match="No mailbox found for 'bad@domain.com'"):
        await _get_mailbox_stats_handler(
            {"email_address": "bad@domain.com"}, mock_client
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_exchange_error_propagates(mock_client: MagicMock) -> None:
    """Non-not-found RuntimeErrors propagate unchanged."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError(
        "connection reset by peer"
    )

    with pytest.raises(RuntimeError, match="connection reset by peer"):
        await _get_mailbox_stats_handler(
            {"email_address": "alice@contoso.com"}, mock_client
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_null_last_logon(mock_client: MagicMock) -> None:
    """Null LastLogonTime passes through as None without crashing."""
    stats = {**_STATS_DICT, "LastLogonTime": None}
    mock_client.run_cmdlet_with_retry.side_effect = [stats, _QUOTA_DICT]

    result = await _get_mailbox_stats_handler(
        {"email_address": "alice@contoso.com"}, mock_client
    )

    assert result["last_logon"] is None


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_no_client() -> None:
    """client=None raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError, match="not available"):
        await _get_mailbox_stats_handler({"email_address": "alice@contoso.com"}, None)


@pytest.mark.asyncio(loop_scope="function")
async def test_get_mailbox_stats_stats_returns_list(mock_client: MagicMock) -> None:
    """Single-element list from Exchange is normalised to a dict transparently."""
    mock_client.run_cmdlet_with_retry.side_effect = [[_STATS_DICT], _QUOTA_DICT]

    result = await _get_mailbox_stats_handler(
        {"email_address": "alice@contoso.com"}, mock_client
    )

    assert result["display_name"] == "Alice Smith"
    assert result["total_size"] == "2.4 GB"
