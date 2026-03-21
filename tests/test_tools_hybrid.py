"""Unit tests for exchange_mcp.tools — get_hybrid_config and get_connector_status handlers.

All tests mock ExchangeClient.run_cmdlet_with_retry to avoid live Exchange
connections.

Tests (get_hybrid_config):
    - test_get_hybrid_config_full_topology
    - test_get_hybrid_config_multiple_org_relationships
    - test_get_hybrid_config_partial_failure
    - test_get_hybrid_config_all_calls_fail
    - test_get_hybrid_config_empty_results
    - test_get_hybrid_config_no_client
    - test_get_hybrid_config_single_dict_normalized

Tests (get_connector_status):
    - test_get_connector_status_all_healthy
    - test_get_connector_status_disabled_connector
    - test_get_connector_status_no_tls
    - test_get_connector_status_invalid_cert
    - test_get_connector_status_cert_unavailable
    - test_get_connector_status_no_connectors
    - test_get_connector_status_no_client
    - test_get_connector_status_exchange_error_propagates
    - test_get_connector_status_single_dict_normalized
    - test_assess_connector_health_direct
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exchange_mcp.tools import (
    _assess_connector_health,
    _get_connector_status_handler,
    _get_hybrid_config_handler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_REL = {
    "Name": "Contoso - Exchange Online",
    "Enabled": True,
    "DomainNames": ["contoso.com", "fabrikam.com"],
    "FreeBusyAccessEnabled": True,
    "FreeBusyAccessLevel": "LimitedDetails",
    "MailboxMoveEnabled": True,
    "DeliveryReportEnabled": True,
    "MailTipsAccessEnabled": True,
    "MailTipsAccessLevel": "All",
    "TargetApplicationUri": "outlook.com",
    "TargetAutodiscoverEpr": "https://autodiscover-s.outlook.com/autodiscover/autodiscover.svc/WSSecurity",
    "TargetSharingEpr": None,
    "TargetOwaURL": None,
    "OrganizationContact": None,
    "ArchiveAccessEnabled": False,
    "PhotosEnabled": True,
}

_FED_TRUST = {
    "Name": "Microsoft Federation Gateway",
    "ApplicationUri": "FYDIBOHF25SPDLT.contoso.com",
    "TokenIssuerUri": "https://nexus.microsoftonline-p.com/",
    "TokenIssuerMetadataEpr": "https://nexus.microsoftonline-p.com/FederationMetadata/2006-12/FederationMetadata.xml",
    "OrgCertThumbprint": "ABCDEF1234567890ABCDEF1234567890ABCDEF12",
    "OrgCertSubject": "CN=FYDIBOHF25SPDLT.contoso.com",
    "OrgCertNotAfter": "2027-01-01T00:00:00.0000000",
    "TokenIssuerCertThumbprint": "FEDCBA0987654321FEDCBA0987654321FEDCBA09",
}

_IOC = {
    "Name": "HybridIOC - contoso.com",
    "Enabled": True,
    "DiscoveryEndpoint": "https://autodiscover-s.outlook.com/autodiscover/autodiscover.svc/WSSecurity",
    "TargetAddressDomains": ["contoso.mail.onmicrosoft.com"],
    "TargetSharingEpr": None,
}

_AVAIL = {
    "Name": "contoso.mail.onmicrosoft.com",
    "ForestName": "contoso.mail.onmicrosoft.com",
    "UserName": None,
    "AccessMethod": "OrgWideFBToken",
    "ProxyUrl": None,
    "UseServiceAccount": False,
}

_HYBRID_SEND = {
    "Name": "Outbound to Office 365",
    "Enabled": True,
    "CloudServicesMailEnabled": True,
    "RequireTLS": True,
    "TlsCertificateName": "<I>CN=DigiCert<S>CN=mail.contoso.com",
    "TlsDomain": "mail.protection.outlook.com",
    "Fqdn": "mail.contoso.com",
    "AddressSpaces": ["contoso.mail.onmicrosoft.com;1"],
    "SmartHosts": ["mail.protection.outlook.com"],
}


def _make_client(*return_values):
    """Return a mock ExchangeClient with run_cmdlet_with_retry using side_effect."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(side_effect=list(return_values))
    return client


