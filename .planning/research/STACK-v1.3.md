# Technology Stack — v1.3 Feature Additions

**Project:** Atlas — Exchange Infrastructure Chat App (Marsh McLennan)
**Milestone:** v1.3 — App Role Access Control, Feedback, Search, Export, Animations
**Researched:** 2026-04-01
**Scope:** NEW stack additions only. Existing validated stack (Python 3.11, Flask 3.x,
Waitress 3.x, SQLite WAL, MSAL, React 19, Vite, TypeScript, Fluent UI v9, Tailwind v4)
is unchanged and not re-researched here.

---

## Executive Summary

v1.3 requires **zero new Python packages** and **one new npm package** (`motion`, which
was planned in v1.2 research but not added to `package.json`). Every feature is
achievable with built-in platform capabilities or libraries already installed:

| Feature | Stack Required | New Package? |
|---------|---------------|--------------|
| App Role access control | Azure AD manifest config + `id_token_claims` in existing `auth.py` | No |
| Per-message feedback | SQLite schema addition + Flask endpoint + React `useState` | No |
| Thread search | Client-side filter on existing thread list (FTS5 optional, built into `sqlite3`) | No |
| Conversation export | Browser `Blob` + `URL.createObjectURL` — zero dependencies | No |
| Motion animations | `motion` v12.38.0 (import from `motion/react`) | Yes — `motion` |

---

## Feature 1: Azure AD App Roles

### What Changes

**No new packages.** MSAL already acquires tokens via auth code flow and stores
`id_token_claims` in `session["user"]`. The `roles` claim appears automatically in
the ID token once App Roles are defined in the Azure AD manifest and users are
assigned to them.

Source: Microsoft official docs (howto-add-app-roles-in-apps, updated 2024-11-13;
configure-tokens-group-claims-app-roles, updated 2025-04-18):

> "For an app that signs in users, the roles claims are included in the ID token."

The claim is a JSON array of strings directly in `id_token_claims`:
```json
"roles": ["Atlas.User", "Atlas.Admin"]
```

### Azure AD Manifest Configuration

In Entra admin center under App Registrations > App roles, create two roles:

```json
"appRoles": [
  {
    "allowedMemberTypes": ["User"],
    "description": "Standard access to Atlas chat interface",
    "displayName": "Atlas User",
    "id": "<generate-new-uuid>",
    "isEnabled": true,
    "value": "Atlas.User"
  },
  {
    "allowedMemberTypes": ["User"],
    "description": "Administrator access to Atlas",
    "displayName": "Atlas Admin",
    "id": "<generate-new-uuid>",
    "isEnabled": true,
    "value": "Atlas.Admin"
  }
]
```

Required field notes:
- `id` must be a fresh UUID: `python -c "import uuid; print(uuid.uuid4())"`
- `value` is the exact string that appears in the `roles` claim — reference it
  verbatim in Python code
- `allowedMemberTypes: ["User"]` permits assigning both individual users and
  Azure AD groups to the role
