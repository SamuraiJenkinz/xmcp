"""Microsoft Graph API client — isolated singleton for colleague lookup."""

from __future__ import annotations

import base64
import json
import logging
import time

import msal
import requests

from chat_app.config import Config

logger = logging.getLogger(__name__)

_cca: msal.ConfidentialClientApplication | None = None
_graph_enabled: bool = False

_GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


def init_graph(client_id: str, client_secret: str, tenant_id: str) -> None:
    """Initialise the MSAL confidential client and verify Graph permissions.

    Acquires a client-credentials token and checks that the required
    application roles (User.Read.All, ProfilePhoto.Read.All) are present
    in the access token.  Sets the module-level ``_graph_enabled`` flag on
    success so callers can check :func:`is_graph_enabled` before making
    Graph requests.
    """
    global _cca, _graph_enabled

    missing = [
        name
        for name, val in (
            ("AZURE_CLIENT_ID", client_id),
            ("AZURE_CLIENT_SECRET", client_secret),
            ("AZURE_TENANT_ID", tenant_id),
        )
        if not val
    ]
    if missing:
        logger.warning(
            "Graph client not initialised — missing config vars: %s",
            ", ".join(missing),
        )
        return

    _cca = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )

    result = _cca.acquire_token_for_client(scopes=_GRAPH_SCOPES)

    if "error" in result:
        consent_url = (
            f"https://login.microsoftonline.com/{tenant_id}"
            f"/adminconsent?client_id={client_id}"
        )
        logger.error(
            "Graph token acquisition failed — %s: %s. "
            "Grant admin consent at: %s",
            result.get("error"),
            result.get("error_description", ""),
            consent_url,
        )
        return

    _verify_roles(result["access_token"], tenant_id, client_id)
    _graph_enabled = True
    logger.info("Graph client initialised successfully")


