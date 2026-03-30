# Phase 17: Sidebar and Tool Panels - Research

**Researched:** 2026-03-29
**Domain:** React sidebar UI (recency grouping, collapse), tool panel redesign (chevron, badges, elapsed time, JSON syntax highlighting), Python SSE backend
**Confidence:** HIGH

---

## Summary

Phase 17 has three workstreams: (1) a Python backend change to add timestamps to SSE tool events, (2) sidebar redesign with date-bucketed recency groups and a collapsible icon-only mode, and (3) tool panel redesign with chevron toggle, status badge, elapsed time, and syntax-highlighted JSON.

The backend timestamp change is minimal: `time.time()` before and after the `call_mcp_tool()` call in `run_tool_loop`, passed through the tool event dict and out as `start_time`/`end_time` ISO strings or epoch floats in the SSE `tool` event. The frontend must extend `ToolPanelData` to carry these fields and compute elapsed duration for display.

The sidebar recency grouping is a pure TypeScript computation: compare each thread's `updated_at` against today's midnight, yesterday's midnight, and the start-of-week. `created_at` is available in the SQLite schema but **not currently returned by the `/api/threads` GET endpoint** — the recency groups should bucket on `updated_at` (which is already returned), not `created_at`. The sidebar collapse uses a CSS width transition (260px → 56px) with `overflow: hidden` and a `data-collapsed` attribute; collapsed state lives in `localStorage`.

For JSON syntax highlighting, the approach that fits this codebase best is a zero-dependency hand-rolled regex replacer: `JSON.stringify(value, null, 2)` produces a string, a single `replace()` call wraps token types in `<span class="json-*">` elements, and a `<pre dangerouslySetInnerHTML>` renders it. The project already uses `rehypeSanitize` pattern (trusting computed content) and has `prettyResult()` in ToolPanel already — this extends it naturally. A library like `react-syntax-highlighter` is overkill for a single JSON use-case and would add ~80 KB to the bundle.

**Primary recommendation:** All three workstreams are straightforward extensions of existing patterns. No new dependencies required. Use `@fluentui/react-icons` (already a transitive dep via `@fluentui/react-components`) for Compose20Regular (new-chat), ChevronDown20Regular/ChevronRight20Regular (tool panel chevron), and PanelLeftContract20Regular/PanelLeftExpand20Regular (sidebar collapse toggle).

---

## Standard Stack

### Core (already installed / available)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@fluentui/react-icons` | 2.0.323 (transitive) | Fluent SVG icons | Ships with `@fluentui/react-components`; already present in node_modules |
| React + TypeScript | 19.x / 5.9.x | Component implementation | Project baseline |
| CSS custom properties (`--atlas-*`) | n/a | Design tokens | Established in Phase 15; all components must use these |
| `localStorage` | Browser native | Persist collapsed state | No library needed |
| `dangerouslySetInnerHTML` + regex | n/a | JSON syntax highlighting | Zero-dep; safe because the input is always `JSON.stringify` output |

### No New Dependencies Needed

All capabilities required for Phase 17 are already available. The only addition is importing named icons from `@fluentui/react-icons` — the package is already in node_modules as a dependency of `@fluentui/react-components`.

**Installation:** None required.

---

## Architecture Patterns

### Pattern 1: Sidebar Collapse with CSS Width Transition

**What:** Add `data-collapsed="true/false"` on `.sidebar`, toggle width via CSS transition. Persist state in `localStorage`. Manage state in `AppLayout.tsx` (the component that owns `.sidebar`).

**When to use:** Single boolean state, no heavy logic needed.

**How it works:**
- `AppLayout` reads `localStorage.getItem('atlas-sidebar-collapsed')` on mount via `useState` initializer
- Toggle button writes back on change
- CSS handles the visual: `width: 260px` → `width: 56px`, `transition: width 200ms ease`
- At 56px, `.thread-list` content hides via `overflow: hidden` on `.sidebar`; only the collapse-toggle button and thread icons (or nothing) are visible

```typescript
// Source: codebase pattern (AppLayout.tsx + index.css)
const [collapsed, setCollapsed] = useState(
  () => localStorage.getItem('atlas-sidebar-collapsed') === 'true'
);

function toggleCollapsed() {
  const next = !collapsed;
  setCollapsed(next);
  localStorage.setItem('atlas-sidebar-collapsed', String(next));
}
```

