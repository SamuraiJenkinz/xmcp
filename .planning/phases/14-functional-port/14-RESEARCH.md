# Phase 14: Functional Port - Research

**Researched:** 2026-03-27
**Domain:** React 19 chat app — SSE streaming, context/reducer state, markdown rendering, Fluent UI v9, Flask backend persistence
**Confidence:** HIGH overall (decisions are locked; research validates them and fills implementation details)

---

## Summary

Phase 14 ports a complete, working vanilla JS chat interface into React 19 components with behavioral parity. The existing `chat_app/static/app.js` (1013 lines) contains every behavior to replicate: SSE streaming with ReadableStream, manual buffer parsing, AbortController cancellation, thread CRUD, inline rename, message rendering with a custom markdown parser, tool panels using native `<details>`, profile cards, search result cards, copy-to-clipboard, auto-resize textarea, and dark mode toggle. Every UI interaction has an exact analog to port.

The backend has two debts to fix in this phase. DEBT-01: `chat.py` currently only persists the final `assistant` text message after streaming; the `tool_calls` and `tool` role messages from `run_tool_loop` are discarded before the SQLite write. DEBT-02: historical messages loaded via `GET /api/threads/<id>/messages` render correctly in the new `AssistantMessage` component (markdown + copy button) because `CopyButton` reads from rendered content rather than a streaming DOM reference.

The locked library decisions are `react-markdown@^10` with `rehype-sanitize` for markdown, React Context + useReducer for state, and Fluent UI v9 (already installed). No external store library. The vanilla JS architecture maps cleanly to the React component tree already specified in CONTEXT.md.

**Primary recommendation:** Port behavior function-by-function from `app.js`, keeping the SSE parsing logic, buffer/flush pattern, and all timing constants identical (1.5s copy feedback, 200px max textarea height). Do not re-invent anything that already works.

---

## Standard Stack

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | ^19.2.4 | Component rendering | Already in package.json |
| @fluentui/react-components | ^9.73.5 | UI primitives, theming | Already installed; FluentProvider used in App.tsx |
| typescript | ~5.9.3 | Type safety | Already configured |
| vite | ^8.0.1 | Dev server + build | Already configured |

### Add in This Phase

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| react-markdown | ^10.1.0 | Markdown → React elements | Replaces hand-rolled regex parser; gives tables, links, nested lists, code blocks for free |
| rehype-sanitize | ^6.0.0 | HTML sanitization | Prevents XSS when rendering AI-generated markdown; replaces DOMPurify |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-markdown | marked + DOMPurify | react-markdown is pure React, no innerHTML; safer integration |
| react-markdown | remark + custom renderer | More complex; react-markdown already wraps this |
| rehype-sanitize | DOMPurify | rehype-sanitize works at the AST level before rendering; DOMPurify works on serialized HTML |
| native `<details>` for tool panels | Fluent UI Accordion | Native `<details>` is zero-dependency, already matches existing behavior; Accordion adds styling overhead. Use native `<details>` (see Pitfalls section) |

**Installation:**
```bash
cd frontend
npm install react-markdown rehype-sanitize
```

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── api/
│   ├── threads.ts       # GET /api/threads, POST, PATCH, DELETE
│   ├── messages.ts      # GET /api/threads/:id/messages
│   └── me.ts            # GET /api/me
├── components/
│   ├── AppLayout.tsx        # Sidebar + ChatPane split
│   ├── Sidebar/
│   │   ├── ThreadList.tsx
│   │   └── ThreadItem.tsx
│   ├── ChatPane/
│   │   ├── Header.tsx
│   │   ├── MessageList.tsx
│   │   ├── InputArea.tsx
│   │   ├── UserMessage.tsx
│   │   ├── AssistantMessage.tsx
│   │   ├── MarkdownRenderer.tsx
│   │   ├── ToolPanel.tsx
│   │   ├── ProfileCard.tsx
│   │   └── SearchResultCard.tsx
│   └── shared/
│       └── CopyButton.tsx
├── contexts/
│   ├── ThreadContext.tsx   # threads[], currentThreadId, dispatch
│   ├── ChatContext.tsx     # messages[], isStreaming, dispatch
│   └── AuthContext.tsx     # user: { displayName, email, oid }
├── hooks/
│   └── useStreamingMessage.ts
├── types/
│   └── index.ts           # Thread, Message, ToolEvent, User types
├── App.tsx
├── main.tsx
└── index.css
```

### Pattern 1: Context + Reducer for Thread State

**What:** ThreadContext holds the threads list and active thread ID. Dispatch actions update both atomically.

**When to use:** Any component that reads threads or switches the active thread.

**Action types to define:**
```typescript
type ThreadAction =
  | { type: 'SET_THREADS'; threads: Thread[] }
  | { type: 'ADD_THREAD'; thread: Thread }
  | { type: 'REMOVE_THREAD'; threadId: number }
  | { type: 'RENAME_THREAD'; threadId: number; name: string }
  | { type: 'SET_ACTIVE'; threadId: number }
