"""Unit tests for the mail flow tool handlers (Phase 5).

All tests mock ExchangeClient -- no live Exchange Online connection is needed.

check_mail_flow tests cover:
    - test_check_mail_flow_external_routing: wildcard connector matches external domain
    - test_check_mail_flow_internal_routing: both domains accepted -> internal delivery
    - test_check_mail_flow_unroutable: no matching connector, not accepted
    - test_check_mail_flow_smart_host_routing: smart host next hop reported
    - test_check_mail_flow_missing_sender: RuntimeError before Exchange call
    - test_check_mail_flow_missing_recipient: RuntimeError before Exchange call
    - test_check_mail_flow_invalid_sender_format: _validate_upn catches bad format
    - test_check_mail_flow_no_client: None client raises immediately
    - test_check_mail_flow_disabled_connector_skipped: enabled-only matching
    - test_check_mail_flow_exchange_error_propagates: RuntimeError passthrough
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exchange_mcp.tools import (
    _check_mail_flow_handler,
    _get_smtp_connectors_handler,
    _get_transport_queues_handler,
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
# Shared test data helpers
# ---------------------------------------------------------------------------

_ACCEPTED_CONTOSO = [
    {"DomainName": "contoso.com", "DomainType": "Authoritative", "Default": True}
]

_SEND_WILDCARD_TLS = [
    {
        "Name": "Internet Outbound",
        "Enabled": True,
        "AddressSpaces": ["SMTP:*;1"],
        "DNSRoutingEnabled": True,
        "SmartHosts": [],
        "RequireTLS": True,
        "TlsDomain": None,
        "Fqdn": "mail.contoso.com",
        "SourceTransportServers": ["EX01"],
    }
]

_RECV_DEFAULT = [
    {
        "Name": "Default Frontend",
        "Enabled": True,
        "AuthMechanism": "Tls",
        "PermissionGroups": "AnonymousUsers",
        "RequireTLS": False,
        "TransportRole": "FrontendTransport",
        "Server": "EX01",
        "Fqdn": "mail.contoso.com",
    }
]


# ---------------------------------------------------------------------------
# 1. test_check_mail_flow_external_routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_external_routing(mock_client: MagicMock) -> None:
    """Wildcard send connector matches external recipient domain."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Accepted domains
        _ACCEPTED_CONTOSO,
        # Call 2: Send connectors (wildcard)
        _SEND_WILDCARD_TLS,
        # Call 3: Receive connectors
        _RECV_DEFAULT,
    ]

    result = await _check_mail_flow_handler(
        {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
        mock_client,
    )

    assert result["routing_type"] == "external"
    assert result["sender_is_internal"] is True
    assert result["recipient_is_internal"] is False
    assert result["matching_connector_count"] == 1
    assert result["matching_send_connectors"][0]["name"] == "Internet Outbound"
    assert "Internet Outbound" in result["routing_description"]
    assert result["sender"] == "alice@contoso.com"
    assert result["recipient"] == "bob@fabrikam.com"
    assert result["recipient_domain"] == "fabrikam.com"
    assert result["sender_domain"] == "contoso.com"


# ---------------------------------------------------------------------------
# 2. test_check_mail_flow_internal_routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_internal_routing(mock_client: MagicMock) -> None:
    """Both sender and recipient domains accepted -> internal delivery route."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Accepted domains (both contoso.com and fabrikam.com are internal)
        [
            {"DomainName": "contoso.com", "DomainType": "Authoritative", "Default": True},
            {"DomainName": "fabrikam.com", "DomainType": "Authoritative", "Default": False},
        ],
        # Call 2: Send connectors
        _SEND_WILDCARD_TLS,
        # Call 3: Receive connectors
        _RECV_DEFAULT,
    ]

    result = await _check_mail_flow_handler(
        {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
        mock_client,
    )

    assert result["routing_type"] == "internal"
    assert result["recipient_is_internal"] is True
    assert result["sender_is_internal"] is True
    assert "Internal delivery" in result["routing_description"]
    assert "accepted domain" in result["routing_description"]


# ---------------------------------------------------------------------------
# 3. test_check_mail_flow_unroutable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_unroutable(mock_client: MagicMock) -> None:
    """No matching connector for external domain -> unroutable result."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Accepted domains (only contoso.com)
        _ACCEPTED_CONTOSO,
        # Call 2: Send connectors (partner-specific, does not match fabrikam.com)
        [
            {
                "Name": "Partner Connector",
                "Enabled": True,
                "AddressSpaces": ["SMTP:partner.com;1"],
                "DNSRoutingEnabled": True,
                "SmartHosts": [],
                "RequireTLS": True,
                "TlsDomain": None,
                "Fqdn": "mail.contoso.com",
                "SourceTransportServers": ["EX01"],
            }
        ],
        # Call 3: Receive connectors
        _RECV_DEFAULT,
    ]

    result = await _check_mail_flow_handler(
        {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
        mock_client,
    )

    assert result["routing_type"] == "unroutable"
    assert result["matching_connector_count"] == 0
    assert "No send connector" in result["routing_description"]
    assert "fabrikam.com" in result["routing_description"]


# ---------------------------------------------------------------------------
# 4. test_check_mail_flow_smart_host_routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_smart_host_routing(mock_client: MagicMock) -> None:
    """Send connector with smart host uses smart host as next hop in description."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Accepted domains
        _ACCEPTED_CONTOSO,
        # Call 2: Send connector with smart host, not DNS routing
        [
            {
                "Name": "Smart Host Relay",
                "Enabled": True,
                "AddressSpaces": ["SMTP:*;1"],
                "DNSRoutingEnabled": False,
                "SmartHosts": ["relay.contoso.com"],
                "RequireTLS": False,
                "TlsDomain": None,
                "Fqdn": "mail.contoso.com",
                "SourceTransportServers": ["EX01"],
            }
        ],
        # Call 3: Receive connectors
        _RECV_DEFAULT,
    ]

    result = await _check_mail_flow_handler(
        {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
        mock_client,
    )

    assert result["routing_type"] == "external"
    assert "Smart host" in result["routing_description"]
    assert "relay.contoso.com" in result["routing_description"]
    assert result["matching_send_connectors"][0]["smart_hosts"] == ["relay.contoso.com"]


# ---------------------------------------------------------------------------
# 5. test_check_mail_flow_missing_sender
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_missing_sender(mock_client: MagicMock) -> None:
    """Missing sender raises RuntimeError before any Exchange call."""
    with pytest.raises(RuntimeError) as exc_info:
        await _check_mail_flow_handler(
            {"recipient": "bob@contoso.com"},
            mock_client,
        )

    assert "sender is required" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 6. test_check_mail_flow_missing_recipient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_missing_recipient(mock_client: MagicMock) -> None:
    """Missing recipient raises RuntimeError before any Exchange call."""
    with pytest.raises(RuntimeError) as exc_info:
        await _check_mail_flow_handler(
            {"sender": "alice@contoso.com"},
            mock_client,
        )

    assert "recipient is required" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 7. test_check_mail_flow_invalid_sender_format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_invalid_sender_format(mock_client: MagicMock) -> None:
    """Invalid sender email format raises RuntimeError from _validate_upn."""
    with pytest.raises(RuntimeError) as exc_info:
        await _check_mail_flow_handler(
            {"sender": "not-an-email", "recipient": "bob@contoso.com"},
            mock_client,
        )

    assert "not a valid email address" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 8. test_check_mail_flow_no_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_no_client() -> None:
    """None client raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError) as exc_info:
        await _check_mail_flow_handler(
            {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
            None,
        )

    assert "not available" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 9. test_check_mail_flow_disabled_connector_skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_disabled_connector_skipped(mock_client: MagicMock) -> None:
    """Disabled connector is skipped; only enabled connector that matches is returned."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Accepted domains
        _ACCEPTED_CONTOSO,
        # Call 2: Two send connectors -- first is disabled but matches, second is enabled
        [
            {
                "Name": "Disabled Wildcard",
                "Enabled": False,
                "AddressSpaces": ["SMTP:*;1"],
                "DNSRoutingEnabled": True,
                "SmartHosts": [],
                "RequireTLS": False,
                "TlsDomain": None,
                "Fqdn": "mail.contoso.com",
                "SourceTransportServers": ["EX01"],
            },
            {
                "Name": "Enabled Internet",
                "Enabled": True,
                "AddressSpaces": ["SMTP:*;2"],
                "DNSRoutingEnabled": True,
                "SmartHosts": [],
                "RequireTLS": True,
                "TlsDomain": None,
                "Fqdn": "mail2.contoso.com",
                "SourceTransportServers": ["EX02"],
            },
        ],
        # Call 3: Receive connectors
        _RECV_DEFAULT,
    ]

    result = await _check_mail_flow_handler(
        {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
        mock_client,
    )

    assert result["matching_connector_count"] == 1
    assert result["matching_send_connectors"][0]["name"] == "Enabled Internet"
    assert result["routing_type"] == "external"


# ---------------------------------------------------------------------------
# 10. test_check_mail_flow_exchange_error_propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_check_mail_flow_exchange_error_propagates(mock_client: MagicMock) -> None:
    """RuntimeError from first Exchange call propagates unchanged."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError("connection timeout")

    with pytest.raises(RuntimeError) as exc_info:
        await _check_mail_flow_handler(
            {"sender": "alice@contoso.com", "recipient": "bob@fabrikam.com"},
            mock_client,
        )

    assert "connection timeout" in str(exc_info.value)


# ===========================================================================
# get_transport_queues tests
# ===========================================================================


# ---------------------------------------------------------------------------
# 1. test_get_transport_queues_all_servers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_all_servers(mock_client: MagicMock) -> None:
    """All servers discovered via Get-TransportService; backlog flagged on EX02."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Transport service discovery
        [{"Name": "EX01"}, {"Name": "EX02"}],
        # Call 2: EX01 queues (below threshold)
        [
            {
                "Identity": "EX01\\Submission",
                "MessageCount": 5,
                "DeliveryType": "SmtpDeliveryToMailbox",
                "NextHopDomain": "DB01",
                "NextHopCategory": "Internal",
                "Status": "Active",
                "LastError": None,
                "Velocity": 10,
            }
        ],
        # Call 3: EX02 queues (above threshold)
        [
            {
                "Identity": "EX02\\Internet",
                "MessageCount": 150,
                "DeliveryType": "DnsConnectorDelivery",
                "NextHopDomain": "fabrikam.com",
                "NextHopCategory": "External",
                "Status": "Retry",
                "LastError": "Connection timed out",
                "Velocity": -5,
            }
        ],
    ]

    result = await _get_transport_queues_handler({}, mock_client)

    assert result["server_count"] == 2
    assert result["total_queue_count"] == 2
    assert result["total_message_count"] == 155
    assert result["backlog_threshold"] == 100
    assert result["servers_with_backlog"] == ["EX02"]

    ex01 = next(s for s in result["servers"] if s["server"] == "EX01")
    assert ex01["queues"][0]["over_threshold"] is False
    assert ex01["has_backlog"] is False

    ex02 = next(s for s in result["servers"] if s["server"] == "EX02")
    assert ex02["queues"][0]["over_threshold"] is True
    assert ex02["has_backlog"] is True


# ---------------------------------------------------------------------------
# 2. test_get_transport_queues_single_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_single_server(mock_client: MagicMock) -> None:
    """server_name skips Get-TransportService; only one Get-Queue call made."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Only call: EX01 queues (no transport service discovery)
        [
            {
                "Identity": "EX01\\Submission",
                "MessageCount": 50,
                "DeliveryType": "SmtpDeliveryToMailbox",
                "NextHopDomain": "DB01",
                "NextHopCategory": "Internal",
                "Status": "Active",
                "LastError": None,
                "Velocity": 5,
            }
        ],
    ]

    result = await _get_transport_queues_handler({"server_name": "EX01"}, mock_client)

    assert result["server_count"] == 1
    assert result["servers"][0]["server"] == "EX01"
    assert result["servers"][0]["queues"][0]["over_threshold"] is False
    mock_client.run_cmdlet_with_retry.assert_called_once()