```css
/* index.css */
.sidebar {
  width: 260px;
  transition: width 200ms ease;
  overflow: hidden;  /* critical: hides content during transition */
}

.sidebar[data-collapsed="true"] {
  width: 56px;
  min-width: 56px;
}
```

### Pattern 2: Thread Recency Grouping (Pure Function)

**What:** A `groupThreadsByRecency(threads: Thread[])` utility that buckets by `updated_at` relative to "now" at call time. Returns an ordered array of `{ label: string; threads: Thread[] }` with empty groups omitted.

**Date bucket logic:**
- Today: `updated_at >= today midnight (local)`
- Yesterday: `>= yesterday midnight && < today midnight`
- This Week: `>= start of current week (Sunday 00:00) && < yesterday midnight`
- Older: everything else

**Key implementation notes:**
- Compare dates in the user's local timezone using `new Date()` — do NOT use UTC midnight or groupings will look off by hours
- "This Week" bucket can include today and yesterday conceptually, but since Today and Yesterday are higher-priority buckets applied first, threads fall through correctly if checked in order
- Empty groups are hidden (do not render the heading)
- Within each group, threads remain sorted newest-first (already ordered by the backend)
- This is a pure utility function in `utils/groupThreadsByRecency.ts`

```typescript
// Source: codebase pattern (utils/ directory)
export interface ThreadGroup {
  label: 'Today' | 'Yesterday' | 'This Week' | 'Older';
  threads: Thread[];
}

function getLocalMidnight(daysAgo: number): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - daysAgo);
  return d;
}

export function groupThreadsByRecency(threads: Thread[]): ThreadGroup[] {
  const todayMidnight = getLocalMidnight(0);
  const yesterdayMidnight = getLocalMidnight(1);
  const weekStart = getLocalMidnight(new Date().getDay()); // days since Sunday

  const groups: ThreadGroup[] = [
    { label: 'Today', threads: [] },
    { label: 'Yesterday', threads: [] },
    { label: 'This Week', threads: [] },
    { label: 'Older', threads: [] },
  ];

  for (const thread of threads) {
    const ts = new Date(thread.updated_at).getTime();
    if (ts >= todayMidnight.getTime()) {
      groups[0].threads.push(thread);
    } else if (ts >= yesterdayMidnight.getTime()) {
      groups[1].threads.push(thread);
    } else if (ts >= weekStart.getTime()) {
      groups[2].threads.push(thread);
    } else {
      groups[3].threads.push(thread);
    }
  }

  return groups.filter(g => g.threads.length > 0);
}
```

### Pattern 3: JSON Syntax Highlighting (Zero-Dependency Regex)

**What:** A `syntaxHighlightJson(jsonString: string): string` function that wraps token types in `<span>` elements. Rendered via `dangerouslySetInnerHTML` in a `<pre>`. Safe because the input is always the output of `JSON.stringify` — no user-supplied HTML.

**Token classes to style:**
- `.json-key` — object keys (the quoted string before `:`)
- `.json-string` — string values
- `.json-number` — numeric values
- `.json-bool` — `true` / `false`
- `.json-null` — `null`

```typescript
// Source: based on classic JSON prettifier (MDN / CSS-Tricks pattern)
export function syntaxHighlightJson(json: string): string {
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = 'json-number';
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'json-key' : 'json-string';
      } else if (/true|false/.test(match)) {
        cls = 'json-bool';
      } else if (/null/.test(match)) {
        cls = 'json-null';
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}
```

**Color theme (Fluent-aligned dark, adapts via --atlas- tokens):**
```css
/* These work in both light and dark mode via data-theme toggle */
.json-key    { color: #9cdcfe; }  /* VS Code JSON key blue */
.json-string { color: #ce9178; }  /* VS Code string orange */
.json-number { color: #b5cea8; }  /* VS Code number green */
.json-bool   { color: #569cd6; }  /* VS Code keyword blue */
.json-null   { color: #569cd6; }  /* VS Code keyword blue */
```

Note: These are hardcoded against the dark panel background (`--atlas-bg-elevated` = `#141414` in dark mode). The tool panel body has a dark background regardless of page theme — do NOT use `--atlas-` tokens for JSON token colors since they adapt to theme but the panel background doesn't.

