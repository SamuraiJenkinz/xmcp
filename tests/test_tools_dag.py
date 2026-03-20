"""Unit tests for the DAG tool handlers (Phase 4).

All tests mock ExchangeClient — no live Exchange Online connection is needed.

list_dag_members tests cover:
    - test_list_dag_members_valid: two-server DAG with full enrichment
    - test_list_dag_members_dag_not_found: non-existent DAG produces friendly error
    - test_list_dag_members_empty_dag_name: empty dag_name raises before Exchange call
    - test_list_dag_members_missing_dag_name: missing dag_name raises before Exchange call
    - test_list_dag_members_no_client: None client raises immediately
    - test_list_dag_members_unreachable_server: partial results for unreachable member
    - test_list_dag_members_single_member_string: string Members value normalised to list
    - test_list_dag_members_exchange_error_propagates: non-not-found errors propagate
    - test_list_dag_members_no_databases_on_server: empty DB copy list → counts of 0
    - test_list_dag_members_dag_result_as_list: single-element list DAG result normalised

get_dag_health tests cover:
    - test_get_dag_health_valid: two-server DAG full replication report
    - test_get_dag_health_dag_not_found: non-existent DAG produces friendly error
    - test_get_dag_health_empty_dag_name: empty dag_name raises before Exchange call
    - test_get_dag_health_no_client: None client raises immediately
    - test_get_dag_health_unreachable_server: partial results for unreachable member
    - test_get_dag_health_single_copy_dict: single dict response normalised to list
    - test_get_dag_health_exchange_error_propagates: non-not-found errors propagate
    - test_get_dag_health_content_index_failed: Failed content index passes through as-is
    - test_get_dag_health_all_servers_unreachable: all servers fail → result still returned
    - test_get_dag_health_single_member_string: string Members value normalised to list
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exchange_mcp.tools import _get_dag_health_handler, _list_dag_members_handler


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
# 1. test_list_dag_members_valid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_valid(mock_client: MagicMock) -> None:
    """Valid two-server DAG returns correct DAG metadata and per-server details."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG metadata
        {
            "Name": "DAG01",
            "Members": ["EX01", "EX02"],
            "WitnessServer": "FSW01",
            "WitnessDirectory": "C:\\DAGFileShareWitnesses\\DAG01",
            "OperationalServers": ["EX01", "EX02"],
            "PrimaryActiveManager": "EX01",
        },
        # Call 2a: EX01 server info
        {
            "Name": "EX01",
            "AdminDisplayVersion": "Version 15.2 (Build 1118.7)",
            "Site": "Sydney",
            "ServerRole": "Mailbox",
        },
        # Call 2b: EX01 DB copies
        [{"Status": "Mounted"}, {"Status": "Healthy"}],
        # Call 3a: EX02 server info
        {
            "Name": "EX02",
            "AdminDisplayVersion": "Version 15.2 (Build 1118.7)",
            "Site": "Melbourne",
            "ServerRole": "Mailbox",
        },
        # Call 3b: EX02 DB copies
        [{"Status": "Healthy"}, {"Status": "Mounted"}],
    ]

    result = await _list_dag_members_handler({"dag_name": "DAG01"}, mock_client)

    assert result["dag_name"] == "DAG01"
    assert result["member_count"] == 2
    assert result["witness_server"] == "FSW01"
    assert result["witness_directory"] == "C:\\DAGFileShareWitnesses\\DAG01"
    assert result["primary_active_manager"] == "EX01"
    assert len(result["members"]) == 2

    ex01 = result["members"][0]
    assert ex01["name"] == "EX01"
    assert ex01["operational"] is True
    assert ex01["site"] == "Sydney"
    assert ex01["exchange_version"] == "Version 15.2 (Build 1118.7)"
    assert ex01["active_database_count"] == 1
    assert ex01["passive_database_count"] == 1
    assert ex01["error"] is None

    ex02 = result["members"][1]
    assert ex02["name"] == "EX02"
    assert ex02["operational"] is True
    assert ex02["site"] == "Melbourne"
    assert ex02["active_database_count"] == 1
    assert ex02["passive_database_count"] == 1
    assert ex02["error"] is None


