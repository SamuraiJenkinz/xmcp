# Phase 16: Chat Experience Redesign - Research

**Researched:** 2026-03-29
**Domain:** React chat UI — CSS animations, bubble geometry, auto-resize textarea, glassmorphism input bar, relative timestamps, welcome state
**Confidence:** HIGH (codebase is read directly; no external library changes required)

---

## Summary

Phase 16 redesigns the visual and interactive layer of the chat pane. The existing codebase (Phase 14/15) has all the structural wiring in place: `UserMessage`, `AssistantMessage`, `InputArea`, `MessageList`, `CopyButton`, and the full streaming pipeline via `useStreamingMessage`. This phase is primarily a CSS restyle plus targeted component augmentation — no new libraries, no context restructuring.

The three sub-plans map cleanly to three independent work areas: (1) bubble geometry and entrance animation, (2) InputArea glassmorphism, stop button, welcome state, and (3) hover-revealed copy button and timestamp overlay. All changes are additive CSS plus small TSX prop extensions; the streaming hook and context reducer are untouched.

**Primary recommendation:** Do all work in `index.css` (`@layer components`) and the existing component files. Do not introduce framer-motion or any animation library — pure CSS `@keyframes` + `animation` on mount is sufficient and already used by the streaming cursor.

---

## Standard Stack

### Core (already installed — no new packages needed)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| React | 19.2.4 | Component model | Already present |
| @fluentui/react-components | 9.73.5 | FluentProvider, icons via SVG or Unicode | Already present |
| Tailwind CSS v4 | 4.2.2 | Utility classes if needed | Already present |
| CSS custom properties (--atlas-*) | — | Design tokens from Phase 15 | 62 tokens defined |

### No new runtime dependencies needed

All required capabilities exist natively:
- CSS `@keyframes` for entrance animation — no framer-motion
- `Intl.RelativeTimeFormat` for relative timestamps — no date-fns
- `backdrop-filter: blur()` for glassmorphism — no library
- `scrollHeight` height-clamping for textarea auto-resize — already implemented in current `InputArea.tsx`

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure CSS @keyframes | framer-motion / motion | framer-motion adds ~35KB; pure CSS is sufficient for one-shot mount animation |
| Intl.RelativeTimeFormat (native) | date-fns/dayjs | Extra ~8KB bundle; native API has 95%+ support and is sufficient |
| CSS backdrop-filter | Solid background | backdrop-filter is desktop-only target, 95%+ support in Chrome/Edge/Firefox 103+ |

---

## Architecture Patterns

### Existing File Structure (relevant to this phase)

```
frontend/src/
├── components/
│   ├── ChatPane/
│   │   ├── UserMessage.tsx          # MODIFY — bubble geometry + entrance anim
│   │   ├── AssistantMessage.tsx     # MODIFY — bubble geometry + entrance anim + streaming cursor color
│   │   ├── InputArea.tsx            # MODIFY — glassmorphism, stop button icon, placeholder, welcome state
│   │   ├── MessageList.tsx          # MODIFY — welcome state conditional rendering
│   │   └── ToolPanel.tsx            # MODIFY — running state spinning indicator (tool status visual)
│   └── shared/
│       └── CopyButton.tsx           # MODIFY — icon-only, position absolute, opacity 0 reveal on parent hover
├── types/index.ts                   # MODIFY — add timestamp to DisplayMessage
├── contexts/ChatContext.tsx         # MODIFY — ADD_USER_MESSAGE sets timestamp; FINALIZE_STREAMING sets timestamp
└── index.css                        # PRIMARY CHANGES — all new CSS classes in @layer components
```

### Pattern 1: CSS @keyframes Mount Animation (no-layout-thrash)

**What:** Define a `@keyframes` in CSS, apply `animation` property directly on the component's root element. Because the element is added to the DOM with `animation` already set, the browser runs the animation exactly once on mount — no state toggle needed.

**When to use:** Entrance animations where the element should animate in once and then be static. This is exactly the Phase 16 requirement.

**Key constraint:** Use only `opacity` and `transform` (translateY). These are compositor-layer properties and do not trigger layout recalculation. Never animate `height`, `width`, `margin`, or `padding` during entrance.

**Example:**
```css
/* Source: existing streaming-cursor blink pattern in index.css + MDN animation docs */
@keyframes message-enter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message {
  animation: message-enter 180ms ease-out both;
}
```