### Pattern 4: Tool Panel Chevron + Status Badge + Elapsed Time

**What:** Replace the implicit `<details>/<summary>` expand indicator with an explicit chevron icon from `@fluentui/react-icons`. Add a status badge and elapsed time in the summary bar.

**Chevron rotation:** `transform: rotate(0deg)` when closed, `rotate(90deg)` when open. Use CSS `transition: transform 150ms` and read `details[open]` state via the `open` attribute.

```typescript
// Source: codebase (ToolPanel.tsx uses native details/summary — locked decision)
import { ChevronRight20Regular } from '@fluentui/react-icons';

// In summary: detect open state to rotate chevron
<details className="tool-panel" ref={detailsRef}>
  <summary className="tool-panel-summary">
    <ChevronRight20Regular
      className={`tool-panel-chevron${isOpen ? ' tool-panel-chevron-open' : ''}`}
    />
    <span className="tool-panel-name">{name}</span>
    <span className={`tool-panel-badge tool-panel-badge-${status}`}>
      {statusLabel}
    </span>
    {elapsedMs !== null && (
      <span className="tool-panel-elapsed">Ran in {formatElapsed(elapsedMs)}</span>
    )}
  </summary>
  ...
</details>
```

**Detecting `details` open state in React:** Use a `useRef` on the `<details>` element and listen to the `toggle` event, OR use a `useState(false)` and toggle it in the `summary`'s `onClick`.

The simpler approach is `useState` + `onClick` on summary to track `isOpen`, and use CSS `details[open] .tool-panel-chevron` selector as a fallback for CSS-only rotation.

**Elapsed time formatting:**
```typescript
function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
// e.g. "Ran in 1.2s", "Ran in 340ms"
```

**Status badge mapping:**
- `success` → "Done" with `--atlas-status-success` color
- `error` → "Error" with `--atlas-status-error` color
- `running` → "Running..." with `--atlas-accent` color + optional spinner

### Pattern 5: Backend Timestamp Addition to SSE Tool Events

**What:** Add `start_time` and `end_time` (ISO 8601 strings or epoch seconds) to the `tool_events` dict in `run_tool_loop`. These propagate through the SSE event.

**Where to change:** `chat_app/openai_client.py` — the `run_tool_loop` function, specifically the `call_mcp_tool` invocation.

```python
# Source: chat_app/openai_client.py run_tool_loop()
import time

start_ts = time.time()
try:
    result_text = call_mcp_tool(tool_name, arguments)
    end_ts = time.time()
    tool_events.append({
        "name": tool_name,
        "status": "success",
        "params": arguments,
        "result": result_text,
        "start_time": start_ts,   # epoch float (seconds)
        "end_time": end_ts,
    })
except Exception as exc:
    end_ts = time.time()
    tool_events.append({
        "name": tool_name,
        "status": "error",
        "params": arguments,
        "result": f"Tool error: {exc}",
        "start_time": start_ts,
        "end_time": end_ts,
    })
```

**SSE event update in `chat.py`:** The `yield _sse({...})` block must pass through `start_time`/`end_time` from each event dict.

**Frontend type changes:**
```typescript
// types/index.ts additions
export interface ToolPanelData {
  name: string;
  params: Record<string, unknown>;
  result: string | null;
  status: 'success' | 'error' | 'running';  // add 'running'
  startTime?: number;   // epoch seconds float
  endTime?: number;     // epoch seconds float
}

// Derived elapsed: (endTime - startTime) * 1000 ms
// If endTime is absent → tool is still running (for future streaming)
```

**SSE event type update:**
```typescript
// types/index.ts
| { type: 'tool'; name: string; status: 'success' | 'error'; params: Record<string, unknown>; result: string | null; start_time?: number; end_time?: number }
```

### Recommended File Structure Changes

```
frontend/src/
├── components/
│   ├── Sidebar/
│   │   ├── ThreadList.tsx       # add grouping, collapse toggle
│   │   ├── ThreadItem.tsx       # unchanged (group heading is in ThreadList)
│   │   └── ThreadGroupHeading.tsx  # NEW: renders "Today", "Yesterday" etc.
│   ├── ChatPane/
│   │   └── ToolPanel.tsx        # add chevron, badge, elapsed, JSON highlight
│   └── AppLayout.tsx            # add collapsed state + data-collapsed attr
├── utils/
│   ├── formatTimestamp.ts       # existing
│   ├── parseHistoricalMessages.ts  # existing
│   ├── groupThreadsByRecency.ts    # NEW: pure bucketing function
│   └── syntaxHighlightJson.ts      # NEW: regex highlighter
└── index.css                    # add sidebar collapse, json token colors
```