# ---------------------------------------------------------------------------
# Test 1: Full topology — all 5 sections populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_full_topology():
    """Handler returns all 5 top-level keys with populated data from 5 cmdlets."""
    client = _make_client(
        [_ORG_REL],
        [_FED_TRUST],
        [_IOC],
        [_AVAIL],
        [_HYBRID_SEND],
    )

    result = await _get_hybrid_config_handler({}, client)

    assert "organization_relationships" in result
    assert "federation_trust" in result
    assert "intra_organization_connectors" in result
    assert "availability_address_spaces" in result
    assert "hybrid_send_connectors" in result

    assert isinstance(result["organization_relationships"], list)
    assert len(result["organization_relationships"]) == 1
    assert result["organization_relationships"][0]["Name"] == "Contoso - Exchange Online"
    assert result["organization_relationships"][0]["Enabled"] is True

    assert isinstance(result["federation_trust"], list)
    assert len(result["federation_trust"]) == 1
    assert result["federation_trust"][0]["OrgCertThumbprint"] == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"

    assert isinstance(result["intra_organization_connectors"], list)
    assert len(result["intra_organization_connectors"]) == 1

    assert isinstance(result["availability_address_spaces"], list)
    assert len(result["availability_address_spaces"]) == 1

    assert isinstance(result["hybrid_send_connectors"], list)
    assert len(result["hybrid_send_connectors"]) == 1
    assert result["hybrid_send_connectors"][0]["CloudServicesMailEnabled"] is True


# ---------------------------------------------------------------------------
# Test 2: Multiple organization relationships
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_multiple_org_relationships():
    """Handler returns list of 2 when Exchange returns 2 org relationships."""
    second_rel = {**_ORG_REL, "Name": "Fabrikam - Exchange Online", "DomainNames": ["fabrikam.com"]}
    client = _make_client(
        [_ORG_REL, second_rel],
        [_FED_TRUST],
        [_IOC],
        [_AVAIL],
        [_HYBRID_SEND],
    )

    result = await _get_hybrid_config_handler({}, client)

    assert len(result["organization_relationships"]) == 2
    names = [r["Name"] for r in result["organization_relationships"]]
    assert "Contoso - Exchange Online" in names
    assert "Fabrikam - Exchange Online" in names


# ---------------------------------------------------------------------------
# Test 3: Partial failure — second call fails, others succeed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_partial_failure():
    """A RuntimeError in one section yields an error key for that section only."""
    client = _make_client(
        [_ORG_REL],
        RuntimeError("connection timeout"),
        [_IOC],
        [_AVAIL],
        [_HYBRID_SEND],
    )

    # Handler must NOT propagate the RuntimeError
    result = await _get_hybrid_config_handler({}, client)

    assert isinstance(result["organization_relationships"], list)
    assert len(result["organization_relationships"]) == 1

    # Failed section is an error dict, not a list
    assert isinstance(result["federation_trust"], dict)
    assert "error" in result["federation_trust"]
    assert "connection timeout" in result["federation_trust"]["error"]

    # Remaining sections succeed
    assert isinstance(result["intra_organization_connectors"], list)
    assert isinstance(result["availability_address_spaces"], list)
    assert isinstance(result["hybrid_send_connectors"], list)


# ---------------------------------------------------------------------------
# Test 4: All calls fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_all_calls_fail():
    """All 5 RuntimeErrors are caught — handler returns 5 error dicts without raising."""
    client = _make_client(
        RuntimeError("err1"),
        RuntimeError("err2"),
        RuntimeError("err3"),
        RuntimeError("err4"),
        RuntimeError("err5"),
    )

    result = await _get_hybrid_config_handler({}, client)

    for key in (
        "organization_relationships",
        "federation_trust",
        "intra_organization_connectors",
        "availability_address_spaces",
        "hybrid_send_connectors",
    ):
        assert isinstance(result[key], dict), f"{key} should be an error dict"
        assert "error" in result[key], f"{key} should have 'error' key"


# ---------------------------------------------------------------------------
# Test 5: Empty results from all calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_empty_results():
    """All 5 sections are empty lists when Exchange returns [] for each cmdlet."""
    client = _make_client([], [], [], [], [])

    result = await _get_hybrid_config_handler({}, client)

    assert result["organization_relationships"] == []
    assert result["federation_trust"] == []
    assert result["intra_organization_connectors"] == []
    assert result["availability_address_spaces"] == []
    assert result["hybrid_send_connectors"] == []


# ---------------------------------------------------------------------------
# Test 6: No client raises immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_no_client():
    """Handler raises RuntimeError immediately when client is None."""
    with pytest.raises(RuntimeError, match="not available"):
        await _get_hybrid_config_handler({}, None)