# ---------------------------------------------------------------------------
# 2. test_list_dag_members_dag_not_found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_dag_not_found(mock_client: MagicMock) -> None:
    """Non-existent DAG name produces a friendly RuntimeError mentioning the name."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError(
        "Couldn't find object 'BADDAG'."
    )

    with pytest.raises(RuntimeError) as exc_info:
        await _list_dag_members_handler({"dag_name": "BADDAG"}, mock_client)

    assert "No DAG found with name 'BADDAG'" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. test_list_dag_members_empty_dag_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_empty_dag_name(mock_client: MagicMock) -> None:
    """Empty dag_name raises RuntimeError with 'dag_name is required' before Exchange."""
    with pytest.raises(RuntimeError) as exc_info:
        await _list_dag_members_handler({"dag_name": ""}, mock_client)

    assert "dag_name is required" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 4. test_list_dag_members_missing_dag_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_missing_dag_name(mock_client: MagicMock) -> None:
    """Missing dag_name key raises RuntimeError with 'dag_name is required' before Exchange."""
    with pytest.raises(RuntimeError) as exc_info:
        await _list_dag_members_handler({}, mock_client)

    assert "dag_name is required" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 5. test_list_dag_members_no_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_no_client() -> None:
    """None client raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError) as exc_info:
        await _list_dag_members_handler({"dag_name": "DAG01"}, None)

    assert "not available" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 6. test_list_dag_members_unreachable_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_unreachable_server(mock_client: MagicMock) -> None:
    """Unreachable server gets error entry with null fields; reachable server succeeds."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG metadata
        {
            "Name": "DAG01",
            "Members": ["EX01", "EX02"],
            "WitnessServer": "FSW01",
            "WitnessDirectory": "C:\\DAGFileShareWitnesses\\DAG01",
            "OperationalServers": ["EX01"],
            "PrimaryActiveManager": "EX01",
        },
        # Call 2a: EX01 server info — succeeds
        {
            "Name": "EX01",
            "AdminDisplayVersion": "Version 15.2 (Build 1118.7)",
            "Site": "Sydney",
            "ServerRole": "Mailbox",
        },
        # Call 2b: EX01 DB copies — succeeds
        [{"Status": "Mounted"}],
        # Call 3a: EX02 server info — raises (connection refused)
        RuntimeError("connection refused"),
    ]

    result = await _list_dag_members_handler({"dag_name": "DAG01"}, mock_client)

    assert result["member_count"] == 2
    assert len(result["members"]) == 2

    ex01 = result["members"][0]
    assert ex01["name"] == "EX01"
    assert ex01["error"] is None
    assert ex01["site"] == "Sydney"
    assert ex01["active_database_count"] == 1

    ex02 = result["members"][1]
    assert ex02["name"] == "EX02"
    assert "Unable to query server" in ex02["error"]
    assert ex02["site"] is None
    assert ex02["exchange_version"] is None
    assert ex02["active_database_count"] is None
    assert ex02["passive_database_count"] is None


# ---------------------------------------------------------------------------
# 7. test_list_dag_members_single_member_string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_single_member_string(mock_client: MagicMock) -> None:
    """Members value returned as a bare string is normalised to a single-item list."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG metadata — Members is a string (single-member DAG)
        {
            "Name": "DAG01",
            "Members": "EX01",
            "WitnessServer": "FSW01",
            "WitnessDirectory": "C:\\DAGFileShareWitnesses\\DAG01",
            "OperationalServers": ["EX01"],
            "PrimaryActiveManager": "EX01",
        },
        # Call 2a: EX01 server info
        {
            "Name": "EX01",
            "AdminDisplayVersion": "Version 15.2 (Build 1118.7)",
            "Site": "Sydney",
            "ServerRole": "Mailbox",
        },
        # Call 2b: EX01 DB copies
        [{"Status": "Mounted"}, {"Status": "Healthy"}],
    ]

    result = await _list_dag_members_handler({"dag_name": "DAG01"}, mock_client)

    assert result["member_count"] == 1
    assert len(result["members"]) == 1
    assert result["members"][0]["name"] == "EX01"