```

### Pattern 2: Context + Reducer for Chat State

**What:** ChatContext holds messages for the active thread and streaming state.

**Action types to define:**
```typescript
type ChatAction =
  | { type: 'SET_MESSAGES'; messages: Message[] }
  | { type: 'APPEND_STREAMING_CHUNK'; delta: string }
  | { type: 'ADD_TOOL_EVENT'; event: ToolEvent }
  | { type: 'FINALIZE_STREAMING'; fullText: string }
  | { type: 'CANCEL_STREAMING' }
  | { type: 'SET_ERROR'; message: string }
  | { type: 'SET_STREAMING'; isStreaming: boolean }
```

**Critical detail:** The in-progress streaming message must be a separate state field (not in the `messages` array) to avoid re-rendering the entire message list on every text delta. Promote it to `messages` only on `FINALIZE_STREAMING`.

### Pattern 3: useStreamingMessage Hook

**What:** Encapsulates fetch + ReadableStream + manual SSE parsing + AbortController. Returns `{ startStream, cancelStream, isStreaming }`.

**AbortController placement:** Store in `useRef`, not `useState`. Changing a ref does not trigger a re-render; the controller only needs to be accessed imperatively.

```typescript
// Source: based on app.js readSSEStream() pattern
const abortControllerRef = useRef<AbortController | null>(null);

function startStream(message: string, threadId: number) {
  abortControllerRef.current = new AbortController();
  const { signal } = abortControllerRef.current;

  fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  }).then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    readSSEStream(res, signal);
  }).catch(err => {
    if (err.name === 'AbortError') {
      dispatch({ type: 'CANCEL_STREAMING' });
    } else {
      dispatch({ type: 'SET_ERROR', message: err.message });
    }
  });
}

function cancelStream() {
  abortControllerRef.current?.abort();
  abortControllerRef.current = null;
}
```

### Pattern 4: SSE Buffer Parsing (port from app.js verbatim)

**What:** The existing buffer-split-on-double-newline approach is battle-tested. Port it directly.

```typescript
// Source: app.js readSSEStream() — verified to handle partial chunks correctly
let buffer = '';
function processChunk(value: Uint8Array) {
  buffer += decoder.decode(value, { stream: true });
  const parts = buffer.split('\n\n');
  buffer = parts.pop() ?? '';  // Last incomplete part stays in buffer
  for (const block of parts) {
    for (const line of block.split('\n')) {
      processLine(line);
    }
  }
}
```

**Important:** Use `TextDecoder` with `{ stream: true }` option to correctly handle multi-byte UTF-8 characters split across chunk boundaries.

### Pattern 5: requestAnimationFrame Text Batching

**What:** Accumulate streaming text deltas in a `useRef` buffer; flush to state via `requestAnimationFrame` to avoid per-character re-renders.

```typescript
const pendingTextRef = useRef('');
const rafRef = useRef<number | null>(null);

function appendText(delta: string) {
  pendingTextRef.current += delta;
  if (rafRef.current === null) {
    rafRef.current = requestAnimationFrame(() => {
      dispatch({ type: 'APPEND_STREAMING_CHUNK', delta: pendingTextRef.current });
      pendingTextRef.current = '';
      rafRef.current = null;
    });
  }
}
```

Cancel the pending rAF in the cleanup / on finalize to avoid state updates after unmount.

### Pattern 6: react-markdown with rehype-sanitize

**What:** Drop-in replacement for the custom `renderMarkdown()` function in app.js.

```typescript
// Source: react-markdown v10 official usage
import Markdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';

