# Research Summary — Atlas v1.3

**Project:** Atlas — Exchange Infrastructure Chat App (Marsh McLennan)
**Milestone:** v1.3 — App Role Access Control, Feedback, Search, Export, Animations
**Researched:** 2026-04-01
**Synthesized:** 2026-04-01
**Overall Confidence:** HIGH (four critical findings verified against official Microsoft Entra docs and SQLite FTS5 docs; one medium-confidence finding on motion library React 19 compat)

---

## Executive Summary

Atlas v1.3 adds five discrete features to a production system that has been running since v1.0: Azure AD App Role access gating, per-message thumbs up/down feedback, thread search, conversation export, and motion entrance animations. The milestone is bounded in scope — the backend stack (Python 3.11, Flask 3.x, Waitress, SQLite WAL, MSAL) and the frontend stack (React 19, Vite, TypeScript, Fluent UI v9, Tailwind v4) are unchanged. Only one new npm package is required (`motion` v12.38.0). No new Python packages are needed.

The highest-risk feature is App Role access control, and it must be completed first. The risk is not technical complexity — the implementation is a single decorator in `auth.py` that reads a claim already present in the session. The risk is operational: a wrong implementation either leaves 80,000 Marsh McLennan tenant users with unblocked access (under-enforcement) or immediately locks out all IT engineers who have an open browser session when the feature ships (session-flush failure). Both failure modes are fully preventable with the specific measures documented in PITFALLS.md. The remaining four features are independent of each other and can be built in parallel after access control is verified.

The key architectural decision for v1.3 is how to identify individual messages for the feedback feature. Messages are currently stored as a JSON blob (`messages_json TEXT`) per thread — there is no per-message primary key. STACK.md recommends keying the `feedback` table on `(thread_id, message_idx)` where `message_idx` is the 0-based position in the append-only array. ARCHITECTURE.md recommends the same `message_idx` approach for v1.3 but flags the PITFALLS.md warning that this key becomes fragile if message deletion is ever added. Research is aligned: `message_idx` is correct for v1.3 given the append-only constraint, and the decision is documented as a known limitation.

---

## Key Findings

### From STACK-v1.3.md

v1.3 requires zero new Python packages and one new npm package. Every backend feature is achievable with capabilities already in the running system. The stack findings are high-confidence, grounded in direct codebase inspection of `auth.py`, `schema.sql`, `conversations.py`, and `frontend/package.json`.

**New dependency:**
- `motion` v12.38.0 (import from `motion/react`) — animation library; was planned in v1.2 research but not installed; confirmed absent from `package.json` as of research date

**No new packages needed for:**
- App Role gating — `id_token_claims` in `session["user"]` already contains the `roles` claim; existing MSAL auth code flow is sufficient
- Feedback — SQLite schema addition + Flask endpoint; React `useState` for local optimistic state
- Thread search — client-side filter on the existing thread list for v1.3; FTS5 is built into Python's `sqlite3` stdlib if server-side search is later needed
- Export — browser `Blob` + `URL.createObjectURL`; no server round-trip needed for Markdown; server-side `Response` with `Content-Disposition` for JSON export

**SQLite schema additions (two new structures):**
1. `feedback` table — `(thread_id, message_idx, user_id, vote)` with `UNIQUE(thread_id, message_idx, user_id)` and `ON DELETE CASCADE`
2. `threads_fts` FTS5 virtual table (optional for v1.3 if client-side filter is sufficient; include triggers if FTS is in scope)

**Critical stack notes:**
- The Azure AD tenant authority (`Config.AZURE_AUTHORITY`) is already tenant-specific, which is required for the `roles` claim to appear. `common` and `consumers` endpoints do not emit `roles`.
- Do NOT decode the access token for roles. `roles` is in the **ID token** (`id_token_claims`), not the access token, for user sign-in flows.
- Do NOT use `framer-motion` as a separate package. It is a thin re-export of `motion` internals; installing both duplicates code.
- Use `LazyMotion` + `m` component + `domAnimation` feature pack to keep the motion bundle at ~19.6KB total (vs ~34KB for the full `motion` component).

### From FEATURES.md