The `animation-fill-mode: both` (shorthand `both` at end) ensures the element starts at the `from` keyframe values even before the animation begins, preventing a flash of the un-animated state.

**React integration:** No `useEffect` needed. The animation fires because the element is newly inserted into the DOM when React renders it. The existing `MessageList.tsx` maps `messages[]` to components — each new component that mounts gets the animation automatically.

### Pattern 2: Asymmetric Border-Radius for Chat Bubbles

**What:** CSS `border-radius` accepts four values (top-left, top-right, bottom-right, bottom-left). Setting one corner to `4px` (or `0`) while others are `14px` creates the Copilot signature geometry.

**User bubble (right-aligned, brand blue):**
```css
/* Source: CSS border-radius MDN + Copilot visual analysis */
.user-message-bubble {
  border-radius: 14px 14px 4px 14px; /* sharp bottom-right */
  /* top-left | top-right | bottom-right | bottom-left */
}
```

**Assistant bubble (left-aligned, elevated surface):**
```css
.assistant-message-bubble {
  border-radius: 4px 14px 14px 14px; /* sharp top-left */
}
```

### Pattern 3: Glassmorphism Input Bar

**What:** `background-color` at partial opacity + `backdrop-filter: blur()` + `position: sticky` at the bottom of the chat column creates the floating-above-content effect.

**Critical constraint:** The element must have a `background-color` with alpha channel (not `background: none`) for `backdrop-filter` to have anything to blur behind it. Use rgba or a CSS variable with opacity modifier.

**Known issue:** `backdrop-filter` breaks if a parent has both `overflow` and `border-radius` set (Firefox bug). The existing `.chat-pane` has `overflow: hidden` — this must be removed or the input bar must be positioned outside the overflow-hidden ancestor.

**Example:**
```css
/* Source: MDN backdrop-filter + Josh W. Comeau backdrop-filter article */
.input-area-glass {
  position: sticky;
  bottom: 0;
  background-color: color-mix(in srgb, var(--atlas-bg-elevated) 80%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px); /* Safari */
  border-radius: 8px;
}

/* Fallback for browsers without backdrop-filter */
@supports not (backdrop-filter: blur(1px)) {
  .input-area-glass {
    background-color: var(--atlas-bg-elevated);
  }
}
```

**Note on Tailwind v4:** The project uses Tailwind with `prefix(tw)` — all Atlas styles are in `@layer components`, not Tailwind utilities. Stick to the same pattern. Do not use `tw-backdrop-blur` for this.

### Pattern 4: Auto-Resize Textarea (Already Implemented)

The existing `InputArea.tsx` already implements the correct pattern:
```ts
el.style.height = 'auto';
el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
```

The 200px cap (approximately 5 lines at 20px line-height) matches the requirement. What needs changing is the max-height CSS value in `.chat-input` (currently `max-height: 120px`) and the placeholder text. The disabled-during-streaming behavior needs `readOnly` added when `isStreaming` is true (currently only `disabled` is set, which changes visual styling more aggressively).

**Distinction:** `readOnly` during streaming preserves the textarea's visual state (color, opacity) while preventing input. `disabled` grays it out. Context says "disabled state" — use `disabled` but add CSS to not desaturate the entire input bar.

### Pattern 5: Relative Timestamps with Intl.RelativeTimeFormat

**What:** Native browser API, no install needed. Available in all modern browsers since 2020. 95%+ global support.

**Implementation:**
```ts
// Source: MDN Intl.RelativeTimeFormat + project requirements
function formatTimestamp(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);

  if (diffMs < 60_000) return 'just now';
  if (diffHours < 24) {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    if (diffMins < 60) return rtf.format(-diffMins, 'minute'); // "2 minutes ago"
    return rtf.format(-diffHours, 'hour');                     // "1 hour ago"
  }
  // Older than 24h — absolute format
  return date.toLocaleString('en', {
    month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit',
  }); // "Mar 29, 3:42 PM"
}
```

**DisplayMessage type extension needed:** Add `timestamp: string` (ISO string) to `DisplayMessage`. The context reducer's `ADD_USER_MESSAGE` and `FINALIZE_STREAMING` actions must stamp `new Date().toISOString()` when creating messages. Historical messages from `parseHistoricalMessages` will not have timestamps — the component renders nothing if `timestamp` is undefined.

