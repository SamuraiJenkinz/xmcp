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

-- FTS5 full-text search index over thread message content.
-- Only user and assistant role messages are indexed (system/tool messages excluded).
-- unicode61 tokenizer preserves Exchange technical terms (e.g. DAGHealth, HMC).

CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
    body,
    tokenize='unicode61'
);

-- Sync trigger: after new messages row inserted, rebuild FTS entry for that thread.
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

-- Sync trigger: after messages row updated (new chat turn saved), rebuild FTS entry.
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

-- Sync trigger: after thread deleted, remove FTS entry.
CREATE TRIGGER IF NOT EXISTS threads_fts_ad
AFTER DELETE ON threads
BEGIN
    DELETE FROM threads_fts WHERE rowid = OLD.id;
END;

-- Backfill: index all existing threads that have messages.
-- INSERT OR IGNORE is idempotent — safe to run on every startup.
INSERT OR IGNORE INTO threads_fts(rowid, body)
SELECT m.thread_id,
       group_concat(json_extract(j.value, '$.content'), ' ')
FROM   messages m,
       json_each(m.messages_json) j
WHERE  json_extract(j.value, '$.role') IN ('user', 'assistant')
AND    json_extract(j.value, '$.content') IS NOT NULL
GROUP BY m.thread_id;