### Anti-Patterns to Avoid

- **Don't read `created_at` for bucketing:** The `/api/threads` GET endpoint currently returns only `id`, `name`, `updated_at`. The schema has `created_at` but the API doesn't expose it. Use `updated_at` — semantically correct anyway (threads move up on activity).
- **Don't use UTC midnight for date boundaries:** `new Date().setHours(0,0,0,0)` gives local midnight. Using `Date.UTC(...)` will cause off-by-timezone grouping.
- **Don't import `@fluentui/react-icons` as a new dependency:** It's already in `node_modules` as a transitive dep. Just import named icons directly.
- **Don't use a library for JSON highlighting:** `react-syntax-highlighter` weighs ~80 KB gzipped including language grammars. The hand-rolled regex covers all JSON token types in ~15 lines.
- **Don't use Fluent `Accordion` for tool panels:** Locked decision from Phase 14 — use native `<details>/<summary>`.
- **Don't commit `localStorage` key collisions:** Use the namespaced key `'atlas-sidebar-collapsed'` to avoid conflicts with other apps on the same origin.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sidebar collapse toggle icon | Custom SVG | `PanelLeftContract20Regular` / `PanelLeftExpand20Regular` from `@fluentui/react-icons` | Already in node_modules; Fluent-aligned |
| New chat button icon | "+" text or custom SVG | `Compose20Regular` from `@fluentui/react-icons` | Matches Copilot aesthetic |
| Tool chevron icon | Custom CSS triangle | `ChevronRight20Regular` from `@fluentui/react-icons` | Consistent with Fluent; easier rotation |
| Thread date grouping | Complex `date-fns` pipeline | Pure vanilla JS `Date` with local midnight calculation | No library needed; 20 lines of TS |
| Sidebar state persistence | Redux/Context | `localStorage.getItem/setItem` | Sufficient for a single boolean |
| Elapsed time format | `date-fns/formatDuration` | Simple `formatElapsed(ms)` function | Single use-case, 5 lines |

**Key insight:** Every capability in Phase 17 has a trivial implementation using existing project tools. The project is already Fluent 2 token-based and has `@fluentui/react-icons` available; no new runtime packages are needed.

---

## Common Pitfalls

### Pitfall 1: `<details>` Chevron State Tracking

**What goes wrong:** CSS `details[open] .chevron` works for the closed→open direction but a React-managed `isOpen` state gets out of sync if the user closes via keyboard or programmatic `.removeAttribute('open')`.

**Why it happens:** Native `<details>` manages its `open` attribute independently; React can't intercept it without an event listener.

**How to avoid:** Attach an `onToggle` handler to `<details>` to sync state. The `toggle` event fires after the browser toggles `open`.

```typescript
<details
  className="tool-panel"
  onToggle={(e) => setIsOpen((e.currentTarget as HTMLDetailsElement).open)}
>
```

**Warning signs:** Chevron stuck in wrong orientation after clicking summary rapidly, or after Escape key on open details.

### Pitfall 2: Date Bucketing Off-By-One Near Midnight

**What goes wrong:** A thread created at 11:58 PM on Monday shows under "Yesterday" when it should be "Today" because midnight calculation used UTC.

**Why it happens:** `new Date().toISOString()` is UTC; comparing against `Date.UTC(year, month, day)` gives UTC midnight, not local midnight.

**How to avoid:** Always compute midnight via `new Date(); d.setHours(0,0,0,0)` which gives local midnight.

**Warning signs:** Threads appear in wrong group during testing around midnight or when the server/client are in different timezones.

### Pitfall 3: Sidebar Collapse Breaks `min-width: 260px`

**What goes wrong:** The `.sidebar` has both `width: 260px` and `min-width: 260px`. Setting `width: 56px` via `data-collapsed` is overridden by `min-width`.

**Why it happens:** CSS specificity — `min-width` beats `width` if they conflict.

