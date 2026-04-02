---
phase: 23-thread-search
plan: 01
subsystem: database, api
tags: [sqlite, fts5, search, fulltext, triggers, flask, python]

requires:
  - phase: 22-per-message-feedback
    provides: migrate_db() pattern, conversations_bp, role_required, _user_id() helper
  - phase: 21-auth
    provides: role_required decorator, session user structure

provides:
  - FTS5 threads_fts virtual table with unicode61 tokenizer
  - 3 sync triggers (messages_fts_ai, messages_fts_au, threads_fts_ad) keeping FTS index current
  - Idempotent backfill INSERT OR IGNORE populating FTS for existing threads on every startup
  - GET /api/threads/search?q=term endpoint scoped to authenticated user
  - _build_fts5_query() helper neutralising FTS5 operators via quoting
  - _strip_mark_tags() helper returning plain-text snippets

affects:
  - 23-thread-search (plan 02 — frontend SearchInput will call this endpoint)
  - Any future search expansion (cross-field, date range, etc.)

tech-stack:
  added: []
  patterns:
    - "FTS5 virtual table with rowid=thread_id for direct JOIN to threads table"
    - "DELETE+INSERT pattern in AFTER INSERT/UPDATE triggers prevents duplicate FTS rows"
    - "INSERT OR IGNORE backfill runs in migrate_db() on every startup — idempotent"
    - "try/except around db.execute for FTS MATCH — malformed queries return [] not 500"
    - "_build_fts5_query: token quoting with trailing * for prefix match, neutralises bare operators"

key-files:
  created: []
  modified:
    - chat_app/schema.sql
    - chat_app/db.py
    - chat_app/conversations.py

key-decisions:
  - "INSERT OR IGNORE backfill (not DELETE+INSERT) — avoids clearing existing FTS rows on restart"
  - "DELETE+INSERT in triggers (not fts5 content table) — simpler, works with group_concat aggregation"
  - "snippet() with <mark> delimiters stripped client-side — frontend can add its own highlighting later"
  - "try/except on FTS MATCH execute — any malformed query returns [] not 500, consistent UX"
  - "_build_fts5_query quotes each token individually — neutralises AND/OR/NOT operators safely"

patterns-established:
  - "FTS sync via triggers: AFTER INSERT ON messages fires DELETE+INSERT into threads_fts"
  - "migrate_db() extended with v23 block using executescript — follows v22 feedback pattern"
  - "User scoping via JOIN threads ON rowid = t.id with WHERE t.user_id = ? — not FTS-only"

duration: 2min
completed: 2026-04-02
---

# Phase 23 Plan 01: Thread Search Backend Summary

**FTS5 threads_fts index with 3 sync triggers, idempotent startup backfill, and user-scoped GET /api/threads/search returning ranked plain-text snippets**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-02T18:35:54Z
- **Completed:** 2026-04-02T18:38:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- FTS5 virtual table (unicode61 tokenizer) auto-created on startup via migrate_db() for both fresh and existing databases
- 3 triggers keep threads_fts current: INSERT fires on new messages, UPDATE fires when chat turns are saved, DELETE fires when a thread is removed
- Idempotent backfill using INSERT OR IGNORE runs on every startup — no duplicates, no errors, no manual intervention
- GET /api/threads/search endpoint with @role_required enforcing 401/403, user_id JOIN scoping, and graceful handling of malformed FTS5 queries

## Task Commits

1. **Task 1: FTS5 virtual table, triggers, and backfill in schema + migrate_db** - `5eca46b` (feat)
2. **Task 2: Search endpoint with query builder and user scoping** - `24d296d` (feat)

## Files Created/Modified

- `/c/xmcp/chat_app/schema.sql` - FTS5 virtual table DDL, 3 triggers, backfill INSERT OR IGNORE
- `/c/xmcp/chat_app/db.py` - migrate_db() extended with v23 FTS block (executescript, idempotent)
- `/c/xmcp/chat_app/conversations.py` - _build_fts5_query helper, _strip_mark_tags helper, search_threads endpoint

## Decisions Made

- **INSERT OR IGNORE for backfill** — DELETE+INSERT would clear existing FTS rows on restart; OR IGNORE is safe to replay
- **DELETE+INSERT in triggers** — FTS5 content table approach is more complex; direct DELETE+INSERT with group_concat is simpler and correct for single-row-per-thread model
- **snippet() mark tags stripped server-side** — returns plain text so frontend owns highlighting logic; no coupling
- **try/except on db.execute** — FTS MATCH can raise sqlite3.OperationalError for edge cases not covered by _build_fts5_query; empty list is better UX than 500
- **Token quoting in _build_fts5_query** — wrapping each token in double-quotes neutralises AND/OR/NOT operators and unclosed quotes at the FTS5 parse level

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. FTS5 virtual table CREATE TRIGGER IF NOT EXISTS syntax worked as documented. INSERT OR IGNORE with rowid correctly prevents backfill duplicates.

## User Setup Required

None - no external service configuration required. FTS index is created automatically on next app startup for existing databases.

## Next Phase Readiness

- Backend search infrastructure complete: FTS5 index, sync triggers, backfill, and endpoint all ready
- Plan 23-02 (frontend SearchInput) can call GET /api/threads/search?q= immediately
- Endpoint returns `[{id, name, updated_at, snippet}]` — exactly the shape the frontend needs
- No blockers

---
*Phase: 23-thread-search*
*Completed: 2026-04-02*