# ---------------------------------------------------------------------------
# 3. test_get_transport_queues_custom_threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_custom_threshold(mock_client: MagicMock) -> None:
    """Custom threshold of 10 causes a queue with 15 messages to be flagged."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Transport service discovery
        [{"Name": "EX01"}],
        # Call 2: EX01 queues (above custom threshold of 10)
        [
            {
                "Identity": "EX01\\Internet",
                "MessageCount": 15,
                "DeliveryType": "DnsConnectorDelivery",
                "NextHopDomain": "external.com",
                "NextHopCategory": "External",
                "Status": "Active",
                "LastError": None,
                "Velocity": 2,
            }
        ],
    ]

    result = await _get_transport_queues_handler({"backlog_threshold": 10}, mock_client)

    assert result["backlog_threshold"] == 10
    assert result["servers"][0]["queues"][0]["over_threshold"] is True
    assert result["servers_with_backlog"] == ["EX01"]


# ---------------------------------------------------------------------------
# 4. test_get_transport_queues_no_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_no_client() -> None:
    """None client raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError) as exc_info:
        await _get_transport_queues_handler({}, None)

    assert "not available" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 5. test_get_transport_queues_unreachable_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_unreachable_server(mock_client: MagicMock) -> None:
    """Unreachable server gets an error entry; reachable server returns queues."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Transport service discovery
        [{"Name": "EX01"}, {"Name": "EX02"}],
        # Call 2: EX01 queues succeed
        [
            {
                "Identity": "EX01\\Submission",
                "MessageCount": 3,
                "DeliveryType": "SmtpDeliveryToMailbox",
                "NextHopDomain": "DB01",
                "NextHopCategory": "Internal",
                "Status": "Active",
                "LastError": None,
                "Velocity": 1,
            }
        ],
        # Call 3: EX02 raises RuntimeError
        RuntimeError("connection refused"),
    ]

    result = await _get_transport_queues_handler({}, mock_client)

    assert result["server_count"] == 2

    ex01 = next(s for s in result["servers"] if s["server"] == "EX01")
    assert len(ex01["queues"]) == 1
    assert ex01["error"] is None

    ex02 = next(s for s in result["servers"] if s["server"] == "EX02")
    assert ex02["queues"] == []
    assert ex02["error"] is not None
    assert "Unable to query queues" in ex02["error"]


# ---------------------------------------------------------------------------
# 6. test_get_transport_queues_empty_server_list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_empty_server_list(mock_client: MagicMock) -> None:
    """Empty transport service list returns zero-count summary."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: No transport servers found
        [],
    ]

    result = await _get_transport_queues_handler({}, mock_client)

    assert result["server_count"] == 0
    assert result["total_queue_count"] == 0
    assert result["servers"] == []
    assert result["servers_with_backlog"] == []