**Must-have (table stakes) per feature:**

*App Role access control:*
- Default-deny: any authenticated user without `Atlas.User` role hits the access denied experience
- Graceful access-denied page inside the React app (not a Jinja2 error page) so Fluent UI design applies
- Contact instructions on denied page — enterprise users need a path to request access without filing a helpdesk ticket
- 403 from `/api/me` triggers `<AccessDenied />` render, not a loading spinner

*Feedback:*
- Thumbs up/down on assistant messages only, visible on hover (not permanently, to avoid clutter in long threads)
- Visual toggle state: `ThumbLikeFilled` / `ThumbDislikeFilled` for active state; regular variants for unvoted
- Persist to SQLite; one vote per user per message; second click on same button toggles off
- Do not show feedback buttons while message is streaming — only after `done` SSE event

*Thread search:*
- Search input at top of sidebar, instant client-side filter against thread names already loaded in memory
- Clear button; empty state when no matches; filter does not change the active thread
- Result count badge and keyboard shortcut (Ctrl+K) are differentiators, not blockers

*Conversation export:*
- Markdown export of active thread (IT engineers paste into Jira/incident reports)
- JSON export for structured data consumers
- Filename includes thread name and date
- Tool call data included in Markdown export — often the key deliverable for Exchange diagnostics

*Animations:*
- Assistant and user message entrance animations (fade + slide up, 150-200ms ease-out)
- `prefers-reduced-motion` respected everywhere — WCAG requirement, not optional
- No animation during streaming; streaming cursor is sufficient

**Defer from v1.3 if scope tightens:**
- Optional freetext comment on thumbs-down (adds Popover + API field change; useful but not table stakes)
- Keyboard shortcut for search (search must exist first)
- FTS5 full-text message search (server-side; client-side title filter ships first)
- Tool panel smooth height animation (requires ToolPanel refactor away from native `<details>`)
- PDF export (requires server-side renderer or heavy client library)

**Anti-features (explicitly do not build):**
- Group-membership claim gating (token overage risk at 80K users; use App Roles)
- Toast notifications for each feedback vote (disruptive in long threads; inline filled icon is sufficient)
- Typewriter text animation (explicitly Out of Scope in PROJECT.md; artificial latency)
- Loading skeleton for thread list (thread list loads in ~50ms; skeleton would flash)

### From ARCHITECTURE.md

v1.3 adds two new Flask Blueprints (`feedback.py`, `export.py`), extends `auth.py` with a `role_required` decorator, adds two SQLite schema structures, adds one new frontend component (`AccessDenied.tsx`), and modifies approximately nine existing files. The overall architecture — Flask blueprints, React 19 SPA contexts, SQLite WAL — is unchanged.

**Access control flow (new):**
```
GET /api/me
  → @role_required
    → session["user"]["roles"] contains "Atlas.User" → 200
    → roles missing "Atlas.User" → 403
    → no session → 401

React AuthGuard:
  → 200 → render app
  → 403 → render <AccessDenied />
  → 401 → redirect to /login
```

**Key architectural decisions resolved by research:**
- Export is server-side via `Response` with `Content-Disposition` for JSON (full fidelity, includes system/tool messages not in frontend state); Markdown is client-side via Blob/URL for simplicity — ARCHITECTURE.md recommends server-side for both formats for consistency, while STACK.md recommends client-side for Markdown. See "Conflicts and Agreements" section below.
- Search backend endpoint (`GET /api/threads/search`) uses FTS5 with `AND t.user_id = ?` ownership join — never returns raw FTS results without scoping to the requesting user.
- Feedback state is local `useState` in `AssistantMessage` — no global state library needed. Historical feedback loads lazily via a separate `GET /api/threads/<id>/feedback` endpoint to avoid blocking message display.

**New backend files:**
- `chat_app/feedback.py` — Blueprint: `POST /api/threads/<id>/messages/<idx>/feedback`, `DELETE` same path
- `chat_app/export.py` — Blueprint: `GET /api/threads/<id>/export?format=markdown|json`

