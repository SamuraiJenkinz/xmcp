# Phase 8: Conversation Persistence - Research

**Researched:** 2026-03-21
**Domain:** Flask + SQLite (stdlib sqlite3), sidebar UI, conversation CRUD, inline rename
**Confidence:** HIGH

## Summary

Phase 8 migrates conversation storage from Flask's filesystem sessions to SQLite,
adds a left sidebar for thread navigation, and implements auto-naming. The stack
is entirely standard library on the Python side (sqlite3) — no new pip dependency
needed. The Flask official tutorial documents the exact `get_db` / `close_db` /
`init_db` pattern to follow. JSON column type (TEXT) is idiomatic SQLite for storing
message arrays and tool_call metadata. The UI changes are pure vanilla JS + CSS
extensions to what already exists — no additional frontend libraries required.

The primary risk area is the migration boundary: sessions currently own the
conversation list, and after Phase 8 sessions own only auth/token data. The
`chat_stream` route must be updated to read/write from SQLite rather than
`session["conversation"]`. The session remains the single source for user identity
(`session["user"]`), which drives the `user_id` foreign key that scopes threads.

**Primary recommendation:** Use Python stdlib `sqlite3` with the Flask official
`get_db` / teardown pattern, store messages as a JSON TEXT column per thread,
and add a `db.py` module plus a `schema.sql` file. Do not introduce SQLAlchemy
or Flask-SQLAlchemy — they would add operational complexity with no benefit at
this scale.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib (Python 3.11+) | Persistence layer | Zero extra dependency; official Flask pattern; correct for <100 users |
| json (stdlib) | stdlib | Serialize message list + tool_call dicts | Idiomatic Python; no ORM needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| flask.g | Flask 3.x | Per-request DB connection holder | Used by every request touching SQLite |
| flask.current_app | Flask 3.x | Access app config inside `get_db` | Required in blueprint/module scope |
| click (bundled with Flask) | Flask 3.x | `flask init-db` CLI command | One-time schema bootstrap |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 (stdlib) | Flask-SQLAlchemy + SQLAlchemy | Unnecessary abstraction; adds ~3 packages; migration complexity |
| sqlite3 (stdlib) | peewee / tortoise-orm | Same as above — no benefit at this scale |
| TEXT JSON column | Normalized messages table | More complex joins; harder to prune; no benefit vs JSON blob here |

**Installation:** No new packages required. sqlite3 is part of Python's standard
library. No changes to `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure

```
chat_app/
├── db.py              # get_db, close_db, init_db, init_app — NEW
├── schema.sql         # DDL for threads + messages tables — NEW
├── conversations.py   # Thread CRUD Flask blueprint — NEW
├── chat.py            # MODIFIED: reads/writes thread from SQLite instead of session
├── app.py             # MODIFIED: calls db.init_app(app), registers conversations_bp
├── templates/
│   └── chat.html      # MODIFIED: adds sidebar markup
└── static/
    └── app.js         # MODIFIED: sidebar JS, thread switching, inline rename
```

### Pattern 1: Flask SQLite Connection Management (Official Tutorial Pattern)

**What:** Use Flask's `g` object to hold one SQLite connection per request. Register
teardown to close automatically. Expose `get_db()` as the single call site.

**When to use:** All routes that need database access call `get_db()`.

**Example:**
```python
# chat_app/db.py
# Source: https://flask.palletsprojects.com/en/stable/tutorial/database/

import sqlite3
import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """Return the per-request SQLite connection, opening it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        # Enable WAL mode on first open for better concurrent read performance
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None) -> None:
    """Close the SQLite connection at the end of every request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Execute schema.sql against the configured database."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))


@click.command("init-db")
def init_db_command() -> None:
    """Create or reset the conversation database."""
    init_db()
    click.echo("Database initialised.")


