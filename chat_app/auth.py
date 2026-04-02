"""MSAL auth code flow routes for Azure AD / Entra ID SSO."""

from __future__ import annotations

import datetime
import functools
import logging
from typing import Any

import msal
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

from chat_app.config import Config

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

REQUIRED_ROLE = "Atlas.User"

# Minimal error page — no separate template file needed
_ERROR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Authentication Error</title></head>
<body>
  <h2>Authentication Error</h2>
  <p>{{ error_description }}</p>
  <a href="{{ login_url }}">Try again</a>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_msal_app(cache: msal.SerializableTokenCache | None = None) -> msal.ConfidentialClientApplication:
    """Create a ConfidentialClientApplication, optionally with a token cache."""
    return msal.ConfidentialClientApplication(
        Config.AZURE_CLIENT_ID,
        authority=Config.AZURE_AUTHORITY,
        client_credential=Config.AZURE_CLIENT_SECRET,
        token_cache=cache,
    )


def _load_cache() -> msal.SerializableTokenCache:
    """Deserialise the token cache from the Flask session (or return empty cache)."""
    cache = msal.SerializableTokenCache()
    serialised = session.get("token_cache")
    if serialised:
        cache.deserialize(serialised)
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist the token cache back to the Flask session if it has changed."""
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()


def get_token_silently() -> dict[str, Any] | None:
    """
    Attempt a silent token acquisition using the cached account.

    Returns the token result dict on success, or None if no cached account
    exists or the silent call fails.
    """
    cache = _load_cache()
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if not accounts:
        return None
    result = cca.acquire_token_silent(["User.Read"], account=accounts[0])
    _save_cache(cache)
    return result or None


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------


def login_required(f):  # type: ignore[no-untyped-def]
    """Decorator that returns 401 for API routes or redirects others to splash."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):  # type: ignore[no-untyped-def]
        if not session.get("user"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("catch_all", path=""))
        return f(*args, **kwargs)

    return decorated_function


def role_required(f):  # type: ignore[no-untyped-def]
    """Decorator that enforces Atlas.User App Role on protected routes.

    Behaviour:
    - No session user (unauthenticated): 401 JSON for /api/ and /chat/ paths,
      redirect to splash for all others.
    - Authenticated but missing REQUIRED_ROLE: 403 JSON for /api/ and /chat/
      paths (includes upn so frontend can display it), redirect to splash
      for all others.  All 403 denials are logged with UPN, endpoint, and
      timestamp.
    - Authenticated with REQUIRED_ROLE: request passes through to the handler.
    """

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):  # type: ignore[no-untyped-def]
        user = session.get("user")
        if not user:
            if request.path.startswith("/api/") or request.path.startswith("/chat/"):
                return (
                    jsonify({"error": "authentication_required", "message": "Login required"}),
                    401,
                )
            return redirect(url_for("catch_all", path=""))

        if REQUIRED_ROLE not in user.get("roles", []):
            upn = user.get("preferred_username", "")
            logger.warning(
                "403 Forbidden: upn=%s endpoint=%s ts=%s",
                upn,
                request.path,
                datetime.datetime.utcnow().isoformat(),
            )
            if request.path.startswith("/api/") or request.path.startswith("/chat/"):
                return (
                    jsonify(
                        {
                            "error": "forbidden",
                            "message": "Atlas.User role required",
                            "required_role": REQUIRED_ROLE,
                            "upn": upn,
                        }
                    ),
                    403,
                )
            return redirect(url_for("catch_all", path=""))

        return f(*args, **kwargs)

    return decorated_function


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@auth_bp.route("/login")
def login() -> Any:
    """
    Initiate the MSAL auth code flow.

    Stores the flow dict in the session and redirects the browser to the
    Microsoft login page.
    """
    cca = _build_msal_app()
    flow = cca.initiate_auth_code_flow(
        scopes=["User.Read"],
        redirect_uri=url_for("auth.auth_callback", _external=True),
    )
    session["auth_flow"] = flow
    return redirect(flow["auth_uri"])


@auth_bp.route("/auth/callback")
def auth_callback() -> Any:
    """
    Handle the authorization code callback from Microsoft.

    Exchanges the auth code for tokens, stores the user's id_token_claims in
    the session, and persists the SerializableTokenCache for silent re-auth.

    Handles:
    - ValueError (CSRF / state mismatch) — redirects to /login
    - 'error' in result (e.g. Conditional Access interaction_required) — shows
      a descriptive error page instead of crashing
    """
    cache = _load_cache()
    cca = _build_msal_app(cache=cache)

    auth_flow = session.pop("auth_flow", {})
    try:
        result = cca.acquire_token_by_auth_code_flow(auth_flow, request.args)
    except ValueError as exc:
        # CSRF protection: state mismatch or stale / missing auth_flow
        logger.warning("Auth code flow state mismatch: %s", exc)
        return redirect(url_for("auth.login"))

    if "error" in result:
        error_description = result.get(
            "error_description", result.get("error", "Unknown authentication error")
        )
        logger.warning("Auth error: %s — %s", result.get("error"), error_description)
        # Conditional Access / interaction_required and other recoverable errors
        # redirect back to login so MSAL can request the missing claims/MFA step.
        error_code = result.get("error", "")
        if "interaction_required" in error_code or "invalid_grant" in error_code:
            return redirect(url_for("auth.login"))
        return render_template_string(
            _ERROR_TEMPLATE,
            error_description=error_description,
            login_url=url_for("auth.login"),
        ), 400

    # Successful token acquisition — store user identity
    session["user"] = result.get("id_token_claims")
    _save_cache(cache)
    logger.info(
        "User authenticated: %s",
        session["user"].get("preferred_username") if session.get("user") else "unknown",
    )
    return redirect(url_for("chat"))


@auth_bp.route("/logout")
def logout() -> Any:
    """Clear the session and redirect to the splash page."""
    session.clear()
    return redirect(url_for("catch_all", path=""))