**Modified backend files (key changes):**
- `chat_app/auth.py` — add `role_required` decorator, `REQUIRED_ROLE` constant
- `chat_app/app.py` — register blueprints; update `/api/me` to return 403 for role failure
- `chat_app/conversations.py` — add `GET /api/threads/search`; swap `@login_required` to `@role_required`
- `chat_app/chat.py` — swap `@login_required` to `@role_required` (critical; easy to miss)
- `chat_app/schema.sql` — feedback table, threads_fts virtual table, three sync triggers

**New frontend files:**
- `frontend/src/components/AccessDenied.tsx`
- `frontend/src/components/Sidebar/SearchInput.tsx`
- `frontend/src/api/feedback.ts`

**Modified frontend files (key changes):**
- `frontend/src/api/me.ts` — handle 403 distinctly from 401
- `frontend/src/contexts/AuthContext.tsx` — add `accessDenied: boolean` state
- `frontend/src/App.tsx` — extend AuthGuard for 403 → `<AccessDenied />`
- `frontend/src/components/ChatPane/AssistantMessage.tsx` — feedback buttons + motion animations
- `frontend/src/components/Sidebar/ThreadList.tsx` — search mode

### From PITFALLS.md

Full pitfall inventory: 6 CRITICAL, 8 HIGH, 10 MEDIUM severity issues across the five features. The five most dangerous are documented in "Critical Pitfalls" below.

---

## Conflicts and Agreements Between Research Files

### Resolved: Export mechanism (client-side vs. server-side)

STACK.md recommends client-side Blob/URL for Markdown export (no server round-trip, all data already in React state). ARCHITECTURE.md recommends server-side `Response` with `Content-Disposition` for both formats (consistency, full fidelity for JSON).

**Resolution:** Hybrid approach. JSON export is server-side — the server response includes system and tool messages not surfaced in the frontend state, producing higher-fidelity output. Markdown export is client-side — the data is already loaded, the transformation is trivial, and a server round-trip adds latency with no benefit. This is consistent with the FEATURES.md recommendation. PITFALLS.md flags that any export path must include the ownership check — apply to the server-side JSON endpoint.

### Agreement: `message_idx` as feedback key

All three files (STACK.md, ARCHITECTURE.md, PITFALLS.md) converge on using `(thread_id, message_idx)` as the feedback key. PITFALLS.md adds the caveat that this is fragile if message deletion is ever introduced. The agreed position: use `message_idx` for v1.3 with a code comment documenting the append-only assumption. Note: ARCHITECTURE.md uses `rating INTEGER CHECK(rating IN (1, -1))` while STACK.md uses `vote TEXT CHECK(vote IN ('up', 'down'))`. Use the `vote TEXT` schema — it is more human-readable in queries and consistent with the FEATURES.md API shape (`"up"` / `"down"` / `null`).

### Agreement: Client-side thread title filter for v1.3

STACK.md, FEATURES.md, and ARCHITECTURE.md all recommend client-side filtering of thread names for v1.3. FTS5 is documented and ready to add but is explicitly deferred unless the scope expands. This is the right call — client-side filter on <500 strings is imperceptible.

### Conflict: FTS5 tokenizer for thread names

STACK.md recommends `porter unicode61` tokenizer for thread name FTS5. PITFALLS.md explicitly warns against `porter` for Exchange technical terms (`DAGHealth`, `MailboxMoveRequest`, `Get-ExchangeCertificate`) — it over-stems and causes missed matches.

**Resolution:** Use `unicode61` tokenizer only (the FTS5 default). It provides case-insensitive matching without over-stemming technical compound terms. If substring matching within compound terms is required later (e.g., `health` matching `DAGHealth`), consider adding the `trigram` tokenizer at that point.

### Agreement: No `framer-motion` package

STACK.md explicitly states `framer-motion` is now a thin re-export of `motion` internals and must not be installed alongside `motion`. ARCHITECTURE.md notes this with medium confidence. PITFALLS.md confirms the risk. Install `motion` only.

### Resolved: `LazyMotion` usage

STACK.md strongly recommends `LazyMotion` + `domAnimation` from the start (bundle size discipline). ARCHITECTURE.md notes it as optional for an internal deployment. Given the enterprise context and standard engineering practice, use `LazyMotion` + `domAnimation` from the start as STACK.md recommends. Bundle discipline costs nothing to establish now.

