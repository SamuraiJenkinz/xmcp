# Feature Landscape: v1.3 Access Control, Feedback, Search, Export, Animations

**Domain:** Enterprise AI chat tool — IT engineer audience, Exchange infrastructure context
**Researched:** 2026-04-01
**Milestone scope:** Five discrete feature additions to the existing Atlas v1.2 application

---

## Feature 1: Azure AD App Role Access Gating

### Table Stakes

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Graceful access denied page | Users who fail role check must not see a broken React shell or raw 401 JSON | Low | AuthContext, /api/me endpoint | Must explain the situation, not just show an error code |
| Contact instructions on denied page | Enterprise users need a path to request access — without it they file helpdesk tickets | Low | None | Link or email for IT admin contact |
| Role check at /api/me | Server-side role extraction from `roles` claim in MSAL id_token_claims; deny before any Exchange data is served | Low | auth.py, MSAL session | The roles claim is present when App Role assignment is configured in Entra ID |
| Session preserved on denied page | User should not be logged out — they are authenticated, just not authorized | Low | Flask session | 403 is not logout |
| Default deny | Any authenticated user without the Atlas.User role gets the access denied experience | Low | auth.py login_required decorator | This is the whole point of the feature |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Admin email as mailto: link | One click to request access — reduces friction to zero | Low | Config value or hardcoded contact | Better than "contact your administrator" with no target |
| Copy-to-clipboard of own UPN on denied page | Users requesting access need to tell the admin who they are; show the authenticated identity | Low | Session user claims | Avoids fumbling for own UPN |
| Role-aware branch in AuthGuard | Extend AuthGuard in App.tsx to detect 403 vs 401 and render AccessDenied component vs. login redirect | Low | AuthContext.tsx, App.tsx | Keeps the full React app mounted — Fluent 2 design applies consistently; better than a Jinja2 error page |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Group-membership-claim-based gating | Risks token overage with 80K+ users; group GUIDs in token are fragile | Use App Roles — already decided in PROJECT.md |
| Showing role name ("Atlas.User") in the UI | Exposes internal security model naming to end users | Show "you don't have access to Atlas" — no role jargon |
| Humor or apology-heavy copy | Enterprise tool — IT admins read errors professionally | Factual: "Your account does not have access. Contact [name/email] to request access." |
| Multiple role tiers in v1.3 | Adds admin vs. read-only complexity; all current operations are read-only anyway | Single Atlas.User role is sufficient; admin console is out of scope |
| Polling or auto-retry after access denied | Users do not suddenly gain roles mid-session | Static denied page with clear instructions is correct |

### Implementation Notes

- The `roles` claim is a list in `id_token_claims`. Check `"Atlas.User" in user.get("roles", [])` server-side.
- Existing `login_required` decorator in `auth.py` needs a companion role check — or extend `login_required` to include role verification after auth succeeds.
- Frontend: `AuthContext` currently tracks `user | null | loading`. Extend to include `accessDenied: boolean`, populated when `/api/me` returns 403. `AuthGuard` in `App.tsx` branches on this to render `<AccessDenied />` instead of redirecting to `/login`.
- The access denied component lives inside the React app (not a separate Jinja2 page) so the Fluent 2 design system applies.
- **Confidence: HIGH** — App Roles pattern is authoritative in Microsoft Learn; roles claim extraction is standard MSAL usage.

---

## Feature 2: Per-Message Thumbs Up / Down Feedback