# ---------------------------------------------------------------------------
# 8. test_list_dag_members_exchange_error_propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_exchange_error_propagates(mock_client: MagicMock) -> None:
    """Non-not-found RuntimeError from Exchange propagates unchanged."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError("connection timeout")

    with pytest.raises(RuntimeError) as exc_info:
        await _list_dag_members_handler({"dag_name": "DAG01"}, mock_client)

    assert "connection timeout" in str(exc_info.value)
    # Must NOT be wrapped in a "No DAG found" message
    assert "No DAG found" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# 9. test_list_dag_members_no_databases_on_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_no_databases_on_server(mock_client: MagicMock) -> None:
    """Server with no database copies returns active_database_count=0, passive_database_count=0."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG metadata
        {
            "Name": "DAG01",
            "Members": ["EX01"],
            "WitnessServer": "FSW01",
            "WitnessDirectory": "C:\\DAGFileShareWitnesses\\DAG01",
            "OperationalServers": ["EX01"],
            "PrimaryActiveManager": "EX01",
        },
        # Call 2a: EX01 server info
        {
            "Name": "EX01",
            "AdminDisplayVersion": "Version 15.2 (Build 1118.7)",
            "Site": "Sydney",
            "ServerRole": "Mailbox",
        },
        # Call 2b: EX01 DB copies — empty list
        [],
    ]

    result = await _list_dag_members_handler({"dag_name": "DAG01"}, mock_client)

    ex01 = result["members"][0]
    assert ex01["active_database_count"] == 0
    assert ex01["passive_database_count"] == 0
    assert ex01["error"] is None


# ---------------------------------------------------------------------------
# 10. test_list_dag_members_dag_result_as_list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_list_dag_members_dag_result_as_list(mock_client: MagicMock) -> None:
    """DAG metadata returned as single-element list is normalised correctly."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG metadata as list (sometimes returned by run_cmdlet_with_retry)
        [
            {
                "Name": "DAG01",
                "Members": ["EX01"],
                "WitnessServer": "FSW01",
                "WitnessDirectory": "C:\\DAGFileShareWitnesses\\DAG01",
                "OperationalServers": ["EX01"],
                "PrimaryActiveManager": "EX01",
            }
        ],
        # Call 2a: EX01 server info
        {
            "Name": "EX01",
            "AdminDisplayVersion": "Version 15.2 (Build 1118.7)",
            "Site": "Sydney",
            "ServerRole": "Mailbox",
        },
        # Call 2b: EX01 DB copies
        [{"Status": "Mounted"}],
    ]

    result = await _list_dag_members_handler({"dag_name": "DAG01"}, mock_client)

    assert result["dag_name"] == "DAG01"
    assert result["member_count"] == 1
    assert result["witness_server"] == "FSW01"
    assert result["members"][0]["name"] == "EX01"
    assert result["members"][0]["active_database_count"] == 1


# ===========================================================================
# get_dag_health tests (Phase 4, Plan 02)
# ===========================================================================


# ---------------------------------------------------------------------------
# 11. test_get_dag_health_valid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_valid(mock_client: MagicMock) -> None:
    """Two-server DAG returns full replication report with per-server copy details."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG member list
        {"Members": ["EX01", "EX02"]},
        # Call 2: EX01 health — two copies (one mounted, one healthy)
        [
            {
                "Name": "DB01\\EX01",
                "Status": "Mounted",
                "CopyQueueLength": 0,
                "ReplayQueueLength": 0,
                "ContentIndexState": "Healthy",
                "LastCopiedLogTime": None,
                "LastInspectedLogTime": "/Date(1708000000000)/",
                "LastReplayedLogTime": None,
                "MailboxServer": "EX01",
            },
            {
                "Name": "DB02\\EX01",
                "Status": "Healthy",
                "CopyQueueLength": 3,
                "ReplayQueueLength": 1,
                "ContentIndexState": "Healthy",
                "LastCopiedLogTime": "/Date(1708000000000)/",
                "LastInspectedLogTime": "/Date(1708000000000)/",
                "LastReplayedLogTime": "/Date(1708000000000)/",
                "MailboxServer": "EX01",
            },
        ],
        # Call 3: EX02 health — one healthy copy
        [
            {
                "Name": "DB01\\EX02",
                "Status": "Healthy",
                "CopyQueueLength": 2,
                "ReplayQueueLength": 0,
                "ContentIndexState": "Healthy",
                "LastCopiedLogTime": "/Date(1708000000000)/",
                "LastInspectedLogTime": "/Date(1708000000000)/",
                "LastReplayedLogTime": "/Date(1708000000000)/",
                "MailboxServer": "EX02",
            }
        ],
    ]

    result = await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    assert result["dag_name"] == "DAG01"
    assert result["member_count"] == 2
    assert len(result["servers"]) == 2

    ex01 = result["servers"][0]
    assert ex01["server"] == "EX01"
    assert ex01["error"] is None
    assert len(ex01["copies"]) == 2

    # First copy: Mounted
    c0 = ex01["copies"][0]
    assert c0["is_mounted"] is True
    assert c0["copy_queue_length"] == 0
    assert c0["replay_queue_length"] == 0
    assert c0["content_index_state"] == "Healthy"

    # Second copy: Healthy (not mounted)
    c1 = ex01["copies"][1]
    assert c1["is_mounted"] is False
    assert c1["copy_queue_length"] == 3
    assert c1["replay_queue_length"] == 1

    ex02 = result["servers"][1]
    assert ex02["server"] == "EX02"
    assert ex02["error"] is None
    assert len(ex02["copies"]) == 1
    assert ex02["copies"][0]["copy_queue_length"] == 2


