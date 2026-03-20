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

from exchange_mcp.tools import _check_mail_flow_handler, _get_transport_queues_handler


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
