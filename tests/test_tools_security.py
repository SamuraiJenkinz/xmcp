"""Unit tests for exchange_mcp.tools — get_dkim_config handler.

All tests mock ExchangeClient.run_cmdlet_with_retry and
exchange_mcp.tools.dns_utils.get_cname_record to avoid live Exchange
or DNS connections.

Tests:
    - test_get_dkim_config_single_domain_match
    - test_get_dkim_config_cname_mismatch
    - test_get_dkim_config_cname_not_published
    - test_get_dkim_config_all_domains
    - test_get_dkim_config_domain_not_found
    - test_get_dkim_config_no_client
    - test_get_dkim_config_dns_error_graceful
    - test_get_dkim_config_exchange_error_propagates
    - test_get_dkim_config_empty_result
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exchange_mcp.tools import _get_dkim_config_handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEL1_EXPECTED = "selector1-contoso-com._domainkey.contoso.onmicrosoft.com"
_SEL2_EXPECTED = "selector2-contoso-com._domainkey.contoso.onmicrosoft.com"

_DKIM_ROW = {
    "Name": "contoso.com",
    "Enabled": True,
    "Status": "Valid",
    "Selector1CNAME": _SEL1_EXPECTED,
    "Selector2CNAME": _SEL2_EXPECTED,
    "KeyCreationTime": "/Date(1708000000000)/",
    "RotateOnDate": None,
}


def _make_client(return_value):
    """Return a mock ExchangeClient whose run_cmdlet_with_retry returns return_value."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(return_value=return_value)
    return client


# ---------------------------------------------------------------------------
# Test 1: Single domain — CNAME matches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_single_domain_match():
    """Handler returns domain_count==1 with selector DNS match == True when CNAMEs match."""
    client = _make_client(_DKIM_ROW)

    with patch(
        "exchange_mcp.tools.dns_utils.get_cname_record",
        new=AsyncMock(side_effect=[_SEL1_EXPECTED, _SEL2_EXPECTED]),
    ):
        result = await _get_dkim_config_handler({"domain": "contoso.com"}, client)

    assert result["domain_count"] == 1
    domain = result["domains"][0]
    assert domain["domain"] == "contoso.com"
    assert domain["enabled"] is True
    assert domain["status"] == "Valid"
    assert domain["selector1_dns_match"] is True
    assert domain["selector2_dns_match"] is True
    assert domain["selector1_cname_published"] == _SEL1_EXPECTED
    assert domain["selector2_cname_published"] == _SEL2_EXPECTED


# ---------------------------------------------------------------------------
# Test 2: CNAME mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_cname_mismatch():
    """Handler sets selector1_dns_match == False when published CNAME differs from expected."""
    client = _make_client(_DKIM_ROW)
    wrong_cname = "wrong-selector._domainkey.contoso.onmicrosoft.com"

    with patch(
        "exchange_mcp.tools.dns_utils.get_cname_record",
        new=AsyncMock(side_effect=[wrong_cname, _SEL2_EXPECTED]),
    ):
        result = await _get_dkim_config_handler({"domain": "contoso.com"}, client)

    domain = result["domains"][0]
    assert domain["selector1_dns_match"] is False
    assert domain["selector2_dns_match"] is True
    assert domain["selector1_cname_published"] == wrong_cname


# ---------------------------------------------------------------------------
# Test 3: CNAME not published (returns None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_cname_not_published():
    """Handler sets dns_match == False and published == None when CNAMEs absent from DNS."""
    client = _make_client(_DKIM_ROW)

    with patch(
        "exchange_mcp.tools.dns_utils.get_cname_record",
        new=AsyncMock(return_value=None),
    ):
        result = await _get_dkim_config_handler({"domain": "contoso.com"}, client)

    domain = result["domains"][0]
    assert domain["selector1_cname_published"] is None
    assert domain["selector2_cname_published"] is None
    # Expected is set but not published — match is False
    assert domain["selector1_dns_match"] is False
    assert domain["selector2_dns_match"] is False


# ---------------------------------------------------------------------------
# Test 4: All domains (no domain filter)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_all_domains():
    """Handler without domain filter returns all domains from Exchange."""
    fabrikam_row = {
        "Name": "fabrikam.com",
        "Enabled": True,
        "Status": "Valid",
        "Selector1CNAME": "selector1-fabrikam-com._domainkey.fabrikam.onmicrosoft.com",
        "Selector2CNAME": "selector2-fabrikam-com._domainkey.fabrikam.onmicrosoft.com",
        "KeyCreationTime": "/Date(1708100000000)/",
        "RotateOnDate": None,
    }
    client = _make_client([_DKIM_ROW, fabrikam_row])

    with patch(
        "exchange_mcp.tools.dns_utils.get_cname_record",
        new=AsyncMock(return_value=None),
    ):
        result = await _get_dkim_config_handler({}, client)

    assert result["domain_count"] == 2
    domains = [d["domain"] for d in result["domains"]]
    assert "contoso.com" in domains
    assert "fabrikam.com" in domains


# ---------------------------------------------------------------------------
# Test 5: Domain not found — friendly error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_domain_not_found():
    """Handler raises RuntimeError with friendly message when domain doesn't exist."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(
        side_effect=RuntimeError("Couldn't find object 'baddomain.com'.")
    )

    with pytest.raises(RuntimeError, match="No DKIM signing configuration found for domain 'baddomain.com'"):
        await _get_dkim_config_handler({"domain": "baddomain.com"}, client)


# ---------------------------------------------------------------------------
# Test 6: No client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_no_client():
    """Handler raises RuntimeError immediately when client is None."""
    with pytest.raises(RuntimeError, match="not available"):
        await _get_dkim_config_handler({"domain": "contoso.com"}, None)


# ---------------------------------------------------------------------------
# Test 7: DNS LookupError — graceful (match stays None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_dns_error_graceful():
    """Handler does NOT propagate LookupError — dns_match stays None on DNS failure."""
    client = _make_client(_DKIM_ROW)

    with patch(
        "exchange_mcp.tools.dns_utils.get_cname_record",
        new=AsyncMock(side_effect=LookupError("CNAME lookup failed for 'selector1._domainkey.contoso.com': Timeout")),
    ):
        result = await _get_dkim_config_handler({"domain": "contoso.com"}, client)

    domain = result["domains"][0]
    # DNS error swallowed — match is None (unknown), published is None
    assert domain["selector1_dns_match"] is None
    assert domain["selector2_dns_match"] is None
    assert domain["selector1_cname_published"] is None
    assert domain["selector2_cname_published"] is None


# ---------------------------------------------------------------------------
# Test 8: Exchange error propagates as-is
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_exchange_error_propagates():
    """Non-not-found RuntimeError from Exchange propagates unchanged."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(
        side_effect=RuntimeError("connection timeout")
    )

    with pytest.raises(RuntimeError, match="connection timeout"):
        await _get_dkim_config_handler({"domain": "contoso.com"}, client)


# ---------------------------------------------------------------------------
# Test 9: Empty Exchange result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dkim_config_empty_result():
    """Handler returns domain_count==0 and empty domains list when Exchange returns []."""
    client = _make_client([])

    result = await _get_dkim_config_handler({}, client)

    assert result["domain_count"] == 0
    assert result["domains"] == []
