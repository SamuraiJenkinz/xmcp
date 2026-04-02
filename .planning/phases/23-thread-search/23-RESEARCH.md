# Phase 23: Thread Search - Research

**Researched:** 2026-04-02
**Domain:** SQLite FTS5 full-text search, React search UI, Fluent UI v9 SearchBox
**Confidence:** HIGH

---

## Summary

Phase 23 adds two-tier thread search to the sidebar: instant client-side title filtering as the user types, and debounced backend FTS5 full-text search across message content for deeper discovery.

The backend challenge is that messages are stored as a JSON array in `messages.messages_json` — FTS5 needs plain text. The correct approach is a standalone `threads_fts` virtual table populated via SQLite triggers that use `json_each()` to extract only `user` and `assistant` message content, excluding `tool` and `system` messages. This avoids indexing JSON structural noise (`role`, `content` as literal keys). Triggers fire on `INSERT` and `UPDATE` of `messages`; a matching `AFTER DELETE ON threads` trigger removes stale FTS rows. The FTS table and triggers are added idempotently via `migrate_db()` with `CREATE ... IF NOT EXISTS`. A one-time backfill query populates existing threads.

On the frontend, Fluent UI v9's `SearchBox` (from `@fluentui/react-components` v9.73.5 — confirmed in main export) handles the input with built-in search icon and dismiss button. Client-side title filtering runs synchronously on the already-loaded threads array. FTS5 calls are debounced 300ms using a `useRef<ReturnType<typeof setTimeout>>` pattern (no external library — consistent with the codebase). A `CounterBadge` shows result count; a `Spinner` shows loading state during FTS fetch.

**Primary recommendation:** Single unified input — title filter instant, FTS5 debounced at 300ms / 2-char minimum. Ctrl+K focuses the sidebar search input (not a command palette — simpler, consistent with the sidebar-first UX).

---

## Standard Stack

### Core (verified in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLite FTS5 | Built-in (SQLite 3.49.1) | Full-text search virtual table | Compiled in, unicode61 tokenizer chosen |
| `@fluentui/react-components` | 9.73.5 | SearchBox, Spinner, CounterBadge | Already the project's component library |
| `@fluentui/react-icons` | 2.0.323 | SearchRegular, DismissRegular icons | Already used in project |
| React 19 | 19.2.4 | Component framework | Locked decision |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Native `setTimeout`/`clearTimeout` | Browser built-in | Debounce FTS5 calls | No external debounce library in project |
| Flask Blueprint | Existing pattern | `/api/threads/search` endpoint | Matches all other API blueprints |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Standalone FTS table + triggers | FTS5 `content=` external content table | `content=` approach requires matching rowid to messages, complex with 1:1 thread/messages; standalone is simpler |
| unicode61 tokenizer | porter tokenizer | Porter over-stems Exchange terms (DAGHealth, etc.) — locked decision |
| Custom search input (`<input>`) | Fluent `SearchBox` | SearchBox provides dismiss button, search icon, accessible labeling out of the box |
| Lodash debounce | `useRef` + `setTimeout` | No lodash in project; the codebase already uses `useRef` refs for timers (see `rafRef` in `useStreamingMessage.ts`) |

### Installation

No new dependencies needed. All packages already installed:
- `@fluentui/react-components` includes `SearchBox`, `Spinner`, `CounterBadge`
- `@fluentui/react-icons` includes `SearchRegular`, `DismissRegular`

---

## Architecture Patterns

### Recommended Project Structure

```
chat_app/
├── conversations.py          # Add search endpoint here (existing blueprint)
├── schema.sql                # Add FTS table + triggers + backfill comment
├── db.py                     # Extend migrate_db() with FTS migration

frontend/src/
├── api/
│   └── threads.ts            # Add searchThreads() function
├── components/Sidebar/
│   ├── SearchInput.tsx        # New: controlled search input component
│   ├── ThreadList.tsx         # Modified: wire up search state
│   └── ThreadItem.tsx         # Unchanged
├── hooks/
│   └── useDebounce.ts         # New: reusable debounce hook
```

### Pattern 1: FTS5 Standalone Table with json_each Triggers

**What:** A `threads_fts` virtual table indexed by `thread_id` as rowid. Triggers use SQLite's `json_each()` to extract clean text from `messages_json`, filtering to only `user` and `assistant` roles. `tool` and `system` messages are excluded (confirmed: they contain JSON-formatted results and system prompts, not user-visible content worth searching).

