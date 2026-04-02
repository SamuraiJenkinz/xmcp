# Architecture Patterns: v1.3 Feature Integration

**Project:** Atlas — Exchange Infrastructure Chat App
**Milestone:** v1.3 — App Role Access Control, Feedback, Search, Export, Animations
**Researched:** 2026-04-01
**Scope:** How five new features integrate with the existing Flask 3.x + React 19 + SQLite architecture.

---

## Baseline Architecture (as of v1.2)

```
Browser (on-prem / VPN)
    |
    | HTTPS (self-signed cert, Waitress WSGI)
    v
+-----------------------------------------------+
|  Flask 3.x / Waitress                         |
|  Blueprints:                                  |
|    auth_bp         /login /auth/callback      |
|                    /logout                    |
|    chat_bp         POST /chat/stream (SSE)    |
|    conversations_bp /api/threads/* (CRUD)     |
|  Routes (app.py):                             |
|    GET /api/me       → user identity JSON     |
|    GET /api/photo/<id> → Graph photo proxy    |
|    GET /api/health   → JSON                   |
|  Session: filesystem (flask-session)          |
|    session["user"] = id_token_claims dict     |
|      contains: oid, name, preferred_username  |
|      v1.3 adds:  roles (list[str])            |
|  Auth: MSAL ConfidentialClientApplication     |
|  DB: SQLite WAL                               |
|    threads(id, user_id, name, created_at,     |
|            updated_at)                        |
|    messages(id, thread_id, messages_json)     |
+-----------------------------------------------+
    |
    +-- React 19 SPA (served from frontend_dist/)
    |     AuthContext   (user state, no roles yet)
    |     ThreadContext (thread list + active id)
    |     ChatContext   (messages + streaming)
    |
    +-- SQLite WAL (chat.db)
    |
    +-- exchange_mcp server (subprocess JSON-RPC)
```

**Key constraint for v1.3:** Session already contains `id_token_claims` from MSAL. The `roles` claim is populated automatically by Azure AD when the user has been assigned an App Role — it arrives as `session["user"]["roles"]` (list of strings, e.g. `["Atlas.User"]`). No token re-acquisition is needed; the claim is present in the ID token that MSAL already captures at `auth_callback`.

---

## Feature 1: App Role Access Control

### How roles appear in the existing session

MSAL's `acquire_token_by_auth_code_flow` returns `id_token_claims` in the result. Azure AD populates a `roles` claim (list of strings) in the ID token when App Roles are configured and assigned. The existing `auth_callback` in `auth.py` stores the entire `id_token_claims` dict as `session["user"]` — so `session["user"].get("roles", [])` is already the right access pattern. No changes to the auth flow are needed.

**HIGH confidence** — confirmed by [Microsoft Entra docs: Add app roles and get them from a token](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps): "for an app that signs in users, the roles claims are included in the ID token."

### Backend changes

**Modified file: `chat_app/auth.py`**

Add a new decorator alongside the existing `login_required`. The new decorator checks both session existence AND roles claim:

```python
REQUIRED_ROLE = "Atlas.User"  # or read from Config

def role_required(f):
    """Decorator: requires authentication AND the Atlas.User app role."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        if not user:
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("catch_all", path=""))
        roles = user.get("roles") or []
        if REQUIRED_ROLE not in roles:
            if request.path.startswith("/api/"):
                return jsonify({"error": "access denied", "code": "insufficient_role"}), 403
            return redirect(url_for("access_denied"))
        return f(*args, **kwargs)
    return decorated
```

The `REQUIRED_ROLE` value string must exactly match the **Value** field of the App Role in the Azure AD manifest (case-sensitive).

**Decorator replacement strategy:** Replace `@login_required` with `@role_required` on all protected routes in `conversations_bp`, `chat_bp`, and `app.py` (`/api/me`, `/api/photo`, `/api/health`). The `login_required` decorator can remain for `/api/health` if that endpoint should be accessible to all authenticated users regardless of role.

**New route in `app.py`:** `GET /access-denied` — serves a React-compatible response. In React SPA mode, this returns `index.html` so the frontend can render the access-denied screen. Alternatively the `/api/me` response can include a `hasAccess: false` flag and the frontend renders the gate.