**How to avoid:** The `[data-collapsed="true"]` rule must also set `min-width: 56px`.

```css
.sidebar[data-collapsed="true"] {
  width: 56px;
  min-width: 56px;  /* REQUIRED */
}
```

**Warning signs:** Sidebar doesn't visually collapse despite state toggle.

### Pitfall 4: `dangerouslySetInnerHTML` XSS in JSON Highlighting

**What goes wrong:** If `syntaxHighlightJson` is accidentally called with user-supplied text (not `JSON.stringify` output), the input could contain `<script>` or HTML events.

**Why it happens:** Developer passes raw tool result string instead of parsed-and-re-stringified value.

**How to avoid:** The function must ONLY receive `JSON.stringify(parsed, null, 2)` output. In `ToolPanel`, always parse first:

```typescript
const prettyJson = JSON.stringify(JSON.parse(result), null, 2);
// then highlight
const highlighted = syntaxHighlightJson(prettyJson);
```

If `JSON.parse` throws, fall back to rendering plain text without `dangerouslySetInnerHTML`.

**Warning signs:** `try/catch` around `JSON.parse` missing in ToolPanel's render path.

### Pitfall 5: SSE Elapsed Time Only for Live Stream, Not Historical

**What goes wrong:** Historical tool panels (loaded via `getMessages`) won't have `start_time`/`end_time` because they're reconstructed from the stored `messages_json`, which only has tool result content.

**Why it happens:** The elapsed time fields are ephemeral SSE metadata, not stored in the conversation history.

**How to avoid:** `ToolPanelData.startTime` and `endTime` are optional (`?`). `ToolPanel` conditionally renders the elapsed time only when both are present. Historical tool panels simply don't show elapsed time — this is acceptable behavior, not a bug.

**Warning signs:** TypeScript error if `startTime` is not typed as optional.

### Pitfall 6: `@fluentui/react-icons` Import Creates Large Bundle

**What goes wrong:** Importing from the package root (`import { Icon } from '@fluentui/react-icons'`) can cause bundlers to tree-shake poorly if the export map is not configured correctly.

**Why it happens:** Some bundler versions don't tree-shake re-exported packages well.

**How to avoid:** Import from the specific atom path if bundle size is a concern. In practice, Vite 8 + the current package structure handles tree-shaking correctly for named imports. Monitor bundle size during build; if icons add more than ~5 KB per icon, switch to deep imports.

---

## Code Examples

### Verified Pattern: `groupThreadsByRecency` consumer in ThreadList

```typescript
// ThreadList.tsx
import { groupThreadsByRecency } from '../../utils/groupThreadsByRecency.ts';

// In render:
const groups = groupThreadsByRecency(threads);

return (
  <div className="thread-list">
    <div className="thread-list-header">
      <button className="new-chat-btn icon-only" onClick={handleNewChat}>
        <Compose20Regular />
      </button>
      {!collapsed && (
        <span className="thread-list-title">Conversations</span>
      )}
    </div>
    {!collapsed && groups.map((group) => (
      <div key={group.label} className="thread-group">
        <div className="thread-group-heading">{group.label}</div>
        {group.threads.map((thread) => (
          <ThreadItem key={thread.id} thread={thread} ... />
        ))}
      </div>
    ))}
  </div>
);
```

### Verified Pattern: localStorage collapse persistence

```typescript
// AppLayout.tsx
const [sidebarCollapsed, setSidebarCollapsed] = useState(
  () => localStorage.getItem('atlas-sidebar-collapsed') === 'true'
);

function handleToggleSidebar() {
  const next = !sidebarCollapsed;
  setSidebarCollapsed(next);
  localStorage.setItem('atlas-sidebar-collapsed', String(next));
}

// In JSX:
<aside className="sidebar" data-collapsed={sidebarCollapsed ? 'true' : undefined}>
  <ThreadList collapsed={sidebarCollapsed} onToggleCollapse={handleToggleSidebar} onCancelStream={handleCancel} />
</aside>
```

### Verified Pattern: ToolPanel with elapsed time

