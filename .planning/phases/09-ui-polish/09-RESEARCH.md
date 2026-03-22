# Phase 9: UI Polish - Research

**Researched:** 2026-03-21
**Domain:** Vanilla JavaScript UI patterns — collapsible panels, clipboard API, CSS animations, dark mode, AbortController
**Confidence:** HIGH

## Summary

Phase 9 polishes the existing Flask + vanilla JS + CSS chat interface. No new libraries are needed. Every feature in scope — collapsible tool panels, clipboard copy, bouncing-dots loading indicator, Esc cancel, dark mode toggle — has a native browser solution that fits the project's zero-dependency JS pattern.

The codebase is plain ES5-style IIFE JavaScript with hand-written CSS. The existing `app.js` already implements Ctrl+Enter (line 484-493) and the streaming cursor. Phase 9 extends that foundation. The SSE event stream already emits `tool` events with `{type, name, status}` — the tool panel needs to attach raw Exchange JSON results, which requires a server-side change to add `result` to those events, or a separate `tool_result` event type.

**Primary recommendation:** Use native browser APIs throughout — `<details>`/`<summary>` for collapsible panels, `navigator.clipboard.writeText()` for copy, CSS keyframe animation for bouncing dots, `AbortController` to abort the fetch stream on Esc, and `data-theme` attribute + CSS custom properties + `localStorage` for dark mode. No new npm packages required.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Native HTML `<details>` | HTML5 (Baseline 2020) | Collapsible tool panel | Zero JS, accessible, keyboard-native, browser-managed ARIA |
| `navigator.clipboard.writeText()` | Baseline 2020 (HTTPS only) | Copy to clipboard | Modern async API, works in all current browsers, Promise-based |
| `AbortController` / `AbortSignal` | Baseline 2019 | Abort in-flight fetch/stream | Standard Web API, aborts fetch + ReadableStream pump in one call |
| CSS custom properties (`--var`) | Widely available | Dark mode color tokens | Enables runtime theme switching without JS per-element traversal |
| CSS `@keyframes` | Universally supported | Bouncing dots animation | Pure CSS, no timer management, GPU-accelerated |
| `window.matchMedia('(prefers-color-scheme: dark)')` | Baseline 2020 | OS preference detection | Synchronous read + event listener for live OS changes |
| `localStorage` | Universally supported | Dark mode preference persistence | Simple key-value store, survives page reload, no server round-trip |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| CSS `transition` on color properties | Universally supported | Smooth 200ms dark mode crossfade | Apply to `background-color`, `color`, `border-color` — NOT `transition: all` (see pitfalls) |
| `JSON.stringify(obj, null, 2)` | Built-in | Pretty-print Exchange JSON in tool panel | Use before inserting into `<pre>` element |
| Regex-based JSON span-wrapping | Vanilla JS | Syntax highlighting on JSON keys/values | Only if CSS-only approach is insufficient; apply after `JSON.stringify` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `<details>/<summary>` | Custom div+button+JS toggle | `<details>` is free — no event wiring, no aria-expanded management, keyboard handled by browser. Custom div only makes sense if animation on expand is required (details animating height is possible in modern CSS with `::details-content` but has limited support) |
| `navigator.clipboard` | `document.execCommand('copy')` | `execCommand` is deprecated. `navigator.clipboard` requires HTTPS (which the app already runs on via Waitress behind IIS/nginx) |
| CSS `data-theme` + custom properties | `prefers-color-scheme` media query only | Media query only has no user override. `data-theme` attribute allows user toggle that persists via `localStorage` |
| AbortController | `reader.cancel()` on ReadableStream | Both work but AbortController is the canonical pattern — also cancels the underlying network request (stops server from sending), `reader.cancel()` alone does not |

**Installation:** No new packages required.

## Architecture Patterns

### Recommended File Structure

No new files needed. All changes go into:
```
chat_app/
├── static/
│   ├── app.js          # All new JS: dark mode, copy, abort, dots indicator
│   └── style.css       # All new CSS: dark theme vars, tool panel, dots, hover copy button
├── templates/
│   ├── base.html       # Dark mode toggle button in header; data-theme init script in <head>
│   └── chat.html       # No structural changes needed (tool panels built by JS)
└── chat.py             # Add tool result data to SSE tool events
```

