"""SQLite connection management following the official Flask tutorial pattern.

Sources:
  https://flask.palletsprojects.com/en/stable/tutorial/database/
  https://flask.palletsprojects.com/en/stable/patterns/sqlite3/
"""

from __future__ import annotations

import os
import sqlite3

import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return the per-request SQLite connection, opening it if needed.

    On first open the connection is stored in Flask's ``g`` object so
    subsequent calls within the same request return the same connection.
    WAL mode and foreign-key enforcement are activated once per connection.

    If the database file does not exist yet this function bootstraps the
    schema automatically so the app is self-starting without any manual
    ``flask init-db`` command.
    """
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        file_exists = os.path.exists(db_path)

        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent-read performance and
        # enforce referential integrity on every connection.
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")

        # Auto-bootstrap schema on first startup (file did not exist).
        if not file_exists:
            init_db()

    return g.db


def close_db(e: BaseException | None = None) -> None:
    """Close the SQLite connection at the end of every request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Execute schema.sql against the configured database.

    Uses ``current_app.open_resource`` so the SQL file is located relative
    to the ``chat_app`` package regardless of the working directory.
    """
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))


def migrate_db() -> None:
    """Apply additive schema migrations so existing databases gain new tables.

    Uses CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / CREATE
    TRIGGER IF NOT EXISTS / INSERT OR IGNORE — fully idempotent and safe to
    run on every startup without data loss.

    Migration history:
      v22: feedback table + analytics indexes
      v23: threads_fts FTS5 virtual table, sync triggers, and backfill
    """
    db = get_db()
    # v22 — feedback table and indexes
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id             INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            assistant_message_idx INTEGER NOT NULL,
            user_id               TEXT    NOT NULL,
            vote                  TEXT    NOT NULL CHECK(vote IN ('up', 'down')),
            comment               TEXT,
            created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            UNIQUE(thread_id, assistant_message_idx, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_thread
            ON feedback(thread_id, assistant_message_idx);

        CREATE INDEX IF NOT EXISTS idx_feedback_user_vote
            ON feedback(user_id, vote, created_at DESC);
        """
    )

    # v23 — FTS5 full-text search index, sync triggers, and backfill.
    # FTS5 virtual table creation and trigger creation are idempotent via
    # IF NOT EXISTS.  The backfill INSERT OR IGNORE skips threads already
    # present in threads_fts so repeated startups produce no duplicates.
    db.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
            body,
            tokenize='unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS messages_fts_ai
        AFTER INSERT ON messages
        BEGIN
            DELETE FROM threads_fts WHERE rowid = NEW.thread_id;
            INSERT INTO threads_fts(rowid, body)
            SELECT NEW.thread_id,
                   group_concat(json_extract(j.value, '$.content'), ' ')
            FROM   json_each(NEW.messages_json) j
            WHERE  json_extract(j.value, '$.role') IN ('user', 'assistant')
            AND    json_extract(j.value, '$.content') IS NOT NULL;
        END;

        CREATE TRIGGER IF NOT EXISTS messages_fts_au
        AFTER UPDATE ON messages
        BEGIN
            DELETE FROM threads_fts WHERE rowid = NEW.thread_id;
            INSERT INTO threads_fts(rowid, body)
            SELECT NEW.thread_id,
                   group_concat(json_extract(j.value, '$.content'), ' ')
            FROM   json_each(NEW.messages_json) j
            WHERE  json_extract(j.value, '$.role') IN ('user', 'assistant')
            AND    json_extract(j.value, '$.content') IS NOT NULL;
        END;

        CREATE TRIGGER IF NOT EXISTS threads_fts_ad
        AFTER DELETE ON threads
        BEGIN
            DELETE FROM threads_fts WHERE rowid = OLD.id;
        END;

        INSERT OR IGNORE INTO threads_fts(rowid, body)
        SELECT m.thread_id,
               group_concat(json_extract(j.value, '$.content'), ' ')
        FROM   messages m,
               json_each(m.messages_json) j
        WHERE  json_extract(j.value, '$.role') IN ('user', 'assistant')
        AND    json_extract(j.value, '$.content') IS NOT NULL
        GROUP BY m.thread_id;
        """
    )

    db.commit()


@click.command("init-db")
def init_db_command() -> None:
    """Create or reset the conversation database tables."""
    init_db()
    click.echo("Database initialised.")


def init_app(app) -> None:  # type: ignore[no-untyped-def]
    """Register db teardown and CLI command with the Flask app factory."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    # Run additive migrations on every startup so existing databases
    # gain new tables (e.g. feedback) without manual intervention.
    with app.app_context():
        migrate_db()
