"""Unit tests for the list_dag_members tool handler (Phase 4).

All tests mock ExchangeClient — no live Exchange Online connection is needed.

Tests cover:
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
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from exchange_mcp.tools import _list_dag_members_handler


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