### Pattern 1: Dark Mode — data-theme + CSS Custom Properties

**What:** Define all color tokens as CSS custom properties on `:root` for light mode. Override them under `[data-theme="dark"]`. Toggle the attribute on `<html>` element.

**When to use:** Whenever the user clicks the toggle OR on page load (from localStorage or OS preference).

**Flash-of-wrong-theme prevention:** A tiny inline `<script>` in `<head>` (before any CSS renders) reads `localStorage` and sets `data-theme` on `<html>` synchronously. This prevents the white flash on page load for users who prefer dark mode.

```html
<!-- base.html <head> — MUST be before <link rel="stylesheet"> -->
<script>
(function() {
    var stored = localStorage.getItem('atlas-theme');
    if (stored) {
        document.documentElement.setAttribute('data-theme', stored);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
    // else: no attribute = light mode (default)
})();
</script>
```

```css
/* style.css */
:root {
    --color-bg: #f5f6fa;
    --color-surface: #ffffff;
    --color-border: #e2e4ea;
    --color-text: #1a1a2e;
    --color-text-muted: #6b7280;
    --color-accent: #2563eb;
    /* ... all tokens */
}

[data-theme="dark"] {
    --color-bg: #1a1a2e;
    --color-surface: #16213e;
    --color-border: #2d3a5e;
    --color-text: #e8eaf0;
    --color-text-muted: #9ca3af;
    --color-accent: #3b82f6;
    /* ... overrides */
}

/* Apply crossfade transition to body (avoids flashing the initial render) */
body {
    transition: background-color 0.2s ease, color 0.2s ease;
}
```

```javascript
// app.js — toggle function
function toggleDarkMode() {
    var html = document.documentElement;
    var current = html.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('atlas-theme', next);
    updateDarkModeIcon(next);
}
```