### Pattern 6: Hover-Reveal Actions (Opacity Toggle)

The existing `.thread-actions` pattern in `index.css` already uses the correct CSS hover-reveal pattern:
```css
/* Existing pattern (thread list) — replicate for messages */
.thread-actions { opacity: 0; transition: opacity 150ms; }
.thread-item:hover .thread-actions { opacity: 1; }
```

Apply the same pattern to `.message-actions` within `.message`:
```css
.message-hover-actions {
  opacity: 0;
  transition: opacity 150ms;
  position: absolute;
  /* placement depends on user vs assistant */
}
.message:hover .message-hover-actions { opacity: 1; }
```

**Prerequisite:** The `.message` wrapper needs `position: relative` to anchor absolutely-positioned hover actions.

### Pattern 7: Welcome State (Conditional in MessageList)

**What:** When `messages.length === 0 && streamingMessage === null`, render a centered welcome layout instead of the message list. The welcome state disappears the moment `messages.length > 0`.

**Where:** Inside `MessageList.tsx` as a conditional branch. No new component file required (or one small `WelcomeState.tsx` extracted for cleanliness).

**Prompt chip behavior:** Each chip calls `onSend` (needs to be threaded down from `AppLayout` to `MessageList` to `WelcomeState`) or uses a shared callback pattern. The cleanest approach is to expose a `onChipClick: (text: string) => void` prop on `MessageList` that `AppLayout` provides — it calls the same `handleSend` already wired there.

**Chip auto-submit:** The chip click handler calls the same `handleSend(text)` function directly. It does NOT set textarea content first — it bypasses the textarea and sends directly. This is consistent with how "quick reply" chips work in chat UIs.

### Anti-Patterns to Avoid

- **Animating `height` or `top` during entrance:** Triggers layout. Use `transform: translateY()` only.
- **Using `disabled` on textarea during streaming for read-only effect:** `disabled` grays out and removes from tab order. Use `readOnly` for the input field during streaming, keeping the stop button enabled.
- **Applying backdrop-filter to an element inside overflow:hidden ancestor:** The blur will be clipped. Remove `overflow: hidden` from `.chat-pane` or restructure the input bar as a sibling to the scroll container.
- **Adding `timestamp` to `RawMessage` type:** Timestamps are only tracked at the display layer. The backend API returns OpenAI-format messages with no UI timestamps. Do not add `timestamp` to `RawMessage` — only to `DisplayMessage`.
- **Using CSS `transition` for entrance (instead of `animation`):** `transition` requires a state change from an initial value. Elements added to the DOM don't have a "previous state" to transition from. Use `animation` + `@keyframes` for mount-triggered effects.
- **Sending `isStreaming` prop down multiple levels:** The `isStreaming` state is already in `ChatContext`. Both `InputArea` and `AssistantMessage` can read it via `useChat()` instead of prop-drilling.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative time formatting | Custom "2 min ago" function | `Intl.RelativeTimeFormat` (native) | Handles pluralization, locale edge cases automatically |
| Textarea auto-resize | New hook | Extend existing `adjustHeight()` in InputArea.tsx | Already works; just update the max-height cap |
| Animation on mount | React state toggle class | CSS `@keyframes` + `animation` directly on element | Simpler, no re-render, no stale closure risk |
| Glassmorphism fallback | JS detection | CSS `@supports (backdrop-filter: blur(1px))` | Single-line, native, correct |
| Stop button icon | Unicode square | Inline SVG `<rect>` or Fluent icon | SVG scales correctly and matches Fluent design language |

**Key insight:** This phase is almost entirely CSS + small prop/type extensions. The React logic layer (context, hooks, streaming) is complete and must not be restructured.

---

## Common Pitfalls

### Pitfall 1: `animation-fill-mode` omitted — flash before animation

**What goes wrong:** Element is visible at full opacity for one frame before the `from` keyframe fires, causing a visible flash.
**Why it happens:** Without `animation-fill-mode: backwards` (or `both`), the element renders at its natural CSS values before the animation clock starts.
**How to avoid:** Always include `both` at the end of the `animation` shorthand: `animation: message-enter 180ms ease-out both`.
**Warning signs:** White flash on new message arrival when testing on a fast machine.

### Pitfall 2: `backdrop-filter` silently fails due to `overflow: hidden` ancestor