def init_app(app) -> None:
    """Register db teardown and CLI command with the app factory."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
```

**Wire into app.py:**
```python
# chat_app/app.py  (additions inside create_app)
from chat_app import db as _db

def create_app() -> Flask:
    app = Flask(__name__)
    # ... existing config, session setup ...
    _db.init_app(app)
    # ... blueprints, openai init, mcp init ...
    return app
```

**Configure DATABASE path in Config:**
```python
# chat_app/config.py addition
import os
DATABASE: str = os.environ.get(
    "CHAT_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "chat.db"),
)
```

### Pattern 2: SQLite Schema — Two-Table Design

**What:** `threads` table owns user-scoped conversation metadata; `messages` stores
the full message history as a JSON TEXT blob. Tool call metadata is embedded in the
JSON blob, not normalized — this matches the existing `list[dict]` structure already
in session and avoids complex joins when loading a thread.

**When to use:** All message history operations. Load = read one row; save = UPDATE
one row.

```sql
-- chat_app/schema.sql
-- Source: Flask tutorial pattern + sqlite3 docs

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS threads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,             -- session['user']['oid'] (Azure AD object ID)
    name        TEXT    NOT NULL DEFAULT '',   -- auto-named or user-renamed
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    messages_json TEXT NOT NULL DEFAULT '[]'  -- JSON array of OpenAI message dicts
);

-- One messages row per thread (1:1 relationship, simpler than per-message rows)
CREATE INDEX IF NOT EXISTS idx_threads_user_updated
    ON threads(user_id, updated_at DESC);
```

**Why 1:1 messages row per thread (not per-message rows):**
- The context window pruning (`prune_conversation`) already operates on the full
  list in memory; loading the whole JSON blob is correct and simpler.
- No joins needed to reconstruct the conversation.
- Tool call metadata (multi-field dicts with nested tool_calls arrays) stores cleanly
  as JSON without a separate tool_calls table.
- The tradeoff is that partial message queries are harder — but this app never needs
  them (it always loads the full thread).

**Why TEXT for user_id (not INTEGER FK to a users table):**
- Azure AD OIDs are UUIDs (strings). There is no users table and no reason to create
  one — the session is the authoritative user store.

### Pattern 3: Thread CRUD Routes

**What:** A dedicated Flask Blueprint (`conversations_bp`) exposes REST-ish JSON
routes for the sidebar to call via fetch. The SSE streaming route (`chat_stream`)
is updated to accept a `thread_id` in the POST body.

```python
# chat_app/conversations.py  — skeleton

from flask import Blueprint, jsonify, request, session
from chat_app.db import get_db
from chat_app.auth import login_required
import json, time

conversations_bp = Blueprint("conversations_bp", __name__)

def _user_id() -> str:
    """Return the Azure AD OID for the current session user."""
    return (session.get("user") or {}).get("oid", "")


@conversations_bp.route("/api/threads", methods=["GET"])
@login_required
def list_threads():
    db = get_db()
    rows = db.execute(
        "SELECT id, name, updated_at FROM threads "
        "WHERE user_id = ? ORDER BY updated_at DESC",
        (_user_id(),),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@conversations_bp.route("/api/threads", methods=["POST"])
@login_required
def create_thread():
    db = get_db()
    cur = db.execute(
        "INSERT INTO threads (user_id, name) VALUES (?, ?)",
        (_user_id(), ""),
    )
    thread_id = cur.lastrowid
    db.execute(
        "INSERT INTO messages (thread_id, messages_json) VALUES (?, ?)",
        (thread_id, "[]"),
    )
    db.commit()
    return jsonify({"id": thread_id, "name": ""}), 201


@conversations_bp.route("/api/threads/<int:thread_id>", methods=["PATCH"])
@login_required
def rename_thread(thread_id: int):
    data = request.get_json(force=True) or {}
    new_name = (data.get("name") or "").strip()[:100]
    db = get_db()
    db.execute(
        "UPDATE threads SET name = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
        "WHERE id = ? AND user_id = ?",
        (new_name, thread_id, _user_id()),
    )
    db.commit()
    return jsonify({"id": thread_id, "name": new_name})


@conversations_bp.route("/api/threads/<int:thread_id>", methods=["DELETE"])
@login_required
def delete_thread(thread_id: int):
    db = get_db()
    db.execute(
        "DELETE FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, _user_id()),
    )
    db.commit()  # ON DELETE CASCADE removes messages row automatically
    return jsonify({"deleted": True})
```

### Pattern 4: Loading a Thread's Message History

**What:** When the sidebar selects a thread, the frontend fetches messages via
`GET /api/threads/<id>/messages`. The chat stream route reads from the same thread.

```python
@conversations_bp.route("/api/threads/<int:thread_id>/messages", methods=["GET"])
@login_required
def get_messages(thread_id: int):
    db = get_db()
    # Verify ownership before returning messages
    thread = db.execute(
        "SELECT id FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, _user_id()),
    ).fetchone()
    if thread is None:
        return jsonify({"error": "Not found"}), 404
    row = db.execute(
        "SELECT messages_json FROM messages WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()
    messages = json.loads(row["messages_json"]) if row else []
    return jsonify({"messages": messages})
```

### Pattern 5: Updating chat_stream to Use SQLite

**What:** `chat_stream` currently reads from `session["conversation"]` and writes back
to it. After Phase 8 it reads from and writes to the `messages` table for a specific
`thread_id`.

Key changes to `chat.py`:
1. POST body must include `thread_id` (from the JS sidebar state).
2. Read conversation from `messages` table (JSON parse), not `session`.
3. After streaming, write conversation back to `messages` table (JSON dump).
4. On first message in thread, auto-name the thread from message text (truncate ~30 chars).
5. Touch `threads.updated_at` after every message so ordering stays correct.

```python
# Inside chat_stream route — reading/writing thread
from chat_app.db import get_db
import json

thread_id: int = (request.json or {}).get("thread_id")
# ... validate thread_id ownership ...

db = get_db()
row = db.execute(
    "SELECT messages_json FROM messages WHERE thread_id = ?", (thread_id,)
).fetchone()
conversation = json.loads(row["messages_json"]) if row else []
if not conversation:
    conversation = [build_system_message()]

# ... after streaming completes inside generate() ...
db = get_db()
db.execute(
    "UPDATE messages SET messages_json = ? WHERE thread_id = ?",
    (json.dumps(conversation), thread_id),
)
db.execute(
    "UPDATE threads SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
    "WHERE id = ?",
    (thread_id,),
)
db.commit()
```

**Critical:** `generate()` is a generator and runs inside `stream_with_context`.
`get_db()` is safe to call inside the generator because `stream_with_context`
preserves the Flask request context. The existing pattern already reads session
data before the generator; the DB write can happen inside the generator after the
stream completes.

### Pattern 6: Auto-Naming from First Message

**What:** After the first user message in a thread, name the thread using the first
~30 chars of the message text. Use a simple truncation with ellipsis.

```python
def _auto_name(text: str, max_chars: int = 30) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\u2026"  # ellipsis

# Inside generate() — after detecting this is the first message:
thread_row = db.execute(
    "SELECT name FROM threads WHERE id = ?", (thread_id,)
).fetchone()
if thread_row and not thread_row["name"]:
    auto_name = _auto_name(user_message)
    db.execute(
        "UPDATE threads SET name = ? WHERE id = ?",
        (auto_name, thread_id),
    )
```

**Fallback name** when auto-naming is called with empty/whitespace input (shouldn't
happen in practice, but defensive):

```python
import datetime

def _fallback_name() -> str:
    now = datetime.datetime.now()
    return now.strftime("Chat \u2014 %b %-d, %-I:%M %p")
    # → "Chat — Mar 21, 2:30 PM"
    # Note: %-d and %-I are Linux-only (no leading zero).
    # Windows equivalent: %#d and %#I
```

**Platform note:** The `%-d` / `%-I` format codes (no leading zero) work on Linux but
not Windows. Since the server runs on Linux, this is safe for production. The
fallback will only trigger if `user_message` is somehow empty after the strip check.

### Pattern 7: Inline Rename (contenteditable)

**What:** Thread names in the sidebar become editable on click via `contenteditable`.
User clicks the thread name, edits, presses Enter or blurs — JavaScript sends
`PATCH /api/threads/<id>` with `{"name": "<new>"}`.

```javascript
// In app.js — inline rename handler
function makeRenameHandler(threadId, nameEl) {
    nameEl.addEventListener('blur', function () {
        var newName = nameEl.textContent.trim();
        fetch('/api/threads/' + threadId, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: newName})
        }).catch(function (err) {
            console.error('[Atlas] Rename failed:', err);
        });
    });
    nameEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            nameEl.blur();  // triggers blur handler above
        }
        if (e.key === 'Escape') {
            // Restore original name
            nameEl.textContent = nameEl.dataset.originalName || '';
            nameEl.blur();
        }
    });
}
```

### Pattern 8: Delete Confirmation Dialog

**What:** Native `window.confirm()` is the recommended zero-dependency approach for
a simple confirmation before deleting a thread. It blocks and is synchronous —
appropriate for a confirmation dialog that has no UX polish requirement.

```javascript
function deleteThread(threadId) {
    if (!window.confirm('Delete this conversation? This cannot be undone.')) return;
    fetch('/api/threads/' + threadId, {method: 'DELETE'})
        .then(function () {
            // Remove from sidebar DOM, select next thread
        });
}
```

### Pattern 9: Initial App Load Behavior (Claude's Discretion)

**Recommendation:** Load the most recently updated thread on initial app load.
This matches the user expectation from tools like Claude.ai and ChatGPT — returning
colleagues see their last conversation immediately without needing to click.

Implementation: The `GET /chat` route passes `last_thread_id` (highest `updated_at`
thread for the user) to the Jinja template as a data attribute. JS reads it on load
and fetches that thread's messages.

If the user has no threads yet (first visit), create a new empty thread
automatically and show the welcome message.

### Anti-Patterns to Avoid

- **Storing conversation as session data after Phase 8:** Session will still hold
  auth data. The conversation must move entirely to SQLite. Do not maintain a dual
  write to both session and DB.
- **Per-message rows with tool_calls normalized:** Adds JOIN complexity and a
  separate tool_calls table without any query benefit for this use case.
- **Using Flask-SQLAlchemy:** Adds three packages, migration tooling (Alembic), and
  ORM concepts for a schema with two tables. Use stdlib sqlite3.
- **Using a users table:** Azure AD OID is already authoritative. No point adding
  a users table that duplicates MSAL session data.
- **Opening a SQLite connection per route:** Always use `get_db()` → Flask `g` pattern.
  Opening connections in each view function skips connection reuse and proper teardown.
- **Storing system prompt in DB:** The context confirms system prompt is global/code.
  Do not store it. Inject it at thread load time (`build_system_message()`), same
  as today.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Connection lifetime management | Manual open/close in each route | `get_db()` + `teardown_appcontext` | Flask official pattern; prevents connection leaks |
| Schema migration | Custom upgrade scripts | `flask init-db` + `IF NOT EXISTS` DDL | Phase 8 is schema creation, not migration from existing data |
| JSON serialization of message list | Custom encoder | `json.dumps` / `json.loads` | stdlib is correct; dicts from OpenAI are already JSON-safe after `_message_to_dict()` |
| Thread ownership check | Trust frontend thread_id | Always `WHERE id = ? AND user_id = ?` | Security: users must not access other users' threads |

**Key insight:** The biggest thing NOT to hand-roll is the ownership check. Every
single DB query that touches threads or messages must filter by `user_id`. Failing
to do this would allow one user to read or delete another's thread by guessing an ID.

## Common Pitfalls

### Pitfall 1: Accessing DB Inside Generator Without Request Context

**What goes wrong:** `get_db()` inside `stream_with_context` generator works, but
if `db.commit()` or a new `get_db()` call happens after the response is sent (in a
background thread, for example), Flask raises "Working outside of request context".

**Why it happens:** The existing code already notes this risk with session reads.
The same applies to SQLite writes inside `generate()`.

**How to avoid:** Perform all DB writes at the END of the generator body, before
`yield _sse({"type": "done"})`. Do not spawn background threads for DB writes.

**Warning signs:** `RuntimeError: Working outside of request context` in logs.

### Pitfall 2: Missing `db.commit()` After Writes

**What goes wrong:** Thread is created, renamed, or messages are saved, but on next
request the data is gone — SQLite did not persist the change.

**Why it happens:** sqlite3 defaults to `isolation_level="DEFERRED"` — writes are
buffered in a transaction until `commit()` or connection close. If the connection
closes without commit, changes are rolled back.

**How to avoid:** Always call `db.commit()` after every INSERT, UPDATE, or DELETE.
The `close_db` teardown does NOT commit — it only closes.

**Warning signs:** Data appears in memory during the request but is missing on reload.

### Pitfall 3: Thread Ownership Not Checked

**What goes wrong:** A user sends `POST /chat/stream` with someone else's `thread_id`
and reads or writes to that thread.

**Why it happens:** Frontend sends the thread_id; if the server trusts it without
checking `user_id`, any authenticated user can access any thread.

**How to avoid:** Every DB query: `WHERE id = ? AND user_id = ?`. Return 403/404 if
no row matches. Apply this consistently to: load messages, stream (write), rename,
delete.

**Warning signs:** Missing `AND user_id = ?` in SQL queries.

### Pitfall 4: `check_same_thread` Error with Waitress

**What goes wrong:** Waitress uses a thread pool. SQLite connections created in one
thread cannot be used in another if `check_same_thread=True` (the default). This
causes `ProgrammingError: SQLite objects created in a thread can only be used in
that same thread`.

**Why it happens:** The `g` object is per-request but Waitress may dispatch requests
from different threads. Flask's `g` is tied to the application context, not a single
thread — each request gets its own `g`, so each request opens its own connection.
This means each connection IS used only in the thread that opened it.

**How to avoid:** The standard `get_db()` / teardown pattern already handles this
correctly — each request creates its own connection, uses it, and closes it. Do not
share connections across requests. With WAL mode, concurrent reads from multiple
threads/requests are safe.

**Warning signs:** `ProgrammingError: SQLite objects created in a thread` in logs.

### Pitfall 5: `generate()` Closes Over Stale Conversation State

**What goes wrong:** `conversation` variable captured by the `generate()` closure
is the pre-request state. If the DB is written inside `generate()` using a fresh
`get_db()` call but the thread has been renamed/deleted mid-stream by a concurrent
request, the write silently succeeds with stale data.

**Why it happens:** Each SSE stream is a long-lived request. Concurrent requests
on the same thread_id would be unusual (same user, two tabs), but possible.

**How to avoid:** This is acceptable behavior for Phase 8 — last writer wins. The
important thing is not to lose messages; last-write-wins for concurrent same-thread
updates is fine given the <100 user assumption.

### Pitfall 6: Sidebar Shows Stale Thread List After Operations

**What goes wrong:** User creates a new thread or deletes one; sidebar doesn't
update because the thread list was fetched once on page load.

**Why it happens:** Single-page fetch pattern without reactive updates.

**How to avoid:** After create/delete/rename operations, re-fetch `GET /api/threads`
and re-render the sidebar from the response. Do this in the JS handlers for each
operation.

### Pitfall 7: `strftime('%Y-%m-%dT%H:%M:%SZ', 'now')` vs `CURRENT_TIMESTAMP`

**What goes wrong:** Using `CURRENT_TIMESTAMP` in schema DDL gives `YYYY-MM-DD
HH:MM:SS` without the `Z` suffix. Sorting by this string still works (ISO 8601
alphabetical order = chronological order), but the format is slightly inconsistent.

**How to avoid:** Use `strftime('%Y-%m-%dT%H:%M:%SZ', 'now')` in DEFAULT expressions
and UPDATE statements for consistent ISO 8601 UTC with `Z` suffix. Both are stored
as TEXT and sort correctly.

### Pitfall 8: `json.dumps` of SQLite `Row` Objects

**What goes wrong:** SQLite `Row` objects (when `row_factory = sqlite3.Row`) are NOT
JSON-serializable. Calling `json.dumps(row)` raises `TypeError`.

**Why it happens:** `sqlite3.Row` is a special mapping type, not a plain dict.

**How to avoid:** Always convert: `dict(row)` or `[dict(r) for r in rows]` before
passing to `jsonify()`. The `get_db()` pattern uses `sqlite3.Row` for
attribute access, but serialization always needs `dict()` conversion.

## Code Examples

Verified patterns from official sources:

### Database Module (db.py) — Official Flask Tutorial Pattern

```python
# Source: https://flask.palletsprojects.com/en/stable/tutorial/database/
import sqlite3
import click
from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(e=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))


@click.command("init-db")
def init_db_command() -> None:
    init_db()
    click.echo("Database initialised.")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
```

### Schema DDL (schema.sql)

```sql
-- Source: sqlite3 docs + Flask tutorial pattern
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

CREATE INDEX IF NOT EXISTS idx_threads_user_updated
    ON threads(user_id, updated_at DESC);
```

### Parameterized Query with Row Conversion

```python
# Source: https://docs.python.org/3/library/sqlite3.html
db = get_db()
rows = db.execute(
    "SELECT id, name, updated_at FROM threads WHERE user_id = ? ORDER BY updated_at DESC",
    (user_id,),
).fetchall()
# Convert sqlite3.Row to dict for jsonify
return jsonify([dict(r) for r in rows])
```

### JSON Round-Trip for Messages

```python
# Saving messages to DB
import json
db.execute(
    "UPDATE messages SET messages_json = ? WHERE thread_id = ?",
    (json.dumps(conversation), thread_id),
)
db.commit()

# Loading messages from DB
row = db.execute(
    "SELECT messages_json FROM messages WHERE thread_id = ?",
    (thread_id,),
).fetchone()
conversation = json.loads(row["messages_json"]) if row else []
```

### Fetch from JavaScript with JSON body (PATCH / DELETE)

```javascript
// Source: https://flask.palletsprojects.com/en/stable/patterns/javascript/
fetch('/api/threads/' + threadId, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: newName})
}).then(function(r) { return r.json(); })
  .then(function(data) { /* update DOM */ });
```

### Sidebar Thread List Render (JavaScript)

```javascript
function renderSidebar(threads, activeId) {
    var list = document.getElementById('thread-list');
    list.innerHTML = '';
    threads.forEach(function(t) {
        var li = document.createElement('li');
        li.className = 'thread-item' + (t.id === activeId ? ' active' : '');
        li.dataset.id = t.id;
        var nameSpan = document.createElement('span');
        nameSpan.className = 'thread-name';
        nameSpan.textContent = t.name || 'New chat';
        nameSpan.contentEditable = 'true';
        nameSpan.dataset.originalName = t.name;
        var delBtn = document.createElement('button');
        delBtn.className = 'thread-delete';
        delBtn.textContent = '\u00d7';  // ×
        delBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            deleteThread(t.id);
        });
        li.appendChild(nameSpan);
        li.appendChild(delBtn);
        li.addEventListener('click', function() { switchThread(t.id); });
        makeRenameHandler(t.id, nameSpan);
        list.appendChild(li);
    });
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Conversation in filesystem session | Conversation in SQLite `messages.messages_json` | Phase 8 | Cross-session persistence; user scoping |
| Single implicit conversation | Named threads with sidebar | Phase 8 | Multiple parallel threads per user |
| Session-cleared on logout | Threads persist independently | Phase 8 | History survives logout/session expiry |

**Deprecated/outdated in Phase 8:**
- `session["conversation"]` key: Must be fully removed from `chat.py` — replaced by
  thread_id + DB reads/writes.
- `POST /chat/clear`: Route behavior changes — it now deletes all messages in a
  thread (or just creates a new thread via the sidebar). Consider deprecating or
  repurposing.

## Open Questions

1. **`/chat/clear` route fate**
   - What we know: Currently clears `session["conversation"]`. In Phase 8 there is
     no conversation in session.
   - What's unclear: Should this route be removed, repurposed as "delete thread", or
     kept as a stub?
   - Recommendation: Remove it. The sidebar's delete button replaces its function.
     If any JS currently calls `/chat/clear`, update it to use `DELETE /api/threads/<id>`.

2. **`chat_stream` concurrency with DB write inside generator**
   - What we know: `stream_with_context` preserves request context; `get_db()` works
     inside generators. Waitress thread pool means multiple requests can run
     simultaneously.
   - What's unclear: Whether SQLite WAL mode handles concurrent writes to different
     threads (rows) correctly without locking.
   - Recommendation: WAL mode allows concurrent reads and one writer at a time. For
     this user count (<100), a brief write lock per message completion is acceptable.
     No special serialization needed.

3. **Database file location**
   - What we know: Config should be env-configurable via `CHAT_DB_PATH`.
   - What's unclear: Default path when running from different working directories.
   - Recommendation: Default to `os.path.join(os.path.dirname(__file__), "..", "chat.db")`
     — places `chat.db` at project root next to `pyproject.toml`. This is
     deterministic regardless of CWD.

4. **Session `conversation` key removal**
   - What we know: All existing code writes to `session["conversation"]`.
   - What's unclear: Whether any test fixtures or test_client code depends on it.
   - Recommendation: Search for all references to `_CONVERSATION_KEY` and `"conversation"`
     in the codebase before removing. The existing `chat.py` module-level constant
     `_CONVERSATION_KEY = "conversation"` should be deleted entirely.

## Sources

### Primary (HIGH confidence)
- Flask official docs: https://flask.palletsprojects.com/en/stable/tutorial/database/ — `get_db`, `close_db`, `init_db`, `init_app` pattern
- Flask official docs: https://flask.palletsprojects.com/en/stable/patterns/sqlite3/ — connection management with `g`, `teardown_appcontext`, `row_factory`
- Flask official docs: https://flask.palletsprojects.com/en/stable/patterns/javascript/ — fetch + JSON API pattern from Flask
- Python stdlib docs: https://docs.python.org/3/library/sqlite3.html — WAL mode, `row_factory`, `check_same_thread`, `PARSE_DECLTYPES`
- SQLite official docs: https://sqlite.org/json1.html — JSON as TEXT column, `json()` validation

### Secondary (MEDIUM confidence)
- WebSearch: Flask + sqlite3 `g` object pattern confirmed by multiple official Flask doc pages
- WebSearch: `strftime('%Y-%m-%dT%H:%M:%SZ', 'now')` for UTC ISO 8601 in SQLite — confirmed by sqlite3 docs

### Tertiary (LOW confidence)
- WebSearch: `contenteditable` inline rename pattern — standard DOM API, confirmed in MDN but not fetched directly
- WebSearch: `window.confirm()` for delete confirmation — standard browser API

## Metadata

**Confidence breakdown:**
- Standard stack (sqlite3, stdlib): HIGH — verified against official Flask docs and Python stdlib docs
- Architecture patterns (db.py module, schema design, CRUD routes): HIGH — directly derived from official Flask tutorial pattern
- JSON column for messages: HIGH — confirmed by sqlite3 docs and SQLite json1 docs
- Inline rename (contenteditable): MEDIUM — standard DOM API, implementation detail is Claude's discretion anyway
- Pitfalls: HIGH — derived from official docs (check_same_thread, commit required, Row serialization)

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (sqlite3 and Flask patterns are very stable; 30-day window is conservative)