**When to use:** Any time you need FTS5 over JSON-stored content.

**Example — FTS table + triggers (goes in migrate_db() and schema.sql):**
```sql
-- FTS5 virtual table: one row per thread, rowid = thread_id
CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts
    USING fts5(body, tokenize='unicode61');

-- Sync on new message row (INSERT into messages at thread creation)
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

-- Sync on every conversation update (chat.py does UPDATE messages SET messages_json)
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

-- Remove FTS index when thread is deleted
CREATE TRIGGER IF NOT EXISTS threads_fts_ad
    AFTER DELETE ON threads
BEGIN
    DELETE FROM threads_fts WHERE rowid = OLD.id;
END;

-- Backfill existing threads (INSERT OR IGNORE = idempotent)
INSERT OR IGNORE INTO threads_fts(rowid, body)
SELECT m.thread_id,
       group_concat(json_extract(j.value, '$.content'), ' ')
FROM   messages m, json_each(m.messages_json) j
WHERE  json_extract(j.value, '$.role') IN ('user', 'assistant')
AND    json_extract(j.value, '$.content') IS NOT NULL
GROUP BY m.thread_id;
```

**Verified:** All of the above runs correctly on SQLite 3.49.1 (the system SQLite). `CREATE VIRTUAL TABLE IF NOT EXISTS` and `CREATE TRIGGER IF NOT EXISTS` are both idempotent.

### Pattern 2: Safe FTS5 Query Builder

**What:** User input must be sanitized before passing to FTS5. Users can type operators (`AND`, `OR`), unclosed quotes, empty strings — all of which cause `sqlite3.OperationalError`. Wrap each whitespace-split token as a double-quoted phrase with a trailing `*` for prefix matching.

**Example:**
```python
def _build_fts5_query(raw: str) -> str | None:
    """Convert raw user input to a safe FTS5 query string.

    Each whitespace-separated token is double-quoted (escaping FTS5 operators)
    and suffixed with * for prefix matching.  Returns None for blank input.

    Example: 'DAG health' -> '"DAG"* "health"*'
    """
    tokens = raw.strip().split()
    if not tokens:
        return None
    return " ".join(f'"{t.replace(chr(34), "")}"*' for t in tokens)
```

**Verified:** Handles `AND`, `OR`, unclosed quotes, `Get-Mailbox`, `user@domain.com`, and `DAGHealth*` without errors.

### Pattern 3: User-Scoped Search Endpoint

**What:** FTS5 has no concept of user isolation. Scope is enforced with a `JOIN threads t ON threads_fts.rowid = t.id WHERE t.user_id = ?` clause. This prevents any user from seeing another user's thread content.

**Example — full search query:**
```python
@conversations_bp.route("/api/threads/search", methods=["GET"])
@role_required
def search_threads():
    """FTS5 full-text search across message content for the current user.

    Query params:
        q: Search term (2+ characters required, enforced in frontend)

    Returns: [{id, name, updated_at, snippet}, ...] — up to 20 results.
    """
    q = (request.args.get("q") or "").strip()
    fts_query = _build_fts5_query(q)
    if not fts_query:
        return jsonify([])

    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT t.id, t.name, t.updated_at,
                   snippet(threads_fts, 0, '<mark>', '</mark>', '...', 16) AS snippet
            FROM   threads_fts
            JOIN   threads t ON threads_fts.rowid = t.id
            WHERE  threads_fts MATCH ?
            AND    t.user_id = ?
            ORDER BY rank
            LIMIT  20
            """,
            (fts_query, _user_id()),
        ).fetchall()
    except Exception:
        return jsonify([])

    return jsonify([dict(r) for r in rows])
```

**Note:** The `snippet()` function returns HTML with `<mark>` tags. The frontend renders the snippet as plain text (strip tags) or trusts `<mark>` only — do not use `dangerouslySetInnerHTML` without sanitization. The simplest safe approach: strip tags server-side and bold the matched text, or return raw snippet text + match positions and highlight client-side. Given sidebar width constraints, stripping to plain text with `...` context is recommended.

### Pattern 4: Debounced FTS5 Hook

**What:** useRef-based debounce to avoid FTS5 calls on every keystroke. Pattern consistent with `rafRef` in `useStreamingMessage.ts`.