# ---------------------------------------------------------------------------
# Test 7: Single dict result is normalized to one-element list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_hybrid_config_single_dict_normalized():
    """Handler normalizes a single-dict Exchange response to a one-element list."""
    # Exchange returns a bare dict (not a list) when there is exactly one result
    client = _make_client(
        _ORG_REL,   # single dict, not wrapped in list
        [_FED_TRUST],
        [_IOC],
        [_AVAIL],
        [_HYBRID_SEND],
    )

    result = await _get_hybrid_config_handler({}, client)

    assert isinstance(result["organization_relationships"], list)
    assert len(result["organization_relationships"]) == 1
    assert result["organization_relationships"][0]["Name"] == "Contoso - Exchange Online"


# ===========================================================================
# get_connector_status tests
# ===========================================================================

# ---------------------------------------------------------------------------
# Test data constants
# ---------------------------------------------------------------------------

_VALID_CERT = {
    "thumbprint": "AABBCC1122334455AABBCC1122334455AABBCC11",
    "subject": "CN=mail.contoso.com",
    "issuer": "CN=DigiCert",
    "not_after": "2027-01-01T00:00:00",
    "not_before": "2024-01-01T00:00:00",
    "status": "Valid",
    "is_self_signed": False,
    "has_private_key": True,
    "certificate_domains": ["mail.contoso.com", "autodiscover.contoso.com"],
}

_SEND_CONNECTOR = {
    "Name": "Outbound to Office 365",
    "Enabled": True,
    "CloudServicesMailEnabled": True,
    "RequireTLS": True,
    "TlsCertificateName": "<I>CN=DigiCert<S>CN=mail.contoso.com",
    "TlsDomain": "mail.protection.outlook.com",
    "Fqdn": "mail.contoso.com",
    "MaxMessageSize": "25 MB (26,214,400 bytes)",
    "AddressSpaces": ["contoso.mail.onmicrosoft.com;1"],
    "SmartHosts": ["mail.protection.outlook.com"],
}

_RECV_CONNECTOR = {
    "Name": "Inbound from Office 365",
    "Enabled": True,
    "RequireTLS": True,
    "TlsCertificateName": "<I>CN=DigiCert<S>CN=mail.contoso.com",
    "Fqdn": "mail.contoso.com",
    "Bindings": ["0.0.0.0:25"],
    "RemoteIPRanges": ["104.47.0.0/17"],
    "AuthMechanism": "Tls",
    "PermissionGroups": "AnonymousUsers",
    "TransportRole": "FrontendTransport",
    "Server": "EX01",
}


# ---------------------------------------------------------------------------
# Test 1: All healthy — send + receive with valid cert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_all_healthy():
    """Handler returns all_healthy=True when both send and receive connectors are healthy."""
    client = MagicMock()
    # First call: send connectors; second call: receive connectors
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[
        [_SEND_CONNECTOR],
        [_RECV_CONNECTOR],
    ])

    with patch(
        "exchange_mcp.tools._lookup_cert_for_fqdn",
        new=AsyncMock(return_value=_VALID_CERT),
    ):
        result = await _get_connector_status_handler({}, client)

    assert result["all_healthy"] is True
    assert result["send_connector_count"] == 1
    assert result["receive_connector_count"] == 1

    send = result["send_connectors"][0]
    assert send["healthy"] is True
    assert send["error"] is None
    assert send["type"] == "send"

    recv = result["receive_connectors"][0]
    assert recv["healthy"] is True
    assert recv["error"] is None
    assert recv["type"] == "receive"


# ---------------------------------------------------------------------------
# Test 2: Disabled connector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_disabled_connector():
    """Disabled send connector is marked unhealthy with 'disabled' in error."""
    disabled = {**_SEND_CONNECTOR, "Enabled": False}
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[
        [disabled],
        [],
    ])

    with patch(
        "exchange_mcp.tools._lookup_cert_for_fqdn",
        new=AsyncMock(return_value=_VALID_CERT),
    ):
        result = await _get_connector_status_handler({}, client)

    assert result["all_healthy"] is False
    assert result["send_connectors"][0]["healthy"] is False
    assert "disabled" in result["send_connectors"][0]["error"].lower()


# ---------------------------------------------------------------------------
# Test 3: RequireTLS not set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_no_tls():
    """Connector with RequireTLS=False is marked unhealthy."""
    no_tls = {**_SEND_CONNECTOR, "RequireTLS": False}
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[
        [no_tls],
        [],
    ])

    with patch(
        "exchange_mcp.tools._lookup_cert_for_fqdn",
        new=AsyncMock(return_value=_VALID_CERT),
    ):
        result = await _get_connector_status_handler({}, client)

    assert result["all_healthy"] is False
    connector = result["send_connectors"][0]
    assert connector["healthy"] is False
    assert "RequireTLS" in connector["error"]