- The `id` field is the unique identifier for the role in the manifest (not the
  same as the app's Client ID)

Post-creation steps (admin task, not code):
1. Under Enterprise Applications > [Atlas] > Users and groups: assign IT users
   or groups to `Atlas.User`; assign admins to `Atlas.Admin`
2. Consider enabling "Assignment required" under Enterprise Applications > Properties.
   This prevents any unauthenticated-to-role tenant user from signing in at all —
   the strongest enforcement posture. Roles do NOT appear in tokens until assignment
   is made.

### MSAL Configuration Changes

**None.** The existing `initiate_auth_code_flow` with `scopes=["User.Read"]` is
sufficient. Azure AD includes App Role claims in the ID token for any successful
auth code flow when the user has role assignments. The authority in `Config.AZURE_AUTHORITY`
is already tenant-specific (confirmed from `auth.py` inspection) — this is required
because `common` and `consumers` endpoints do not emit `roles` claims.

### Flask Code Change (auth.py)

Extend `auth.py` with a role check helper alongside the existing `login_required`:

```python
def require_role(*roles):
    """Decorator factory: requires session user to have at least one of the
    given App Role values from the 'roles' claim in id_token_claims.

    Must be applied AFTER @login_required so session["user"] is guaranteed present.
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            user = session.get("user") or {}
            user_roles = user.get("roles") or []
            if not any(r in user_roles for r in roles):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "forbidden"}), 403
                return redirect(url_for("catch_all", path=""))
            return f(*args, **kwargs)
        return decorated
    return decorator
```

Usage:
```python
@conversations_bp.route("/api/threads", methods=["GET"])
@login_required
@require_role("Atlas.User", "Atlas.Admin")
def list_threads():
    ...
```

The `roles` key is populated directly from the ID token by MSAL — no JWT decoding
is needed. `session["user"]` is already a Python dict with all claims.

### React API Change

The `/api/me` endpoint (or the `session["user"]` data passed to the frontend)
should include the `roles` array so the React app can gate UI elements (e.g., hide
admin controls from non-admin users). This is purely cosmetic gating — the Flask
decorators enforce the actual access control.

### What NOT to Add

- Do NOT add `msal-extensions`, `python-jose`, or any token validation library.
  `id_token_claims` returned by MSAL after a successful auth code flow is already
  validated by MSAL. Re-validating server-side adds no security.
- Do NOT check the `access_token` for App Roles. App Roles appear in the **ID token**
  for sign-in flows. The access token carries roles only when the app is an API being
  called by another app with application permissions.
- Do NOT use the `groups` claim as an alternative. Groups require matching on GUIDs
  (which differ between tenants and are meaningless to read), are limited to 200 per
  token, and create group overage issues at Marsh McLennan's 80K+ user scale. App
  Roles are the purpose-built mechanism.

---

## Feature 2: Per-Message Thumbs Up/Down Feedback

### What Changes

**No new packages.** SQLite schema addition + Flask endpoint (~30 lines) + React
`useState` for local feedback tracking.

### SQLite Schema Addition

```sql
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    message_idx INTEGER NOT NULL,
    user_id     TEXT    NOT NULL,
    vote        TEXT    NOT NULL CHECK(vote IN ('up', 'down')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(thread_id, message_idx, user_id)
);
```

Design decisions:
- `message_idx` is the 0-based position in the `messages_json` array for the
  relevant thread. This avoids a larger schema refactor (splitting `messages_json`
  into individual rows) and works correctly because messages are append-only.
  If a future milestone splits messages into rows, `message_idx` maps cleanly to row IDs.
- `UNIQUE(thread_id, message_idx, user_id)` enforces one vote per user per message.
  Use `INSERT OR REPLACE INTO feedback ...` to handle vote changes atomically.
- `ON DELETE CASCADE` removes all feedback when a thread is deleted. Consistent with
  the existing pattern in `schema.sql` for the messages table.
- `CHECK(vote IN ('up', 'down'))` prevents invalid values at the database level.

### Flask Endpoints

```
POST /api/threads/<int:thread_id>/messages/<int:message_idx>/feedback
Body: {"vote": "up" | "down" | null}   # null removes the vote
Returns: 200 {"vote": "up"} or 200 {"vote": null}
```

Implementation:
- Verify thread ownership first: `SELECT id FROM threads WHERE id=? AND user_id=?`
- For non-null vote: `INSERT OR REPLACE INTO feedback (thread_id, message_idx, user_id, vote) VALUES (?, ?, ?, ?)`
- For null vote: `DELETE FROM feedback WHERE thread_id=? AND message_idx=? AND user_id=?`
- Return 404 if thread not found (same pattern as existing endpoints)

Enhance the existing `GET /api/threads/<thread_id>/messages` endpoint to return
feedback for each message alongside the message data. Merge in a single query:

```sql
SELECT f.message_idx, f.vote
FROM feedback f
WHERE f.thread_id = ? AND f.user_id = ?
```

Return as a `feedback` dict in the messages response so the frontend has all state
in one load round trip.

### React State Management

No external state library. Local `useState` within `MessageList` or passed down
to individual `AssistantMessage` components:

```tsx
const [feedback, setFeedback] = useState<Map<number, 'up' | 'down'>>(
  () => new Map(
    (initialFeedbackFromApi ?? []).map(f => [f.message_idx, f.vote])
  )
);

function handleVote(messageIdx: number, vote: 'up' | 'down') {
  const current = feedback.get(messageIdx);
  const newVote = current === vote ? null : vote;  // toggle off if same

  // Optimistic update
  setFeedback(prev => {
    const next = new Map(prev);
    if (newVote) next.set(messageIdx, newVote);
    else next.delete(messageIdx);
    return next;
  });

  // Sync to API, revert on error
  fetch(`/api/threads/${threadId}/messages/${messageIdx}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ vote: newVote }),
    headers: { 'Content-Type': 'application/json' },
  }).catch(() => setFeedback(prev => { /* revert */ return prev; }));
}
```

### Icon Usage

`@fluentui/react-components` already bundles `@fluentui/react-icons`. Use:
- `<ThumbLike20Regular />` / `<ThumbDislike20Regular />` — default state
- `<ThumbLike20Filled />` / `<ThumbDislike20Filled />` — active (voted) state

Use Fluent UI's `Button` with `appearance="subtle"` for the thumbs buttons — this
gives the correct hover, focus, and active states matching the Atlas design system
without custom CSS.

### What NOT to Add

- Do NOT add a global state library (Zustand, Redux) for feedback. The feedback map
  is local to message rendering; it does not need cross-component sharing.
- Do NOT add a separate `GET /feedback` endpoint. Merge feedback into the messages
  GET response to keep page load at one round trip per thread.
- Do NOT store feedback in `messages_json`. Keeping feedback in a separate table
  preserves the immutability of message history and allows future analytics queries.

---

## Feature 3: Thread Search

### Approach Decision: Client-Side Filter for v1.3

The sidebar already loads all threads via `GET /api/threads`. Filter in React on
the client — zero backend changes, zero new packages, instant results:

```tsx
const filtered = useMemo(
  () => threads.filter(t =>
    t.name.toLowerCase().includes(query.toLowerCase())
  ),
  [threads, query]
);
```

This is sufficient for the expected thread counts in an internal tool. Most users
will accumulate fewer than 500 threads; filtering 500 strings client-side is
imperceptible (<1ms).

Add a search input at the top of the sidebar using Fluent UI's `SearchBox` component
(part of `@fluentui/react-components`).

### SQLite FTS5 (Add in Future Milestone if Needed)

If server-side search becomes necessary (e.g., search message content, support
`GET /api/threads?q=...`), use SQLite FTS5 — it is built into Python's standard
library `sqlite3` module and requires no additional packages.

Verify availability (should always pass on CPython on Windows):
```python
import sqlite3
conn = sqlite3.connect(":memory:")
conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")  # no exception = available
```

FTS5 setup for thread name search:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts
USING fts5(
    name,
    content='threads',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Sync triggers (required when using external content tables)
CREATE TRIGGER IF NOT EXISTS threads_ai AFTER INSERT ON threads BEGIN
    INSERT INTO threads_fts(rowid, name) VALUES (new.id, new.name);
END;
CREATE TRIGGER IF NOT EXISTS threads_ad AFTER DELETE ON threads BEGIN
    INSERT INTO threads_fts(threads_fts, rowid, name)
    VALUES ('delete', old.id, old.name);
END;
CREATE TRIGGER IF NOT EXISTS threads_au AFTER UPDATE ON threads BEGIN
    INSERT INTO threads_fts(threads_fts, rowid, name)
    VALUES ('delete', old.id, old.name);
    INSERT INTO threads_fts(rowid, name) VALUES (new.id, new.name);
END;
```