### Table Stakes

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Thumbs up / thumbs down on each assistant message | Industry standard since ChatGPT and GitHub Copilot; Copilot Studio ships it by default; absence is conspicuous | Low | AssistantMessage.tsx | |
| Buttons visible on message hover | Not permanently visible — clutter increases with long threads; hover reveal matches ChatGPT and Copilot pattern | Low | `.message-hover-actions` zone already exists in AssistantMessage | CopyButton already uses this zone |
| Persist vote to SQLite | Without persistence the signal is useless | Low | db.py, schema.sql (new feedback table or column) | One vote per message per user; second click on same button = toggle off |
| Visual toggle state | Button must indicate selected state — filled vs. outline icon, or accent color | Low | Fluent UI ThumbLike / ThumbDislike icon variants | Use `ThumbLikeFilled` / `ThumbDislikeFilled` for selected states |
| Streaming messages excluded | Do not show feedback buttons while response is still streaming | Low | `isStreaming` prop already on AssistantMessage | Show only after `done` SSE event |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Optional freetext comment on thumbs-down | Thumbs-down without context is a weak signal; comment reveals why | Medium | Fluent UI Popover component | Optional, not required; submit immediately on thumbs-down, comment is secondary action |
| ARIA live region announcement | "Feedback submitted" spoken to screen readers after vote | Low | `aria-live` region in AssistantMessage | Complements WCAG AA already in place |
| Data schema designed for future admin analytics | Per-message feedback in SQLite is the foundation for a future admin view; schema decisions made now shape what is queryable later | Low | schema.sql design | Admin UI is out of scope for v1.3 |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Mandatory comment before thumbs-down submits | Friction eliminates most feedback; users close the dialog | Make comment optional; submit immediately on click |
| Stars or multi-level rating | Overkill for a read-only infrastructure tool; binary signal is sufficient | Binary thumbs only |
| Feedback on user messages | Users rate AI responses, not their own messages | Assistant messages only |
| Toast notification for each vote | Disruptive in a tool that may have long threads; repeated toasts are annoying | Inline state change (button fills in) is sufficient confirmation |

### Implementation Notes

- The `messages` table currently stores `messages_json TEXT` per thread — a JSON blob, not per-message rows. A new `feedback` table needs a message-level identifier. The simplest key is `(thread_id, message_index)` as a composite, where message_index is the 0-based position in the messages array.
- The hover-action zone already exists in `AssistantMessage.tsx` next to `CopyButton`. Add `ThumbLikeRegular` / `ThumbLikeFilled` and `ThumbDislikeRegular` / `ThumbDislikeFilled` from `@fluentui/react-icons`.
- API shape: `POST /api/threads/:id/feedback` with body `{ message_index: number, vote: "up" | "down" | null, comment?: string }`. `null` = retract.
- Optional comment: Fluent UI v9 `Popover` on thumbs-down, small `Textarea`, "Submit" and "Skip" buttons. Submitted via same endpoint with optional `comment` field.
- **Confidence: HIGH** — pattern is well-established; the main complexity is the message identity schema decision.

---

## Feature 3: Thread Search

The requirement names two search modes: sidebar title filter (client-side) and full-text message search (SQLite FTS5 backend). These are distinct UX patterns with different affordances and different implementation complexity.

### Table Stakes — Title Filter (Sidebar, Client-Side)

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Search input at top of sidebar thread list | ChatGPT, Copilot, Claude all place conversation search at the top of the sidebar | Low | ThreadList.tsx | Above the thread groups |
| Instant client-side filter as user types | No round-trip needed; thread names are already loaded in ThreadContext | Low | `groupThreadsByRecency` util | Filter before grouping, or filter within groups |
| Clear button inside the input | Standard for search inputs; users should be able to reset quickly | Low | Controlled input | Fluent UI `SearchBox` or custom input with clear affordance |
| Empty state when no matches | "No conversations match" — prevents silent empty list confusion | Low | ThreadList.tsx | Short copy |
| Filter does not affect active thread | The active thread can be visually hidden by filter but session state must not change | Low | ThreadContext | Filter is display-only |

### Table Stakes — Full-Text Message Search (Backend, SQLite FTS5)

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Search across message content, not just titles | Power users need to find "which thread did I ask about mailbox quotas?" | Medium | SQLite FTS5 virtual table on messages | Requires schema migration |
| Results show thread name + message snippet | Without context, a list of thread names is useless; snippet confirms relevance | Medium | Backend FTS5 `snippet()` function | FTS5 snippet() is built-in; returns marked-up context |
| Click result navigates to thread | Search is navigation — clicking a result should open that thread | Low | ThreadList handleSelectThread | Same flow as clicking a thread item |
| Debounced search input (300ms) | FTS5 is fast but debounce avoids per-keystroke round trips | Low | Frontend useEffect or custom hook | Standard practice |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Result count badge ("3 threads") | Tells the user whether to narrow or broaden the query | Low | Computed from results array length | |
| Highlight matched term in snippet | Helps user confirm relevance before clicking | Medium | FTS5 `highlight()` function; sanitize output before render | |
| Keyboard shortcut to open search (Ctrl+K) | ChatGPT uses Ctrl+K for history search; power users expect it | Low | keydown listener in ThreadList or App level | Atlas already has keyboard shortcut infrastructure |
| Search-as-toggle (icon reveals input) | Avoids permanently occupying sidebar real estate; matches ChatGPT's magnifying glass approach | Low | Toggle state in ThreadList | Relevant when sidebar is collapsed |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Search hitting the backend on every keystroke | Hammers SQLite with rapid FTS5 queries | Debounce 300ms minimum; 2-character minimum before triggering |
| Queries shorter than 2 characters | FTS5 prefix queries on 1-char terms match almost everything; meaningless results | Enforce minimum 2 chars |
| Fuzzy or semantic search | Requires embeddings or external search index; out of scope | Exact and prefix FTS5 match is the right v1 approach |
| Replacing the sidebar thread list with search results | Users need both simultaneously | Search results are an overlay or expansion of the sidebar, not a replacement |
| Showing full message content in results | Security and noise concern | 50-80 character snippet around match is the pattern |

