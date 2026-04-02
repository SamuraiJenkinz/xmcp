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

-- Feedback votes on individual assistant messages.
-- assistant_message_idx: 0-based ordinal counting only content-bearing
--   assistant messages within the thread's messages_json array.
-- vote: 'up' | 'down' — retraction deletes the row (no NULL votes).
-- comment: optional freetext from thumbs-down popover (max 500 chars, enforced at API).

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
