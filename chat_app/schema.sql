-- SQLite schema for conversation persistence.
-- Uses IF NOT EXISTS throughout so this script is idempotent and safe to
-- re-run (e.g. via `flask init-db`) without destroying existing data.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS threads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT    NOT NULL,
    name       TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id     INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    messages_json TEXT    NOT NULL DEFAULT '[]'
);

-- Composite index: all queries filter by user_id then sort by updated_at DESC.
CREATE INDEX IF NOT EXISTS idx_threads_user_updated
    ON threads(user_id, updated_at DESC);