Source: [MDN prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme), [whitep4nth3r.com — best dark mode toggle](https://whitep4nth3r.com/blog/best-light-dark-mode-theme-toggle-javascript/)

### Pattern 2: Collapsible Tool Panel — native `<details>`/`<summary>`

**What:** For each tool call in an assistant message, render a `<details>` element containing the tool name, parameters, and raw Exchange JSON result. Default `open` attribute absent = collapsed.

**When to use:** Built by `addToolChip()` replacement function when a `tool` SSE event arrives. The raw Exchange JSON must come from the server (see server change below).

```javascript
// In createAssistantMessage(), replace/extend addToolChip:
addToolPanel: function(toolName, params, rawResult) {
    var details = document.createElement('details');
    details.className = 'tool-panel';

    var summary = document.createElement('summary');
    summary.className = 'tool-panel-summary';
    // spinner icon + tool name
    summary.innerHTML = '<span class="tool-panel-icon"></span>' +
        '<span class="tool-panel-name">Querying ' + toolName + '\u2026</span>';

    var body = document.createElement('div');
    body.className = 'tool-panel-body';

    // Parameters section
    if (params) {
        var paramPre = document.createElement('pre');
        paramPre.className = 'tool-panel-json';
        paramPre.textContent = JSON.stringify(params, null, 2);
        body.appendChild(paramPre);
    }

    // Result section (added when tool_result event arrives)
    var resultPre = document.createElement('pre');
    resultPre.className = 'tool-panel-json tool-panel-result';
    resultPre.textContent = 'Waiting for result\u2026';
    body.appendChild(resultPre);

    // Copy button for raw JSON
    var copyBtn = document.createElement('button');
    copyBtn.className = 'tool-panel-copy';
    copyBtn.textContent = 'Copy JSON';
    body.appendChild(copyBtn);

    details.appendChild(summary);
    details.appendChild(body);
    els.content.insertBefore(details, textNode);

    return { details: details, summary: summary, resultPre: resultPre, copyBtn: copyBtn };
}
```

Source: [MDN details element](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/details)

### Pattern 3: Server-Side — Emit Tool Result in SSE

**What:** The current `chat.py` emits `{type: "tool", name: ..., status: ...}` but does NOT include the raw Exchange JSON result. Phase 9 requires that data for the tool panel.

**Where to change:** `run_tool_loop()` in `openai_client.py` already has the tool result. The `tool_events` list currently stores `{name, status}`. Add `result` field.

```python
# In openai_client.py run_tool_loop():
tool_events.append({
    "name": tool_name,
    "status": "success",      # or "error"
    "params": tool_args,      # The arguments dict sent to the tool
    "result": tool_result,    # The raw dict/list returned by call_mcp_tool()
})
```

```python
# In chat.py generate():
for event in tool_events:
    yield _sse({
        "type": "tool",
        "name": event["name"],
        "status": event["status"],
        "params": event.get("params", {}),
        "result": event.get("result"),  # may be None on error
    })
```

The JavaScript `processLine()` in `readSSEStream()` already handles `event.type === 'tool'` — extend that branch to pass `event.params` and `event.result` to `addToolPanel()`.

### Pattern 4: Copy to Clipboard — navigator.clipboard.writeText()

**What:** Async copy API. Requires HTTPS (already satisfied). Show brief visual confirmation — a tooltip or in-place text change on the button ("Copied!" → reverts after 1500ms).

**When to use:** Hover-visible copy button on assistant message content. Separate copy button on tool panel JSON.

```javascript
// Source: MDN Clipboard API
function copyToClipboard(text, btn) {
    if (!navigator.clipboard) {
        // Fallback for non-HTTPS or very old browser (should not happen in this app)
        console.warn('[Atlas] Clipboard API not available');
        return;
    }
    navigator.clipboard.writeText(text).then(function() {
        var original = btn.textContent;
        btn.textContent = 'Copied!';
        btn.classList.add('copy-success');
        setTimeout(function() {
            btn.textContent = original;
            btn.classList.remove('copy-success');
        }, 1500);
    }).catch(function(err) {
        console.error('[Atlas] Clipboard write failed:', err);
    });
}
```

Source: [MDN Clipboard.writeText()](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText)

### Pattern 5: Bouncing Dots — CSS Keyframe Animation

**What:** Three `<span>` elements with staggered `animation-delay`. Shown immediately when `doSend()` is called, before any SSE event arrives. Removed when first `tool` or `text` event is received.

```javascript
// In createAssistantMessage():
var dotsEl = document.createElement('div');
dotsEl.className = 'thinking-dots';
dotsEl.innerHTML = '<span></span><span></span><span></span>';
els.content.appendChild(dotsEl);

// Store reference for removal
var removeDots = function() {
    if (dotsEl.parentNode) {
        dotsEl.parentNode.removeChild(dotsEl);
    }
};
// Call removeDots() in processLine when type === 'tool' OR type === 'text'
```

```css
.thinking-dots {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 0;
}

.thinking-dots span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #9ca3af;
    animation: bounce-dot 1.2s ease-in-out infinite;
}

.thinking-dots span:nth-child(1) { animation-delay: 0s; }
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce-dot {
    0%, 60%, 100% { transform: translateY(0); }
    30%            { transform: translateY(-6px); }
}
```

### Pattern 6: Esc to Cancel — AbortController

**What:** Create an `AbortController` at the start of `doSend()`. Pass `signal` to `fetch()`. On Esc keydown (when streaming), call `controller.abort()`. The `pump()` promise rejects with `AbortError` — catch it and show "interrupted" state.

```javascript
var currentAbortController = null;

function doSend(text) {
    setStreaming(true);
    appendUserMessage(text);
    var assistantMsg = createAssistantMessage();

    currentAbortController = new AbortController();
    var signal = currentAbortController.signal;

    fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: currentThreadId }),
        signal: signal   // <-- attach abort signal
    })
    .then(function(response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        readSSEStream(response, assistantMsg, signal);
    })
    .catch(function(err) {
        if (err.name === 'AbortError') {
            assistantMsg.markInterrupted();
        } else {
            assistantMsg.markError(/* ... */);
        }
        setStreaming(false);
        currentAbortController = null;
    });
}

// In readSSEStream pump() catch:
pump().catch(function(err) {
    if (err.name === 'AbortError') {
        assistantMsg.markInterrupted();
    } else {
        assistantMsg.markError('Connection interrupted. Please try again.');
    }
    setStreaming(false);
});

// Esc handler (document-level):
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && isStreaming && currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
});
```

Source: [MDN AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)

### Pattern 7: Interrupted Message State

**What:** When Esc is pressed mid-stream, partial text already rendered stays visible. Add `markInterrupted()` to the assistant message object — adds a visual marker without erasing content.

```javascript
markInterrupted: function() {
    cursor.remove();
    var marker = document.createElement('span');
    marker.className = 'interrupted-marker';
    marker.textContent = ' [response cancelled]';
    els.content.appendChild(marker);
}
```

```css
.interrupted-marker {
    color: #9ca3af;
    font-size: 12px;
    font-style: italic;
    margin-left: 4px;
}
```

### Pattern 8: JSON Syntax Highlighting (CSS-only approach)

**What:** A small JavaScript function post-processes the `JSON.stringify()` output with regex, wrapping different token types in `<span>` elements. Applied to `<pre>` elements in tool panels.

**Recommended approach:** Single regex replace — simpler and sufficient for the read-only display use case.

```javascript
function highlightJson(jsonStr) {
    // Escape HTML first
    var escaped = jsonStr
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    return escaped.replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        function(match) {
            var cls = 'json-num';
            if (/^"/.test(match)) {
                cls = /:$/.test(match) ? 'json-key' : 'json-str';
            } else if (/true|false/.test(match)) {
                cls = 'json-bool';
            } else if (/null/.test(match)) {
                cls = 'json-null';
            }
            return '<span class="' + cls + '">' + match + '</span>';
        }
    );
}
```

```css
.tool-panel-json { background: #f8f9ff; font-family: Consolas, monospace; font-size: 12px; }
.json-key  { color: #2563eb; }
.json-str  { color: #16a34a; }
.json-num  { color: #ea580c; }
.json-bool { color: #7c3aed; }
.json-null { color: #9ca3af; }

[data-theme="dark"] .tool-panel-json { background: #0f1729; }
[data-theme="dark"] .json-key  { color: #60a5fa; }
[data-theme="dark"] .json-str  { color: #4ade80; }
[data-theme="dark"] .json-num  { color: #fb923c; }
[data-theme="dark"] .json-bool { color: #a78bfa; }
[data-theme="dark"] .json-null { color: #6b7280; }
```

Source: [pdfcup.com — JSON highlighting without library](https://www.pdfcup.com/2024/09/how-to-highlight-json-code-in-html.html)

### Anti-Patterns to Avoid

- **`transition: all 0.2s ease` on body for dark mode:** Animates every property including transforms and layout-affecting ones. Causes performance issues and animates things that should not animate. Use explicit property list: `background-color 0.2s, color 0.2s, border-color 0.2s`.
- **Setting `data-theme` in body's DOMContentLoaded:** Too late — causes flash of wrong theme. Must be in `<head>` inline `<script>` before CSS renders.
- **`open="false"` on `<details>`:** Does not work. The `open` attribute is boolean — its presence means open, its absence means closed. To close: `details.removeAttribute('open')`.
- **`reader.cancel()` for Esc cancel without AbortController:** `reader.cancel()` cancels the stream reading but does NOT abort the underlying HTTP request. The server continues generating and sending data. Use `AbortController` to terminate both the network connection and the stream.
- **Copy button always visible:** Context spec says copy appears on hover — use CSS `opacity: 0` + `.assistant-message:hover .copy-btn { opacity: 1 }`. Important: also show on keyboard focus for accessibility (`focus-within`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collapsible panel open/close + ARIA | Custom div + JS click handler + aria-expanded toggle | `<details>/<summary>` | Browser manages toggle state, keyboard (Enter/Space), and ARIA automatically |
| Clipboard copy | Custom textarea + `execCommand('copy')` | `navigator.clipboard.writeText()` | `execCommand` is deprecated; async API works in all modern browsers under HTTPS |
| SSE stream cancellation | Manual `reader.releaseLock()` + `reader.cancel()` chain | `AbortController` + signal passed to `fetch()` | AbortController terminates both network request and pump loop cleanly |
| OS dark preference detection | User-agent sniffing or server-side hint | `window.matchMedia('(prefers-color-scheme: dark)')` | Synchronous, event-listenable, accurate, no server round-trip |
| Syntax highlighting for JSON | Third-party library (highlight.js, Prism) | Regex span-wrapping function + CSS classes | Adds no dependency, tiny code, sufficient for read-only display |

**Key insight:** This phase is pure browser API work. The existing app deliberately avoids npm dependencies (plain JS IIFE). Every feature in scope has a native browser solution that is equally capable.

## Common Pitfalls

### Pitfall 1: Flash of Wrong Theme on Page Load

**What goes wrong:** JavaScript that sets `data-theme` runs during `DOMContentLoaded` or after JS bundle parses. The browser has already rendered the default (light) background. Users who prefer dark see a white flash.

**Why it happens:** The `<link rel="stylesheet">` parses and applies before any external JS runs. The DOM is painted in light mode before the toggle runs.

**How to avoid:** Place a tiny inline `<script>` in `<head>` **before** the `<link rel="stylesheet">`. It reads `localStorage` synchronously and sets `document.documentElement.setAttribute('data-theme', 'dark')` before CSS is applied.

**Warning signs:** Users report "white flash" before dark mode activates. Only reproducible on hard refresh or first visit.

### Pitfall 2: Tool Result Data Not Available at SSE Event Time

**What goes wrong:** The current SSE `tool` event fires when the tool starts (before result). The tool panel needs the result JSON — but `result` is only available after `run_tool_loop()` completes.

**Why it happens:** `chat.py` currently emits tool events during the loop (per the existing code pattern `for event in tool_events: yield _sse(...)` which runs AFTER the full tool loop). Actually — looking at the code: `run_tool_loop` is called, then `tool_events` is iterated to emit SSE. So the result IS available at emit time.

**How to avoid:** Confirm `tool_events` in `openai_client.py` captures the full result dict. Add `params` and `result` keys to each event dict in `run_tool_loop()`. The SSE emit in `chat.py` just needs to forward those additional fields.

**Warning signs:** Tool panel shows "Waiting for result..." permanently. Check that `event.result` is present in SSE JSON logged in browser DevTools Network tab.

### Pitfall 3: AbortError vs Stream End in pump()

**What goes wrong:** The `pump().catch()` handler treats `AbortError` the same as a network error — shows error message instead of "interrupted" state.

**Why it happens:** Both abort and genuine network failure reject the `reader.read()` promise. Without checking `err.name === 'AbortError'`, the handler cannot distinguish them.

**How to avoid:** Check `err.name === 'AbortError'` in catch handler. Call `assistantMsg.markInterrupted()` (keeps partial text) rather than `assistantMsg.markError()` (replaces text with error message).

**Warning signs:** Users who press Esc see their partial response replaced with an error message.

### Pitfall 4: Server-Side Stream Not Terminated After Client Abort

**What goes wrong:** Client presses Esc, fetch is aborted, but the Python generator in `chat.py` continues running — calling `run_tool_loop()`, making Exchange queries, and computing an answer that is immediately discarded.

**Why it happens:** Flask generators run in a thread. The Waitress WSGI server does not immediately surface client disconnect to the generator. The generator only discovers the disconnect when it tries to `yield` to a closed connection (raises `GeneratorExit`).

**Mitigation:** This is a known Flask SSE limitation (confirmed by Flask GitHub issue #2702). The generator will eventually receive `GeneratorExit` when it tries to write to the closed connection. For Phase 9, this is acceptable — the 2-4s tool execution window is short enough that wasted work is minimal. Do NOT attempt a custom `GeneratorExit` handler for Phase 9.

**Warning signs:** Server logs show tool calls being made after client disconnected. Acceptable in this context.

### Pitfall 5: CSS `transition: all` Animates Layout Properties

**What goes wrong:** Applying `transition: all 0.2s ease` to `body` causes box shadows, transforms, and layout properties to animate when dark mode toggles. Creates janky visual artifacts.

**How to avoid:** Enumerate only color-related properties: `transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease`. Apply this to `body`, `.app-header`, `.sidebar`, `.message-content`, `.tool-panel`, etc.

### Pitfall 6: Hover Copy Button Inaccessible to Keyboard Users

**What goes wrong:** Copy button is `opacity: 0` by default, visible only on mouse hover. Keyboard users tabbing through the chat cannot trigger it.

**How to avoid:** Also show on focus: `.assistant-message:hover .copy-btn, .assistant-message:focus-within .copy-btn { opacity: 1; }`. Ensure button has a meaningful `title` attribute.

### Pitfall 7: navigator.clipboard Unavailable Without HTTPS

**What goes wrong:** `navigator.clipboard` is `undefined` on HTTP connections. The app runs on Waitress (HTTP in dev), behind IIS/nginx in prod (HTTPS).

**How to avoid:** Guard with `if (!navigator.clipboard) { return; }` — silently skip, since HTTP is only a dev concern. Do NOT add `document.execCommand('copy')` fallback (deprecated).

### Pitfall 8: Multiple AbortControllers on Rapid Sends

**What goes wrong:** User sends message, aborts with Esc, sends again quickly. If the old abort controller reference is not cleared, the new fetch may reference a stale signal.

**How to avoid:** Set `currentAbortController = null` in the catch handler after abort. Create fresh `new AbortController()` at the start of each `doSend()` call. Never reuse controllers.

## Code Examples

Verified patterns from official sources and inspected codebase:

### Dark Mode Init Script (base.html `<head>`)

```html
<!-- Place BEFORE <link rel="stylesheet"> -->
<script>
(function() {
    'use strict';
    var stored = localStorage.getItem('atlas-theme');
    if (stored === 'dark' || stored === 'light') {
        document.documentElement.setAttribute('data-theme', stored);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
    // No attribute = light (CSS :root defaults apply)
})();
</script>
```

Source: [MDN prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme)

### Dark Mode Toggle Button (base.html header)

```html
<button class="theme-toggle" id="theme-toggle" type="button" title="Toggle dark mode" aria-label="Toggle dark mode">
    <span class="theme-toggle-icon">☀</span>
</button>
```

### AbortController Fetch Pattern (app.js doSend)

```javascript
// Source: MDN AbortController
var currentAbortController = null;

function doSend(text) {
    // Clean up any stale controller
    currentAbortController = new AbortController();

    fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: currentThreadId }),
        signal: currentAbortController.signal
    })
    .then(function(response) {
        readSSEStream(response, assistantMsg);
    })
    .catch(function(err) {
        if (err.name === 'AbortError') {
            assistantMsg.markInterrupted();
            setStreaming(false);
        } else {
            assistantMsg.markError(/*...*/);
            setStreaming(false);
        }
        currentAbortController = null;
    });
}
```

### Clipboard Copy Pattern (app.js)

```javascript
// Source: MDN Clipboard.writeText()
function copyText(text, btn) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(function() {
        var original = btn.textContent;
        btn.textContent = 'Copied!';
        btn.disabled = true;
        setTimeout(function() {
            btn.textContent = original;
            btn.disabled = false;
        }, 1500);
    }).catch(function(err) {
        console.error('[Atlas] Copy failed:', err);
    });
}
```

### Tool Panel SSE Event — Server Side (openai_client.py)

```python
# In run_tool_loop() where tool_events is built:
tool_events.append({
    "name": tool_call.function.name,
    "status": "success",
    "params": tool_args,          # dict of arguments sent to tool
    "result": result_data,        # raw dict/list from call_mcp_tool()
})
```

```python
# In chat.py generate():
for event in tool_events:
    yield _sse({
        "type": "tool",
        "name": event["name"],
        "status": event["status"],
        "params": event.get("params", {}),
        "result": event.get("result"),
    })
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `document.execCommand('copy')` | `navigator.clipboard.writeText()` | Chrome 66+, 2018; Baseline 2020 | Async, promise-based, more reliable; old method deprecated |
| `EventSource` for SSE | `fetch()` + `ReadableStream` | Project decision (07-01) | Required because POST body needed for chat stream; AbortController works natively with fetch |
| Media query only for dark mode | `data-theme` attr + localStorage + matchMedia | Established pattern circa 2020 | User override persists across sessions; avoids needing server-side preference storage |
| Custom JS accordion components | `<details>/<summary>` HTML element | HTML5, Baseline 2020 | Zero JS, accessible, keyboard-managed by browser |

**Deprecated/outdated:**
- `document.execCommand('copy')`: Deprecated in all major browsers. Do not use.
- `EventSource` native API: Cannot POST a body. Already avoided in this codebase (decision 07-01).
- `@media (prefers-color-scheme)` only (no toggle): Does not allow user override. Insufficient for Phase 9 requirements.

## Open Questions

1. **Tool result size in SSE events**
   - What we know: Exchange tool results can be large JSON objects (e.g., full DAG health, connector lists). These will be included in SSE event payloads.
   - What's unclear: Whether very large Exchange responses (e.g., 50KB+) cause issues with SSE buffering or browser memory in the tool panel `<pre>`.
   - Recommendation: Truncate `result` in SSE to a reasonable size (e.g., 32KB). Add a note in the tool panel if truncated. Alternatively, load the tool result lazily only when the `<details>` is expanded — but this requires a separate API endpoint and is over-engineered for Phase 9. Keep it simple: include full result in SSE, monitor in practice.

2. **Dark mode color values for all UI elements**
   - What we know: Decided palette is `#1a1a2e` backgrounds (which is the existing light-mode text color), `#2563eb` accent. Full dark palette for all surfaces (sidebar, messages, input, header, tool panels) needs to be designed.
   - What's unclear: Exact values for border colors, muted text, hover states, error states in dark mode.
   - Recommendation: This is marked as "Claude's discretion" in CONTEXT.md. Define a coherent dark palette in CSS custom properties. Suggested tokens: surface=`#16213e`, border=`#2d3a5e`, text=`#e8eaf0`, text-muted=`#9ca3af`. The existing `#2563eb` accent works but may benefit from slightly lighter `#3b82f6` in dark mode for contrast.

3. **Copy button hover on touch devices**
   - What we know: The copy button is hover-revealed. Touch devices have no hover.
   - What's unclear: Whether colleagues use mobile (probably not for an infrastructure tool).
   - Recommendation: This is a corporate internal tool. Mobile support is not a requirement. The hover pattern is acceptable. Touch users can still tab to the button.

## Sources

### Primary (HIGH confidence)
- [MDN Clipboard.writeText()](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText) — API signature, browser support, security context
- [MDN AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController) — abort() method, AbortError DOMException
- [MDN details element](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/details) — open attribute, toggle event, browser support
- [MDN prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme) — JavaScript matchMedia(), values, browser support
- Codebase inspection — `chat_app/static/app.js`, `chat_app/static/style.css`, `chat_app/chat.py`, `chat_app/templates/base.html`, `chat_app/templates/chat.html`

### Secondary (MEDIUM confidence)
- [whitep4nth3r.com — best dark mode toggle pattern](https://whitep4nth3r.com/blog/best-light-dark-mode-theme-toggle-javascript/) — localStorage + matchMedia cascade, verified against MDN
- [pdfcup.com — JSON highlighting without library](https://www.pdfcup.com/2024/09/how-to-highlight-json-code-in-html.html) — regex span-wrapping technique (confirmed functional via pattern inspection)
- Design Drastic typing indicator snippet — CSS keyframe bouncing dots pattern (confirmed by multiple CodePen implementations)

### Tertiary (LOW confidence)
- Flask GitHub issue #2702 — server-side stream not terminated on client disconnect (referenced via websearch; known limitation, not critical for Phase 9)
- WebSearch results for SSE + Flask + GeneratorExit — passive cleanup strategy confirmation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all APIs are MDN Baseline features with verified official docs
- Architecture: HIGH — patterns derived from existing codebase structure + MDN verified APIs
- Server-side change (tool result in SSE): HIGH — straightforward addition to existing `tool_events` dict
- Pitfalls: HIGH — flash-of-theme and AbortError are confirmed behaviors; Flask disconnect limitation is documented
- Dark mode color palette: MEDIUM — specific hex values are design choices, not technical research

**Research date:** 2026-03-21
**Valid until:** Stable (all features are Baseline browser APIs, not fast-moving)