**Example:**
```typescript
// hooks/useDebounce.ts
import { useEffect, useRef, useState } from 'react';

export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setDebounced(value), delay);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, delay]);

  return debounced;
}
```

**Usage in SearchInput:**
```typescript
const debouncedQuery = useDebounce(query, 300);
const shouldFetch = debouncedQuery.trim().length >= 2;

useEffect(() => {
  if (!shouldFetch) {
    setFtsResults([]);
    return;
  }
  let cancelled = false;
  setIsLoading(true);
  searchThreads(debouncedQuery)
    .then((results) => { if (!cancelled) setFtsResults(results); })
    .catch(() => { if (!cancelled) setFtsResults([]); })
    .finally(() => { if (!cancelled) setIsLoading(false); });
  return () => { cancelled = true; };
}, [debouncedQuery, shouldFetch]);
```

### Pattern 5: Ctrl+K Keyboard Shortcut

**What:** Global `keydown` handler on the `document` in a `useEffect`. Calls `.focus()` on the search input ref. Implemented in `ThreadList.tsx` (or a parent). The search input is the sidebar input, not a command palette.

**Example:**
```typescript
useEffect(() => {
  function handleGlobalKeyDown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      searchInputRef.current?.focus();
    }
  }
  document.addEventListener('keydown', handleGlobalKeyDown);
  return () => document.removeEventListener('keydown', handleGlobalKeyDown);
}, []);
```

### Pattern 6: Unified Input — Title Filter + FTS5 Combined

**What:** Single `SearchBox` drives both behaviors. Client-side title filter applies immediately (synchronous). FTS5 results appear below the title-filtered list after 300ms debounce. Result display: title matches show as normal thread items; FTS5 results show as a separate "Message matches" section with snippet subtitle. This two-section layout answers "title matches vs content matches grouping" (discretion area) without hiding either result type.

**Search state on navigation:** Clear the search query when the user clicks a result to navigate to a thread. This matches natural UX — you found what you were looking for. The active thread remains visible by ensuring the FTS5 click triggers `handleSelectThread` and then clears the search state.

**Active thread during filter:** Do NOT pin the active thread. If the active thread's name doesn't match, it disappears from the title-filter view — this is correct behavior and avoids special-casing.

### Anti-Patterns to Avoid

- **Storing raw JSON in FTS5:** Causes JSON keys (`role`, `content`, `assistant`) to be indexed as searchable terms, producing false matches. Always use `json_each()` to extract clean text.
- **Using `dangerouslySetInnerHTML` for snippets:** The `snippet()` function returns `<mark>` tags. Rendering these as HTML without sanitization is an XSS risk. Either strip tags server-side and send plain text, or parse `<mark>` tags manually on the client.
- **No error handling around FTS5 MATCH:** Malformed queries cause `sqlite3.OperationalError`. Always wrap in try/except and return empty results.
- **Not scoping FTS5 to user:** FTS virtual table has no `user_id` column. Must JOIN to `threads` table to enforce user isolation.
- **Calling migrate_db with executescript when triggers exist:** `executescript` commits the current transaction before running. This is the existing pattern in `db.py` and is fine for DDL.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Search input with dismiss/icon | Custom `<input>` wrapper | Fluent `SearchBox` | Built-in accessible dismiss button, search icon, keyboard handling |
| FTS tokenization | Manual string splitting / LIKE queries | FTS5 unicode61 | LIKE `%term%` scans every row; FTS5 uses inverted index |
| Query sanitization | Complex regex | Token-and-quote pattern (above) | One-liner, handles all edge cases verified in testing |
| Debouncing | Custom class or external library | `useRef` + `setTimeout` hook | Zero deps, consistent with codebase patterns |

**Key insight:** SQLite FTS5 is already compiled in (verified: SQLite 3.49.1, FTS5 available). No additional Python packages needed for search.

---

## Common Pitfalls

### Pitfall 1: FTS5 Not Synced When Messages Update

**What goes wrong:** `threads_fts` has stale content after a chat conversation updates the messages. New messages are not searchable.

**Why it happens:** FTS5 virtual tables don't have foreign key relationships or cascades. The `messages` table is updated (not replaced) on every chat turn via `UPDATE messages SET messages_json = ?`.