Initial population of an existing database (run once):
```sql
INSERT INTO threads_fts(threads_fts) VALUES('rebuild');
```

FTS5 query:
```python
db.execute(
    "SELECT t.id, t.name, t.updated_at FROM threads t"
    " JOIN threads_fts ON threads_fts.rowid = t.id"
    " WHERE t.user_id = ? AND threads_fts MATCH ?"
    " ORDER BY rank",
    (_user_id(), query + "*"),  # trailing * = prefix match
)
```

The `porter unicode61` tokenizer handles English stemming and Unicode normalization.
It is appropriate for internal tool thread names in English.

### What NOT to Add

- Do NOT add `whoosh`, `tantivy`, `elasticsearch-py`, or any search library.
  FTS5 inside `sqlite3` is sufficient for the scale of this tool.
- Do NOT index `messages_json` content in v1.3. The JSON blob requires `json_each()`
  extraction or Python-side parsing before indexing — a meaningful schema refactor.
  Defer to a future milestone that restructures message storage into individual rows.

---

## Feature 4: Conversation Export

### What Changes

**No new packages.** Pure client-side using the browser's `Blob` and
`URL.createObjectURL` APIs. No server endpoint needed.

### Implementation

```tsx
function exportConversation(
  format: 'markdown' | 'json',
  thread: { id: number; name: string },
  messages: Array<{ role: string; content: string }>
) {
  const name = (thread.name || 'conversation')
    .replace(/[\\/:*?"<>|]/g, '-')  // strip invalid filename chars
    .trim();

  let content: string;
  let mimeType: string;
  let filename: string;

  if (format === 'json') {
    content = JSON.stringify({ thread, messages }, null, 2);
    mimeType = 'application/json';
    filename = `${name}.json`;
  } else {
    content = formatAsMarkdown(thread, messages);
    mimeType = 'text/markdown';
    filename = `${name}.md`;
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);  // release memory immediately
}

function formatAsMarkdown(
  thread: { name: string },
  messages: Array<{ role: string; content: string }>
): string {
  const lines = [`# ${thread.name || 'Conversation'}`, ''];
  for (const msg of messages) {
    const label = msg.role === 'user' ? '**You**' : '**Atlas**';
    lines.push(`${label}`, '', msg.content, '');
  }
  return lines.join('\n');
}
```

`Blob` and `URL.createObjectURL` are supported in all modern browsers (Chrome, Edge,
Firefox, Safari). No polyfills needed. The `document.body.appendChild/removeChild`
pattern is required in Firefox for the `download` attribute to fire correctly.

### Trigger Point

Add an export option to the thread context menu or a toolbar button above the message
list. Fluent UI's `Menu` + `MenuItem` components (already available via
`@fluentui/react-components`) are the correct pattern for a "..." overflow menu.

### What NOT to Add

- Do NOT add `file-saver`, `jszip`, `html2pdf`, or any export library. The Blob/URL
  pattern is ~15 lines and has no dependencies.
- Do NOT add a server-side export endpoint. The messages are already in the client
  for rendering. Server-side generation adds a round trip and temp file management.
- Do NOT add PDF export in v1.3. PDF generation requires either a server-side library
  (`WeasyPrint`, `ReportLab`) or a client-side one (`jspdf`, `pdfmake`), both of which
  introduce meaningful complexity and non-trivial bundle weight. Defer if requested.

---

## Feature 5: Motion Animations

### Package

`motion` — import from `motion/react`.

**Current version:** 12.38.0  
**Source:** GitHub CHANGELOG at `motiondivision/motion` — version 12.38.0 released
2026-03-16 (HIGH confidence, verified directly).

**Installation status:** `motion` is NOT currently in `frontend/package.json`
(confirmed by direct file inspection). It was listed as a planned dependency in
v1.2 research but was not added. Install now:

```bash
cd /c/xmcp/frontend && npm install motion
```

### Why `motion` Over `@fluentui/react-motion`

`@fluentui/react-motion` (v9.11.6, a `@fluentui/react-components` sub-package)
provides Web Animations API primitives for Fluent UI's internal component transitions
(Presence component pattern for Dialogs, Tooltips, Popovers). It is NOT a general
animation library — it does not expose `AnimatePresence` equivalents for arbitrary
component tree entrances and exits.

`motion/react` provides:
- `AnimatePresence` for mount/unmount animations (correct for message list additions
  and thread item deletions)
- `layout` prop for smooth list reordering without manual position tracking
- Imperative `useAnimate` hook for programmatic animations
- Full TypeScript support; production-tested with React 19 + Vite + Tailwind v4

Both libraries can coexist. If Fluent UI components ship their own Presence-based
transitions via `@fluentui/react-motion`, those will continue to work independently
alongside `motion/react` for Atlas-specific animations.

### Bundle Size Strategy

Use `LazyMotion` + `m` component + `domAnimation` feature pack to minimize bundle
impact:

```tsx
// In App.tsx or the animated section root:
import { LazyMotion, domAnimation } from 'motion/react';

