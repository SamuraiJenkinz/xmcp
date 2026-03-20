"""Unit tests for mailbox tool handlers and shared helper functions.

All tests mock ExchangeClient — no live Exchange Online connection is needed.

Tests cover:
    - _validate_upn: valid UPN, invalid formats (no @, empty, no domain)
    - _escape_ps_single_quote: single quote doubling, no-op on clean strings
    - _format_size: GB, MB, KB, B, None, and zero cases
    - _get_mailbox_stats_handler: valid input with merged stats+quota response,
      invalid email rejection, not-found error interception, other Exchange errors
      propagating unchanged, null LastLogonTime, no client, list normalization
    - _search_mailboxes_handler: all three filter modes, empty results, truncation
      detection, invalid filter type, empty filter value, single-result normalization,
      no client, wildcard stripping, not-found as empty result, default max_results
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exchange_mcp.tools import (
    _escape_ps_single_quote,
    _format_size,
    _get_mailbox_stats_handler,
    _search_mailboxes_handler,
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


# ---------------------------------------------------------------------------
# _search_mailboxes_handler tests
# ---------------------------------------------------------------------------

_MB_JOHN = {
    "DisplayName": "John Smith",
    "PrimarySmtpAddress": "john.smith@contoso.com",
    "RecipientTypeDetails": "UserMailbox",
    "Database": "DB01",
}
_MB_JOHN2 = {
    "DisplayName": "John Doe",
    "PrimarySmtpAddress": "john.doe@contoso.com",
    "RecipientTypeDetails": "UserMailbox",
    "Database": "DB02",
}
_MB_JOHN3 = {
    "DisplayName": "John Brown",
    "PrimarySmtpAddress": "john.brown@contoso.com",
    "RecipientTypeDetails": "UserMailbox",
    "Database": "DB01",
}
_MB_SHARED1 = {
    "DisplayName": "Finance Inbox",
    "PrimarySmtpAddress": "finance@contoso.com",
    "RecipientTypeDetails": "SharedMailbox",
    "Database": "DB01",
}
_MB_SHARED2 = {
    "DisplayName": "HR Inbox",
    "PrimarySmtpAddress": "hr@contoso.com",
    "RecipientTypeDetails": "SharedMailbox",
    "Database": "DB02",
}


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_by_name(mock_client: MagicMock) -> None:
    """Filter by name returns list of mailboxes with snake_case fields."""
    mock_client.run_cmdlet_with_retry.return_value = [_MB_JOHN, _MB_JOHN2, _MB_JOHN3]

    result = await _search_mailboxes_handler(
        {"filter_type": "name", "filter_value": "john"}, mock_client
    )

    assert result["count"] == 3
    assert result["truncated"] is False
    assert len(result["results"]) == 3
    first = result["results"][0]
    assert "display_name" in first
    assert "email_address" in first
    assert "mailbox_type" in first
    assert "database" in first
    assert first["display_name"] == "John Smith"
    assert first["email_address"] == "john.smith@contoso.com"


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_by_type(mock_client: MagicMock) -> None:
    """Filter by type returns mailboxes matching the given RecipientTypeDetails."""
    mock_client.run_cmdlet_with_retry.return_value = [_MB_SHARED1, _MB_SHARED2]

    result = await _search_mailboxes_handler(
        {"filter_type": "type", "filter_value": "SharedMailbox"}, mock_client
    )

    assert result["count"] == 2
    assert all(r["mailbox_type"] == "SharedMailbox" for r in result["results"])


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_by_database(mock_client: MagicMock) -> None:
    """Filter by database returns mailboxes on that database."""
    mock_client.run_cmdlet_with_retry.return_value = [_MB_JOHN]

    result = await _search_mailboxes_handler(
        {"filter_type": "database", "filter_value": "DB01"}, mock_client
    )

    assert result["count"] == 1
    assert result["results"][0]["database"] == "DB01"


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_empty_results(mock_client: MagicMock) -> None:
    """Empty list from Exchange returns structured empty response."""
    mock_client.run_cmdlet_with_retry.return_value = []

    result = await _search_mailboxes_handler(
        {"filter_type": "name", "filter_value": "nobody"}, mock_client
    )

    assert result["count"] == 0
    assert result["results"] == []
    assert result["truncated"] is False
    assert "No mailboxes matched" in result["message"]


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_truncation(mock_client: MagicMock) -> None:
    """When Exchange returns more results than max_results, truncated flag is set."""
    # Return 4 results; max_results=3 → truncation detected
    mock_client.run_cmdlet_with_retry.return_value = [
        _MB_JOHN, _MB_JOHN2, _MB_JOHN3, _MB_SHARED1
    ]

    result = await _search_mailboxes_handler(
        {"filter_type": "name", "filter_value": "test", "max_results": 3}, mock_client
    )

    assert result["truncated"] is True
    assert result["count"] == 3
    assert "capped at 3" in result["message"]


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_invalid_filter_type(mock_client: MagicMock) -> None:
    """Unknown filter_type raises RuntimeError with 'Unknown filter_type'."""
    with pytest.raises(RuntimeError, match="Unknown filter_type"):
        await _search_mailboxes_handler(
            {"filter_type": "invalid", "filter_value": "x"}, mock_client
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_empty_filter_value(mock_client: MagicMock) -> None:
    """Empty filter_value raises RuntimeError before calling Exchange."""
    with pytest.raises(RuntimeError, match="filter_value is required"):
        await _search_mailboxes_handler(
            {"filter_type": "name", "filter_value": ""}, mock_client
        )
    mock_client.run_cmdlet_with_retry.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_single_result_dict(mock_client: MagicMock) -> None:
    """Single dict result (not a list) is normalised to a list of 1."""
    mock_client.run_cmdlet_with_retry.return_value = _MB_JOHN

    result = await _search_mailboxes_handler(
        {"filter_type": "name", "filter_value": "john"}, mock_client
    )

    assert result["count"] == 1
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_no_client() -> None:
    """client=None raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError, match="not available"):
        await _search_mailboxes_handler(
            {"filter_type": "name", "filter_value": "john"}, None
        )


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_name_strips_wildcard(mock_client: MagicMock) -> None:
    """Trailing wildcard in name filter_value is stripped before passing to -Anr."""
    mock_client.run_cmdlet_with_retry.return_value = [_MB_JOHN]

    await _search_mailboxes_handler(
        {"filter_type": "name", "filter_value": "john*"}, mock_client
    )

    call_args = mock_client.run_cmdlet_with_retry.call_args
    cmdlet_str = call_args[0][0]
    assert "-Anr 'john'" in cmdlet_str
    assert "-Anr 'john*'" not in cmdlet_str


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_not_found_returns_empty(mock_client: MagicMock) -> None:
    """Exchange 'not found' error for database filter returns empty result (not raised)."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError(
        "Couldn't find the object 'BadDB'."
    )

    result = await _search_mailboxes_handler(
        {"filter_type": "database", "filter_value": "BadDB"}, mock_client
    )

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio(loop_scope="function")
async def test_search_mailboxes_default_max_results(mock_client: MagicMock) -> None:
    """Without max_results arg, cmdlet uses ResultSize 101 (default 100 + 1)."""
    mock_client.run_cmdlet_with_retry.return_value = [_MB_JOHN, _MB_JOHN2, _MB_JOHN3]

    await _search_mailboxes_handler(
        {"filter_type": "name", "filter_value": "test"}, mock_client
    )

    call_args = mock_client.run_cmdlet_with_retry.call_args
    cmdlet_str = call_args[0][0]
    assert "-ResultSize 101" in cmdlet_str