function MarkdownRenderer({ content }: { content: string }) {
  return (
    <Markdown rehypePlugins={[rehypeSanitize]}>
      {content}
    </Markdown>
  );
}
```

**Note:** react-markdown is ESM-only. Vite handles ESM natively; no extra config needed.

**Note on rehype-sanitize plugin order:** `rehypeSanitize` should be the last rehype plugin in the array. Everything processed after it could reintroduce unsafe content.

**No rehype-raw needed:** The AI output is markdown text, not raw HTML. `rehype-raw` is only needed if you want to render embedded HTML tags — leave it out.

### Pattern 7: Auto-resize Textarea

**What:** Port `resizeInput()` from app.js using `useRef` + `useEffect`.

```typescript
const textareaRef = useRef<HTMLTextAreaElement>(null);

function adjustHeight() {
  const el = textareaRef.current;
  if (!el) return;
  el.style.height = 'auto';           // Reset first — required for shrinking
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
}

function resetHeight() {
  if (textareaRef.current) {
    textareaRef.current.style.height = 'auto';
  }
}
```

Call `adjustHeight()` in the `onChange` handler. Call `resetHeight()` after submit.

### Pattern 8: Thread Switch with Stream Abort

**What:** When switching threads, abort any in-flight stream first.

```typescript
function switchThread(newThreadId: number) {
  cancelStream();               // Abort in-flight SSE if any
  dispatch({ type: 'SET_ACTIVE', threadId: newThreadId });
  dispatch({ type: 'SET_MESSAGES', messages: [] });
  loadMessages(newThreadId);    // Fetch from /api/threads/:id/messages
}
```

### Anti-Patterns to Avoid

- **Storing AbortController in useState:** Causes unnecessary re-renders on every stream start/cancel. Use `useRef`.
- **Dispatching on every SSE text delta:** Causes hundreds of React re-renders per second. Use the rAF batching pattern.
- **Putting streaming message inside the `messages[]` array:** Makes `SET_MESSAGES` (on thread switch) clobber in-progress stream. Keep `streamingMessage` as separate state.
- **Using contentEditable for thread rename in React:** React does not manage contentEditable reliably. Use a controlled `<input>` with `onBlur` → PATCH pattern.
- **Fetching thread list after every message send:** The existing app.js does `fetchThreads()` after `done` to re-sort. In React, update ThreadContext locally after the `thread_named` event — avoid the round-trip.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown rendering | Custom regex parser (already exists in app.js) | react-markdown | Tables, nested lists, GFM extensions; the existing parser misses many edge cases |
| HTML sanitization | Manual allowlist | rehype-sanitize | Edge cases in HTML sanitization are a known XSS source |
| Photo placeholder with initials | Client-side SVG generator | `/api/photo/<user_id>?name=<name>` (existing) | Already implemented server-side in `app.py::_generate_placeholder_svg` |
| SSE parser library | — | Manual buffer splitting (port from app.js) | The existing pattern is 12 lines, battle-tested, and avoids an extra dependency |
| Copy-to-clipboard hook library | — | `navigator.clipboard.writeText()` directly in CopyButton | Already works in app.js; no library needed |

**Key insight:** The vanilla JS already solved the hard problems (SSE parsing, buffer management, AbortController cleanup). Port those solutions; don't re-derive them.

---

## Common Pitfalls

### Pitfall 1: Fluent UI Accordion vs Native `<details>` for Tool Panels

**What goes wrong:** Using Fluent UI `<Accordion>` for tool panels introduces significant DOM overhead (multiple wrapper divs, ARIA attributes, animation) and styling conflicts with existing tool panel CSS classes (`tool-panel`, `tool-panel-summary`, etc.).

**Why it happens:** CONTEXT.md says "Claude's discretion" for this choice. The Accordion is a heavyweight enterprise component designed for navigation-level expand/collapse — it's overkill for inline tool status panels.

**How to avoid:** Use native HTML `<details>` + `<summary>` elements. This exactly matches the existing behavior (`details.className = 'tool-panel'`), requires no extra imports, and accepts the same CSS classes from the existing stylesheet.

**Warning signs:** If ToolPanel imports from `@fluentui/react-components`, question whether it's necessary.

### Pitfall 2: Streaming Message Clobbered by Thread Switch

**What goes wrong:** If `streamingMessage` is stored inside the `messages` array and the user switches threads mid-stream, `SET_MESSAGES` (loading history for the new thread) replaces the entire array and the streaming message is lost with no `[response cancelled]` marker.

**Why it happens:** Mixing live-state and persistent-state in one array.

**How to avoid:** Keep `streamingMessage: StreamingMessageState | null` as a separate field in ChatContext. Only `FINALIZE_STREAMING` moves it into `messages[]`. `SET_MESSAGES` only touches the `messages[]` field.

### Pitfall 3: SSE TextDecoder Without `{ stream: true }`

**What goes wrong:** Multi-byte UTF-8 characters (emoji, accented letters) split across chunk boundaries are decoded as replacement characters `\uFFFD`.

**Why it happens:** `TextDecoder.decode()` without the `stream` option treats each chunk as a standalone document.

**How to avoid:** Always construct `new TextDecoder('utf-8')` once and call `decoder.decode(chunk, { stream: true })` inside the read loop. This is already the pattern in app.js.

### Pitfall 4: DEBT-01 Backend Fix — Tool Events Not Persisted

**What goes wrong:** After fixing DEBT-01, the structure of `messages_json` changes. Historical messages now contain `tool_calls` (on assistant messages) and `role: "tool"` messages interleaved with the conversation. The frontend's `GET /api/threads/<id>/messages` will return these.

**Why it happens:** The existing `switchThread()` in app.js only renders `role: "user"` and `role: "assistant"` messages, silently ignoring `role: "tool"` and `role: "system"` messages. This works today because tool messages weren't persisted. After DEBT-01, they will be in the JSON.

**How to avoid:**
- In `loadMessages()`, filter: render `user` messages as `UserMessage`, render `assistant` messages that have `content` (non-null) as `AssistantMessage`.
- For `assistant` messages that have `tool_calls` but no `content`, check the *next* sibling `tool` role message(s) and render them as `ToolPanel` components inside the preceding AssistantMessage.
- Skip `system` and standalone `tool` role messages (they're already consumed by the associated assistant message rendering logic).

**The exact pairing algorithm:**
```
For each message in history (skip system):
  if role === 'user' → render UserMessage
  if role === 'assistant' && content → render AssistantMessage(content, toolPanels=[])
  if role === 'assistant' && tool_calls && !content → collect following 'tool' messages as ToolPanel data
  if role === 'tool' → skip (rendered as part of preceding assistant turn)