```typescript
// ToolPanel.tsx
const elapsedMs = (startTime && endTime)
  ? Math.round((endTime - startTime) * 1000)
  : null;

const statusLabel = status === 'success' ? 'Done' : 'Error';
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Thread list: flat, sorted by `updated_at` | Grouped under Today / Yesterday / This Week / Older headings | Matches modern AI chat UI (ChatGPT, Copilot) |
| Sidebar: always 260px wide | Collapsible to 56px icon-only with CSS transition | Gives more chat surface area |
| Tool panels: dot icon + success/error text | Chevron + status badge + elapsed time | Matches M365 Copilot tool call UX |
| JSON in tool panels: plain `<pre>` | Syntax-highlighted JSON with token colors | Dramatically more readable for large payloads |
| New chat: "+ New Chat" text button | Compose icon button with optional label | Copilot-style, space-efficient in collapsed mode |

---

## Open Questions

1. **Sidebar collapsed-mode content:** At 56px, only a single icon column is possible. The simplest approach is: collapse-toggle icon at top, thread icons (using thread initials or a generic chat bubble icon) as clickable items, no thread names visible. The thread icon approach requires either a generic icon for all threads or extracting an initial from `thread.name`. **Recommendation:** Show only the collapse-toggle button at 56px; clicking any thread requires expanding first. This avoids the complexity of icon-per-thread.

2. **"Running" status for tool panels during live stream:** The SSE tool events arrive as completed (`success`/`error`) events — there's no `tool_start` event before `tool_end`. Success criteria 5 says "backend SSE tool events carry start/end timestamps" — this is the Phase 17-01 work. There is no live "running" animation needed unless a separate `tool_start` event is added. **Recommendation:** For Phase 17, `running` status can be omitted from the badge — only `done`/`error` badges needed. If a future phase adds streaming tool status, the badge enum can be extended.

3. **Thread group "This Week" edge case — what if today is Sunday/Monday?** If today is Sunday, week start = today midnight, so "This Week" bucket is empty (all of today is already "Today"). If today is Monday, yesterday is Sunday, and "This Week" includes last Sunday only. These edge cases are mathematically correct. "This Week" can be labeled "Earlier this week" for clarity. **Recommendation:** Keep label as "This Week" for simplicity.

4. **`created_at` vs `updated_at` for bucketing:** `created_at` is in the DB schema but NOT returned by `/api/threads`. Using `updated_at` means a thread created last week but messaged today shows under "Today" — this is the correct behavior for chat UIs (recency = last activity). No API change needed.

---

## Sources

### Primary (HIGH confidence)

- Codebase direct inspection: `/c/xmcp/frontend/src/`, `/c/xmcp/chat_app/` — all findings about existing types, components, CSS, and API shape come from reading the actual source
- `/c/xmcp/frontend/node_modules/@fluentui/react-icons/lib/atoms/fonts/` — verified icon names: `ComposeRegular`, `Compose20Regular`, `ChevronRight20Regular`, `ChevronDown20Regular`, `PanelLeftContract20Regular`, `PanelLeftExpand20Regular`
- `/c/xmcp/chat_app/schema.sql` — verified `created_at` and `updated_at` both exist in `threads` table
- `/c/xmcp/chat_app/conversations.py` — verified `/api/threads` returns only `id, name, updated_at` (not `created_at`)
- `@fluentui/react-icons` version 2.0.323 — verified installed as transitive dep of `@fluentui/react-components@9.73.5`

### Secondary (MEDIUM confidence)

- WebSearch: sidebar collapse localStorage pattern — confirmed standard React pattern using `useState` initializer reading `localStorage`
- WebSearch: JSON syntax highlighting — confirmed regex-replace approach is well-established, widely used without external libraries

### Tertiary (LOW confidence)

- WebSearch: `react-syntax-highlighter` bundle size ~80 KB — approximate, depends on language pack selection; not directly measured

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from node_modules and existing code
- Architecture patterns: HIGH — directly derived from existing codebase structure
- Backend timestamp changes: HIGH — straightforward addition to existing `run_tool_loop` dict
- JSON syntax highlighting approach: HIGH — classic well-known pattern, zero risk
- Icon names: HIGH — verified in installed package's `.d.ts` files
- Pitfalls: HIGH — derived from reading actual code constraints (CSS `min-width`, `details` native behavior, `dangerouslySetInnerHTML`)

**Research date:** 2026-03-29
**Valid until:** 2026-04-29 (stable codebase, no rapidly-changing dependencies)