---

## Architecture Approach

The v1.3 architecture is additive. The existing layered structure (Flask blueprints → SQLite WAL → React 19 contexts) does not change shape — it grows new nodes.

**Access control** inserts at the Flask middleware layer via a `role_required` decorator that wraps the existing `login_required` pattern. It reads `session["user"]["roles"]` — a claim that MSAL has been populating in every ID token since auth was first implemented; v1.3 simply starts reading it. The React side adds one new state field to `AuthContext` and one new render branch in `AuthGuard`.

**Feedback** adds one new SQLite table and one new Blueprint. The message-level identity problem (no per-message primary key) is solved by treating `message_idx` as a stable position key under the append-only constraint. Feedback state lives in local component state in `AssistantMessage.tsx`; no context changes needed. Historical feedback loads lazily via a separate endpoint.

**Search** at v1.3 scope is entirely client-side — a `useMemo` filter on the thread list already in memory. If FTS5 is in scope, it adds a virtual table, three sync triggers, and one new endpoint. The FTS5 design scopes all results to the requesting user via a JOIN on `threads.user_id`.

**Export** adds one new Blueprint with a single endpoint that branches on `?format=`. Ownership check is mandatory (thread IDs are auto-increment integers — enumerable by design). JSON export serves the raw `messages_json` with thread metadata. Markdown export filters out system/tool messages and renders a human-readable format.

**Animations** are purely additive — `motion.div` and `motion.button` wrappers replace plain HTML elements where animations apply. No structural component changes. `LazyMotion` wraps the app root. `MotionConfig reducedMotion="user"` is added alongside it to respect OS-level accessibility settings.

---

## Critical Pitfalls

### 1. Portal "Assignment Required" without code-level role check (CRITICAL)

Enabling "User Assignment Required" in Entra ID is not sufficient access control. This Entra ID setting can be changed by any Cloud Application Administrator — it is not defense in depth. If the Flask `@login_required` decorator is not extended to check `session["user"].get("roles", [])`, all 80K tenant users regain access the moment the portal setting is changed. The code-level check in `auth.py` is mandatory and must be implemented before the portal setting is enabled.

**Prevention:** Add `role_required` decorator to `auth.py`. Apply it to every protected route in `conversations.py`, `chat.py`, and `app.py`. Verify with a test that a session without the `Atlas.User` role receives 403.

### 2. Missing `role_required` on `/chat/stream` in `chat.py` (CRITICAL)

`chat.py` is a separate Blueprint from `conversations.py`. Role checking is not centralized — each Blueprint applies decorators independently. A developer who updates `conversations.py` and misses `chat.py` leaves the SSE streaming endpoint unprotected. An unauthorized user who knows the endpoint URL can call the AI directly.

**Prevention:** After adding `role_required`, grep for all `@login_required` usages and verify each has the role check. Consider combining both checks into a single `@require_app_role` decorator to eliminate the possibility of applying one without the other.

### 3. Existing sessions lack the `roles` claim on deployment day (CRITICAL)

Flask filesystem sessions (`/tmp/flask-sessions`) persist across deployments. Users who authenticated before App Role enforcement have `session["user"]` populated from their previous login — which does not contain a `roles` claim. When the deployment goes live, all IT engineers with an open browser session will immediately receive 403 errors on their next API call, even if they are in the authorized group.

**Prevention:** Include a session flush step in the deployment runbook: `rm -rf /tmp/flask-sessions/*`. Communicate the forced re-login to users before deployment. Make the 403 message actionable ("Please log in again to apply new access settings") rather than generic ("Access denied").

### 4. Export endpoint missing ownership check (CRITICAL)

Thread IDs are auto-incrementing integers starting from 1 — trivially enumerable. If the export endpoint queries `messages` by `thread_id` alone without the `AND user_id = ?` ownership check, any authenticated user can export any other user's conversation by incrementing the ID. Every other `conversations.py` query includes the ownership check; the export Blueprint, being new, may miss it.