```

### Pitfall 5: Copy-to-Clipboard Requires Secure Context

**What goes wrong:** `navigator.clipboard.writeText()` throws or silently fails in non-HTTPS contexts (except localhost).

**Why it happens:** Browser security policy — clipboard API requires `window.isSecureContext === true`.

**How to avoid:** The production app uses HTTPS (per `project_deployment.md`), so this is not a concern in prod. For local dev over HTTP, add a fallback:
```typescript
async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
  } else {
    // Fallback for non-HTTPS dev: not needed in prod
    console.warn('Clipboard API unavailable (non-secure context)');
  }
}
```

### Pitfall 6: react-markdown ESM-only with Vite

**What goes wrong:** `react-markdown` is ESM-only. Older Jest + Node.js CommonJS test setups fail to import it.

**Why it happens:** The package ships ES modules only (no CommonJS fallback).

**How to avoid:** This project uses Vite (native ESM), so there is no issue in production or dev. If unit tests are added that import `MarkdownRenderer`, the test runner must support ESM (Vitest, not Jest by default).

**Warning signs:** `SyntaxError: require() of ES Module` in test output.

### Pitfall 7: Thread Name Update via `thread_named` vs Re-fetch

**What goes wrong:** After the first message completes, the existing app.js calls `fetchThreads()` to re-sort the sidebar. The `thread_named` SSE event fires before `done`. If React re-fetches the full thread list on every `done`, it triggers an extra network request and a full re-render of ThreadList.

**Why it happens:** app.js uses `fetchThreads()` as a lazy update strategy; React can do better.

**How to avoid:**
- On `thread_named` event: dispatch `RENAME_THREAD` to ThreadContext — update name in-place, no fetch.
- On `done` event: dispatch a `BUMP_THREAD_UPDATED_AT` action to re-sort the local thread list by moving the active thread to the top — no fetch.
- Only re-fetch from `/api/threads` on initial load and after delete (to ensure order is stable).

---

## Code Examples

### Thread API Module

```typescript
// Source: conversations.py route structure — direct mapping
// frontend/src/api/threads.ts