### Implementation Notes

- Schema: create `messages_fts` FTS5 virtual table. Note that the existing `messages` table stores `messages_json TEXT` (a JSON blob per thread, not per-message rows). FTS5 will tokenize the raw JSON text. Consider whether to index the extracted text content or the raw JSON. Indexing extracted plain text is preferable but requires a trigger or a population script to extract text from the JSON during migration.
- In v1.3, the messages table has no per-message row to link a search hit to a scroll position within a thread. Navigating to the thread is sufficient for v1.3 — scroll-to-message can be v1.4.
- Two-phase search UI: (1) immediate client-side title filter while typing; (2) on-demand full-text search posted to `GET /api/search?q=<term>` when input exceeds 2 chars and 300ms has passed.
- **Confidence: HIGH for title filter** (pure client-side, no risk). **MEDIUM for FTS5 backend** — the messages_json blob schema complicates clean indexing; phase-specific research needed during implementation.

---

## Feature 4: Conversation Export

### Table Stakes

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Markdown export of current thread | IT engineers writing incident reports, runbooks, or Jira tickets want formatted output they can paste | Low | Messages in ChatContext | Render messages as `## User` / `## Assistant` with code blocks for tool results |
| JSON export of current thread | Power users and automation consumers want structured data | Low | Existing `GET /api/threads/:id/messages` endpoint | Server-side preferred for fidelity (includes system and tool messages not surfaced in frontend) |
| Single-thread export scope | Export the currently active thread | Low | activeThreadId from ThreadContext | Exporting all threads at once is a different use case not requested |
| Filename includes thread name and date | `atlas-exchange-dag-health-2026-04-01.md` is useful; `export.md` is not | Low | Thread name + Date.now() | Slugify thread name |
| Download via browser (client-side for Markdown) | Markdown can be assembled from loaded messages with no server round-trip | Low | Messages already in React state | Use `Blob` + `URL.createObjectURL` pattern |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Tool call data included in Markdown export | IT engineers want to see which Exchange tool was called and what it returned — often the key deliverable | Low | ToolPanelData already on DisplayMessage | Format as fenced code block labeled with tool name |
| Copy full thread to clipboard (no file) | Engineers working in Confluence or Jira often paste directly — faster than download-then-open | Low | navigator.clipboard API | Alongside download, not instead of it |
| Timestamp on each message in export | Report context — "the query was run at 14:32" matters for incident timelines | Low | `timestamp` already on DisplayMessage | Include per-message in Markdown output |
| Export button in ChatPane header | Discoverable — users should not hunt for export | Low | Header.tsx already exists | `ArrowDownloadRegular` icon with `Menu` for format selection |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| PDF export | Requires server-side renderer or heavy client library (html2canvas, jsPDF); fragile with Markdown formatting | Markdown is the right format; if PDF is needed, Markdown-to-PDF is a user-side step |
| Multi-thread batch export | The use case is "export this conversation for my ticket" — batch export is a different story | Single thread only |
| HTML export | Heavy, non-portable; engineers do not paste HTML into tickets | Markdown covers the use case |
| Export that strips tool panel data | Tool results are often the most valuable part of an Atlas response | Always include tool data |
| Server-side Markdown generation | Markdown assembly from messages is trivial client-side; server round-trip adds latency for no benefit | Client-side generation |

### Implementation Notes