**Prevention:** Follow the same ownership verification pattern as `get_messages()` in `conversations.py`: verify thread ownership with a `SELECT id FROM threads WHERE id = ? AND user_id = ?` query before accessing message content. Code review must verify this check before any export endpoint is merged. Add a test: attempt to export a thread owned by user A while authenticated as user B — expect 404.

### 5. `prefers-reduced-motion` not respected in animation implementation (HIGH)

WCAG 2.1 SC 2.3.3 requires that motion triggered by user interaction can be disabled. Enterprise Windows machines commonly have "Reduce animations" enabled in accessibility settings. Sidebar animations that fire on every thread switch are a significant accessibility failure for users with vestibular disorders.

**Prevention:** Wrap the app in `<MotionConfig reducedMotion="user">` in `App.tsx`. This single wrapper disables transform and layout animations for users with OS-level motion reduction enabled. Test by enabling "Reduce animations" in Windows Settings before reviewing any animation work. Do not ship animation code without this wrapper.

---

## Implications for Roadmap

Research across all four files converges on a clear phase ordering driven by two constraints: (1) access control is a security gate that must be verified before other features are user-tested, and (2) features 2-4 are independent of each other and can be built in parallel.

### Phase 1: App Role Access Control

**Rationale:** Security feature; gates all subsequent user-facing testing. If access control ships broken (over-permissive or over-restrictive), any user testing of feedback/search/export is compromised. It also touches the most files (auth.py, app.py, conversations.py, chat.py, AuthContext, App.tsx) — doing it first avoids merge conflicts with the other features.

**Delivers:** Users without `Atlas.User` assignment see the `<AccessDenied />` screen. All 80K tenant users who are not IT engineers are blocked. IT engineers see no change.

**Implements:** `role_required` decorator in `auth.py`; 403 path in `/api/me`; `accessDenied` state in `AuthContext`; `<AccessDenied />` component; Azure AD App Role manifest configuration; session flush on deployment.

**Must avoid:** Pitfalls 1.1 (portal-only enforcement), 1.3 (existing sessions), 6.2 (missing decorator on `chat.py`).

**Research flags:** Standard pattern (Microsoft Entra docs are authoritative; no deeper research needed during planning). Azure AD manifest configuration is an admin task, not a code task — coordinate with the tenant admin.

### Phase 2a: Per-Message Feedback

**Rationale:** Schema decision (vote TEXT vs rating INTEGER; `message_idx` key) must be locked before building. Once locked, the feature is fully self-contained: one new table, one new Blueprint, local state in `AssistantMessage.tsx`. No dependencies on search or export.

**Delivers:** IT engineers can vote thumbs up/down on assistant messages. Votes persist to SQLite. Toggle-off by clicking the same button again. Feedback buttons absent during streaming.

**Implements:** `feedback` table in `schema.sql`; `feedback.py` Blueprint; `AssistantMessage.tsx` feedback buttons with Fluent UI icon variants; optimistic state with revert on error.

**Must avoid:** Pitfall 2.1 (fragile `message_idx` — document append-only assumption); Pitfall 2.2 (UNIQUE constraint and INSERT OR REPLACE for double-vote prevention); Pitfall 2.3 (hide buttons during streaming).

**Research flags:** Schema design decision (vote TEXT vs integer) is the only decision point needing confirmation before planning. Standard implementation pattern otherwise.

### Phase 2b: Thread Search (Client-Side)

**Rationale:** Client-side filter is independent of Phase 2a and can build in parallel. Zero backend changes. Immediate value. Establishes the search input component that FTS5 would extend if server-side search is added later.

**Delivers:** Users can filter the thread sidebar by typing in a search box. Instant results. Clear button. Empty state.

**Implements:** `SearchInput.tsx` component; `useMemo` filter in `ThreadList.tsx`; Fluent UI `SearchBox` or styled `<input type="search">`.

**Must avoid:** No critical pitfalls for this scope; pure frontend filter has no security or data integrity implications.

**Research flags:** No deeper research needed. Standard React filter pattern.

### Phase 2c: Conversation Export

**Rationale:** Also independent of feedback and search. One new Blueprint, one new endpoint. The ownership check pitfall makes this worth a dedicated phase rather than bundling with other backend work — reviewers should be focused on export-specific code.

