"""Flask chat application for Exchange Infrastructure MCP Server."""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, redirect, render_template, session, url_for
from flask_session import Session

from chat_app import db as _db
from chat_app.auth import auth_bp, login_required
from chat_app.chat import chat_bp
from chat_app.config import Config
from chat_app.conversations import conversations_bp
from chat_app.db import get_db
from chat_app.graph_client import init_graph
from chat_app.mcp_client import get_openai_tools, init_mcp, is_connected
from chat_app.openai_client import init_openai
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

    # Initialize SQLite database (registers teardown and CLI command)
    _db.init_app(app)

    # Register conversations blueprint (provides /api/threads/* CRUD routes)
    app.register_blueprint(conversations_bp)

    # Register auth blueprint (provides /login, /auth/callback, /logout)
    app.register_blueprint(auth_bp)

    # Register chat blueprint (provides /chat/stream)
    app.register_blueprint(chat_bp)

    # --- Initialize OpenAI client ---
    # Graceful degradation: log error but allow app to start for development.
    try:
        init_openai()
    except Exception as exc:
        logger.error("OpenAI client initialization failed (degraded mode): %s", exc)

    # --- Initialize MCP client (spawns exchange_mcp.server subprocess) ---
    # Graceful degradation: chat works without tools if MCP is unavailable.
    try:
        init_mcp(app)
    except Exception as exc:
        logger.error("MCP client initialization failed (degraded mode — no tools): %s", exc)

    # --- Initialize Graph API client (colleague lookup) ---
    # Graceful degradation: chat works without Graph if consent is missing.
    try:
        init_graph(
            client_id=Config.AZURE_CLIENT_ID,
            client_secret=Config.AZURE_CLIENT_SECRET,
            tenant_id=Config.AZURE_TENANT_ID,
        )
    except Exception as exc:
        logger.error("Graph client initialization failed (degraded mode): %s", exc)

    # --- Root route ---
    @app.route("/")
    def index():
        if session.get("user"):
            return redirect(url_for("chat"))
        return render_template("splash.html")

    # --- Chat route (protected) ---
    @app.route("/chat")
    @login_required
    def chat():
        user = session.get("user")
        display_name = user.get("name", "Colleague")
        # Find the user's most recently active thread for initial sidebar focus
        db = get_db()
        user_id = user.get("oid", "")
        last_thread = db.execute(
            "SELECT id FROM threads WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        last_thread_id = last_thread["id"] if last_thread else None
        return render_template(
            "chat.html",
            user=user,
            display_name=display_name,
            last_thread_id=last_thread_id,
        )

    # --- Health endpoint ---
    @app.route("/api/health")
    def health():
        """Report application health including MCP connectivity and tool count."""
        mcp_connected = is_connected()
        tools = get_openai_tools()
        return jsonify(
            {
                "status": "ok",
                "mcp_connected": mcp_connected,
                "tools_count": len(tools),
            }
        )

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