**What goes wrong:** Input bar renders but no blur effect appears.
**Why it happens:** The current `.chat-pane` uses `overflow: hidden`. The browser clips the stacking context needed for backdrop-filter.
**How to avoid:** The `.input-area` wrapper must be a direct child of the flex column and NOT inside the `.chat-messages` overflow container. Current structure has `InputArea` as a sibling to `MessageList` inside `chat-pane` — this is already correct. Verify `.chat-pane` does not have `overflow: hidden` set.
**Warning signs:** Glassmorphism works in Chrome but not Firefox. Or works only after removing border-radius from a parent.

### Pitfall 3: Textarea shrinks on backspace with scroll offset

**What goes wrong:** Deleting characters causes the textarea to shrink, but it "snaps" rather than smoothly reducing.
**Why it happens:** The `adjustHeight()` pattern requires setting `height: auto` first so `scrollHeight` recalculates correctly. If this reset is missing, `scrollHeight` accumulates and the textarea never shrinks.
**How to avoid:** Always set `el.style.height = 'auto'` before reading `el.scrollHeight`. Current code does this correctly — just preserve the pattern when modifying.
**Warning signs:** Textarea only grows, never shrinks when deleting text.

### Pitfall 4: Timestamp renders as "NaN minutes ago" for historical messages

**What goes wrong:** Historical messages loaded from `parseHistoricalMessages` have no `timestamp` field. If the component unconditionally calls `formatTimestamp(msg.timestamp)`, it crashes or renders garbage.
**Why it happens:** `DisplayMessage.timestamp` will be added as optional (`timestamp?: string`). Historical messages won't have it.
**How to avoid:** Guard with `{msg.timestamp && <TimestampOverlay ts={msg.timestamp} />}`. Historical messages simply show no timestamp — acceptable per the design.

### Pitfall 5: Prompt chip sends to wrong thread on first message

**What goes wrong:** Clicking a chip when no thread is active (welcome state is shown when `messages.length === 0`) triggers `handleSend` which calls `createThread()`. If the chip click doesn't await the thread creation before streaming starts, the stream is sent to `threadId: null`.
**Why it happens:** `handleSend` in `AppLayout.tsx` already handles this case — it creates the thread first if `activeThreadId === null`. The chip just needs to call the same `handleSend` that `InputArea` uses.
**How to avoid:** Pass `handleSend` down to `MessageList` (and then to `WelcomeState`) as an `onChipSend` prop. Do not create a separate send path for chips.
**Warning signs:** First chip-triggered message appears in a new empty thread rather than the created thread.

### Pitfall 6: Stop button "double-submit" race condition

**What goes wrong:** User clicks Stop, `cancelStream()` fires, `isStreaming` flips to false, `CANCEL_STREAMING` is dispatched, but the button momentarily shows "Send" before the re-render settles — user can click again and send an empty message.
**Why it happens:** The `isStreaming` state in `useStreamingMessage` and the `isStreaming` in `ChatContext` are separate values. There's a one-render gap.
**How to avoid:** The `isButtonDisabled` guard in `InputArea` already checks `message.trim() === ''` for the send path. An empty textarea means the send button does nothing even if clicked. Ensure this guard is preserved.

---

## Code Examples

### Message Entrance Animation (verified against existing pattern)

```css
/* Source: extends existing @keyframes blink in index.css — same structure */
@keyframes message-enter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message {
  /* existing properties preserved */
  position: relative;               /* anchors hover-action overlays */
  animation: message-enter 180ms ease-out both;
}

@media (prefers-reduced-motion: reduce) {
  .message { animation: none; }
}
```

### User Message Bubble

```css
/* Source: CONTEXT.md decisions + CSS border-radius MDN */
.user-message {
  align-self: flex-end;
  max-width: 75%;
  background-color: var(--atlas-accent);
  color: var(--atlas-accent-text);
  padding: 10px 14px;
  border-radius: 14px 14px 4px 14px; /* sharp bottom-right — Copilot signature */
  font-size: var(--atlas-text-body);
  line-height: var(--atlas-lh-body);
  word-break: break-word;
}
```

### Assistant Message Bubble

```css
/* Source: CONTEXT.md decisions — tonal shift not border */
.assistant-message {
  align-self: flex-start;
  max-width: 75%;
  background-color: var(--atlas-bg-elevated);
  color: var(--atlas-text-primary);
  padding: 10px 14px;
  border-radius: 4px 14px 14px 14px; /* sharp top-left */
  /* no border — elevation provides containment per Stitch No-Line principle */
}
```