# ---------------------------------------------------------------------------
# 12. test_get_dag_health_dag_not_found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_dag_not_found(mock_client: MagicMock) -> None:
    """Non-existent DAG name produces a friendly RuntimeError mentioning the name."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError(
        "Couldn't find object 'BADDAG'."
    )

    with pytest.raises(RuntimeError) as exc_info:
        await _get_dag_health_handler({"dag_name": "BADDAG"}, mock_client)

    assert "No DAG found with name 'BADDAG'" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 13. test_get_dag_health_empty_dag_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_empty_dag_name(mock_client: MagicMock) -> None:
    """Empty dag_name raises RuntimeError with 'dag_name is required' before Exchange."""
    with pytest.raises(RuntimeError) as exc_info:
        await _get_dag_health_handler({"dag_name": ""}, mock_client)

    assert "dag_name is required" in str(exc_info.value)
    mock_client.run_cmdlet_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# 14. test_get_dag_health_no_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_no_client() -> None:
    """None client raises RuntimeError mentioning 'not available'."""
    with pytest.raises(RuntimeError) as exc_info:
        await _get_dag_health_handler({"dag_name": "DAG01"}, None)

    assert "not available" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 15. test_get_dag_health_unreachable_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_unreachable_server(mock_client: MagicMock) -> None:
    """Unreachable server gets error entry with empty copies; reachable server succeeds."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG member list
        {"Members": ["EX01", "EX02"]},
        # Call 2: EX01 health — succeeds
        [
            {
                "Name": "DB01\\EX01",
                "Status": "Mounted",
                "CopyQueueLength": 0,
                "ReplayQueueLength": 0,
                "ContentIndexState": "Healthy",
                "LastCopiedLogTime": None,
                "LastInspectedLogTime": None,
                "LastReplayedLogTime": None,
                "MailboxServer": "EX01",
            }
        ],
        # Call 3: EX02 health — raises (connection refused)
        RuntimeError("connection refused"),
    ]

    result = await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    assert len(result["servers"]) == 2

    ex01 = result["servers"][0]
    assert ex01["error"] is None
    assert len(ex01["copies"]) == 1

    ex02 = result["servers"][1]
    assert "Unable to query server" in ex02["error"]
    assert ex02["copies"] == []