**Preferred approach:** Return a `403` from `/api/me` (not a JSON body with `hasAccess: false`) when the user is authenticated but lacks the role. This means `api_me` in `app.py` also uses `@role_required`. The React `AuthGuard` in `App.tsx` already handles 401; it needs a 403 branch added.

### Frontend changes

**Modified file: `frontend/src/api/me.ts`**

Handle `403` response distinctly from `401`:
```typescript
if (res.status === 401) return null;       // not authenticated → redirect to /login
if (res.status === 403) throw new AccessDeniedError();  // authenticated, no role
```

**Modified file: `frontend/src/contexts/AuthContext.tsx`**

Add `accessDenied: boolean` to `AuthState`. Set it when `/api/me` returns 403.

**Modified file: `frontend/src/App.tsx`**

Extend `AuthGuard` to render an `<AccessDenied />` component when `accessDenied` is true, instead of redirecting to login.

**New file: `frontend/src/components/AccessDenied.tsx`**

Standalone screen explaining the user is authenticated but does not have access. Shows their email, a contact-IT message, and a logout link.

### Azure AD manifest changes

1. Open App Registration in Entra admin center.
2. Under **App roles**, create a new role:
   - Display name: `Atlas User`
   - Allowed member types: `Users/Groups`
   - Value: `Atlas.User` (this exact string goes in `REQUIRED_ROLE`)
   - Description: `Can access the Atlas Exchange chat application`
   - Enabled: `true`
3. Under **Enterprise Applications** → the app → **Users and groups**, assign the pilot group or individual users to the `Atlas.User` role.
4. No manifest JSON editing is required; the portal UI handles it.

**No new environment variables needed** — the role name string can be hardcoded as a constant in `auth.py` or added to `Config` if it needs to vary across environments.

---

## Feature 2: Thumbs Up/Down Feedback

### Data model

