"""Microsoft Graph API client — isolated singleton for colleague lookup."""

from __future__ import annotations

import base64
import json
import logging

import msal
import requests

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