def _verify_roles(access_token: str, tenant_id: str, client_id: str) -> None:
    """Decode the JWT payload and warn if required app roles are absent."""
    try:
        payload_b64 = access_token.split(".")[1]
        padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))

        roles: list[str] = payload.get("roles", [])
        required = {"User.Read.All", "ProfilePhoto.Read.All"}
        missing = required - set(roles)

        if missing:
            consent_url = (
                f"https://login.microsoftonline.com/{tenant_id}"
                f"/adminconsent?client_id={client_id}"
            )
            logger.error(
                "Graph token is missing required application roles: %s. "
                "Grant admin consent at: %s",
                ", ".join(sorted(missing)),
                consent_url,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not decode Graph token payload for role check: %s", exc)


def is_graph_enabled() -> bool:
    """Return True if the Graph client has been successfully initialised."""
    return _graph_enabled


def _get_token() -> str | None:
    """Acquire (or return cached) client-credentials token via MSAL.

    MSAL handles cache internally — calling this on every request is correct
    and cheap on cache hits (MSAL 1.34.0 returns cached token if >5 min
    remaining, refreshes transparently when expiry is close).

    Returns the access token string, or None if the client is not initialised
    or token acquisition fails.
    """
    if _cca is None:
        return None

    result = _cca.acquire_token_for_client(scopes=_GRAPH_SCOPES)

    if "access_token" in result:
        return result["access_token"]

    logger.error(
        "Graph token acquisition failed — %s: %s",
        result.get("error"),
        result.get("error_description", ""),
    )
    return None


def _make_headers(*, search: bool = False) -> dict[str, str] | None:
    """Build authorization headers for a Graph API request.

    Args:
        search: When True, adds ``ConsistencyLevel: eventual`` header.
            This is MANDATORY for ``$search`` on directory objects — without
            it Graph returns HTTP 400.

    Returns:
        A dict of headers, or None if no token is available.
    """
    token = _get_token()
    if token is None:
        return None

    headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
    if search:
        headers["ConsistencyLevel"] = "eventual"

    return headers


def _graph_request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict,
    params: dict | None = None,
    max_retries: int = 3,
    timeout: int = Config.GRAPH_TIMEOUT,
) -> requests.Response:
    """Execute a Graph API request with retry logic for 429/503 and timeouts.

    Retries on HTTP 429 (Too Many Requests) and 503 (Service Unavailable),
    honouring the ``Retry-After`` response header when present, falling back
    to exponential backoff (``2 ** attempt`` seconds) if absent.

    Args:
        method: HTTP verb, e.g. ``"GET"``.
        url: Absolute Graph endpoint URL.
        headers: Request headers (from :func:`_make_headers`).
        params: Optional query-string parameters.
        max_retries: Maximum number of attempts before giving up.
        timeout: Per-request socket timeout in seconds.

    Returns:
        The :class:`requests.Response` from the first non-retriable response.

    Raises:
        RuntimeError: If all retries are exhausted without a successful
            non-retriable response.
        requests.exceptions.Timeout: Propagated if last attempt times out
            after all retries.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = requests.request(
                method, url, headers=headers, params=params, timeout=timeout
            )

            if response.status_code in (429, 503):
                retry_after_raw = response.headers.get("Retry-After")
                retry_after = (
                    int(retry_after_raw) if retry_after_raw else 2 ** attempt
                )
                logger.warning(
                    "Graph request got HTTP %d on attempt %d/%d — "
                    "retrying after %ds",
                    response.status_code,
                    attempt + 1,
                    max_retries,
                    retry_after,
                )
                time.sleep(retry_after)
                continue

            # Any other status code (200, 404, 400, 500, …): return to caller.
            return response

        except requests.exceptions.Timeout as exc:
            last_exc = exc
            backoff = 2 ** attempt
            logger.warning(
                "Graph request timed out on attempt %d/%d — retrying after %ds",
                attempt + 1,
                max_retries,
                backoff,
            )
            time.sleep(backoff)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Graph request failed after retries")


def search_users(term: str) -> list[dict]:
    """Search Active Directory users by display name or email.

    Uses Graph ``$search`` with ``ConsistencyLevel: eventual`` header — the
    header is mandatory for directory-object searches; without it Graph returns
    HTTP 400.

    Args:
        term: Free-text search string matched against displayName and mail.
            Empty or whitespace-only strings return ``[]`` immediately without
            making a network request.

    Returns:
        A list of dicts, each containing ``id``, ``displayName``, ``mail``,
        ``jobTitle``, and ``department``.  Returns ``[]`` when Graph is
        disabled, the term is blank, or any error occurs.
    """
    if not _graph_enabled or not term or not term.strip():
        return []

    term = term.strip()

    headers = _make_headers(search=True)
    if headers is None:
        return []

    url = f"{Config.GRAPH_BASE_URL}/users"
    params = {
        "$search": f'"displayName:{term}" OR "mail:{term}"',
        "$select": "id,displayName,mail,jobTitle,department",
        "$filter": "accountEnabled eq true",
        "$top": str(Config.GRAPH_SEARCH_MAX_RESULTS),
    }

    try:
        resp = _graph_request_with_retry("GET", url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("value", [])
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph search_users failed for term %r: %s", term, exc)
        return []


def get_user_photo_bytes(user_id: str) -> bytes | None:
    """Retrieve the profile photo for a user as raw bytes.

    Returns ``None`` silently when the user has no photo (HTTP 404).  Missing
    photos are normal in large organisations and must not generate log noise.

    Args:
        user_id: The Graph user object ID (GUID).  Empty string returns
            ``None`` without a network request.

    Returns:
        JPEG or PNG bytes on success, ``None`` if the user has no photo or
        Graph is disabled.  Never raises an exception to the caller.
    """
    if not _graph_enabled or not user_id:
        return None

    headers = _make_headers()
    if headers is None:
        return None

    url = f"{Config.GRAPH_BASE_URL}/users/{user_id}/photo/$value"

    try:
        resp = _graph_request_with_retry("GET", url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph get_user_photo_bytes failed for user %r: %s", user_id, exc)
        return None


def get_user_profile(user_id: str) -> dict | None:
    """Retrieve detailed profile for a user including manager display name.

    Fetches user properties plus the manager's display name in a single
    Graph API call using ``$expand=manager($select=displayName)``.

    Args:
        user_id: The Graph user object ID (GUID).  Empty string returns
            ``None`` without a network request.

    Returns:
        A dict containing user profile fields on success, ``None`` if the
        user is not found (HTTP 404), Graph is disabled, or any error occurs.
        Never raises an exception to the caller.
    """
    if not _graph_enabled or not user_id:
        return None

    headers = _make_headers()
    if headers is None:
        return None

    url = f"{Config.GRAPH_BASE_URL}/users/{user_id}"
    params = {
        "$select": "id,displayName,mail,jobTitle,department,officeLocation,businessPhones",
        "$expand": "manager($select=displayName)",
    }

    try:
        resp = _graph_request_with_retry("GET", url, headers=headers, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph get_user_profile failed for user %r: %s", user_id, exc)
        return None


def get_user_photo_96(user_id: str) -> bytes | None:
    """Retrieve the 96x96 profile photo for a user as raw bytes.

    Uses the ``/photos/96x96/$value`` endpoint which returns a consistently
    sized thumbnail suitable for display in the chat UI.  Returns ``None``
    silently when the user has no photo (HTTP 404) — missing photos are normal
    in large organisations and must not generate log noise.

    Args:
        user_id: The Graph user object ID (GUID).  Empty string returns
            ``None`` without a network request.

    Returns:
        JPEG bytes on success, ``None`` if the user has no photo or Graph is
        disabled.  Never raises an exception to the caller.
    """
    if not _graph_enabled or not user_id:
        return None

    headers = _make_headers()
    if headers is None:
        return None

    url = f"{Config.GRAPH_BASE_URL}/users/{user_id}/photos/96x96/$value"

    try:
        resp = _graph_request_with_retry("GET", url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph get_user_photo_96 failed for user %r: %s", user_id, exc)
        return None