### Streaming Cursor (update existing to use --atlas-accent)

```css
/* Current: uses --atlas-text-primary. Update to --atlas-accent per CONTEXT.md */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background-color: var(--atlas-accent); /* was --atlas-text-primary */
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}
```

### Glassmorphism Input Bar

```css
/* Source: CONTEXT.md decisions + MDN backdrop-filter */
.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 20px 16px;
  margin: 0 auto 12px;
  max-width: 768px;
  width: calc(100% - 48px);
  border-radius: 12px;
  background-color: rgba(0, 0, 0, 0);    /* transparent base */
  background-color: color-mix(in srgb, var(--atlas-bg-elevated) 80%, transparent);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  align-items: flex-end;
  /* Remove border-top from old design */
}

@supports not (backdrop-filter: blur(1px)) {
  .input-area {
    background-color: var(--atlas-bg-elevated);
  }
}
```

### Stop Button (CSS)

```css
/* Source: CONTEXT.md — filled circle, square icon, --atlas-status-error */
.stop-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: var(--atlas-status-error);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stop-btn::before {
  content: '';
  display: block;
  width: 12px;
  height: 12px;
  background-color: white;
  border-radius: 2px;  /* rounded square */
}
```

### Hover Actions Reveal

```css
/* Source: extends existing .thread-actions pattern in index.css */
.message-hover-actions {
  position: absolute;
  top: -8px;
  right: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 150ms;
}

.message:hover .message-hover-actions {
  opacity: 1;
}

.message-timestamp-overlay {
  position: absolute;
  bottom: -18px;
  right: 0;
  font-size: var(--atlas-text-caption2);
  color: var(--atlas-text-tertiary);
  white-space: nowrap;
  opacity: 0;
  transition: opacity 150ms;
}

.message:hover .message-timestamp-overlay {
  opacity: 1;
}
```

### Welcome State Layout

```css
/* Source: CONTEXT.md decisions */
.welcome-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding: 48px 24px;
}

.welcome-heading {
  font-size: var(--atlas-text-title3);
  line-height: var(--atlas-lh-title3);
  font-weight: 600;
  color: var(--atlas-text-primary);
  letter-spacing: -0.02em;
  text-align: center;
}

.prompt-chips-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  max-width: 480px;
  width: 100%;
}

.prompt-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background-color: var(--atlas-bg-elevated);
  border: none;
  border-radius: 9999px;  /* rounded-full */
  color: var(--atlas-text-secondary);
  font-size: var(--atlas-text-body);
  font-family: var(--atlas-font-base);
  cursor: pointer;
  transition: background-color 100ms;
  text-align: left;
}

/* Surface tier escalation on hover — one step up from elevated */
[data-theme="light"] .prompt-chip:hover {
  background-color: var(--atlas-stroke-2); /* one tier up in light */
}

[data-theme="dark"] .prompt-chip:hover {
  background-color: var(--atlas-bg-surface); /* one tier up in dark */
}
```

### DisplayMessage Type Extension

```ts
// Source: types/index.ts — add optional timestamp field
export interface DisplayMessage {
  type: 'user' | 'assistant';
  content: string;
  toolPanels?: ToolPanelData[];
  timestamp?: string;  // ISO 8601 string, set at creation time; absent for historical messages
}
```

### Context Reducer Timestamp Stamping

```ts
// Source: ChatContext.tsx — ADD_USER_MESSAGE and FINALIZE_STREAMING cases
case 'ADD_USER_MESSAGE':
  return {
    ...state,
    messages: [...state.messages, {
      type: 'user',
      content: action.content,
      timestamp: new Date().toISOString(),  // ADD
    }],
  };

case 'FINALIZE_STREAMING': {
  const finalized: DisplayMessage = {
    type: 'assistant',
    content: state.streamingMessage!.content,
    toolPanels: state.streamingMessage!.toolPanels.length > 0
      ? state.streamingMessage!.toolPanels : undefined,
    timestamp: new Date().toISOString(),  // ADD
  };
  // ...
}
```

---

## State of the Art

