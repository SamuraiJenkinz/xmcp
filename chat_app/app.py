"""Flask chat application for Exchange Infrastructure MCP Server."""

from __future__ import annotations

import logging
import os

from flask import Flask, redirect, render_template, session, url_for
from flask_session import Session

from chat_app.config import Config
from chat_app.secrets import load_secrets

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Flask application factory."""
    app = Flask(__name__)

    # Load secrets and update config
    secrets = load_secrets()
    Config.update_from_secrets(secrets)
    app.config.from_object(Config)

    # Ensure session directory exists
    session_dir = app.config.get("SESSION_FILE_DIR", "/tmp/flask-sessions")
    os.makedirs(session_dir, exist_ok=True)

    # Initialize server-side sessions (filesystem)
    Session(app)

    # --- Root route ---
    @app.route("/")
    def index():
        if session.get("user"):
            return redirect(url_for("chat"))
        return render_template("splash.html")

    # --- Chat route (protected — auth check; auth routes added in 07-02) ---
    @app.route("/chat")
    def chat():
        user = session.get("user")
        if not user:
            return redirect(url_for("index"))
        display_name = user.get("name", "Colleague")
        return render_template("chat.html", user=user, display_name=display_name)

    # --- Placeholder routes for auth (registered in 07-02) ---
    # login and logout routes are registered by auth blueprint in 07-02.
    # Stub them here so templates that reference url_for('login') / url_for('logout')
    # do not raise BuildError before 07-02 is wired up.
    @app.route("/login")
    def login():
        """Stub — replaced by MSAL auth flow in 07-02."""
        return redirect(url_for("index"))

    @app.route("/logout")
    def logout():
        """Stub — replaced by MSAL logout in 07-02."""
        session.clear()
        return redirect(url_for("index"))

    logger.info("Flask app created successfully")
    return app


def main() -> None:
    """Entry point: run Flask app with Waitress."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    app = create_app()
    from waitress import serve

    logger.info("Starting Waitress on %s:%s", Config.HOST, Config.PORT)
    serve(app, host=Config.HOST, port=Config.PORT)


if __name__ == "__main__":
    main()