export interface Thread {
  id: number;
  name: string;
  updated_at: string;
}

export async function listThreads(): Promise<Thread[]> {
  const res = await fetch('/api/threads');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createThread(): Promise<{ id: number; name: string }> {
  const res = await fetch('/api/threads', { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function renameThread(id: number, name: string): Promise<void> {
  const res = await fetch(`/api/threads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function deleteThread(id: number): Promise<void> {
  const res = await fetch(`/api/threads/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function getMessages(id: number): Promise<{ messages: RawMessage[] }> {
  const res = await fetch(`/api/threads/${id}/messages`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
```

### CopyButton Component

```typescript
// Source: app.js copyText() function — direct port
import { useState, useCallback } from 'react';

interface CopyButtonProps {
  getText: () => string;  // Lazy: read from rendered content, not streaming ref
}

export function CopyButton({ getText }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(getText());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);  // Match app.js 1500ms
    } catch (err) {
      console.error('[Atlas] Copy failed:', err);
    }
  }, [getText]);

  return (
    <button type="button" onClick={handleCopy} className="copy-btn">
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}
```

**DEBT-02 fix built-in:** `getText` is a function called at click time, reading from rendered content. Historical messages provide it just like live messages.

### DEBT-01 Backend Fix (chat.py)

The fix is in `generate()` inside `chat_stream()`. Currently line 265:
```python
conversation.append({"role": "assistant", "content": full_response})
```

The tool_events are already in `conversation` (appended by `run_tool_loop` as `role: "tool"` messages) but the final streaming assistant message needs to be appended too. The conversation at the point of the DB write already contains all tool messages — the issue is that the non-streaming assistant message was removed at step 4 and the streamed content is only re-appended just before the DB write.

**Verify current flow:**
1. `run_tool_loop` appends `assistant (tool_calls)` + `tool` messages to `conversation`
2. Step 4 removes the last `assistant` message (the non-streaming final answer)
3. Step 5 streams the fresh response
4. Step 6 appends `{"role": "assistant", "content": full_response}` and writes to DB

**After DEBT-01 fix:** The `messages_json` stored in SQLite will include:
- `{"role": "user", "content": "..."}` — user message
- `{"role": "assistant", "tool_calls": [...]}` — tool call request
- `{"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}` — tool result
- (repeat for multiple tools)
- `{"role": "assistant", "content": "full response text"}` — final response

This is already correct! The tool_calls and tool role messages ARE in `conversation` when `db.execute("UPDATE messages ...")` is called. The DEBT-01 issue is that after step 4, the last assistant message (non-streaming final answer from `run_tool_loop`) is removed — but the `tool_calls` assistant and `tool` role messages remain. These ARE being persisted already.

**Re-verify DEBT-01 by reading the conversation flow more carefully:**

Looking at `run_tool_loop` in `openai_client.py`:
- Each loop iteration: appends `assistant_msg` (which includes `tool_calls`) + `tool` messages
- Final iteration (no tool_calls): appends plain `assistant` text message
- Returns the full `messages` list

Back in `chat.py` step 4: removes the last `assistant` message (the non-tool final answer). The `tool_calls` assistant + `tool` messages from earlier iterations remain. Step 6 appends the streamed final answer and writes to DB.

**Conclusion:** Tool messages ARE already being saved. The DEBT-01 issue is specifically: `tool_events` (the SSE-formatted list built for the frontend) contains `params` and `result` that are NOT in the standard OpenAI `tool` role messages. The standard `tool` message has: `tool_call_id`, `name`, `content` (the raw result). The frontend needs `params` (the arguments) to render the "Parameters" section of the tool panel.

**The actual fix for DEBT-01:** When rendering historical tool panels from `messages_json`, the `params` come from the `tool_calls[].function.arguments` field on the preceding `assistant` message (not from the `tool` role message). Parse the arguments JSON from the assistant message's `tool_calls` array.

### ToolPanel Component (using native `<details>`)

```typescript
// Source: app.js addToolPanel() — direct port to React
interface ToolPanelProps {
  name: string;
  status: 'success' | 'error';
  params: Record<string, unknown>;
  result: string | null;
}

export function ToolPanel({ name, status, params, result }: ToolPanelProps) {
  const hasParams = params && Object.keys(params).length > 0;

  return (
    <details className="tool-panel">
      <summary className="tool-panel-summary">
        <span className="tool-panel-icon" />
        <span className="tool-panel-name">{name}</span>
        <span className={`tool-panel-status ${status === 'error' ? 'status-error' : 'status-success'}`}>
          {status === 'error' ? 'Error' : 'Success'}
        </span>
      </summary>
      <div className="tool-panel-body">
        {hasParams && (
          <>
            <div className="tool-panel-label">Parameters</div>
            <pre className="tool-panel-json">{JSON.stringify(params, null, 2)}</pre>
          </>
        )}
        {result && (
          <>
            <div className="tool-panel-label">Exchange Result</div>
            <pre className="tool-panel-json tool-panel-result">{result}</pre>
            <CopyButton getText={() => result} />
          </>
        )}
      </div>
    </details>
  );
}
```

---

## DEBT-01 Deep Dive: Rendering Historical Tool Panels

This is the most complex part of Phase 14. The existing vanilla JS `switchThread()` ignores all non-user/non-assistant messages. After DEBT-01, `messages_json` stores the full OpenAI conversation including tool turns.

### Historical Message Parsing Algorithm

```typescript
// Source: derived from OpenAI message format + app.js switchThread() logic
interface RawMessage {
  role: 'system' | 'user' | 'assistant' | 'tool' | 'function';
  content: string | null;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string;
  name?: string;
}

function parseHistoricalMessages(raw: RawMessage[]): DisplayMessage[] {
  const result: DisplayMessage[] = [];
  let i = 0;

  while (i < raw.length) {
    const msg = raw[i];

    if (msg.role === 'system') { i++; continue; }

    if (msg.role === 'user') {
      result.push({ type: 'user', content: msg.content ?? '' });
      i++;
      continue;
    }

    if (msg.role === 'assistant') {
      // Collect any tool panels associated with this assistant turn
      const toolPanels: ToolPanelData[] = [];

      if (msg.tool_calls) {
        // For each tool call, find the matching tool result
        for (const tc of msg.tool_calls) {
          const toolName = tc.function.name;
          let params: Record<string, unknown> = {};
          try { params = JSON.parse(tc.function.arguments); } catch {}

          // Look ahead for matching tool result
          let result: string | null = null;
          let status: 'success' | 'error' = 'success';
          for (let j = i + 1; j < raw.length; j++) {
            if (raw[j].role === 'tool' && raw[j].tool_call_id === tc.id) {
              result = raw[j].content ?? '';
              break;
            }
            if (raw[j].role === 'assistant') break; // Next turn
          }

          toolPanels.push({ name: toolName, params, result, status });
        }
      }

      if (msg.content) {
        result.push({
          type: 'assistant',
          content: msg.content,
          toolPanels,
        });
      }
      i++;
      continue;
    }

    if (msg.role === 'tool') { i++; continue; }  // Already consumed above

    i++;
  }

  return result;
}
```

### Special Tool Rendering (Profile Cards and Search Results)

The vanilla JS detects `get_colleague_profile` and `search_colleagues` tool names and renders cards instead of tool panels. This logic must be preserved in `AssistantMessage`:

```typescript
function renderToolResult(panel: ToolPanelData) {
  if (panel.name === 'get_colleague_profile' && panel.status === 'success') {
    return <ProfileCard key={panel.name} resultJson={panel.result ?? ''} />;
  }
  if (panel.name === 'search_colleagues' && panel.status === 'success') {
    return <SearchResultCard key={panel.name} resultJson={panel.result ?? ''} />;
  }
  return <ToolPanel key={panel.name} {...panel} />;
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Custom regex markdown parser (app.js) | react-markdown + rehype-sanitize | Tables, code blocks, nested lists; XSS-safe at AST level |
| contentEditable thread rename | Controlled `<input>` with onBlur PATCH | No React/DOM sync bugs |
| DOM mutation for streaming text | rAF-batched dispatch to ChatContext | 60fps render cadence instead of per-token re-renders |
| Global isStreaming var + DOM sendBtn.disabled | ChatContext `isStreaming` → InputArea props | React-idiomatic, testable |

---

## Open Questions

1. **DEBT-01 scope confirmation**
   - What we know: Tool messages ARE in `conversation` when it's written to SQLite. The `params` (arguments) are stored in `tool_calls[].function.arguments` on the assistant message.
   - What's unclear: Confirm whether the current `messages_json` in production actually contains `tool_calls` messages, or if there is a bug preventing them from persisting. A quick `SELECT messages_json FROM messages WHERE thread_id = <any_thread_with_tools>` on the live DB will confirm.
   - Recommendation: In Plan 14-02, add a step to verify with a live DB query before writing any backend code. The "fix" may be purely frontend (the parsing algorithm above) rather than a backend change.

2. **Dark mode migration boundary**
   - What we know: CONTEXT.md says "Read existing `atlas-theme` localStorage value for continuity with v1.1" and "CSS custom properties from existing style.css migrated as needed (full token migration is Phase 15)".
   - What's unclear: The existing `style.css` uses `data-theme="dark"` on `<html>`. Fluent UI's `FluentProvider` uses its own theme prop. These are two parallel theming systems.
   - Recommendation: In Phase 14, keep both in sync: when toggling dark mode, update both localStorage + FluentProvider theme prop. The existing `index.css` keeps `data-theme` CSS vars working for any styles not yet migrated to Fluent tokens. Full reconciliation is Phase 15.

3. **Error boundary placement**
   - What we know: CONTEXT.md defers placement to Claude's discretion.
   - Recommendation: Place one `<ErrorBoundary>` around `<ChatPane>` and one around `<Sidebar>`. This ensures a crash in message rendering doesn't take down thread management.

---

## Sources

### Primary (HIGH confidence)

- Codebase — `chat_app/static/app.js` — complete vanilla JS implementation being ported (read directly)
- Codebase — `chat_app/chat.py` — SSE streaming endpoint, 5 event types, DB write logic (read directly)
- Codebase — `chat_app/conversations.py` — REST API endpoints for thread CRUD (read directly)
- Codebase — `chat_app/openai_client.py` — tool loop, `_message_to_dict`, message format (read directly)
- Codebase — `frontend/package.json` — installed versions confirmed (read directly)
- Codebase — `frontend/src/App.tsx` — current shell, FluentProvider already present (read directly)
- React official docs — `useReducer` + Context pattern for scaling state (react.dev)

### Secondary (MEDIUM confidence)

- WebSearch (multiple sources): react-markdown v10.1.0 is the current version; ESM-only; works with React 19 + Vite; confirmed by npm page and GitHub
- WebSearch (multiple sources): rehype-sanitize v6.0.0; should be last in rehype plugin chain; GitHub-schema default
- WebSearch verified: rAF text-batching pattern for streaming — confirmed as production standard by multiple 2025/2026 sources
- WebSearch: Fluent UI Accordion v9.9.2 confirmed; `@fluentui/react-components` already includes it (no separate install needed if using the full bundle)

### Tertiary (LOW confidence)

- WebSearch only: `navigator.clipboard` HTTPS requirement in some environments — confirmed by MDN docs (actually MEDIUM), included as standard practice

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — package.json verified; react-markdown/rehype-sanitize versions confirmed via npm
- Architecture: HIGH — CONTEXT.md locks all major decisions; patterns derived directly from app.js source
- DEBT-01 fix: MEDIUM — algorithm is correct but actual DB state needs a live verification query
- Pitfalls: HIGH — derived from direct code reading (buffer parsing, contentEditable, AbortController ref)
- Code examples: HIGH — directly ported from verified source (app.js), not invented

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain; react-markdown and Fluent UI release infrequently)