# ---------------------------------------------------------------------------
# 7. test_get_transport_queues_no_queues_on_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_no_queues_on_server(mock_client: MagicMock) -> None:
    """Server with empty queue list returns valid server entry with zero counts."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Transport service discovery
        [{"Name": "EX01"}],
        # Call 2: EX01 has no queues
        [],
    ]

    result = await _get_transport_queues_handler({}, mock_client)

    assert result["server_count"] == 1
    ex01 = result["servers"][0]
    assert ex01["queue_count"] == 0
    assert ex01["total_messages"] == 0
    assert ex01["has_backlog"] is False
    assert ex01["error"] is None


# ---------------------------------------------------------------------------
# 8. test_get_transport_queues_default_threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_default_threshold(mock_client: MagicMock) -> None:
    """No backlog_threshold argument defaults to 100 in the result."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: No transport servers (simplest path to check threshold)
        [],
    ]

    result = await _get_transport_queues_handler({}, mock_client)

    assert result["backlog_threshold"] == 100


# ---------------------------------------------------------------------------
# 9. test_get_transport_queues_exchange_error_propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_transport_queues_exchange_error_propagates(mock_client: MagicMock) -> None:
    """RuntimeError from Get-TransportService propagates unchanged."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError("connection timeout")

    with pytest.raises(RuntimeError) as exc_info:
        await _get_transport_queues_handler({}, mock_client)

    assert "connection timeout" in str(exc_info.value)


# ===========================================================================
# get_smtp_connectors tests
# ===========================================================================

_SEND_CONNECTOR_FULL = {
    "Name": "Internet Outbound",
    "Enabled": True,
    "AddressSpaces": ["SMTP:*;1"],
    "DNSRoutingEnabled": True,
    "SmartHosts": [],
    "RequireTLS": True,
    "TlsDomain": None,
    "TlsCertificateName": None,
    "Fqdn": "mail.contoso.com",
    "MaxMessageSize": "25 MB (26,214,400 bytes)",
    "SourceTransportServers": ["EX01"],
    "CloudServicesMailEnabled": False,
    "UseExternalDNSServersEnabled": False,
}

_RECV_CONNECTOR_FULL = {
    "Name": "Default Frontend EX01",
    "Enabled": True,
    "Bindings": ["0.0.0.0:25"],
    "RemoteIPRanges": ["0.0.0.0-255.255.255.255"],
    "AuthMechanism": "Tls, Integrated",
    "PermissionGroups": "AnonymousUsers",
    "RequireTLS": False,
    "TlsCertificateName": None,
    "TransportRole": "FrontendTransport",
    "Server": "EX01",
    "Fqdn": "mail.contoso.com",
    "MaxMessageSize": "36 MB (37,748,736 bytes)",
    "MaxRecipientsPerMessage": 5000,
}


# ---------------------------------------------------------------------------
# 1. test_get_smtp_connectors_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_all(mock_client: MagicMock) -> None:
    """Default connector_type=all returns both send and receive connectors."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Get-SendConnector
        [_SEND_CONNECTOR_FULL],
        # Call 2: Get-ReceiveConnector
        [_RECV_CONNECTOR_FULL],
    ]

    result = await _get_smtp_connectors_handler({}, mock_client)

    assert result["connector_type_filter"] == "all"
    assert result["send_connector_count"] == 1
    assert result["receive_connector_count"] == 1

    send = result["send_connectors"][0]
    assert send["name"] == "Internet Outbound"
    assert send["enabled"] is True
    assert send["address_spaces"] == ["SMTP:*;1"]
    assert send["require_tls"] is True
    assert send["max_message_size"] == "25 MB (26,214,400 bytes)"

    recv = result["receive_connectors"][0]
    assert recv["name"] == "Default Frontend EX01"
    assert recv["bindings"] == ["0.0.0.0:25"]
    assert recv["auth_mechanism"] == "Tls, Integrated"
    assert recv["server"] == "EX01"