**New SQLite table (add to `schema.sql`):**

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    message_idx INTEGER NOT NULL,   -- 0-based index into messages_json array
    user_id     TEXT    NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating IN (1, -1)),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (thread_id, message_idx, user_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_thread
    ON feedback(thread_id);
```

`message_idx` is the position of the assistant message within the `messages_json` array. Using an index (not a content hash or timestamp) is simplest given the existing storage model — the array is append-only and messages do not reorder.

The `UNIQUE` constraint prevents double-voting and makes upsert semantics possible (a second vote on the same message flips or removes the rating).

### Backend changes

**New file: `chat_app/feedback.py`** — new Blueprint with two endpoints:

- `POST /api/threads/<thread_id>/messages/<int:message_idx>/feedback` — body `{"rating": 1}` or `{"rating": -1}`. Verifies thread ownership first (same ownership pattern as `conversations.py`). Upserts feedback row using `INSERT OR REPLACE`.
- `DELETE /api/threads/<thread_id>/messages/<int:message_idx>/feedback` — removes the user's feedback row (allows un-rating).

**Modified file: `chat_app/app.py`**

Register `feedback_bp` blueprint.

### Frontend changes

**New file: `frontend/src/api/feedback.ts`** — `submitFeedback(threadId, messageIdx, rating)` and `deleteFeedback(threadId, messageIdx)`.

**Modified file: `frontend/src/types/index.ts`**

Add `feedback?: 1 | -1 | null` to `DisplayMessage`.

**Modified file: `frontend/src/components/ChatPane/AssistantMessage.tsx`**

Add thumbs-up / thumbs-down buttons below assistant message content. On click, call `submitFeedback`. Show active state (filled vs outline icon) based on local optimistic state. Use Fluent UI `ThumbLike20Regular` / `ThumbLike20Filled` / `ThumbDislike20Regular` / `ThumbDislike20Filled` icons (already available from `@fluentui/react-icons`).

**State management note:** Feedback state is local to each message component — no global state changes needed. The `DisplayMessage` type gets a `feedback` field, populated when loading historical messages if feedback data is included in the response.

**Loading historical feedback:** The `GET /api/threads/<id>/messages` endpoint in `conversations.py` currently returns only `messages_json`. Options:

- Option A: Add a separate `GET /api/threads/<id>/feedback` endpoint that returns `{messageIdx: rating}` map. Frontend fetches this alongside messages when switching threads.
- Option B: Extend the existing messages endpoint to include feedback in the response.

Recommendation: Option A (separate endpoint). It keeps `conversations.py` unchanged and allows feedback to load lazily without blocking message display.

---

## Feature 3: Thread Search

### Storage design

The messages are stored as a JSON array in `messages.messages_json`. FTS5 cannot index JSON arrays directly. Two approaches:

**Option A: FTS5 external content table on threads.name only (thread-level search)**

Search thread names only. Simple to implement — thread names are plain text strings.

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
    name,
    content='threads',
    content_rowid='id'
);
```

**Option B: FTS5 on a denormalized message_text table (message-level search)**

Maintain a separate `message_text(id, thread_id, message_idx, role, content)` table alongside `messages`. FTS5 indexes this table. The `chat.py` SSE endpoint writes to `message_text` after each conversation turn.

Recommendation: **Option A first, Option B later.** Thread-name search satisfies the use case of "find that conversation about Exchange quota issues." Searching within message content can be a v1.4 feature. Thread names are meaningful (auto-named from first message), searchable, and index simply.

**Schema additions for thread search (add to `schema.sql`):**

```sql
-- FTS5 index on thread names (content table approach)
CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
    name,
    content='threads',
    content_rowid='id'
);

-- Triggers to keep FTS index in sync with threads table
CREATE TRIGGER IF NOT EXISTS threads_fts_ai AFTER INSERT ON threads BEGIN
    INSERT INTO threads_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TRIGGER IF NOT EXISTS threads_fts_au AFTER UPDATE OF name ON threads BEGIN
    INSERT INTO threads_fts(threads_fts, rowid, name) VALUES ('delete', old.id, old.name);
    INSERT INTO threads_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TRIGGER IF NOT EXISTS threads_fts_ad AFTER DELETE ON threads BEGIN
    INSERT INTO threads_fts(threads_fts, rowid, name) VALUES ('delete', old.id, old.name);
END;
```

**Important:** FTS5 external content tables do not auto-populate on creation. After running the schema migration, a one-time backfill is required:

```sql
INSERT INTO threads_fts(rowid, name) SELECT id, name FROM threads WHERE name != '';
```

This backfill must run as part of the `flask init-db` command or as a separate migration step.

### Backend changes

**Modified file: `chat_app/conversations.py`**

Add one new endpoint:

```python
@conversations_bp.route("/api/threads/search")
@role_required
def search_threads():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    db = get_db()
    rows = db.execute(
        """
        SELECT t.id, t.name, t.updated_at
        FROM threads_fts
        JOIN threads t ON threads_fts.rowid = t.id
        WHERE threads_fts MATCH ?
          AND t.user_id = ?
        ORDER BY bm25(threads_fts)
        LIMIT 20
        """,
        (q, _user_id()),
    ).fetchall()
    return jsonify([dict(r) for r in rows])
```

The `AND t.user_id = ?` join ensures users can only search their own threads — same ownership model as the rest of `conversations.py`.

### Frontend changes

**Modified file: `frontend/src/api/threads.ts`**

Add `searchThreads(q: string): Promise<Thread[]>`.

**Modified file: `frontend/src/components/Sidebar/ThreadList.tsx`**

Add a search input at the top of the thread list. When focused or when the user types, switch between the full thread list and search results. A debounced `onChange` handler calls `searchThreads`. An empty query string reverts to the normal thread list.

**State:** Search query string and search results are local state within `ThreadList` — no context changes needed.

**New file (optional): `frontend/src/components/Sidebar/SearchInput.tsx`**

Extracted input component for the search box — Fluent UI `SearchBox` or a styled `<input type="search">`.

---

## Feature 4: Conversation Export

### Design decisions

Export is generated server-side from the stored `messages_json`. This keeps the frontend thin and ensures the export accurately reflects what is persisted (not transient UI state).

**Supported formats:**

- Markdown (`.md`) — human-readable, copy-pasteable, renders in tools like Obsidian/VS Code
- JSON (`.json`) — full fidelity, includes tool events and metadata

### Backend changes

**New file: `chat_app/export.py`** — Blueprint with one endpoint:

```python
@export_bp.route("/api/threads/<int:thread_id>/export")
@role_required
def export_thread(thread_id: int):
    fmt = request.args.get("format", "markdown")  # "markdown" or "json"
    db = get_db()
    # ownership check (same pattern as conversations.py)
    thread = db.execute(
        "SELECT id, name FROM threads WHERE id = ? AND user_id = ?",
        (thread_id, _user_id()),
    ).fetchone()
    if thread is None:
        return jsonify({"error": "Not found"}), 404

    row = db.execute(
        "SELECT messages_json FROM messages WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    messages = json.loads(row["messages_json"]) if row else []

    if fmt == "json":
        payload = json.dumps({
            "thread_id": thread_id,
            "name": thread["name"],
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "messages": messages,
        }, indent=2)
        filename = f"atlas-thread-{thread_id}.json"
        return Response(
            payload,
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Markdown format
    lines = [f"# {thread['name'] or f'Thread {thread_id}'}", ""]
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content") or ""
        if role == "system":
            continue
        if role == "user":
            lines += [f"**You:** {content}", ""]
        elif role == "assistant":
            lines += [f"**Atlas:** {content}", ""]
        # tool and tool_calls messages are omitted from markdown export

    payload = "\n".join(lines)
    safe_name = (thread["name"] or f"thread-{thread_id}").replace(" ", "-")[:50]
    filename = f"atlas-{safe_name}.md"
    return Response(
        payload,
        mimetype="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Modified file: `chat_app/app.py`**

Register `export_bp` blueprint.

### Frontend changes

**Modified file: `frontend/src/components/Sidebar/ThreadItem.tsx`**

Add "Export" to the existing thread item context menu (or as an icon button alongside rename/delete). The export triggers a `window.location.href` navigation to `/api/threads/<id>/export?format=markdown` — the browser handles the file download natively. No API module change needed for the simplest path.

Alternatively, add `exportThread(id, format)` to `frontend/src/api/threads.ts` using `fetch` + `URL.createObjectURL` for a programmatic download, which avoids navigating away. The programmatic approach is cleaner for a SPA.

---

## Feature 5: Motion Animations

### Library

**Package:** `motion` (formerly framer-motion, rebranded). Import from `"motion/react"`.

```bash
npm install motion
```

The package is `motion`, not `framer-motion`. The import path is `motion/react` for React components. React 19 compatibility is not explicitly documented but the library uses standard React APIs (hooks, ref forwarding) — no known incompatibility.

**Confidence: MEDIUM** — library docs verified via WebFetch but explicit React 19 compat statement not found. Risk is low; motion uses standard React APIs.

### Integration points

Animations are additive to existing components — no structural changes required. The `motion.div` / `motion.button` etc. wrappers replace the plain HTML elements where animations are wanted.

**Candidate locations:**

| Component | Animation | Motion API |
|-----------|-----------|------------|
| `AssistantMessage.tsx` | Fade + slide in on mount | `initial={{ opacity: 0, y: 8 }}` → `animate={{ opacity: 1, y: 0 }}` |
| `UserMessage.tsx` | Fade in on mount | Same pattern |
| `ThreadItem.tsx` | Subtle scale on hover | `whileHover={{ scale: 1.01 }}` |
| `Sidebar` | Slide transition on collapse/expand | `animate={{ width: collapsed ? 48 : 260 }}` |
| Feedback thumbs | Scale bounce on click | `whileTap={{ scale: 0.85 }}` |
| `AccessDenied.tsx` | Fade in on mount | `initial={{ opacity: 0 }}` |

**Anti-pattern to avoid:** Animating streaming message chunks. Each SSE `text` delta appends to the assistant message content string. Wrapping the entire streaming message in a `motion` component and animating on every `content` change will cause jank. Animation on mount (when the component first appears) is fine. Content updates during streaming should not trigger re-animation.

**LazyMotion:** For bundle size, use `LazyMotion` with `domAnimation` feature set if bundle size becomes a concern. Not needed immediately given the internal deployment context.

---

## New Components Summary

### New backend files

| File | Type | Purpose |
|------|------|---------|
| `chat_app/feedback.py` | New Blueprint | POST/DELETE feedback endpoints |
| `chat_app/export.py` | New Blueprint | GET export endpoint (Markdown + JSON) |

### Modified backend files

| File | Change |
|------|--------|
| `chat_app/auth.py` | Add `role_required` decorator, `REQUIRED_ROLE` constant |
| `chat_app/app.py` | Register feedback + export blueprints; update `api_me` to use `role_required`; add access-denied route |
| `chat_app/conversations.py` | Add `GET /api/threads/search` endpoint; switch to `role_required` |
| `chat_app/chat.py` | Switch `@login_required` to `@role_required` |
| `chat_app/schema.sql` | Add `feedback` table, `threads_fts` virtual table, three FTS sync triggers |

### New frontend files

| File | Purpose |
|------|---------|
| `frontend/src/components/AccessDenied.tsx` | Access denied screen for role-gated users |
| `frontend/src/components/Sidebar/SearchInput.tsx` | Search input component |
| `frontend/src/api/feedback.ts` | Feedback API calls |

### Modified frontend files

| File | Change |
|------|--------|
| `frontend/src/api/me.ts` | Handle 403 → `AccessDeniedError` |
| `frontend/src/api/threads.ts` | Add `searchThreads`, optionally `exportThread` |
| `frontend/src/contexts/AuthContext.tsx` | Add `accessDenied` state field |
| `frontend/src/types/index.ts` | Add `feedback` field to `DisplayMessage`; add `AccessDeniedError` |
| `frontend/src/App.tsx` | Extend `AuthGuard` for 403 → `<AccessDenied />` |
| `frontend/src/components/ChatPane/AssistantMessage.tsx` | Add feedback buttons; add motion animations |
| `frontend/src/components/ChatPane/UserMessage.tsx` | Add motion animations |
| `frontend/src/components/Sidebar/ThreadList.tsx` | Add search input + results mode |
| `frontend/src/components/Sidebar/ThreadItem.tsx` | Add export action; add motion hover |

---

## SQLite Schema Additions

Full additions to append to `chat_app/schema.sql`:

```sql
-- Feedback ratings for assistant messages
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    message_idx INTEGER NOT NULL,
    user_id     TEXT    NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating IN (1, -1)),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (thread_id, message_idx, user_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_thread
    ON feedback(thread_id);

-- FTS5 virtual table for thread name search
CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(
    name,
    content='threads',
    content_rowid='id'
);

-- Triggers to keep threads_fts in sync with threads.name
CREATE TRIGGER IF NOT EXISTS threads_fts_ai AFTER INSERT ON threads BEGIN
    INSERT INTO threads_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TRIGGER IF NOT EXISTS threads_fts_au AFTER UPDATE OF name ON threads BEGIN
    INSERT INTO threads_fts(threads_fts, rowid, name) VALUES ('delete', old.id, old.name);
    INSERT INTO threads_fts(rowid, name) VALUES (new.id, new.name);
END;

CREATE TRIGGER IF NOT EXISTS threads_fts_ad AFTER DELETE ON threads BEGIN
    INSERT INTO threads_fts(threads_fts, rowid, name) VALUES ('delete', old.id, old.name);
END;
```

**Migration note:** `CREATE VIRTUAL TABLE IF NOT EXISTS` is safe to run on an existing database. However, the FTS index will be empty until the backfill runs. Add a backfill step to the `flask init-db` CLI command or as a separate `flask backfill-fts` command:

```python
@click.command("backfill-fts")
def backfill_fts_command():
    """Populate threads_fts from existing thread names."""
    db = get_db()
    db.execute(
        "INSERT INTO threads_fts(rowid, name) SELECT id, name FROM threads WHERE name != ''"
    )
    db.commit()
    click.echo("FTS backfill complete.")
```

---

## Azure AD Manifest Changes

All changes are made via Entra admin center UI — no raw manifest JSON editing needed.

**App Registration → App roles:**

| Field | Value |
|-------|-------|
| Display name | `Atlas User` |
| Allowed member types | `Users/Groups` |
| Value | `Atlas.User` |
| Description | `Can access the Atlas Exchange chat application` |
| Enabled | `true` |

**Enterprise Applications → [App name] → Users and groups:**

- Assign the pilot group or individual users to the `Atlas.User` role.
- Users without an assignment will receive a `roles` claim with no entries, triggering the 403 path.

**No redirect URI changes.** The auth code flow callback URL (`/auth/callback`) is unchanged.

**Important:** The `roles` claim appears in the **ID token** (not just the access token) because this is a web app signing in users, not a daemon calling an API. MSAL's `acquire_token_by_auth_code_flow` returns `id_token_claims` which includes `roles`. This is already what `auth_callback` stores as `session["user"]`.

---

## Data Flow Changes

### Access control flow (new)

```
Browser → GET /api/me
    ↓
Flask api_me → @role_required
    → session["user"]["roles"] contains "Atlas.User" → 200 JSON
    → session["user"]["roles"] missing "Atlas.User" → 403 JSON
    → session["user"] not set → 401 JSON

React AuthGuard:
    → 200 → render app
    → 403 → render <AccessDenied />
    → 401 → redirect to /login
```

### Feedback flow (new)

```
User clicks thumbs-up on message[idx]
    → optimistic UI update (local state)
    → POST /api/threads/<id>/messages/<idx>/feedback {"rating": 1}
    → Flask: ownership check → INSERT OR REPLACE feedback
    → 200 → confirm
    → error → revert optimistic state
```

### Search flow (new)

```
User types in search box (debounced, 300ms)
    → GET /api/threads/search?q=<term>
    → Flask: FTS5 MATCH query + user_id filter → list of threads
    → ThreadList renders search results instead of full list
    → User clicks result → handleSelectThread (existing)
```

### Export flow (new)

```
User clicks Export on ThreadItem
    → GET /api/threads/<id>/export?format=markdown
    → Flask: ownership check → build Markdown → Response with Content-Disposition
    → Browser: native file download
```

---

## Suggested Build Order

Dependencies drive this order. Each feature can be built and tested independently after its prerequisites.

```
1. App Role Access Control  (no dependencies — pure auth layer change)
   Backend:  auth.py → role_required decorator
             app.py  → update api_me, add access-denied handling
             conversations.py / chat.py → swap decorators
   Frontend: me.ts → 403 handling
             AuthContext → accessDenied state
             App.tsx → AuthGuard 403 branch
             AccessDenied.tsx → new component
   Azure AD: create Atlas.User app role, assign test users

2. Feedback              (depends on: auth control complete)
   Backend:  schema.sql → feedback table
             feedback.py → new Blueprint + endpoints
             app.py → register blueprint
   Frontend: types → DisplayMessage.feedback
             api/feedback.ts → new
             AssistantMessage.tsx → thumbs buttons

3. Thread Search         (depends on: auth control complete; independent of feedback)
   Backend:  schema.sql → threads_fts + triggers
             conversations.py → /api/threads/search endpoint
             db.py → backfill-fts CLI command
   Frontend: api/threads.ts → searchThreads
             ThreadList.tsx → search mode
             SearchInput.tsx → new component

4. Export                (depends on: auth control complete; independent of 2 and 3)
   Backend:  export.py → new Blueprint
             app.py → register blueprint
   Frontend: ThreadItem.tsx → export action

5. Animations            (depends on: all other features complete or concurrent)
   Frontend: npm install motion
             AssistantMessage, UserMessage, ThreadItem, Sidebar → motion wrappers
             AccessDenied → fade-in
             Feedback buttons → whileTap
```

Features 2, 3, and 4 can be built in parallel after feature 1 is complete. Feature 5 is additive and can be layered on at any point, but it is cleanest to apply after the component structure is settled.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| App Roles in ID token claims | HIGH | Microsoft Entra docs confirm `roles` in ID token for user sign-in scenario |
| `session["user"]["roles"]` access pattern | HIGH | `auth_callback` stores full `id_token_claims`; `roles` is a standard claim |
| FTS5 external content table + triggers | HIGH | SQLite FTS5 official documentation, verified via WebFetch |
| FTS5 backfill requirement | HIGH | FTS5 doc: content tables do not auto-populate |
| BM25 ranking direction (lower = better) | HIGH | SQLite FTS5 doc: "better matches receive lower numeric values" |
| `feedback` table design (index-based) | MEDIUM | Reasonable given messages are append-only; fragile if message deletion is added later |
| Motion library React 19 compat | MEDIUM | Standard React APIs used; no explicit React 19 statement found in docs |
| Export server-side generation | HIGH | Standard Flask `Response` with `Content-Disposition`; no new dependencies |

---

## Sources

- [Microsoft Entra: Add app roles and get them from a token](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps)
- [SQLite FTS5 documentation](https://sqlite.org/fts5.html)
- [Motion for React quick start](https://motion.dev/docs/react-quick-start)
