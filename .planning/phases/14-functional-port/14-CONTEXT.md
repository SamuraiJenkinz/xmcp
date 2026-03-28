# Phase 14: Functional Port - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Port all existing vanilla JS chat features into React 19 components with behavioral parity: SSE streaming, thread management (create/rename/delete/switch), message rendering (user/assistant/tool panels/profile cards/search results), input area (auto-resize, keyboard shortcuts), copy-to-clipboard, and dark mode toggle. Fix DEBT-01 (persist tool events to SQLite so historical messages show tool panels) and DEBT-02 (copy-to-clipboard on historical messages). No visual redesign — that's Phase 16+.

</domain>

<decisions>
## Implementation Decisions

### State management
- Use React Context + useReducer for shared state — no external store library (Zustand/Redux are overkill for this app's state surface)
- Shared state: `currentThreadId`, `isStreaming`, `user` session info, `threads` list, `messages` for active thread
- Each concern gets its own context to avoid unnecessary re-renders: `ThreadContext` (thread list + active thread), `ChatContext` (messages + streaming state), `AuthContext` (user session from /api/me)
- SSE events flow through a custom `useStreamingMessage` hook that dispatches to ChatContext

### Component tree
- Top-level: `App > FluentProvider > AuthGuard > AppLayout`
- AppLayout splits into: `Sidebar` and `ChatPane`
- Sidebar: `ThreadList > ThreadItem` (each with rename/delete inline)
- ChatPane: `Header`, `MessageList`, `InputArea`
- MessageList: `UserMessage`, `AssistantMessage` (handles streaming + finalized states)
- AssistantMessage children: `ToolPanel`, `ProfileCard`, `SearchResultCard`, `MarkdownRenderer`
- Shared: `CopyButton` (reusable across message content, tool panels, JSON blocks)

### SSE streaming hook
- Port existing fetch + ReadableStream + manual SSE parsing into `useStreamingMessage` hook
- AbortController stored in `useRef` (not useState) — per prior research decision in STATE.md
- Hook handles all 5 event types: `text`, `tool`, `thread_named`, `done`, `error`
- Streaming text appended to a ref and flushed to state on requestAnimationFrame to avoid per-character re-renders
- On abort: display "[response cancelled]" inline (match existing behavior)
- On `thread_named`: update thread name in ThreadContext without refetching

### Thread management
- Abort any in-flight stream when switching threads (call AbortController.abort())
- Fetch `/api/threads/<id>/messages` on thread switch, render from `messages_json`
- Historical tool panels rendered from the persisted `tool_calls` + `tool` role messages in `messages_json` (DEBT-01 enables this — tool events must be persisted by the backend fix in 14-02)
- Thread CRUD operations: POST /api/threads (create), PATCH (rename), DELETE (delete) — all existing REST endpoints, no backend changes needed
- New thread: create via API, set as active, clear message list
- Inline rename: controlled input (not contentEditable) for better React integration

### Message rendering
- User messages: plain text in a styled container, no markdown
- Assistant messages: render through `MarkdownRenderer` component
- Use `react-markdown` with `rehype-sanitize` (DOMPurify equivalent) instead of the existing custom regex parser — gives tables, links, images, nested lists for free
- Fenced code blocks: syntax highlighting deferred to Phase 16 (keep basic `<pre><code>` for now)
- Tool panels: collapsible via Fluent UI `Accordion` or native `<details>` — match existing expand/collapse UX
- Profile cards: dedicated component reading tool result JSON, photo from `/api/photo/<user_id>`
- Search result cards: list of mini-cards from `search_colleagues` tool results

### Input area
- Auto-resize textarea: useRef + useEffect recalculating height on input (max ~5 lines / 200px), same pattern as existing
- Submit on Enter (single line) or Ctrl+Enter (multi-line) — match existing behavior
- Shift+Enter inserts newline
- Escape cancels in-flight stream
- Send button disabled during streaming, text changes to "Stop" (prep for Phase 16 visual redesign)
- Reset textarea height on submit

### Copy-to-clipboard
- `CopyButton` component using `navigator.clipboard.writeText()`
- Shows "Copied!" feedback for 1.5s (match existing timing)
- Appears on: assistant message content, tool panel JSON, historical messages (DEBT-02 fix)
- For historical messages: extract text content from rendered markdown DOM or store raw text alongside

### Dark mode
- Read existing `atlas-theme` localStorage value for continuity with v1.1
- Toggle in Header component, persist to localStorage
- Apply via FluentProvider theme prop: `webDarkTheme` / `webLightTheme`
- CSS custom properties from existing style.css migrated as needed (full token migration is Phase 15)

### DEBT-01: Tool event persistence
- Backend change: persist tool_calls and tool role messages into `messages_json` during the streaming loop
- Currently only the final assistant text content is persisted; tool events are fire-and-forget
- After fix: historical thread loads show tool panels identical to live-streamed ones
- This is a backend-only change in `chat.py` — modify the message append logic before database write

### DEBT-02: Historical message copy
- Currently copy-to-clipboard only works on newly streamed messages (DOM element reference)
- Fix: `CopyButton` component works from rendered content, not streaming state
- Every `AssistantMessage` (historical or live) gets a CopyButton regardless of how it was loaded

### Claude's Discretion
- Exact React Context structure and reducer action names
- Whether to use Fluent UI Accordion vs native `<details>` for tool panels (whichever integrates better)
- Loading skeleton / spinner design during thread switch
- Error boundary placement and fallback UI
- Exact file organization within `frontend/src/` (components/, hooks/, api/, types/, etc.)
- Whether `react-markdown` needs additional rehype/remark plugins beyond sanitize

</decisions>

<specifics>
## Specific Ideas

- SSE parsing must handle partial buffer chunks correctly — port the existing `buffer.split('\n\n')` pattern; it's battle-tested
- The existing JSON syntax highlighter uses custom CSS classes (`json-key`, `json-str`, etc.) with Catppuccin colors — keep this approach for tool panel JSON rather than pulling in a heavy syntax highlighting library
- Thread rename should use a controlled `<input>` in React, not `contentEditable` — avoids React/DOM sync issues
- Photo placeholder SVG generation (initials + deterministic color) happens server-side at `/api/photo/<user_id>` — no frontend change needed
- The 5-iteration tool-calling loop limit and token pruning are all backend — no frontend awareness needed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-functional-port*
*Context gathered: 2026-03-27*