# ---------------------------------------------------------------------------
# Test 4: Invalid certificate status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_invalid_cert():
    """Connector with an expired/invalid cert is marked unhealthy."""
    expired_cert = {**_VALID_CERT, "status": "DateInvalid"}
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[
        [_SEND_CONNECTOR],
        [],
    ])

    with patch(
        "exchange_mcp.tools._lookup_cert_for_fqdn",
        new=AsyncMock(return_value=expired_cert),
    ):
        result = await _get_connector_status_handler({}, client)

    assert result["all_healthy"] is False
    connector = result["send_connectors"][0]
    assert connector["healthy"] is False
    assert "DateInvalid" in connector["error"]


# ---------------------------------------------------------------------------
# Test 5: Certificate lookup unavailable (None) — treat as healthy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_cert_unavailable():
    """Connector is healthy when cert lookup returns None (Exchange Online environment)."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[
        [_SEND_CONNECTOR],
        [],
    ])

    with patch(
        "exchange_mcp.tools._lookup_cert_for_fqdn",
        new=AsyncMock(return_value=None),
    ):
        result = await _get_connector_status_handler({}, client)

    assert result["all_healthy"] is True
    assert result["send_connectors"][0]["healthy"] is True
    assert result["send_connectors"][0]["certificate"] is None


# ---------------------------------------------------------------------------
# Test 6: No connectors found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_no_connectors():
    """Empty connector lists return counts of zero and all_healthy=True."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[[], []])

    result = await _get_connector_status_handler({}, client)

    assert result["send_connector_count"] == 0
    assert result["receive_connector_count"] == 0
    assert result["all_healthy"] is True
    assert result["send_connectors"] == []
    assert result["receive_connectors"] == []


# ---------------------------------------------------------------------------
# Test 7: No client raises immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_no_client():
    """Handler raises RuntimeError immediately when client is None."""
    with pytest.raises(RuntimeError, match="not available"):
        await _get_connector_status_handler({}, None)


# ---------------------------------------------------------------------------
# Test 8: Exchange error propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_exchange_error_propagates():
    """RuntimeError from send connector cmdlet is propagated to caller."""
    client = MagicMock()
    client.run_cmdlet_with_retry = AsyncMock(
        side_effect=RuntimeError("Exchange throttle limit exceeded")
    )

    with pytest.raises(RuntimeError, match="throttle"):
        await _get_connector_status_handler({}, client)


# ---------------------------------------------------------------------------
# Test 9: Single dict result normalized to one-element list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_connector_status_single_dict_normalized():
    """Handler normalizes a single-dict Exchange response to one connector."""
    client = MagicMock()
    # Exchange returns a bare dict instead of a list when there is one connector
    client.run_cmdlet_with_retry = AsyncMock(side_effect=[
        _SEND_CONNECTOR,  # dict, not list
        [],
    ])

    with patch(
        "exchange_mcp.tools._lookup_cert_for_fqdn",
        new=AsyncMock(return_value=_VALID_CERT),
    ):
        result = await _get_connector_status_handler({}, client)

    assert result["send_connector_count"] == 1
    assert result["send_connectors"][0]["name"] == "Outbound to Office 365"


# ---------------------------------------------------------------------------
# Test 10: _assess_connector_health direct unit tests
# ---------------------------------------------------------------------------


def test_assess_connector_health_direct():
    """_assess_connector_health returns correct (healthy, error) tuples."""
    # Case 1: disabled connector
    healthy, err = _assess_connector_health({"Enabled": False, "RequireTLS": True}, _VALID_CERT)
    assert healthy is False
    assert "disabled" in err.lower()

    # Case 2: RequireTLS not set
    healthy, err = _assess_connector_health({"Enabled": True, "RequireTLS": False}, _VALID_CERT)
    assert healthy is False
    assert "RequireTLS" in err

    # Case 3: valid cert
    healthy, err = _assess_connector_health({"Enabled": True, "RequireTLS": True}, _VALID_CERT)
    assert healthy is True
    assert err is None

    # Case 4: cert unavailable (None) — treat as healthy
    healthy, err = _assess_connector_health({"Enabled": True, "RequireTLS": True}, None)
    assert healthy is True
    assert err is None

    # Case 5: cert with non-Valid status
    bad_cert = {**_VALID_CERT, "status": "Revoked"}
    healthy, err = _assess_connector_health({"Enabled": True, "RequireTLS": True}, bad_cert)
    assert healthy is False
    assert "Revoked" in err