**How to avoid:** The `messages_fts_au` AFTER UPDATE trigger handles this. The trigger does DELETE + INSERT to replace the FTS row atomically. Verified this pattern works.

**Warning signs:** Searches return threads but snippets show old content.

### Pitfall 2: FTS5 Syntax Errors From User Input

**What goes wrong:** `sqlite3.OperationalError: fts5: syntax error near "AND"` when user types FTS5 reserved words.

**Why it happens:** FTS5 query syntax has reserved operators: `AND`, `OR`, `NOT`, `NEAR`, `^`, `*`, `"`, `(`, `)`.

**How to avoid:** Use the `_build_fts5_query()` function (Pattern 2) — wraps every token in double quotes + `*` prefix. Verified against all failure cases.

**Warning signs:** 500 errors from search endpoint on specific queries.

### Pitfall 3: Backfill Runs on Every App Restart

**What goes wrong:** `migrate_db()` reruns the backfill INSERT on every Flask startup, either failing with UNIQUE constraint or silently duplicating FTS rows.

**Why it happens:** FTS5 virtual tables don't have UNIQUE constraints by default — rowid is the key but multiple inserts can create duplicate rows.

**How to avoid:** Use `INSERT OR IGNORE INTO threads_fts(rowid, body)`. FTS5 rowid-based `INSERT OR IGNORE` is idempotent — if the rowid already exists, the insert is skipped. Verified this works correctly.

**Warning signs:** Search returns duplicate results.

### Pitfall 4: Empty Query Passed to FTS5

**What goes wrong:** `sqlite3.OperationalError: fts5: syntax error near ""` on empty string.

**Why it happens:** FTS5 requires at least one token.

**How to avoid:** `_build_fts5_query()` returns `None` for empty input; endpoint returns `[]` immediately.

### Pitfall 5: SearchBox in Collapsed Sidebar

**What goes wrong:** Ctrl+K focuses a hidden input when sidebar is collapsed.

**Why it happens:** The search area is inside the `{!collapsed && ...}` block in `ThreadList.tsx`.

**How to avoid:** Ctrl+K handler should first expand the sidebar (set `sidebarCollapsed = false`), then focus the input on next render. Use a ref + `useEffect` to focus after collapse state change, or `setTimeout(0)` to defer focus until after DOM update.

### Pitfall 6: Tool Message Content in Search Index

**What goes wrong:** Searching for common JSON terms (`success`, `error`, `true`, `null`) returns irrelevant threads because tool call results are indexed.

**Why it happens:** `messages_json` contains `{"role": "tool", "content": "{\"status\": \"success\", ...}"}` entries.

**How to avoid:** The trigger's `WHERE json_extract(j.value, '$.role') IN ('user', 'assistant')` clause excludes tool messages. Verified: tool content is not indexed.

---

## Code Examples

### FTS5 Search Endpoint (verified)
```python
# Source: verified against SQLite 3.49.1 in this project
@conversations_bp.route("/api/threads/search", methods=["GET"])
@role_required
def search_threads():
    q = (request.args.get("q") or "").strip()
    fts_query = _build_fts5_query(q)
    if not fts_query:
        return jsonify([])
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT t.id, t.name, t.updated_at,
                   snippet(threads_fts, 0, '<mark>', '</mark>', '...', 16) AS snippet
            FROM   threads_fts
            JOIN   threads t ON threads_fts.rowid = t.id
            WHERE  threads_fts MATCH ?
            AND    t.user_id = ?
            ORDER BY rank
            LIMIT  20
            """,
            (fts_query, _user_id()),
        ).fetchall()
    except Exception:
        return jsonify([])
    return jsonify([dict(r) for r in rows])
```

### Frontend Search API Function
```typescript
// Source: follows existing threads.ts pattern
export interface SearchResult {
  id: number;
  name: string;
  updated_at: string;
  snippet: string;  // plain text with <mark> stripped server-side, or kept for parsing
}

export async function searchThreads(q: string): Promise<SearchResult[]> {
  const res = await fetch(`/api/threads/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) throw new Error(`searchThreads failed: ${res.status}`);
  return res.json() as Promise<SearchResult[]>;
}
```

### SearchBox Import (verified — in main export)
```typescript
// SearchBox is in @fluentui/react-components main index (not unstable)
// CounterBadge and Spinner are also in main index
import { SearchBox, CounterBadge, Spinner } from '@fluentui/react-components';
import { SearchRegular, DismissRegular } from '@fluentui/react-icons';
```

### Client-Side Title Filter (synchronous)
```typescript
// Runs in render path — no async needed
const filteredThreads = query.trim()
  ? threads.filter(t =>
      (t.name || 'New Chat').toLowerCase().includes(query.trim().toLowerCase())
    )
  : threads;
