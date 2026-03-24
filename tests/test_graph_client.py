"""Unit tests for chat_app.graph_client core operations.

All tests mock ``requests.request`` and ``msal.ConfidentialClientApplication``
to avoid any real network calls.  No live Graph API connection is required.

Tests cover:
    - Disabled-client fallback: search_users returns [] when _graph_enabled is False
    - Disabled-client fallback: get_user_photo_bytes returns None when _graph_enabled is False
    - Empty/whitespace guard: search_users returns [] without a network call
    - Empty user_id guard: get_user_photo_bytes returns None without a network call
    - ConsistencyLevel: eventual header is sent on every search_users call
    - Successful response parsing: search_users returns the ``value`` array
    - Exception safety: search_users returns [] on Timeout (not an exception)
    - 404 path: get_user_photo_bytes returns None on HTTP 404
    - 200 path: get_user_photo_bytes returns raw bytes on HTTP 200
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

import chat_app.graph_client as gc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
    content: bytes = b"",
) -> MagicMock:
    """Build a fake ``requests.Response`` with configurable attributes."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = {}
    resp.json.return_value = json_data if json_data is not None else {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_mock_cca() -> MagicMock:
    """Return a mock ConfidentialClientApplication that always yields a token."""
    cca = MagicMock()
    cca.acquire_token_for_client.return_value = {"access_token": "fake-token"}
    return cca


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _disable_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure _graph_enabled is False and _cca is None for the test."""
    monkeypatch.setattr(gc, "_graph_enabled", False)
    monkeypatch.setattr(gc, "_cca", None)


@pytest.fixture()
def _enable_graph(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Set _graph_enabled = True and wire a mock CCA that returns a token."""
    mock_cca = _make_mock_cca()
    monkeypatch.setattr(gc, "_graph_enabled", True)
    monkeypatch.setattr(gc, "_cca", mock_cca)
    return mock_cca


# ---------------------------------------------------------------------------
# Disabled-client tests
# ---------------------------------------------------------------------------


def test_search_users_returns_empty_when_graph_disabled(
    _disable_graph: None,
) -> None:
    """search_users() returns [] immediately when _graph_enabled is False."""
    with patch("requests.request") as mock_req:
        result = gc.search_users("alice")

    assert result == []
    mock_req.assert_not_called()


def test_get_user_photo_bytes_returns_none_when_graph_disabled(
    _disable_graph: None,
) -> None:
    """get_user_photo_bytes() returns None immediately when _graph_enabled is False."""
    with patch("requests.request") as mock_req:
        result = gc.get_user_photo_bytes("some-user-id")

    assert result is None
    mock_req.assert_not_called()


# ---------------------------------------------------------------------------
# Empty / whitespace guard tests
# ---------------------------------------------------------------------------


def test_search_users_empty_string_returns_empty(_enable_graph: MagicMock) -> None:
    """search_users('') returns [] without making a network call."""
    with patch("requests.request") as mock_req:
        result = gc.search_users("")

    assert result == []
    mock_req.assert_not_called()


def test_search_users_whitespace_only_returns_empty(_enable_graph: MagicMock) -> None:
    """search_users('   ') returns [] without making a network call."""
    with patch("requests.request") as mock_req:
        result = gc.search_users("   ")

    assert result == []
    mock_req.assert_not_called()


def test_get_user_photo_bytes_empty_user_id_returns_none(
    _enable_graph: MagicMock,
) -> None:
    """get_user_photo_bytes('') returns None without making a network call."""
    with patch("requests.request") as mock_req:
        result = gc.get_user_photo_bytes("")

    assert result is None
    mock_req.assert_not_called()


# ---------------------------------------------------------------------------
# search_users — successful path tests
# ---------------------------------------------------------------------------


def test_search_users_sends_consistency_level_header(
    _enable_graph: MagicMock,
) -> None:
    """search_users() must include ConsistencyLevel: eventual in every request."""
    with patch("requests.request") as mock_req, patch("time.sleep"):
        mock_req.return_value = _make_response(200, {"value": []})
        gc.search_users("alice")

    mock_req.assert_called_once()
    _call_kwargs = mock_req.call_args
    # headers are passed as a keyword argument
    sent_headers: dict = _call_kwargs.kwargs.get("headers") or _call_kwargs.args[2]
    assert "ConsistencyLevel" in sent_headers, (
        "ConsistencyLevel header was not sent"
    )
    assert sent_headers["ConsistencyLevel"] == "eventual"


def test_search_users_returns_value_array(_enable_graph: MagicMock) -> None:
    """search_users() returns the 'value' array from the Graph JSON response."""
    users = [{"id": "1", "displayName": "Alice"}]
    with patch("requests.request") as mock_req, patch("time.sleep"):
        mock_req.return_value = _make_response(200, {"value": users})
        result = gc.search_users("alice")

    assert result == users


# ---------------------------------------------------------------------------
# search_users — exception safety
# ---------------------------------------------------------------------------


def test_search_users_returns_empty_on_exception(_enable_graph: MagicMock) -> None:
    """search_users() returns [] (not raises) when requests.request raises Timeout."""
    with patch("requests.request") as mock_req, patch("time.sleep"):
        mock_req.side_effect = requests.exceptions.Timeout("timed out")
        result = gc.search_users("alice")

    assert result == []


# ---------------------------------------------------------------------------
# get_user_photo_bytes tests
# ---------------------------------------------------------------------------


def test_get_user_photo_bytes_returns_none_on_404(_enable_graph: MagicMock) -> None:
    """get_user_photo_bytes() returns None when Graph responds with 404."""
    with patch("requests.request") as mock_req, patch("time.sleep"):
        mock_req.return_value = _make_response(404, content=b"")
        result = gc.get_user_photo_bytes("user-id-404")

    assert result is None


def test_get_user_photo_bytes_returns_bytes_on_200(_enable_graph: MagicMock) -> None:
    """get_user_photo_bytes() returns raw bytes when Graph responds with 200."""
    photo_bytes = b"\x89PNG\r\n\x1a\n"
    with patch("requests.request") as mock_req, patch("time.sleep"):
        mock_req.return_value = _make_response(200, content=photo_bytes)
        result = gc.get_user_photo_bytes("user-id-200")

    assert result == photo_bytes