**Delivers:** IT engineers can download the active thread as Markdown or JSON from the thread context menu.

**Implements:** `export.py` Blueprint; `GET /api/threads/<id>/export?format=` endpoint with ownership check; Markdown renderer that filters system/tool messages; JSON export with `Content-Disposition`; export trigger in `ThreadItem.tsx`.

**Must avoid:** Pitfall 4.1 (raw messages_json without transformation); Pitfall 4.2 (missing ownership check — CRITICAL); Pitfall 4.3 (HTML escaping if HTML export is ever added).

**Research flags:** No deeper research needed. Standard Flask Response pattern.

### Phase 3: Animations

**Rationale:** Purely additive — applies motion wrappers to components whose structure is settled after Phases 1-2. Building animations last avoids re-animating components whose structure is still changing. `MotionConfig reducedMotion="user"` must be added before any animation ships.

**Delivers:** Message entrance animations; sidebar collapse transition; feedback button micro-interaction; `AccessDenied` fade-in. Polished feel consistent with Copilot aesthetic established in v1.2.

**Implements:** `npm install motion`; `LazyMotion` + `domAnimation` in `App.tsx`; `MotionConfig reducedMotion="user"`; `m.div` wrappers in `AssistantMessage`, `UserMessage`, `ThreadItem`, `Sidebar`; `whileTap` on feedback buttons.

**Must avoid:** Pitfall 5.1 (prefers-reduced-motion — CRITICAL for WCAG); Pitfall 5.2 (layout prop on thread list — jank during streaming); Pitfall 5.3 (entry animation on streaming message component).

**Research flags:** `motion` + React 19 compatibility is MEDIUM confidence. Test the `npm install motion` and a basic `<m.div>` render against the existing app before committing to the full animation plan.

### Phase Ordering Rationale

- Phase 1 first: security gate; touches auth infrastructure that all other phases depend on
- Phases 2a, 2b, 2c in parallel: independent of each other after auth is locked; no shared files except `app.py` (blueprint registration), which can be merged last
- Phase 3 last: additive polish; component structure must be settled before applying motion wrappers; `MotionConfig` must be established before any animation PR is reviewed

### Research Flags

Phases needing deeper research during planning:
- **Phase 1 (Azure AD config):** Not code research — requires confirmation that the Entra admin has created the `Atlas.User` App Role and assigned the IT engineers group before code can be tested end-to-end. Block on this admin task.
- **Phase 2a (schema design):** Confirm vote field type (`TEXT` vs `INTEGER`) and whether optional comment field is in scope for v1.3 before writing the schema. Comment field changes the API shape.
- **Phase 3 (motion compat):** Spike `npm install motion` and a basic `<m.div animate>` in the dev environment before planning the full animation scope.

Phases with standard patterns (skip research):
- **Phase 2b (client-side search):** `useMemo` filter on a string array. No research needed.
- **Phase 2c (export):** Standard Flask `Response` with `Content-Disposition`. Blueprint ownership check pattern is already established in `conversations.py`.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| App Roles in ID token | HIGH | Official Microsoft Entra docs (2024-11-13, 2025-04-18) with explicit token payload examples |
| No MSAL config change needed | HIGH | Auth code flow with any scope emits ID token with roles once user is assigned; `User.Read` scope confirmed sufficient |
| `session["user"]["roles"]` access pattern | HIGH | Direct codebase inspection: `session["user"] = result.get("id_token_claims")` confirmed in `auth.py` |
| SQLite FTS5 in Python stdlib | HIGH | CPython standard library; built-in on all platforms; no compilation flags needed |
| FTS5 external content table + trigger pattern | HIGH | Official SQLite FTS5 docs; pattern stable since FTS5 stable release |
| FTS5 backfill required for existing data | HIGH | SQLite FTS5 docs explicit: content tables do not auto-populate on creation |
| Client-side Blob/URL export | HIGH | W3C-specified browser API; universally supported in modern browsers |
| Server-side Flask Response export | HIGH | Standard pattern; no new dependencies |
| `motion` v12.38.0 | HIGH | Verified against GitHub CHANGELOG (released 2026-03-16) |
| `LazyMotion + domAnimation` bundle ~19.6KB | HIGH | Verified against official motion.dev docs (March 2026) |
| `motion` + React 19 compatibility | MEDIUM | Library uses standard React APIs; no explicit React 19 compatibility statement found in docs |
| `feedback.message_idx` stability | MEDIUM | Holds under append-only constraint; fragile if message deletion is ever added |
| `@fluentui/react-motion` lacks AnimatePresence | MEDIUM | Inferred from package scope (Web Animations API utilities for Fluent components only); not directly verified |

