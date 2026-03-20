"""Unit tests for exchange_mcp.tools — get_dkim_config, get_dmarc_status,
and check_mobile_devices handlers.

All tests mock ExchangeClient.run_cmdlet_with_retry and relevant
exchange_mcp.tools.dns_utils functions to avoid live Exchange or DNS
connections.

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
    - test_get_dmarc_status_found
    - test_get_dmarc_status_not_found
    - test_get_dmarc_status_missing_domain
    - test_get_dmarc_status_dns_error
    - test_get_dmarc_status_no_client_ok
    - test_check_mobile_devices_with_devices
    - test_check_mobile_devices_no_devices
    - test_check_mobile_devices_with_wipe_history
    - test_check_mobile_devices_not_found
    - test_check_mobile_devices_invalid_email
    - test_check_mobile_devices_no_client
    - test_check_mobile_devices_single_device_dict
    - test_check_mobile_devices_exchange_error_propagates
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exchange_mcp.tools import (
    _get_dkim_config_handler,
    _get_dmarc_status_handler,
    _check_mobile_devices_handler,
)


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


# ===========================================================================
# get_dmarc_status tests
# ===========================================================================

_DMARC_FOUND = {
    "found": True,
    "domain": "contoso.com",
    "version": "DMARC1",
    "policy": "reject",
    "subdomain_policy": "reject",
    "pct": 100,
    "rua": "mailto:dmarc@contoso.com",
    "ruf": None,
    "adkim": "r",
    "aspf": "r",
    "raw": "v=DMARC1; p=reject;",
}

_SPF_FOUND = {
    "found": True,
    "domain": "contoso.com",
    "version": "spf1",
    "mechanisms": ["include:spf.protection.outlook.com"],
    "all": "-all",
    "raw": "v=spf1 include:spf.protection.outlook.com -all",
}


# ---------------------------------------------------------------------------
# Test 10: DMARC and SPF found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dmarc_status_found():
    """Handler returns parsed DMARC and SPF records when both are present."""
    with (
        patch(
            "exchange_mcp.tools.dns_utils.get_dmarc_record",
            new=AsyncMock(return_value=_DMARC_FOUND),
        ),
        patch(
            "exchange_mcp.tools.dns_utils.get_spf_record",
            new=AsyncMock(return_value=_SPF_FOUND),
        ),
    ):
        result = await _get_dmarc_status_handler({"domain": "contoso.com"}, None)

    assert result["domain"] == "contoso.com"
    assert result["dmarc"]["found"] is True
    assert result["dmarc"]["policy"] == "reject"
    assert result["spf"]["found"] is True
    assert result["spf"]["all"] == "-all"


# ---------------------------------------------------------------------------
# Test 11: DMARC and SPF not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dmarc_status_not_found():
    """Handler returns found==False for both records when neither is published."""
    with (
        patch(
            "exchange_mcp.tools.dns_utils.get_dmarc_record",
            new=AsyncMock(return_value={"found": False, "domain": "nodmarc.com"}),
        ),
        patch(
            "exchange_mcp.tools.dns_utils.get_spf_record",
            new=AsyncMock(return_value={"found": False, "domain": "nodmarc.com"}),
        ),
    ):
        result = await _get_dmarc_status_handler({"domain": "nodmarc.com"}, None)

    assert result["dmarc"]["found"] is False
    assert result["spf"]["found"] is False


# ---------------------------------------------------------------------------
# Test 12: Missing domain argument
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dmarc_status_missing_domain():
    """Handler raises RuntimeError with 'domain is required' when domain is absent."""
    with pytest.raises(RuntimeError, match="domain is required"):
        await _get_dmarc_status_handler({}, None)


# ---------------------------------------------------------------------------
# Test 13: DNS lookup error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dmarc_status_dns_error():
    """Handler raises RuntimeError with 'DNS lookup failed' on LookupError."""
    with patch(
        "exchange_mcp.tools.dns_utils.get_dmarc_record",
        new=AsyncMock(side_effect=LookupError("DNS timeout")),
    ):
        with pytest.raises(RuntimeError, match="DNS lookup failed"):
            await _get_dmarc_status_handler({"domain": "contoso.com"}, None)


# ---------------------------------------------------------------------------
# Test 14: No client is OK (pure DNS tool)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dmarc_status_no_client_ok():
    """Handler succeeds with client=None — it is a pure DNS tool."""
    with (
        patch(
            "exchange_mcp.tools.dns_utils.get_dmarc_record",
            new=AsyncMock(return_value=_DMARC_FOUND),
        ),
        patch(
            "exchange_mcp.tools.dns_utils.get_spf_record",
            new=AsyncMock(return_value=_SPF_FOUND),
        ),
    ):
        # Must NOT raise RuntimeError("not available")
        result = await _get_dmarc_status_handler({"domain": "contoso.com"}, None)

    assert result["domain"] == "contoso.com"
    assert result["dmarc"]["found"] is True


# ===========================================================================
# check_mobile_devices tests
# ===========================================================================

_DEVICE_IPHONE = {
    "DeviceFriendlyName": "iPhone 15",
    "DeviceModel": "iPhone15,2",
    "DeviceOS": "iOS 17.3",
    "DeviceUserAgent": "Apple-iPhone15C2/2814.402.1",
    "DeviceID": "ABC123",
    "DeviceType": "iPhone",
    "LastSyncAttemptTime": "/Date(1708000000000)/",
    "Status": "DeviceOK",
    "DeviceAccessState": "Allowed",
    "DeviceWipeSentTime": None,
    "DeviceWipeRequestTime": None,
    "DeviceWipeAckTime": None,
    "LastDeviceWipeRequestor": None,
}

_DEVICE_GALAXY = {
    "DeviceFriendlyName": "Galaxy S24",
    "DeviceModel": "SM-S921B",
    "DeviceOS": "Android 14",
    "DeviceUserAgent": "Samsung-SM-S921B",
    "DeviceID": "DEF456",
    "DeviceType": "EASDevice",
    "LastSyncAttemptTime": "/Date(1708000000000)/",
    "Status": "DeviceOK",
    "DeviceAccessState": "Allowed",
    "DeviceWipeSentTime": None,
    "DeviceWipeRequestTime": None,
    "DeviceWipeAckTime": None,
    "LastDeviceWipeRequestor": None,
}


def _make_mobile_client(return_value):
    """Return a mock ExchangeClient whose run_cmdlet_with_retry returns return_value."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(return_value=return_value)
    return client


