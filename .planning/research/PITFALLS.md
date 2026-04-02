# Domain Pitfalls — v1.3 Feature Addition

**Domain:** Adding access control, feedback, search, export, and animations to an existing Flask + React + Azure AD chat app
**Project:** Atlas — Marsh McLennan Exchange infrastructure chat
**Milestone:** v1.3 (App Role access control, thumbs feedback, FTS5 thread search, export, animations)
**Researched:** 2026-04-01
**Confidence:** HIGH — verified against actual codebase (auth.py, db.py, schema.sql, conversations.py), official Microsoft Entra ID docs, and SQLite FTS5 documentation

---

## Preface: These Are Additive Changes to a Production System

Every pitfall below is scoped to the specific risk of **adding** a feature to this existing running system. Generic advice ("don't ship bugs") is excluded. The question answered for each pitfall is: "Given the exact code in this repository, what specific mistake would a developer make when implementing this feature?"

The highest-risk feature in v1.3 is the App Role access control change. Getting it wrong in either direction — too permissive (80K users remain unblocked) or too restrictive (IT engineers locked out) — is a production incident. That feature section is disproportionately detailed.

---

## SECTION 1: App Role Access Control

### Pitfall 1.1 — "User Assignment Required" Set Without Code-Level Role Check

**Severity:** CRITICAL

**What goes wrong:**
A developer enables "Assignment required?" in Entra ID Enterprise Apps for the Atlas registration, assigns the IT engineers group to the app, and considers access control done. They do not add a role check to the Flask `@login_required` decorator or callback handler.

This feels complete because unassigned users do receive a Microsoft-side "you do not have access" page when they attempt to sign in. However, this is not defense in depth — it is sole reliance on an Entra ID tenant configuration that any Cloud Application Administrator can change. The Flask application itself performs no authorization, only authentication.

**Why this is a problem for Atlas specifically:**
`auth.py:login_required` only checks `session.get("user")` (line 97). It does not check any claim within that user object. If "User Assignment Required" is ever accidentally disabled (common during IT admin turnover), all 80K tenant users regain access silently. Flask would issue sessions to anyone who successfully authenticates.

**Official Microsoft guidance:**
Microsoft explicitly documents this as a two-layer approach: "Developers can use popular authorization patterns like Azure RBAC" alongside the "built-in feature of Microsoft Entra ID." The portal setting restricts sign-in; the code-level check enforces authorization.

**Prevention:**
- After verifying the `roles` claim is present in `id_token_claims`, add a `require_role` decorator in `auth.py` that reads `session["user"].get("roles", [])` and checks for the expected role value string
- The portal setting is a convenience, not a substitute for code-level enforcement
- Document this in comments: "This check is intentional defense-in-depth. The Entra ID portal setting is the outer gate; this is the inner gate."

**Warning signs:**
- `@login_required` decorator is unchanged after the v1.3 App Role work
- No unit test exists that verifies a session without the correct role is rejected

**Phase that must address it:** Phase 1 of v1.3. Must be implemented before the portal setting is enabled.

---

### Pitfall 1.2 — Roles Claim Exists in ID Token but Not in Access Token

**Severity:** CRITICAL

**What goes wrong:**
For a web app that signs in users (which Atlas is), App Roles appear in the **ID token**, not the access token. The current `auth_callback` route already stores `id_token_claims` in `session["user"]` (auth.py line 169). This is correct.

The pitfall occurs when a developer reads documentation about App Roles appearing in "the token" and tests their configuration using `jwt.ms` or by decoding the access token (`result["access_token"]`) — and finds the `roles` claim missing there. They conclude the App Role configuration is wrong and spend hours debugging the Entra ID manifest, when the configuration is actually fine.

The `roles` claim is in `id_token_claims`, which MSAL returns as a decoded dict in `result["id_token_claims"]`. It is already being stored. The developer only needs to read from `session["user"]["roles"]`.

**Official Microsoft documentation (verified):**
"For an app that signs in users, the roles claims are included in the ID token. When your application calls an API, the roles claims are included in the access token."