```

### Snippet Tag Stripping (server-side recommended)
```python
import re

def _strip_mark_tags(snippet: str) -> str:
    """Remove <mark>...</mark> tags, keeping the inner text."""
    return re.sub(r'</?mark>', '', snippet)
```

Alternatively, render snippet with bold on match client-side by parsing `<mark>` tags into `<strong>` elements (safe, no XSS since tags are only `<mark>` and `</mark>`).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LIKE `%term%` queries | FTS5 virtual table | SQLite 3.8.3+ | Orders of magnitude faster on large tables; supports ranking |
| FTS4 | FTS5 | SQLite 3.9.0 | FTS5 adds `snippet()`, `highlight()`, `rank`, auxiliary functions |
| Separate debounce lib | `useRef` + `setTimeout` | React hooks era | No external dependency; cleanup handled in `useEffect` return |

**Deprecated/outdated:**
- FTS4: No `snippet()` function. FTS5 is the standard since 2015.
- Porter tokenizer for this project: Over-stems Exchange technical terms — locked to `unicode61`.

---

## Open Questions

1. **Snippet tag rendering strategy**
   - What we know: `snippet()` returns `<mark>text</mark>` HTML. Rendering in sidebar requires a decision.
   - What's unclear: Whether to strip server-side (simpler) or parse client-side (highlights visible).
   - Recommendation: Strip `<mark>` tags server-side in the endpoint, return plain text with `...` context. Highlighted matches add visual noise in a narrow sidebar. Plain text with context is sufficient for IT engineers to identify the right thread.

2. **Result count badge**
   - What we know: `CounterBadge` is available in Fluent v9 main export.
   - What's unclear: Whether to show count for title-filter results, FTS5 results, or both.
   - Recommendation: Show a small count badge only for FTS5 results (title filter is immediate and visible). Place badge inline with the "Message matches" section heading.

3. **Min-character hint**
   - Recommendation: No visual hint for the 2-char minimum. The Fluent `SearchBox` placeholder text covers this implicitly (e.g., "Search conversations"). Silent activation at 2 chars is the cleanest UX.

---

## Sources

### Primary (HIGH confidence)
- Verified in SQLite 3.49.1 on this system — all FTS5 queries, triggers, backfill patterns tested and confirmed
- `/c/xmcp/chat_app/schema.sql` — current schema, confirmed no FTS table exists
- `/c/xmcp/chat_app/db.py` — `migrate_db()` pattern for additive schema changes
- `/c/xmcp/chat_app/conversations.py` — `_user_id()` helper, `@role_required` decorator, Blueprint pattern
- `/c/xmcp/chat_app/chat.py` — confirms `UPDATE messages SET messages_json` write path (triggers must handle UPDATE)
- `/c/xmcp/frontend/node_modules/@fluentui/react-components` v9.73.5 — `SearchBox`, `Spinner`, `CounterBadge` all exported from main index (confirmed in `index.d.ts`)
- `/c/xmcp/frontend/node_modules/@fluentui/react-icons` v2.0.323 — `SearchRegular`, `DismissRegular` confirmed in chunk type files
- `/c/xmcp/frontend/src/components/Sidebar/ThreadList.tsx` — existing component structure for integration
- `/c/xmcp/frontend/src/hooks/useStreamingMessage.ts` — `useRef` timer pattern for debounce
- `/c/xmcp/frontend/package.json` — no lodash/debounce library

### Secondary (MEDIUM confidence)
- SQLite FTS5 documentation — `snippet()`, `highlight()`, `rank` built-in auxiliary functions behavior

---

## Metadata

**Confidence breakdown:**
- Backend FTS5 schema/triggers/queries: HIGH — all verified with Python SQLite on project's actual SQLite version
- Fluent component availability: HIGH — confirmed in installed node_modules type definitions
- Frontend React patterns: HIGH — consistent with existing codebase patterns
- UX discretion choices: MEDIUM — based on sidebar width constraints and Fluent/Copilot aesthetic reasoning

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable technology stack)