# ---------------------------------------------------------------------------
# Test 15: User has multiple devices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_with_devices():
    """Handler returns device_count==2 with correct field mappings."""
    client = _make_mobile_client([_DEVICE_IPHONE, _DEVICE_GALAXY])

    result = await _check_mobile_devices_handler(
        {"email_address": "alice@contoso.com"}, client
    )

    assert result["device_count"] == 2
    assert result["devices"][0]["friendly_name"] == "iPhone 15"
    assert result["devices"][0]["os"] == "iOS 17.3"
    assert result["devices"][0]["access_state"] == "Allowed"


# ---------------------------------------------------------------------------
# Test 16: User has no devices (empty list is valid, not an error)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_no_devices():
    """Handler returns device_count==0 and empty devices list when Exchange returns []."""
    client = _make_mobile_client([])

    result = await _check_mobile_devices_handler(
        {"email_address": "alice@contoso.com"}, client
    )

    assert result["device_count"] == 0
    assert result["devices"] == []


# ---------------------------------------------------------------------------
# Test 17: Device with wipe history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_with_wipe_history():
    """Handler includes all wipe history fields when they are populated."""
    wiped_device = {
        **_DEVICE_IPHONE,
        "DeviceWipeSentTime": "/Date(1708100000000)/",
        "DeviceWipeRequestTime": "/Date(1708090000000)/",
        "DeviceWipeAckTime": "/Date(1708110000000)/",
        "LastDeviceWipeRequestor": "admin@contoso.com",
    }
    client = _make_mobile_client([wiped_device])

    result = await _check_mobile_devices_handler(
        {"email_address": "alice@contoso.com"}, client
    )

    device = result["devices"][0]
    assert device["wipe_sent_time"] == "/Date(1708100000000)/"
    assert device["wipe_request_time"] == "/Date(1708090000000)/"
    assert device["wipe_ack_time"] == "/Date(1708110000000)/"
    assert device["wipe_requestor"] == "admin@contoso.com"


# ---------------------------------------------------------------------------
# Test 18: Mailbox not found — friendly error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_not_found():
    """Handler raises RuntimeError with friendly message when mailbox doesn't exist."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(
        side_effect=RuntimeError("Couldn't find object 'bad@contoso.com'.")
    )

    with pytest.raises(RuntimeError, match="No mailbox found for 'bad@contoso.com'"):
        await _check_mobile_devices_handler(
            {"email_address": "bad@contoso.com"}, client
        )


# ---------------------------------------------------------------------------
# Test 19: Invalid email address
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_invalid_email():
    """Handler raises RuntimeError with 'not a valid email address' for bad UPN."""
    client = MagicMock()

    with pytest.raises(RuntimeError, match="not a valid email address"):
        await _check_mobile_devices_handler(
            {"email_address": "not-an-email"}, client
        )


# ---------------------------------------------------------------------------
# Test 20: No client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_no_client():
    """Handler raises RuntimeError immediately when client is None."""
    with pytest.raises(RuntimeError, match="not available"):
        await _check_mobile_devices_handler(
            {"email_address": "alice@contoso.com"}, None
        )


# ---------------------------------------------------------------------------
# Test 21: Exchange returns single dict (not list)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_single_device_dict():
    """Handler normalises a single-device dict response to a one-element list."""
    client = _make_mobile_client(_DEVICE_IPHONE)

    result = await _check_mobile_devices_handler(
        {"email_address": "alice@contoso.com"}, client
    )

    assert result["device_count"] == 1
    assert result["devices"][0]["friendly_name"] == "iPhone 15"


# ---------------------------------------------------------------------------
# Test 22: Non-not-found Exchange error propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mobile_devices_exchange_error_propagates():
    """Non-not-found RuntimeError from Exchange propagates unchanged."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(
        side_effect=RuntimeError("connection timeout")
    )

    with pytest.raises(RuntimeError, match="connection timeout"):
        await _check_mobile_devices_handler(
            {"email_address": "alice@contoso.com"}, client
        )