export function App() {
  return (
    <LazyMotion features={domAnimation} strict>
      {/* rest of app */}
    </LazyMotion>
  );
}

// In individual components:
import { m, AnimatePresence } from 'motion/react';
```

Bundle size breakdown (verified against motion.dev docs, March 2026):
- Full `motion` component: ~34KB — do NOT use this
- `m` + `LazyMotion` initial render: ~4.6KB
- `domAnimation` feature pack: +~15KB (covers animate, variants, exit animations,
  tap/hover/focus gestures)
- **Total with domAnimation: ~19.6KB** — acceptable for a chat application

`domMax` (+~25KB) adds drag gestures and layout animations — add only if sidebar
collapse needs a layout-aware transition. Start with `domAnimation`.

### Atlas Animation Targets

| Location | Element | Animation | Values |
|----------|---------|-----------|--------|
| Message list | `AssistantMessage`, `UserMessage` on mount | Fade + slide up | `initial: {opacity:0, y:8}` → `animate: {opacity:1, y:0}` 150ms ease-out |
| Thread sidebar | `ThreadItem` on mount/unmount | Fade + slide right | Same pattern; `AnimatePresence` handles unmount |
| Tool call panel | `ToolPanel` expand/collapse | Height + opacity | `AnimatePresence` + `m.div` with `initial: {height:0, opacity:0}` |
| Feedback buttons | Thumbs up/down on tap | Scale micro-bounce | `whileTap: {scale: 0.85}` — no `LazyMotion` feature needed |
| Sidebar collapse | Sidebar wrapper | Width transition | `animate: {width: isCollapsed ? 48 : 280}` 200ms; upgrade to `domMax` + `layout` if needed |

### What NOT to Add

- Do NOT add `framer-motion` as a separate package alongside `motion`. `framer-motion`
  is now a thin re-export of the `motion` package internals; installing both creates
  duplicate code.
- Do NOT use CSS `transition` for mount/unmount animations. CSS transitions do not fire
  on element mount (initial render) or unmount (removal from DOM). `AnimatePresence`
  is the correct tool for those.
- Do NOT animate every interaction. Limit animations to: (a) spatial orientation
  during list changes, (b) expand/collapse for panels with variable height, (c) micro-
  interactions that confirm user actions (thumbs scale). Do not animate hover states,
  focus rings, button hover color changes, or scroll events.

---

## Installation Summary

```bash
# Frontend — one new package
cd /c/xmcp/frontend
npm install motion
# Expected: motion@12.38.0 (or current patch)