- Markdown assembly: iterate `DisplayMessage[]` from ChatContext. Each message: `## User` or `## Assistant` heading, message body, timestamp line. For assistant messages, prepend tool panels as fenced JSON blocks with `json` language tag and a comment showing the tool name.
- JSON export: call `GET /api/threads/:id/messages` and trigger download of the response. This returns the raw messages_json which includes all message types (system, tool call, tool result) that the frontend does not display — better fidelity than serializing the DisplayMessage array.
- Export trigger: `ArrowDownloadRegular` icon in `Header.tsx`. Fluent UI v9 `Menu` with items "Download as Markdown" and "Download as JSON". Optionally a "Copy to clipboard" item. Only enabled when `messages.length > 0`.
- **Confidence: HIGH** — straightforward browser Blob download pattern; no novel technology.

---

## Feature 5: Motion Entrance Animations and Transitions

### Table Stakes

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| New assistant message entrance (fade-in + upward translate) | ChatGPT, Claude, and Copilot all animate new AI responses appearing; absence feels static and abrupt | Low | AssistantMessage.tsx | `opacity: 0→1`, `translateY: 8px→0`, 200ms ease-out |
| New user message entrance | User bubble appearing instantly while AI thinks feels inconsistent | Low | UserMessage.tsx | Same pattern, 150ms — slightly faster |
| `prefers-reduced-motion` respected everywhere | WCAG requirement; vestibular disorders affect a meaningful percentage of users | Low | CSS media query | Wrap all animation definitions in `@media (prefers-reduced-motion: no-preference)` |
| No additional animation during streaming | The blinking cursor already signals "working"; layering animation on top is distracting | Low | Existing `streaming-cursor` | The streaming cursor is sufficient |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Sidebar collapse/expand width transition | Adds a 200-250ms ease-in-out to the sidebar width toggle; matches Copilot sidebar behavior | Low | AppLayout.tsx / index.css | Pure CSS `transition: width` on the sidebar element |
| Tool panel expand/collapse easing | Currently uses `<details>` + `<summary>` which snaps open/closed; smooth height animation makes the UI feel polished | Medium | ToolPanel.tsx — `<details>` does not support CSS height transitions natively | Requires either a React-controlled expand state with `max-height` transition or accepting the snap behavior |
| Feedback button micro-interaction (scale on click) | Tactile feedback on thumbs-up/down — scale 1 → 1.15 → 1 over 100ms | Low | FeedbackButtons component (new in this milestone) | Affirms the user's action was registered |
| New thread item highlight | When the AI names a thread (`thread_named` SSE event), the sidebar item should briefly flash | Low | ThreadItem.tsx + CSS keyframe | Background flash accent → transparent over 600ms |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Typewriter / per-character text animation | Explicitly Out of Scope in PROJECT.md — artificial latency, frustrates fast readers | SSE streaming already gives real progressiveness; the cursor handles the working signal |
| Animate sidebar list reorder | Thread order changes when a thread is renamed (updated_at changes); animating list sort is complex and low value | Accept instant reorder |
| Smooth scroll-to-bottom animation | Message list should snap to bottom, not slide — users lose context if the view slides away | `scrollIntoView({ behavior: 'instant' })` |
| Loading skeleton animations for thread list | Thread list loads in ~50ms from SQLite; a skeleton would flash briefly and look broken | Existing loading state is sufficient |
| Heavy animation library (Framer Motion / GSAP) | Adds 30-80KB to bundle for effects achievable with CSS transitions | CSS transitions and `@keyframes` are sufficient; `@fluentui/react-motion` is available if JS-driven animation is needed without adding dependencies |
| Entrance animation on historical messages when thread loads | Animating 20 messages simultaneously when switching threads is disorienting and slow-looking | Only animate messages that arrive during the active session |

### Implementation Notes