| Old Approach (current) | New Approach (Phase 16) | Impact |
|------------------------|------------------------|--------|
| `.user-message` — bg-elevated, no alignment | Right-aligned brand blue bubble, asymmetric corners | Clear role differentiation |
| `.assistant-message` — padding 12px 0, no background | Left-aligned elevated-surface card, asymmetric corners | Consistent containment without borders |
| `.input-area` — border-top, full-width, bg-surface | Centered max-768px, glassmorphism, no border | Premium floating feel |
| `<button>Stop</button>` text | Circular stop button with square icon, error color | Visually distinct from send |
| CopyButton always visible | CopyButton opacity:0, reveal on hover | Cleaner message canvas |
| No welcome state | Welcome state with prompt chips | Better first-use experience |
| No entrance animation | `@keyframes message-enter` fade+slide | Smoother message flow |
| Streaming cursor uses `--atlas-text-primary` | Streaming cursor uses `--atlas-accent` | Better visual consistency |
| Placeholder: "Type a message..." | "Ask Atlas anything about Exchange..." | Context-specific guidance |

**Deprecated/outdated in this phase:**
- `.input-area { border-top: 1px solid var(--atlas-stroke-2) }` — replaced by glassmorphism
- `.message { max-width: 800px; margin: 0 auto }` — replaced by per-role alignment (user: flex-end, assistant: flex-start) with 75% max-width

---

## Open Questions

1. **`.chat-pane` `overflow: hidden` and backdrop-filter**
   - What we know: `.chat-pane` has `overflow: hidden` currently via the app layout; `backdrop-filter` may fail if an ancestor has `overflow: hidden` combined with `border-radius` (Firefox bug).
   - What's unclear: Whether the current `.chat-pane` has `border-radius` set — if not, the Firefox bug may not apply.
   - Recommendation: Test glassmorphism in Firefox during 16-02 implementation. If backdrop-filter fails, the `@supports` fallback ensures a solid background is used.

2. **Chip auto-submit threading**
   - What we know: `handleSend` in `AppLayout.tsx` handles threadless state — it creates a thread then sends. The chip needs to call this same function.
   - What's unclear: `MessageList` currently receives no props from `AppLayout` — it reads from context. Threading `onChipSend` down requires adding a prop to `MessageList`.
   - Recommendation: Add `onChipSend?: (text: string) => void` prop to `MessageList`. It's a shallow addition. Alternative: put a shared `sendMessage` function into `ChatContext` — but that would merge concern from `AppLayout`, which is cleaner not to do.

3. **Dark mode surface tier for prompt chip hover**
   - What we know: In dark mode, the surface hierarchy is canvas (#292929) > surface (#1f1f1f) > elevated (#141414). Elevated is the darkest, surface is mid.
   - What's unclear: The chip background is `--atlas-bg-elevated` (#141414 in dark). One tier "up" (lighter) would be `--atlas-bg-surface` (#1f1f1f). This is visually very subtle.
   - Recommendation: In dark mode, use `--atlas-bg-canvas` (#292929) for chip hover — two tiers up — to ensure visible feedback.

---

## Sources

### Primary (HIGH confidence)

- Codebase read directly — `frontend/src/index.css`, `ChatContext.tsx`, `InputArea.tsx`, `AssistantMessage.tsx`, `UserMessage.tsx`, `MessageList.tsx`, `useStreamingMessage.ts`, `types/index.ts`
- Phase 16 CONTEXT.md — locked decisions for all visual specifications
- `https://developer.mozilla.org/en-US/docs/Web/CSS/animation` — animation-fill-mode: both behavior
- `https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/RelativeTimeFormat` — API and browser support

### Secondary (MEDIUM confidence)

- `https://www.joshwcomeau.com/css/backdrop-filter/` — backdrop-filter glassmorphism, overflow:hidden issue documented
- CSS border-radius asymmetric corners: MDN reference + Copilot/chat bubble pattern widely understood

### Tertiary (LOW confidence)

- WebSearch results on "CSS chat bubble Copilot 2025" — general pattern confirmation only, not used as prescriptive source

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new packages
- Architecture: HIGH — read directly from codebase; changes are additive
- Animation approach: HIGH — `@keyframes` is the simplest correct approach; verified against existing usage in this codebase
- Glassmorphism pitfall (overflow:hidden): MEDIUM — documented as known browser issue; needs runtime verification
- Chip threading: MEDIUM — pattern is clear but the exact prop placement is a planning-time decision

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable CSS and React APIs; no fast-moving dependencies)