# Backend — no new packages
# (no pip install needed)
```

### SQLite Schema Migrations

Two SQL statements to add (append to `schema.sql` for new deployments; run directly
against the production `.db` file for existing deployments):

```sql
-- 1. Per-message feedback
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    message_idx INTEGER NOT NULL,
    user_id     TEXT    NOT NULL,
    vote        TEXT    NOT NULL CHECK(vote IN ('up', 'down')),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(thread_id, message_idx, user_id)
);

-- 2. Thread FTS index (DEFER TO FUTURE MILESTONE unless server-side search is in scope)
-- CREATE VIRTUAL TABLE IF NOT EXISTS threads_fts USING fts5(...);
```

---

## Alternatives Considered

| Feature | Recommended | Alternative | Why Not |
|---------|-------------|-------------|---------|
| App Roles claim source | ID token `roles` from `id_token_claims` | Groups claim or on-demand Graph API call | Groups have overage risk at 80K+ user scale; Graph call adds latency to every request; App Roles are the purpose-built mechanism |
| Feedback storage | Separate `feedback` table with `message_idx` | Embed vote fields in `messages_json` | JSON blob modification on every vote is error-prone and complicates concurrent writes; separate table is queryable for analytics |
| Thread search | Client-side filter (v1.3) → FTS5 (future) | PostgreSQL, Meilisearch, Algolia | Gross overkill; SQLite FTS5 is zero-dependency and sufficient for expected thread volumes in an internal tool |
| Export format | Markdown + JSON | PDF, DOCX, CSV | PDF/DOCX require heavy libraries with non-trivial bundle weight; CSV is wrong format for conversational data |
| Export mechanism | Client-side Blob/URL | Server-side file generation endpoint | Server-side adds a round trip and requires writing + cleaning temp files; all data is already client-side |
| Animation library | `motion/react` with `LazyMotion + domAnimation` | Full `motion` component; `@fluentui/react-motion`; CSS transitions | Full `motion` = 34KB unnecessary overhead; `@fluentui/react-motion` lacks `AnimatePresence` for arbitrary list transitions; CSS transitions don't fire on mount/unmount |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| App Roles `roles` claim in ID token | HIGH | Official Microsoft docs (howto-add-app-roles-in-apps 2024-11-13; configure-tokens-group-claims-app-roles 2025-04-18) with token payload examples showing `"roles": ["Approver", "Reviewer"]` |
| No MSAL config change needed | HIGH | Same docs: auth code flow with any scope emits ID token with `roles` once user is assigned; `User.Read` scope is sufficient |
| `id_token_claims` already populated in session | HIGH | Direct `auth.py` code inspection: `session["user"] = result.get("id_token_claims")` |
| SQLite FTS5 built into Python `sqlite3` | HIGH | CPython standard library on all platforms; no optional compilation flag needed on Windows |
| FTS5 external content table + trigger pattern | HIGH | Official SQLite FTS5 documentation; pattern is stable since FTS5's stable release |
| Client-side export via Blob/URL | HIGH | W3C-specified browser API; universally supported in all modern browsers (Chrome, Edge, Firefox) |
| `motion` version 12.38.0 | HIGH | Verified directly against GitHub CHANGELOG (released 2026-03-16) |
| `motion/react` + React 19 compatibility | HIGH | Motion docs explicitly state production-tested with React 19 + Vite + Tailwind v4 |
| `LazyMotion + domAnimation` bundle ~4.6KB initial + 15KB features | HIGH | Verified against official motion.dev/docs/react-reduce-bundle-size (document dated March 2026) |
| `@fluentui/react-motion` lacks `AnimatePresence` | MEDIUM | Inferred from package scope (Web Animations API utilities for Fluent components only); verified that `AnimatePresence` is not in the package's public API based on search results |
| `feedback.message_idx` design holds for append-only messages | MEDIUM | Architectural assumption: messages are append-only (confirmed by existing code — no message editing endpoint); index stability holds while this constraint holds |

---

## Sources

**Official documentation (HIGH confidence):**
- [Add app roles and get them from a token — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps) (updated 2024-11-13)
- [Configure group claims and app roles in tokens — Microsoft Learn](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles) (updated 2025-04-18)
- [Microsoft Entra app manifest reference (Microsoft Graph format) — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity-platform/reference-microsoft-graph-app-manifest)
- [SQLite FTS5 Extension — official documentation](https://sqlite.org/fts5.html)
- [Reduce bundle size — motion.dev](https://motion.dev/docs/react-reduce-bundle-size) (March 2026)
- [motion CHANGELOG — GitHub](https://github.com/motiondivision/motion/blob/main/CHANGELOG.md) (v12.38.0, 2026-03-16)

**Community sources (MEDIUM confidence, cross-verified):**
- [How to download CSV and JSON files in React — theroadtoenterprise.com](https://theroadtoenterprise.com/blog/how-to-download-csv-and-json-files-in-react)
- [FTS5 triggers — simonh.uk](https://simonh.uk/2021/05/11/sqlite-fts5-triggers/)
- [motion vs framer-motion mobile performance 2025 — reactlibraries.com](https://www.reactlibraries.com/blog/framer-motion-vs-motion-one-mobile-animation-performance-in-2025)

**Direct codebase inspection (HIGH confidence):**
- `frontend/package.json` — `motion` not present as of research date; React 19.2.4, Fluent UI 9.73.5 confirmed
- `chat_app/auth.py` — `session["user"] = result.get("id_token_claims")` at line 169; `Config.AZURE_AUTHORITY` is tenant-specific
- `chat_app/schema.sql` — threads + messages tables exist; no feedback or FTS tables
- `chat_app/conversations.py` — message storage pattern (append-only `messages_json` blob) confirmed

---

*Research completed: 2026-04-01*
*Feeds into: v1.3 roadmap creation*
*Companion files: STACK.md (existing — covers Layers 1-5 for prior milestones)*