# ---------------------------------------------------------------------------
# 2. test_get_smtp_connectors_send_only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_send_only(mock_client: MagicMock) -> None:
    """connector_type=send returns only send connectors; no receive connector call made."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Only one call: Get-SendConnector
        [_SEND_CONNECTOR_FULL],
    ]

    result = await _get_smtp_connectors_handler({"connector_type": "send"}, mock_client)

    assert "send_connectors" in result
    assert "receive_connectors" not in result
    assert result["send_connector_count"] == 1
    mock_client.run_cmdlet_with_retry.assert_called_once()


# ---------------------------------------------------------------------------
# 3. test_get_smtp_connectors_receive_only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_receive_only(mock_client: MagicMock) -> None:
    """connector_type=receive returns only receive connectors; no send connector call made."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Only one call: Get-ReceiveConnector
        [_RECV_CONNECTOR_FULL],
    ]

    result = await _get_smtp_connectors_handler({"connector_type": "receive"}, mock_client)

    assert "receive_connectors" in result
    assert "send_connectors" not in result
    assert result["receive_connector_count"] == 1
    mock_client.run_cmdlet_with_retry.assert_called_once()


# ---------------------------------------------------------------------------
# 4. test_get_smtp_connectors_invalid_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_invalid_type(mock_client: MagicMock) -> None:
    """Invalid connector_type raises RuntimeError immediately without Exchange call."""
    with pytest.raises(RuntimeError) as exc_info:
        await _get_smtp_connectors_handler({"connector_type": "invalid"}, mock_client)

    assert "Invalid connector_type" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 5. test_get_smtp_connectors_no_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_no_client() -> None:
    """None client raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError) as exc_info:
        await _get_smtp_connectors_handler({}, None)

    assert "not available" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 6. test_get_smtp_connectors_empty_results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_empty_results(mock_client: MagicMock) -> None:
    """Empty Exchange results produce zero-count summaries for both connector types."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Get-SendConnector returns empty list
        [],
        # Call 2: Get-ReceiveConnector returns empty list
        [],
    ]

    result = await _get_smtp_connectors_handler({}, mock_client)

    assert result["send_connector_count"] == 0
    assert result["receive_connector_count"] == 0
    assert result["send_connectors"] == []
    assert result["receive_connectors"] == []


# ---------------------------------------------------------------------------
# 7. test_get_smtp_connectors_single_dict_normalized
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_single_dict_normalized(mock_client: MagicMock) -> None:
    """Single connector returned as dict (not list) is normalized to a list."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: Get-SendConnector returns a single dict (Exchange single-result quirk)
        _SEND_CONNECTOR_FULL,
        # Call 2: Get-ReceiveConnector returns empty list
        [],
    ]

    result = await _get_smtp_connectors_handler({}, mock_client)

    assert result["send_connector_count"] == 1
    assert result["send_connectors"][0]["name"] == "Internet Outbound"


# ---------------------------------------------------------------------------
# 8. test_get_smtp_connectors_exchange_error_propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_smtp_connectors_exchange_error_propagates(mock_client: MagicMock) -> None:
    """RuntimeError from Get-SendConnector propagates unchanged."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError("connection timeout")

    with pytest.raises(RuntimeError) as exc_info:
        await _get_smtp_connectors_handler({}, mock_client)

    assert "connection timeout" in str(exc_info.value)

    assert "connection timeout" in str(exc_info.value)