**Overall confidence:** HIGH for all four security and data features. MEDIUM for animation library compatibility — mitigated by the recommendation to spike `motion` before committing to the full animation scope.

### Gaps to Address

- **`motion` React 19 compat spike:** Install `motion` and render a basic `<m.div animate>` before planning Phase 3 in detail. If incompatibility is found, the fallback is CSS `@keyframes` for entrance animations (documented in FEATURES.md as the zero-dependency alternative).
- **Optional comment on thumbs-down:** FEATURES.md lists this as a differentiator worth building; STACK.md does not include the API field for it. Decide during Phase 2a planning whether the `comment` field is in scope. If yes, the API shape changes to `{"vote": "up"|"down"|null, "comment"?: string}` and the schema adds a nullable `comment TEXT` column.
- **FTS5 in scope for v1.3?** Research consistently defers server-side FTS5 search to a future milestone, with client-side title filter shipping in v1.3. Confirm this scope decision before planning Phase 2b. If FTS5 is in scope, Phase 2b grows to include the schema migration, backfill command, and search endpoint.
- **Session flush coordination:** The session flush on deployment day (`rm -rf /tmp/flask-sessions/*`) requires coordination with the server admin (usdf11v1784.mercer.com). Include this in the deployment runbook, not just the code review.
- **Azure AD admin task timing:** The `Atlas.User` App Role must be created in the Entra admin center and the IT engineers group assigned before any end-to-end testing of Phase 1 is possible. This is a blocking dependency that is not in the developer's control.

---

## Sources

### Primary (HIGH confidence)
- [Microsoft Entra: Add app roles and get them from a token](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps) (updated 2024-11-13)
- [Microsoft Entra: Configure group claims and app roles in tokens](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles) (updated 2025-04-18)
- [Microsoft Entra app manifest reference](https://learn.microsoft.com/en-us/entra/identity-platform/reference-microsoft-graph-app-manifest)
- [SQLite FTS5 Extension — official documentation](https://sqlite.org/fts5.html)
- [Reduce bundle size — motion.dev](https://motion.dev/docs/react-reduce-bundle-size) (March 2026)
- [motion CHANGELOG — GitHub](https://github.com/motiondivision/motion/blob/main/CHANGELOG.md) (v12.38.0, 2026-03-16)
- [Fluent 2 Motion Design System](https://fluent2.microsoft.design/motion)
- Direct codebase inspection: `auth.py`, `schema.sql`, `conversations.py`, `chat.py`, `frontend/package.json`

### Secondary (MEDIUM confidence)
- [Motion for React quick start](https://motion.dev/docs/react-quick-start)
- [Motion — Accessibility / useReducedMotion](https://motion.dev/docs/react-accessibility)
- [SQLite FTS5 tokenizers — audrey.feldroy.com (2025)](https://audrey.feldroy.com/articles/2025-01-13-SQLite-FTS5-Tokenizers-unicode61-and-ascii)
- [Mickaël Derriey — consequences of user assignment required](https://mderriey.com/2019/04/19/aad-apps-user-assignment-required/)
- [Josh W. Comeau — Accessible Animations with prefers-reduced-motion](https://www.joshwcomeau.com/react/prefers-reduced-motion/)
- [NN/G — Animation Duration and Motion Characteristics](https://www.nngroup.com/articles/animation-duration/)

---

*Research completed: 2026-04-01*
*Replaces: SUMMARY.md for v1.2 (Atlas UI/UX Redesign)*
*Ready for roadmap: yes*