# ---------------------------------------------------------------------------
# 16. test_get_dag_health_single_copy_dict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_single_copy_dict(mock_client: MagicMock) -> None:
    """Single dict (not list) returned by server is normalised to a list of one copy."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG member list — single member
        {"Members": ["EX01"]},
        # Call 2: EX01 health — single dict (not list)
        {
            "Name": "DB01\\EX01",
            "Status": "Mounted",
            "CopyQueueLength": 0,
            "ReplayQueueLength": 0,
            "ContentIndexState": "Healthy",
            "LastCopiedLogTime": None,
            "LastInspectedLogTime": None,
            "LastReplayedLogTime": None,
            "MailboxServer": "EX01",
        },
    ]

    result = await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    assert len(result["servers"]) == 1
    ex01 = result["servers"][0]
    assert ex01["error"] is None
    assert len(ex01["copies"]) == 1
    assert ex01["copies"][0]["is_mounted"] is True


# ---------------------------------------------------------------------------
# 17. test_get_dag_health_exchange_error_propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_exchange_error_propagates(mock_client: MagicMock) -> None:
    """Non-not-found RuntimeError from DAG lookup propagates unchanged."""
    mock_client.run_cmdlet_with_retry.side_effect = RuntimeError("connection timeout")

    with pytest.raises(RuntimeError) as exc_info:
        await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    assert "connection timeout" in str(exc_info.value)
    assert "No DAG found" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# 18. test_get_dag_health_content_index_failed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_content_index_failed(mock_client: MagicMock) -> None:
    """ContentIndexState value 'Failed' is passed through as-is without modification."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        {"Members": ["EX01"]},
        [
            {
                "Name": "DB01\\EX01",
                "Status": "Healthy",
                "CopyQueueLength": 0,
                "ReplayQueueLength": 0,
                "ContentIndexState": "Failed",
                "LastCopiedLogTime": None,
                "LastInspectedLogTime": None,
                "LastReplayedLogTime": None,
                "MailboxServer": "EX01",
            }
        ],
    ]

    result = await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    copy = result["servers"][0]["copies"][0]
    assert copy["content_index_state"] == "Failed"
    assert copy["is_mounted"] is False


# ---------------------------------------------------------------------------
# 19. test_get_dag_health_all_servers_unreachable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_all_servers_unreachable(mock_client: MagicMock) -> None:
    """When ALL servers are unreachable, result is returned with per-server error entries."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG member list
        {"Members": ["EX01", "EX02"]},
        # Call 2: EX01 health — raises
        RuntimeError("EX01 unreachable"),
        # Call 3: EX02 health — raises
        RuntimeError("EX02 unreachable"),
    ]

    result = await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    # Result is returned (not an exception)
    assert result["dag_name"] == "DAG01"
    assert result["member_count"] == 2
    assert len(result["servers"]) == 2

    for srv in result["servers"]:
        assert srv["copies"] == []
        assert srv["error"] is not None
        assert "Unable to query server" in srv["error"]


# ---------------------------------------------------------------------------
# 20. test_get_dag_health_single_member_string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_dag_health_single_member_string(mock_client: MagicMock) -> None:
    """Members returned as a bare string is normalised to a single-member list."""
    mock_client.run_cmdlet_with_retry.side_effect = [
        # Call 1: DAG metadata — Members is a string (single-member DAG)
        {"Members": "EX01"},
        # Call 2: EX01 health
        [
            {
                "Name": "DB01\\EX01",
                "Status": "Mounted",
                "CopyQueueLength": 0,
                "ReplayQueueLength": 0,
                "ContentIndexState": "Healthy",
                "LastCopiedLogTime": None,
                "LastInspectedLogTime": None,
                "LastReplayedLogTime": None,
                "MailboxServer": "EX01",
            }
        ],
    ]

    result = await _get_dag_health_handler({"dag_name": "DAG01"}, mock_client)

    assert result["member_count"] == 1
    assert len(result["servers"]) == 1
    assert result["servers"][0]["server"] == "EX01"
    assert len(result["servers"][0]["copies"]) == 1