**Consequence of misdiagnosis:**
Developer modifies the auth flow to acquire an access token for a downstream API (which Atlas doesn't have) to get roles in an access token — introducing unnecessary complexity, a second token request, and a potential silent regression in the auth flow.

**Prevention:**
- Verify the `roles` claim by decoding `result["id_token_claims"]` immediately after `acquire_token_by_auth_code_flow`, not `result["access_token"]`
- Add a debug log in development: `logger.debug("id_token_claims: %s", result.get("id_token_claims", {}))`
- Use jwt.ms to decode the **ID token** (`result["id_token"]`), not the access token

**Warning signs:**
- Developer reports "roles claim not found" but is looking at the access token
- Pull request adds a second `cca.acquire_token_silent()` call solely to get roles
- `get_token_silently()` in auth.py is called inside the auth callback to "get roles"

**Phase that must address it:** Phase 1 of v1.3 implementation.

---

### Pitfall 1.3 — Existing Sessions From Before the Role Change Are Never Invalidated

**Severity:** CRITICAL

**What goes wrong:**
When App Role access control is deployed, all existing Flask filesystem sessions remain valid. Users who were signed in before deployment will have `session["user"]` populated with `id_token_claims` from their previous login — which will **not contain a `roles` claim** because they authenticated before App Roles were configured.

The new `require_role` check reads `session["user"].get("roles", [])`. For all existing sessions, this returns `[]`. These users will be immediately unauthorized on their next API call, even if they are members of the authorized group. They will hit a wall with no explanation.

**Specific risk in this codebase:**
Flask-Session stores sessions in `/tmp/flask-sessions` (config.py line 14). These files persist across deployments unless explicitly deleted. There is no session expiry configuration in `config.py` (`SESSION_PERMANENT = False` means sessions don't persist across browser close, but do persist while the browser is open).

**Consequence:**
IT engineers who are in the authorized group but had an open browser session will be kicked out on first request after deployment and need to re-login. This is actually acceptable behavior, but it must be communicated. The failure mode is if the error message is confusing ("Access denied") rather than actionable ("Please log in again to apply new access settings").

**Prevention:**
- Before deploying App Role enforcement, delete all existing session files: `rm -rf /tmp/flask-sessions/*`
- OR: Add a session version check — store a `session_version` field at login, and check it against a current expected version on every request; mismatch triggers a forced re-login redirect
- Present a clear "Please log in again to access this application" message rather than a generic 403, specifically for the case where `roles` is absent but the user is otherwise authenticated
- Communicate the forced re-login to users before deployment

**Warning signs:**
- IT engineers report being locked out immediately after deployment despite being in the authorized group
- Session files in `/tmp/flask-sessions` still exist from pre-deployment
- No session flush step in the deployment runbook

**Phase that must address it:** Deployment step in Phase 1 of v1.3.

---

### Pitfall 1.4 — Group Assignment to App Role: Roles Claim Appears in Token

**Severity:** HIGH

**What goes wrong:**
The design intends to assign a security group (the IT engineers group) to an App Role in Entra ID. A developer reads the documented limitation: "if you add a service principal to a group, and then assign an app role to that group, Microsoft Entra ID doesn't add the roles claim to tokens it issues."

They interpret this as "group assignment to App Roles doesn't work." This is wrong. The limitation applies specifically to **service principal** members of groups. For **users** who are members of a security group, assigning that security group to an App Role works correctly — when a user signs in, their group memberships are evaluated, the App Role is found, and the `roles` claim is included in their ID token.

**Prevention:**
- Assign the security group directly to the App Role via Enterprise Apps → Users and Groups → Add Assignment → select the security group → select the App Role
- Verify by signing in as a member of the group and checking `id_token_claims["roles"]` in the session
- Do NOT assign roles directly to individual users — this creates an unmanageable maintenance burden with 80K users in the tenant

**Warning signs:**
- Developer assigns the App Role only to individual users, not the security group
- Developer tries to assign a Managed Identity or service principal to the group and wonders why roles don't appear
- Documentation confusion leads to using `groups` claim instead of `roles` claim

**Phase that must address it:** Entra ID configuration step in Phase 1 of v1.3.

---

### Pitfall 1.5 — Role Value String Mismatch Between Manifest and Code

**Severity:** HIGH

**What goes wrong:**
The App Role defined in the Entra ID App Registration manifest has a `value` field (e.g., `Atlas.User`). The Flask code checks for a specific string in `session["user"]["roles"]`. If these strings do not match exactly — including case — the check always fails, blocking all users.

Common causes: developer uses `atlas.user` (lowercase) in code, manifest has `Atlas.User`; developer uses `AtlasUser` in code, manifest has `Atlas.User`; manifest value contains spaces (invalid — the manifest rejects spaces in the `value` field, but the display name may have spaces, causing confusion).

**Specific risk in this codebase:**
There is currently no ALLOWED_ROLE constant defined anywhere. The first implementation of `require_role` will hard-code the role name string somewhere. If that string is typed manually without copy-pasting from the manifest, it will likely differ.

**Prevention:**
- Copy the `value` field from the manifest JSON verbatim; do not retype it
- Store the role name in `config.py` as `REQUIRED_APP_ROLE = "Atlas.User"` (or equivalent) rather than inline in the decorator
- Add a startup log: `logger.info("Enforcing App Role: %s", Config.REQUIRED_APP_ROLE)` so the value is visible in deployment logs
- Test with a real user account from the authorized group before calling the phase complete

**Warning signs:**
- All authenticated users receive "insufficient role" errors, including known IT engineers
- Log shows `session["user"]["roles"]` is `["Atlas.User"]` but `Config.REQUIRED_APP_ROLE` is `"atlas.user"`

**Phase that must address it:** Implementation and configuration review in Phase 1 of v1.3.

---

### Pitfall 1.6 — App Role Not Assigned a "Users/Groups" Allowed Member Type

**Severity:** HIGH

**What goes wrong:**
When creating the App Role in the Entra ID manifest, the developer sets "Allowed member types" to "Applications" only (for app-to-app scenarios) or forgets to set it to "Users/Groups." The role appears in the manifest but cannot be assigned to the security group because the portal UI hides roles that don't allow user/group assignment.

Result: the role exists, but no users can have it assigned. The `roles` claim is always absent from ID tokens.

**Prevention:**
- In the App Role creation UI: "Allowed member types" must be set to "Users/Groups" or "Both (Users/Groups + Applications)"
- After creating the role, navigate to Enterprise Apps → Users and Groups to verify the role appears as an option in the role selector when adding an assignment

**Warning signs:**
- Role is visible in App registrations → App roles but not available in Enterprise Apps → Users and groups → Add assignment → Select role dropdown
- All user ID tokens lack the `roles` claim despite the role being defined

**Phase that must address it:** Entra ID configuration step in Phase 1 of v1.3.

---

### Pitfall 1.7 — Frontend Shows "Loading" Indefinitely When Role Check Returns 403

**Severity:** MEDIUM

**What goes wrong:**
The React `AuthContext` (`contexts/AuthContext.tsx`) fetches `/api/me` on mount. Currently `/api/me` returns the user object or 401 (if no session). With App Role enforcement, there is a new state: authenticated (session exists, `session["user"]` is populated) but unauthorized (role is missing). The backend may return 403.

The frontend `fetchMe()` function in `api/me.ts` handles 401 by redirecting to login. It does not handle 403. The React app enters an error state (`error: "Forbidden"`) and the `loading: false, user: null` path in `AuthContext` shows whatever the catch branch shows — likely nothing useful or an infinite loading spinner if the error is swallowed.

**Prevention:**
- The 403 response from a role-enforcement failure must include a redirect to a clear "access denied" page, not a JSON body that the SPA will fail to handle gracefully
- OR: update `fetchMe()` to handle 403 explicitly and show a dedicated "You don't have access to this application. Contact your IT manager." message
- Do NOT silently swallow the 403 and show the SPA in a broken state
- Test: sign in with a user who is not in the authorized group and verify they see an actionable error, not a loading spinner

**Warning signs:**
- Loading spinner persists indefinitely for unauthorized users
- Browser DevTools shows `/api/me` returning 403 but UI shows no feedback to the user
- `AuthContext` error state does not render any visible component

**Phase that must address it:** Phase 1 of v1.3, frontend error handling for the new 403 state.

---

## SECTION 2: Thumbs Up/Down Feedback

### Pitfall 2.1 — Feedback Stored Per Thread Instead of Per Message

**Severity:** HIGH

**What goes wrong:**
Messages are stored as a JSON blob in `messages.messages_json` (one row per thread, containing the entire conversation array). There is no per-message primary key in the current schema. A developer implements feedback as a new `feedback` table with `thread_id + message_index` as the key.

`message_index` is fragile: messages can be retried, regenerated, or pruned. If a user deletes a thread and re-creates a similar one, the index becomes meaningless. If message arrays are ever truncated for context length, indices shift, and feedback rows point to the wrong messages.

**Specific risk in this codebase:**
`schema.sql` does not have a `messages` table with individual rows — it has a single `messages_json TEXT` column. Adding feedback to this schema requires either: (a) adding a message-level ID to the JSON objects, or (b) creating a `feedback` table keyed on `(thread_id, message_content_hash)`.

**Prevention:**
- Add a stable `message_id` (e.g., UUID or monotonic counter) to each message object when it is appended to `messages_json`; store this ID as part of the JSON structure
- Key the `feedback` table on `message_id`, not `(thread_id, index)`
- If adding `message_id` to existing messages is out of scope for v1.3, use `(thread_id, sha256(role + content[:200]))` as a fallback key — imperfect but stable for unedited messages

**Warning signs:**
- `feedback` table has a `message_index INTEGER` column
- No per-message ID field in the message JSON objects in `messages.messages_json`
- Feedback query joins on array index position

**Phase that must address it:** Schema design phase for feedback feature.

---

### Pitfall 2.2 — Double-Voting Not Prevented at the Database Level

**Severity:** MEDIUM

**What goes wrong:**
A user clicks thumbs up, the network is slow, they click again. Two `INSERT` calls reach the API. The `feedback` table accumulates duplicate rows for the same `(user_id, message_id)`, corrupting any future analytics query.

**Prevention:**
- Apply a `UNIQUE` constraint on `(user_id, message_id)` in the `feedback` table
- Use `INSERT OR REPLACE` (upsert) semantics so a second vote overwrites the first rather than duplicating it: `INSERT OR REPLACE INTO feedback (user_id, message_id, vote) VALUES (?, ?, ?)`
- The API endpoint should be idempotent: calling `POST /api/feedback` with the same `(user_id, message_id)` twice returns 200 both times with the current vote state

**Warning signs:**
- No `UNIQUE` constraint in the feedback table DDL
- Feedback analytics queries use `COUNT(*)` and find more votes than distinct `(user_id, message_id)` pairs

**Phase that must address it:** Schema design for the feedback feature.

---

### Pitfall 2.3 — Feedback UI Displayed During Active Streaming

**Severity:** MEDIUM

**What goes wrong:**
Thumbs up/down buttons are rendered per assistant message. If they appear while the message is still streaming (content is partial), a user could vote on an incomplete response. The feedback is recorded for a message that was never fully read. This makes feedback data meaningless for quality analysis.

**Prevention:**
- Render the feedback buttons only after the `done` SSE event is received and the message is complete
- In the React streaming state (`useStreamingMessage.ts`), track an `isComplete` flag; only render `<FeedbackButtons>` when `isComplete === true`
- Historical messages (loaded from `GET /api/threads/:id/messages`) should show feedback buttons immediately since they are already complete

**Warning signs:**
- Thumbs buttons are visible while the streaming cursor is still animating
- A `FeedbackButtons` component is rendered inside the streaming message component without an `isComplete` guard

**Phase that must address it:** Feedback UI implementation.

---

## SECTION 3: Thread Search with SQLite FTS5

### Pitfall 3.1 — Searching the JSON Blob Directly Instead of an FTS Index

**Severity:** HIGH

**What goes wrong:**
The existing schema stores all messages as a JSON string in `messages.messages_json`. A developer implements search as `SELECT * FROM messages WHERE messages_json LIKE '%query%'` with a per-user filter. This works for small datasets but:
- Does a full-table scan for every search (no index possible on a LIKE with leading wildcard)
- Returns the entire JSON blob even when only one message matches
- Does not support phrase matching, ranking, or stemming
- Does not search thread names (`threads.name`)

At 80K potential users with potentially hundreds of threads each, this degrades rapidly.

**Prevention:**
- Create an FTS5 virtual table that indexes content extracted from `threads.name` and the text content of messages
- Use an external content table pointing at a denormalized search view, or maintain the FTS index via triggers
- The FTS table should be keyed to `thread_id` so results can be filtered by `user_id` (FTS5 does not support user-scoping natively — filter after retrieval)

**Warning signs:**
- Search implementation uses `LIKE '%term%'` on the `messages_json` column
- No `CREATE VIRTUAL TABLE` statement in the schema
- Search query is not filtered by `user_id` before returning results

**Phase that must address it:** FTS schema design step.

---

### Pitfall 3.2 — FTS5 External Content Table Without Sync Triggers

**Severity:** HIGH

**What goes wrong:**
A developer creates an FTS5 virtual table as an external content table pointing at a source table. They populate the FTS index at creation time but do not create `AFTER INSERT`, `AFTER UPDATE`, and `AFTER DELETE` triggers on the source table. As new threads and messages are added, the FTS index becomes stale. Search stops returning new content.

**Official SQLite documentation (verified):**
"It is the responsibility of the user to ensure that an FTS5 external content table ... is kept consistent with the content table itself."

**Specific risk in this codebase:**
The existing schema does not have per-message rows. FTS5 will need to index content extracted from the JSON blob (or a view over it). Triggers on the `messages` table must fire when `messages_json` is updated (which happens on every message append in `conversations.py`). The trigger must re-extract text from the JSON and update the FTS index. This is non-trivial with SQLite's limited JSON functions.

**Prevention:**
- Create INSERT, UPDATE, and DELETE triggers on the `messages` table that update the FTS virtual table
- Alternatively, maintain a denormalized `thread_search_content` table (thread_id, combined_text) that is updated by the application layer when messages are appended; index this table with FTS5 — this avoids JSON extraction in triggers
- After creating triggers, verify with `INSERT INTO fts_threads(fts_threads) VALUES('integrity-check')` that the index is consistent

**Warning signs:**
- FTS5 table created without corresponding trigger definitions in schema.sql
- New conversations are not returned in search results but old ones are
- `INSERT INTO fts(fts) VALUES('rebuild')` is needed after every deployment to refresh the index

**Phase that must address it:** FTS schema design and migration step.

---

### Pitfall 3.3 — FTS5 Does Not Scope Results to the Current User

**Severity:** HIGH

**What goes wrong:**
FTS5 virtual tables cannot use WHERE clauses that reference non-FTS columns efficiently. A query like `SELECT * FROM fts_threads WHERE fts_threads MATCH ? AND user_id = ?` will perform the full-text match first and then filter by `user_id`, meaning it scans all users' indexed content. Worse: if the FTS virtual table does not store `user_id` at all, there is no way to filter at the FTS level.

This means one user's search might (depending on FTS join design) inadvertently expose thread IDs from other users' threads, which the subsequent ownership check on the threads table would catch — but the thread IDs themselves could leak in error messages or intermediate query state.

**Prevention:**
- Include `user_id` as an indexed column in the FTS virtual table, even though it will not be searched with FTS MATCH — this allows the content retrieval JOIN to be scoped by user
- OR: Accept that FTS returns `thread_id` results and always JOIN back to `threads WHERE user_id = ?` before returning anything to the client — this is the minimum correct pattern, already used in `conversations.py` for all other queries
- Never return raw FTS match results without the ownership JOIN

**Warning signs:**
- Search endpoint returns `thread_id` values from the FTS table without joining to `threads WHERE user_id = ?`
- No `user_id` filter on the search API endpoint at all

**Phase that must address it:** Search API implementation.

---

### Pitfall 3.4 — Porter Tokenizer Produces Unexpected Match Behavior for Technical Terms

**Severity:** MEDIUM

**What goes wrong:**
Exchange infrastructure conversations contain technical terms: `DAGHealth`, `MailboxMoveRequest`, `TransportService`, `Get-ExchangeCertificate`. The Porter stemmer is designed for English prose. It will stem `TransportService` to `transportservic` and `mailboxmoverequest` to `mailboxmoverequest` (no useful stemming on compound terms). Worse, it may over-stem: `databases` → `databas`, `queues` → `queu`.

Users searching for `DAG` will not match `DAGHealth` with Porter stemming unless the query also contains `dag`.

**Prevention:**
- Use the `unicode61` tokenizer (the FTS5 default) for Exchange thread content — it handles case-insensitive matching without over-stemming technical terms
- Do NOT use the Porter tokenizer for this use case
- Consider the `trigram` tokenizer if substring matching within compound terms is required (e.g., `health` matching `DAGHealth`) — but note trigram indexes are significantly larger

**Warning signs:**
- FTS5 table created with `tokenize = "porter unicode61"`
- Search for `DAG` does not return threads containing `DAGHealth`
- Search for `cert` does not return threads containing `certificate`

**Phase that must address it:** FTS schema design step.

---

### Pitfall 3.5 — FTS5 Migration Does Not Backfill Existing Threads

**Severity:** MEDIUM

**What goes wrong:**
The FTS5 table and triggers are added in a schema migration. The triggers fire on new inserts going forward. But all existing threads and messages in the database are not indexed. Users search for conversations they had last week and find nothing.

**Prevention:**
- Include a backfill step in the schema migration script that populates the FTS table from existing data:
  ```sql
  INSERT INTO fts_threads(rowid, thread_id, user_id, content)
  SELECT t.id, t.id, t.user_id, t.name || ' ' || m.messages_json
  FROM threads t JOIN messages m ON m.thread_id = t.id;
  ```
- Run `INSERT INTO fts_threads(fts_threads) VALUES('optimize')` after the backfill
- Verify backfill row count matches `SELECT COUNT(*) FROM threads`

**Warning signs:**
- Schema migration creates FTS table and triggers but has no `INSERT INTO fts_threads SELECT ...` backfill
- Search returns zero results until users create new conversations after the deployment

**Phase that must address it:** FTS schema migration.

---

## SECTION 4: Conversation Export

### Pitfall 4.1 — Export Contains Raw `messages_json` Structure, Not Human-Readable Content

**Severity:** HIGH

**What goes wrong:**
Messages are stored in OpenAI chat format as a JSON array. A naive export endpoint returns the raw `messages_json` content: `[{"role": "system", "content": "..."}, {"role": "tool", "tool_call_id": "...", "content": "..."}]`. This is not usable by a non-developer. IT engineers expect a Markdown or plain-text file they can paste into a report.

**Prevention:**
- The export endpoint must parse `messages_json`, filter out `system` and `tool` role messages, and render a human-readable format
- Format: `**User:** <content>\n\n**Atlas:** <content>\n\n` — simple, copyable, readable
- Tool call results should be included in collapsed form (e.g., `[Tool: Get-MailboxStatistics — success]`) not as raw JSON

**Warning signs:**
- Export endpoint returns `json.loads(row["messages_json"])` directly without transformation
- Exported file contains `tool_call_id` fields or `system` role messages

**Phase that must address it:** Export API implementation.

---

### Pitfall 4.2 — Export Does Not Validate Thread Ownership Before Serving Content

**Severity:** CRITICAL

**What goes wrong:**
A developer implements `GET /api/threads/<id>/export` by fetching `messages_json` using only `thread_id`, without the `user_id = ?` ownership check. Any authenticated user (or any user with a valid session, since role enforcement only gates app entry) can export any other user's conversation by guessing or iterating thread IDs.

Thread IDs in this schema are auto-incrementing integers starting from 1 — trivially enumerable.

**Specific risk in this codebase:**
Every other `conversations.py` query includes `AND user_id = ?` (lines 46, 83, 102, 124). An export endpoint written by a developer not familiar with this pattern will miss it.

**Prevention:**
- All export queries must follow the same pattern as `get_messages()` in `conversations.py`: verify thread ownership first with a separate `SELECT id FROM threads WHERE id = ? AND user_id = ?` query
- Code review must verify the ownership check is present before any export endpoint is merged
- Add a test: attempt to export a thread owned by user A while authenticated as user B — expect 404

**Warning signs:**
- Export endpoint queries `messages` table directly by `thread_id` without checking `threads.user_id`
- Export endpoint is exempt from `@login_required` decorator

**Phase that must address it:** Export API implementation.

---

### Pitfall 4.3 — Markdown in Exported Content Renders Differently Than in the App

**Severity:** MEDIUM

**What goes wrong:**
If the export format is Markdown, the rendered Markdown in the export file may not match what the user saw in the app. The app renders Markdown with `react-markdown` and custom styling. The exported file, when opened in a text editor or pasted into Word/Outlook, renders differently (or not at all).

More critically: if the export format is HTML, the assistant's Markdown content (which may contain `<code>` blocks, `<pre>` sections, user input with angle brackets) must be HTML-escaped in the export, or the HTML export will contain executable script content.

**Prevention:**
- If exporting as plain text: strip all Markdown formatting, or export raw Markdown with a `.md` extension and a note that it is best viewed in a Markdown reader
- If exporting as HTML: HTML-escape all user message content before inserting into the template; render assistant content through a trusted Markdown-to-HTML converter with sanitization
- The `Content-Disposition: attachment` header must be set so the browser downloads the file rather than rendering it inline (which would execute any injected scripts)

**Warning signs:**
- HTML export uses string interpolation (`f"<div>{message_content}</div>"`) without `html.escape()`
- Export response header is `Content-Type: text/html` without `Content-Disposition: attachment`
- User messages containing `<` characters are not escaped in the export

**Phase that must address it:** Export implementation.

---

### Pitfall 4.4 — Large Threads Cause Memory Spikes on Export

**Severity:** MEDIUM

**What goes wrong:**
A long Exchange troubleshooting session might have 50+ turns with large tool result JSON blobs in each message. The `messages_json` column for such a thread could be several megabytes. The current export approach (load the entire `messages_json`, deserialize, transform, serialize to output format) loads the entire content into memory at once per request.

For a single export by one user this is fine. But this is a synchronous Flask route on Waitress with a fixed thread pool. Multiple concurrent exports of large threads will exhaust available memory.

**Prevention:**
- Add a size guard: if `len(messages_json) > 500KB`, return a 400 with "Thread too large to export via browser. Contact your IT admin for a database export."
- OR: implement streaming export using `Response(generate(), mimetype='text/plain')` with a generator that processes messages one at a time
- In practice, for IT engineers with normal usage patterns, this is unlikely to be an issue in v1.3 — a size guard is sufficient

**Warning signs:**
- No size limit on the export route
- Export response does not use Flask's streaming `Response` for large content
- No `Content-Length` header on export response (which would reveal the size before the client downloads)

**Phase that must address it:** Export API implementation, can be addressed with a simple size guard.

---

## SECTION 5: Motion Animations

### Pitfall 5.1 — `prefers-reduced-motion` Not Respected in Animation Implementation

**Severity:** HIGH

**What goes wrong:**
Atlas is used by IT engineers who may have vestibular disorders, or who work in environments where motion is distracting. WCAG 2.1 Success Criterion 2.3.3 (AAA) and strong industry guidance requires that animations triggered by user interaction can be disabled. More practically: enterprise Windows machines commonly have "Reduce motion" enabled in accessibility settings.

If animations are implemented without checking `prefers-reduced-motion`, the app fails for these users in a highly visible way (e.g., sidebar slides that animate on every thread switch are nauseating at scale).

**Specific risk in this codebase:**
The library rename from `framer-motion` to `motion` (package: `motion`, import: `motion/react`) happened in 2024-2025. If a developer installs `framer-motion` based on older documentation, they are using the deprecated package but it still works. The real pitfall is not the package name — it is the missing `MotionConfig reducedMotion="user"` wrapper.

**Prevention:**
- Wrap the entire React app (or the relevant subtree) in `<MotionConfig reducedMotion="user">` — this single wrapper disables transform and layout animations for users who have "Reduce motion" enabled at the OS level
- Additionally, for animations that affect opacity or color (not just transforms), use `useReducedMotion()` hook to conditionally apply them
- Test by enabling "Reduce animations" in Windows Settings → Accessibility → Visual effects before reviewing any animation work

**Warning signs:**
- No `<MotionConfig>` wrapper in `App.tsx` or `main.tsx`
- Animations use `animate={{ x: ... }}` transform properties without a `useReducedMotion()` guard
- No mention of `prefers-reduced-motion` in the implementation PR

**Phase that must address it:** Animation implementation phase.

---

### Pitfall 5.2 — Layout Animations on the Thread List Cause Reflow on Every Message

**Severity:** MEDIUM

**What goes wrong:**
If `layout` prop is added to the thread list items in the sidebar (to animate reordering as threads are updated), Framer Motion / Motion performs layout calculations on every item in the list during every re-render. The sidebar re-renders on every message chunk during streaming (because `thread_named` SSE events update thread names, and streaming messages update state). This creates a cascading layout animation calculation on potentially 20-50 thread items for every streamed text token.

Result: visible jank during streaming, especially on lower-end machines.

**Prevention:**
- Do NOT apply `layout` prop to the thread list container or thread items
- Apply animations only to discrete user-initiated events: thread selection highlight, new thread insertion, thread deletion
- If `layout` animation is desired for thread reordering: gate it with a debounce (only animate when the user has not received a new streaming token for 500ms)
- Profile with React DevTools Profiler before and after adding any layout animations to the sidebar

**Warning signs:**
- `<motion.div layout>` on thread list items
- Animation frame drops visible in browser DevTools Performance tab during streaming
- CPU usage increases measurably when adding sidebar animations

**Phase that must address it:** Animation implementation phase.

---

### Pitfall 5.3 — Message Entry Animations Interfere with Streaming Cursor

**Severity:** MEDIUM

**What goes wrong:**
Adding an entry animation (`initial={{ opacity: 0 }} animate={{ opacity: 1 }}`) to the streaming message component will cause the entire message to fade in from zero opacity. During streaming, the message component mounts at the start of the stream and then receives incremental content updates. If the fade-in animation takes 200ms and the first token arrives in 50ms, the first tokens are invisible during the animation. The user perceives slower streaming.

**Prevention:**
- Apply entry animations only to completed messages (historical messages loaded on thread switch)
- Do NOT apply entry animations to the live streaming message component — it mounts once and grows in place
- Alternatively: apply only a one-time `opacity: 0 → 1` transition to the message container, not to the text content, and complete the transition in 100ms or less

**Warning signs:**
- `MessageList.tsx` applies `initial={{ opacity: 0 }}` to a component that is also used during streaming
- Users report the streaming feels slower than before the animations were added

**Phase that must address it:** Animation implementation phase.

---

### Pitfall 5.4 — Animations Block on Low-Performance Machines

**Severity:** MEDIUM

**What goes wrong:**
The target users are IT engineers, typically on corporate laptops with integrated graphics and background processes (antivirus, endpoint protection, monitoring agents). CSS animations driven by the GPU (transforms, opacity) are fine. JavaScript-driven frame-by-frame animations that call `requestAnimationFrame` in tight loops are not — they contend with corporate security agents for CPU time.

Framer Motion's spring physics animations are JavaScript-driven for complex scenarios. Simple `ease` or `linear` transitions are CSS-driven. Using spring animations on every interactive element in the app may cause visible stutter on IT laptops.

**Prevention:**
- Use CSS-based transitions (`transition={{ type: "tween", ease: "easeOut", duration: 0.15 }}`) for most animations
- Reserve spring physics for intentional playful interactions (e.g., a "sent" bounce on message submit) — maximum one per screen at a time
- Test on a mid-spec corporate machine, not a development workstation

**Warning signs:**
- All animations use default spring physics (Framer Motion's default when no `type` is specified)
- Frame rate drops below 30fps during sidebar interactions in DevTools Performance

**Phase that must address it:** Animation implementation and review phase.

---

## Cross-Feature Integration Pitfalls

### Pitfall 6.1 — FTS5 Triggers Fire During Export, Causing Lock Contention

**Severity:** MEDIUM

**What goes wrong:**
If export reads `messages_json` from the `messages` table at the same time that a user in another session is adding a new message (which triggers the FTS5 UPDATE trigger), both operations need a write lock. SQLite WAL mode allows concurrent reads but serializes all writes. The FTS5 trigger is a write (updating the FTS virtual table). If the export is inside a read transaction and the FTS trigger fires, the trigger's write must wait. Under high load with multiple concurrent users, export requests can be blocked for several seconds by FTS trigger writes.

**Prevention:**
- Export reads should not hold long transactions — keep the query atomic (one SELECT, no explicit transaction wrapping)
- FTS5 triggers should be as lightweight as possible — do not include full JSON processing inside the trigger body
- This is unlikely to be a practical problem with the current user base, but it is the correct design consideration for WAL mode with FTS triggers

**Warning signs:**
- Export endpoint wraps its query in `BEGIN TRANSACTION ... COMMIT` for no reason
- Exported queries are slow during periods of high chat activity
- SQLite `SQLITE_BUSY` errors appear in logs

**Phase that must address it:** Integration testing after both FTS5 and export are implemented.

---

### Pitfall 6.2 — App Role Enforcement Added to `/api/threads` But Not to `/chat/stream`

**Severity:** CRITICAL

**What goes wrong:**
A developer adds the `require_role` decorator to the REST endpoints in `conversations.py` but misses the SSE streaming endpoint in `chat.py`. An unauthorized user who knows the `/chat/stream` endpoint URL could post directly to it and get responses from the AI without going through the access control gate.

**Specific risk in this codebase:**
`chat.py` is a separate Blueprint from `conversations.py`. Role checking is not centralized — each Blueprint applies decorators independently. It is easy to update one Blueprint and not the other.

**Prevention:**
- Apply `require_role` to ALL protected endpoints, not just the ones in `conversations.py`
- Audit: after implementing `require_role`, search the codebase for all `@login_required` usages and verify each also has `@require_role` where appropriate
- The `@login_required` and `@require_role` decorators can be combined into a single `@require_app_role` decorator that checks both in one step, reducing the chance of applying one without the other

**Warning signs:**
- `require_role` is applied in `conversations.py` but not in `chat.py`
- `grep "@require_role"` in the codebase returns fewer results than `grep "@login_required"`
- The chat stream endpoint is not in the list of protected routes reviewed during security testing

**Phase that must address it:** Phase 1 of v1.3 access control, as part of the protected-routes audit.

---

## Phase-Specific Warnings Summary

| Phase | Feature | Pitfall | Severity |
|-------|---------|---------|---------|
| 1 — Access Control | App Roles | Portal setting alone is not sufficient; code-level check required | CRITICAL |
| 1 — Access Control | App Roles | Roles are in `id_token_claims`, not access token | CRITICAL |
| 1 — Access Control | App Roles | Existing sessions lack `roles` claim; must flush sessions on deploy | CRITICAL |
| 1 — Access Control | App Roles | `/chat/stream` in `chat.py` must also get `require_role` | CRITICAL |
| 1 — Access Control | App Roles | 403 state not handled in `AuthContext`; shows broken loading state | MEDIUM |
| 1 — Access Control | App Roles | Role value string case mismatch between manifest and code | HIGH |
| 2 — Feedback | Thumbs | No per-message ID in current schema; feedback keyed on fragile index | HIGH |
| 2 — Feedback | Thumbs | No `UNIQUE` constraint; double-vote creates analytics corruption | MEDIUM |
| 2 — Feedback | Thumbs | Feedback buttons visible during streaming before message is complete | MEDIUM |
| 3 — Search | FTS5 | LIKE query used instead of FTS virtual table | HIGH |
| 3 — Search | FTS5 | FTS5 external content table created without sync triggers | HIGH |
| 3 — Search | FTS5 | FTS results not scoped to `user_id` before returning to client | HIGH |
| 3 — Search | FTS5 | Porter tokenizer used; destroys matching for Exchange technical terms | MEDIUM |
| 3 — Search | FTS5 | FTS table not backfilled from existing threads on migration | MEDIUM |
| 4 — Export | Conversation | Raw `messages_json` returned without human-readable transformation | HIGH |
| 4 — Export | Conversation | Ownership check missing; any user can export any thread by ID | CRITICAL |
| 4 — Export | Conversation | HTML export without escaping; XSS via user-supplied message content | MEDIUM |
| 5 — Animations | Motion | `prefers-reduced-motion` not respected; WCAG violation | HIGH |
| 5 — Animations | Motion | `layout` prop on thread list; jank during streaming | MEDIUM |
| 5 — Animations | Motion | Entry animation on streaming message component; perceived lag | MEDIUM |

---

## Sources

- Microsoft Entra ID — App Roles: [Add app roles and get them from a token](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps), [Restrict app to set of users](https://learn.microsoft.com/en-us/entra/identity-platform/howto-restrict-your-app-to-a-set-of-users)
- Azure AD roles claim in ID token vs access token: [Missing roles claim in access token from auth code flow](https://learn.microsoft.com/en-us/answers/questions/1179547/missing-roles-claim-in-access-token-from-authoriza)
- Group assignment to App Roles limitation: [Add app roles — "service principal to group" note](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps) (verified in official docs)
- "User Assignment Required" behavior: [Mickaël Derriey — consequences of user assignment required](https://mderriey.com/2019/04/19/aad-apps-user-assignment-required/)
- SQLite FTS5 documentation (external content tables, triggers, REBUILD/OPTIMIZE): [sqlite.org/fts5.html](https://sqlite.org/fts5.html)
- FTS5 external content sync responsibility: [SQLite Forum — FTS5 External Content Update Statement](https://sqlite.org/forum/info/ac5fbb99316b3a5f3800e8b6d2db5a5274525e45ab1db0f02396f38e0b5e3e4a)
- FTS5 tokenizers (unicode61, porter, trigram): [SQLite FTS5 Tokenizers — audrey.feldroy.com (2025)](https://audrey.feldroy.com/articles/2025-01-13-SQLite-FTS5-Tokenizers-unicode61-and-ascii)
- Motion animations accessibility: [Motion — Accessibility docs](https://motion.dev/docs/react-accessibility), [useReducedMotion hook](https://motion.dev/docs/react-use-reduced-motion)
- Markdown XSS in export: [Pitfall of Potential Stored XSS in React-Markdown Editors](https://medium.com/@brian3814/pitfall-of-potential-xss-in-markdown-editors-1d9e0d2df93a)
- SQLite WAL concurrent write limitations: [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- Existing codebase reviewed directly: `chat_app/auth.py`, `chat_app/db.py`, `chat_app/schema.sql`, `chat_app/conversations.py`, `chat_app/config.py`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/types/index.ts`
