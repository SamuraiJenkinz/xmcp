---
phase: 08-conversation-persistence
plan: 01
subsystem: database
tags: [sqlite3, flask, blueprint, crud, rest-api, conversation-persistence]

requires:
  - phase: 07-chat-app-core
    provides: Flask app factory, auth blueprint with login_required, Flask session with user OID

provides:
  - SQLite database module (db.py) with Flask official tutorial pattern
  - Schema DDL (schema.sql) with threads and messages tables
  - Thread CRUD REST blueprint (conversations_bp) with 5 routes
  - DATABASE config path wired into Flask app config
  - Auto-bootstrap: schema created on first app startup without manual CLI

affects:
  - 08-02: chat.py must call get_db() instead of session["conversation"]
  - 08-03: sidebar UI depends on /api/threads/* routes existing

tech-stack:
  added: []
  patterns:
    - "Flask official tutorial get_db/close_db/init_db/init_app pattern for SQLite"
    - "Blueprint-per-resource: conversations_bp owns /api/threads/* namespace"
    - "User-scoped ownership: every SQL query includes AND user_id = ?"
    - "WAL mode + foreign_keys ON enabled on first connection open"
    - "Auto-bootstrap schema when database file does not exist"

key-files:
  created:
    - chat_app/db.py
    - chat_app/schema.sql
    - chat_app/conversations.py
  modified:
    - chat_app/config.py
    - chat_app/app.py

key-decisions:
  - "Auto-bootstrap schema in get_db() on first open — no manual flask init-db required"
  - "1:1 messages row per thread (not per-message rows) — context window pruning works on full JSON blob"
  - "user_id stored as TEXT (Azure AD OID UUID) — no users table, session is authoritative"
  - "strftime('%Y-%m-%dT%H:%M:%SZ','now') not CURRENT_TIMESTAMP — consistent ISO 8601 with Z suffix"
  - "rename_thread does NOT update updated_at — renaming should not re-order sidebar threads"

patterns-established:
  - "get_db() pattern: store connection in flask.g, configure once, teardown_appcontext closes"
  - "Ownership check pattern: every thread/messages query must include AND user_id = ?"
  - "Row conversion: always dict(row) or [dict(r) for r in rows] before jsonify()"
  - "db.commit() required after every INSERT, UPDATE, DELETE — close_db does not commit"

duration: 3min
completed: 2026-03-21
---

# Phase 8 Plan 1: SQLite Persistence Layer and Thread CRUD API Summary

**SQLite database module with Flask tutorial get_db pattern, threads+messages schema with WAL mode, and 5-route thread CRUD blueprint at /api/threads/* with user_id ownership enforcement**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-21T23:16:34Z
- **Completed:** 2026-03-21T23:18:51Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created chat_app/db.py following the official Flask tutorial get_db/close_db/init_db/init_app pattern with WAL mode and foreign key enforcement, plus auto-bootstrap on first startup
- Created chat_app/schema.sql with threads and messages DDL using IF NOT EXISTS for idempotency, CASCADE deletes, and composite index on (user_id, updated_at DESC)
- Created chat_app/conversations.py as a Flask Blueprint with 5 REST routes for thread CRUD, all enforcing user_id ownership via parameterized WHERE clauses
- Wired DATABASE config into config.py and registered db.init_app + conversations_bp in app.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SQLite database module, schema, and config** - `a4dc6ce` (feat)
2. **Task 2: Create thread CRUD blueprint and register in app factory** - `b9ae369` (feat)

**Plan metadata:** committed with SUMMARY.md and STATE.md update

## Files Created/Modified

- `chat_app/db.py` - SQLite connection management: get_db, close_db, init_db, init_app, auto-bootstrap
- `chat_app/schema.sql` - DDL for threads and messages tables with WAL, foreign keys, and index
- `chat_app/conversations.py` - conversations_bp Blueprint with 5 thread CRUD REST routes
- `chat_app/config.py` - Added DATABASE attribute pointing to chat.db at project root
- `chat_app/app.py` - Added _db.init_app(app) and app.register_blueprint(conversations_bp)

## Decisions Made

- Auto-bootstrap schema in get_db() when database file does not exist — avoids requiring a manual `flask init-db` step on first deployment; the app self-starts correctly
- rename_thread PATCH does NOT update updated_at — renaming a thread should not re-order it in the sidebar; only new messages should bump position
- 1:1 messages row per thread (not per-message rows) — matches the existing list[dict] in-memory structure, loads whole thread in one query, no joins needed
- user_id stored as TEXT (Azure AD OID) — there is no users table and no reason to create one; session["user"]["oid"] is the authoritative identity

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Python import check used wrong interpreter (system Python without flask_session); switched to .venv/Scripts/python for verification. No code changes required.

## User Setup Required

None — no external service configuration required. SQLite database creates itself at chat.db (project root) on first request.

## Next Phase Readiness

- get_db() and conversations_bp are ready for 08-02 which wires chat_stream to read/write thread messages from SQLite instead of session["conversation"]
- All 5 thread CRUD routes are live and tested — 08-03 sidebar JS can call them immediately
- No blockers for subsequent plans

---
*Phase: 08-conversation-persistence*
*Completed: 2026-03-21*