- All entrance animations: CSS `@keyframes` or `transition` on `.assistant-message` and `.user-message`. Suggested token values to add: `--atlas-duration-fast: 150ms`, `--atlas-duration-normal: 200ms`, `--atlas-easing-decelerate: cubic-bezier(0, 0, 0.2, 1)`. These align with Fluent 2 motion principles (ease-out for entering elements).
- `prefers-reduced-motion` approach: all motion CSS wrapped in `@media (prefers-reduced-motion: no-preference) { ... }`. This is simpler than a React hook and requires zero JS. Elements outside that block render their final (non-animated) state immediately.
- Entrance animation on historical messages: use a CSS class like `.animate-entrance` added only to messages appended to the live chat, not to messages loaded from history. The message list can add this class only during active streaming sessions.
- Tool panel height transition: the native `<details>` + `<summary>` approach does not support CSS height transitions (height goes from 0 to `auto`). Options: (a) switch ToolPanel to React-controlled expand state with `max-height` transition — pragmatic, no new dependencies; (b) use `@fluentui/react-motion` Web Animations API; (c) accept the snap behavior and skip this animation. Option (a) is recommended. If descoped, the snap behavior is acceptable.
- **Confidence: HIGH for entrance animations and sidebar transition** (pure CSS). **MEDIUM for tool panel height animation** — requires ToolPanel to stop using native `<details>` toggle if smooth animation is required.

---

## Feature Dependency Map

```
App Role access gating
  Requires: /api/me backend role check, AuthContext extension, new AccessDenied component
  Independent of: all other v1.3 features

Thumbs up/down feedback
  Requires: new feedback table (schema decision), new POST /api/threads/:id/feedback route
  Soft-depends on: message identity model (schema work must precede implementation)
  Reuses: AssistantMessage hover-actions zone, Fluent UI icon set

Thread search — title filter
  Requires: only ThreadList.tsx change
  Independent of: all other v1.3 features

Thread search — full-text backend
  Requires: schema migration (FTS5 virtual table), new GET /api/search route
  Independent of: feedback, export, animations

Conversation export
  Requires: messages loaded in ChatContext (already true), Header.tsx export button
  JSON path reuses: existing GET /api/threads/:id/messages endpoint
  Independent of: all other v1.3 features

Motion animations
  CSS entrance animations: no new dependencies
  Sidebar transition: no new dependencies
  Tool panel height animation: requires ToolPanel.tsx refactor away from native <details>
  Feedback button micro-interaction: depends on feedback component being built first
```

---

## MVP Prioritization for v1.3

**Implement first (foundational / risk-bearing):**
1. App Role access gating — security feature; must be verified before other features are tested by users
2. Thread title filter — zero backend work; immediate value; no risk
3. Feedback thumbs up/down (vote only, no comment) — schema decision must be made early; optional comment can follow

**Implement second (medium complexity):**
4. Conversation export (Markdown client-side first, JSON second)
5. FTS5 full-text message search — after title filter ships and the messages_json indexing approach is designed

**Implement last (polish, no blockers):**
6. CSS entrance animations for messages and sidebar
7. Tool panel height animation (contingent on ToolPanel refactor decision)
8. Feedback button micro-interaction (after feedback component exists)

**Defer from v1.3 if scope tightens:**
- Optional comment on thumbs-down (adds Popover component and API field change)
- Keyboard shortcut for search (nice-to-have, search must exist first)
- Highlight matched search term in results (FTS5 highlight() adds markup-handling complexity)

---

## Sources

- [Microsoft Learn — Add App Roles and get them from a token](https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps) — HIGH confidence
- [Microsoft Learn — Collect thumbs up/down feedback in Copilot Studio (2025)](https://learn.microsoft.com/en-us/power-platform/release-plan/2025wave1/microsoft-copilot-studio/collect-thumbs-up-or-down-feedback-comments-agents) — HIGH confidence
- [OpenAI Help Center — How to search ChatGPT chat history](https://help.openai.com/en/articles/10056348-how-do-i-search-my-chat-history-in-chatgpt) — HIGH confidence
- [Fluent 2 Motion Design System](https://fluent2.microsoft.design/motion) — HIGH confidence
- [NN/G — Animation Duration and Motion Characteristics](https://www.nngroup.com/articles/animation-duration/) — HIGH confidence
- [Josh W. Comeau — Accessible Animations with prefers-reduced-motion](https://www.joshwcomeau.com/react/prefers-reduced-motion/) — HIGH confidence
- [Motion.dev — React Accessibility (prefers-reduced-motion)](https://motion.dev/docs/react-accessibility) — HIGH confidence
- [SQLite FTS5 Official Documentation](https://sqlite.org/fts5.html) — HIGH confidence
- [NN/G — Animation for Attention and Comprehension](https://www.nngroup.com/articles/animation-usability/) — HIGH confidence
- [LogRocket — Writing clear UX error messages](https://blog.logrocket.com/ux-design/writing-clear-error-messages-ux-guidelines-examples/) — MEDIUM confidence
