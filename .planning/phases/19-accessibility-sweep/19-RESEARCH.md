# Phase 19: Accessibility Sweep - Research

**Researched:** 2026-03-30
**Domain:** Web Accessibility — WCAG AA keyboard navigation + focus indicators in React/TypeScript/CSS
**Confidence:** HIGH (CSS/HTML patterns are stable W3C specs; React patterns verified against MDN)

## Summary

This phase applies keyboard operability and visible focus indicators to the existing Atlas React UI. The codebase audit reveals **zero existing focus ring CSS** (`.chat-input` has `outline: none`), **no skip link**, and **thread items rendered as inaccessible `<div>` elements** with click handlers. The decisions in CONTEXT.md are sound and align with WCAG 2.2 SC 2.4.13 and W3C APG patterns.

The Fluent 2 double-ring pattern (inner white ring + outer brand-color ring) is implemented in CSS via `outline` + `box-shadow`. This is the only viable two-ring approach: CSS does not support two simultaneous `outline` declarations on one element, so `box-shadow` provides the second ring. Windows High Contrast Mode (forced-colors) suppresses `box-shadow`, so a `@media (forced-colors: active)` fallback is required. The CONTEXT decision to "use CSS outline (not box-shadow)" needs a practical refinement: use `outline` for the inner ring and `box-shadow` for the outer ring with a forced-colors fallback.

The thread list roving tabindex must be implemented from scratch using React `useRef` arrays and `onKeyDown` handlers. No external library is needed — the pattern is 15–20 lines of straightforward React. The `aria-activedescendant` approach is an alternative but requires each thread item to have an id and the container to manage its attribute; roving tabindex (moving actual DOM focus) is simpler to implement and provides stronger AT compatibility.

**Primary recommendation:** One CSS block of global `:focus-visible` rules covers all buttons/links/inputs/summary elements. The only bespoke work is the ThreadList roving tabindex hook, the ThreadItem div-to-button conversion, and the skip link component in AppLayout.

## Standard Stack

No additional npm packages are needed. All patterns use native browser APIs and existing React.

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | useRef, useCallback, useEffect for focus management | Already in use |
| TypeScript | — | Type-safe refs and event handlers | Already in use |
| Vite | 8.0.1 | No build changes needed | Already in use |

### Supporting (no new installs)
| Tool/API | Purpose | When to Use |
|---------|---------|-------------|
| CSS `:focus-visible` | Show focus rings only on keyboard navigation, not mouse click | All interactive elements globally |
| CSS `outline` + `box-shadow` | Double-ring pattern — outline is inner ring, box-shadow is outer ring | All `:focus-visible` rules |
| `@media (forced-colors: active)` | Windows High Contrast fallback — box-shadow is stripped in forced colors mode | Alongside every focus ring rule |
| `element.focus()` | Programmatic focus for state-change management (thread deletion, creation) | useEffect after state updates |
| `useRef<HTMLElement[]>` | Store refs to thread item DOM nodes for roving tabindex | ThreadList component |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Roving tabindex (DOM focus moves) | `aria-activedescendant` | aria-activedescendant is more complex: requires all items to have IDs, container manages attribute, no actual DOM focus moves (weaker AT support). Roving tabindex is simpler and better supported. |
| Inline `box-shadow` for outer ring | `::after` pseudo-element with outline | Pseudo-element technique works but requires `position: relative` on the parent and careful stacking. box-shadow is simpler and cleaner. |

**Installation:** None required.

## Architecture Patterns

### Recommended File Changes
```
frontend/src/
├── index.css              # Add --atlas-stroke-focus tokens + global :focus-visible block
├── components/
│   ├── AppLayout.tsx      # Add <SkipLink /> as first child
│   ├── SkipLink.tsx       # NEW: "Skip to chat" visually-hidden-until-focused component
│   ├── Sidebar/
│   │   ├── ThreadList.tsx # Add roving tabindex hook, role="listbox", aria-label
│   │   └── ThreadItem.tsx # Convert <div> to <button> or add tabIndex+role+onKeyDown
│   └── ChatPane/
│       └── Header.tsx     # Add aria-label to theme toggle button
```

### Pattern 1: Global Focus Ring via :focus-visible

**What:** A single CSS block at the top of the component layer that applies the double-ring to every interactive element. Individual component styles do not override this.

**When to use:** Every `button`, `a`, `input`, `textarea`, `select`, and `summary` element in the app.

**The double-ring technique:** CSS cannot apply two `outline` values to one element. The Fluent 2 pattern uses `outline` for the inner ring and `box-shadow` for the outer ring. The `outline-offset` creates space for the inner ring between the element edge and the outer box-shadow ring.

```css
/* Source: W3C WCAG C40 technique + Fluent 2 focus spec */
/* === Global Focus Rings === */

/* Light mode: white inner ring + black outer ring */
:root {
  --atlas-stroke-focus-inner: #ffffff;
  --atlas-stroke-focus-outer: #000000;
}

/* Dark mode: white inner ring + brand accent outer ring */
[data-theme="dark"] {
  --atlas-stroke-focus-inner: #ffffff;
  --atlas-stroke-focus-outer: var(--atlas-accent);
}

/* Applied globally — no per-component overrides needed */
:focus-visible {
  outline: 2px solid var(--atlas-stroke-focus-inner);
  outline-offset: 1px;
  /* box-shadow creates the outer ring: spread = inner(2px) + offset(1px) + outer(2px) gap = 5px */
  box-shadow: 0 0 0 4px var(--atlas-stroke-focus-outer);
}

/* Windows High Contrast: box-shadow is stripped; fallback to single outline */
@media (forced-colors: active) {
  :focus-visible {
    outline: 2px solid ButtonText;
    outline-offset: 2px;
    box-shadow: none;
  }
}

/* Remove the custom ring from elements where Fluent UI manages its own focus style */
/* (None in this project — Fluent UI components are not used for interactive elements) */
```

**Important:** Remove `outline: none` from `.thread-item-name-input` and `.chat-input` — these suppress the global rule.

### Pattern 2: Skip Link Component

**What:** A visually-hidden anchor that reveals on Tab focus. First focusable element in DOM. Target is the chat message container.

**When to use:** In AppLayout.tsx as the first child element.

```tsx
// Source: WebAIM skip navigation + WCAG 2.4.1 (Bypass Blocks, Level A)
// frontend/src/components/SkipLink.tsx

export function SkipLink() {
  return (
    <a href="#chat-messages" className="skip-link">
      Skip to chat
    </a>
  );
}
```

```css
/* In index.css — add to @layer components */
.skip-link {
  position: absolute;
  top: -9999px;
  left: 8px;
  z-index: 9999;
  padding: 8px 16px;
  background-color: var(--atlas-accent);
  color: #ffffff;
  font-size: var(--atlas-text-body);
  font-weight: 600;
  border-radius: 0 0 6px 6px;
  text-decoration: none;
  white-space: nowrap;
}

.skip-link:focus-visible {
  top: 0;
  outline: 2px solid #ffffff;
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--atlas-accent);
}
```

The `.chat-messages` div in MessageList needs `id="chat-messages"` and `tabIndex={-1}` added so it can receive programmatic focus when the skip link is activated.

### Pattern 3: Roving Tabindex in ThreadList

**What:** The thread list becomes a single Tab stop. Arrow Up/Down, Home/End navigate within it. Only the focused item has `tabIndex={0}`; all others have `tabIndex={-1}`.

**When to use:** ThreadList component — the `<div className="thread-list">` wrapping all thread groups.

```tsx
// Source: MDN Keyboard-navigable JavaScript widgets + W3C APG Listbox pattern
// Inside ThreadList.tsx

const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
const [focusedIndex, setFocusedIndex] = useState(0);

// Flatten threads across all groups for linear navigation
const flatThreads = groups.flatMap(g => g.threads);

function handleListKeyDown(e: React.KeyboardEvent) {
  const len = flatThreads.length;
  if (len === 0) return;

  let next = focusedIndex;

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault();
      next = (focusedIndex + 1) % len;
      break;
    case 'ArrowUp':
      e.preventDefault();
      next = (focusedIndex - 1 + len) % len;
      break;
    case 'Home':
      e.preventDefault();
      next = 0;
      break;
    case 'End':
      e.preventDefault();
      next = len - 1;
      break;
    default:
      return;
  }

  setFocusedIndex(next);
  itemRefs.current[next]?.focus();
}

// Each ThreadItem button:
// tabIndex={thread.id === flatThreads[focusedIndex]?.id ? 0 : -1}
// ref={(el) => { itemRefs.current[globalIndex] = el; }}
// onClick also updates focusedIndex: onFocus={() => setFocusedIndex(globalIndex)}
```

The thread list container needs:
```tsx
<div
  className="thread-list"
  role="listbox"
  aria-label="Conversations"
  onKeyDown={handleListKeyDown}
>
```

Each ThreadItem needs:
```tsx
<button
  role="option"
  aria-selected={isActive}
  tabIndex={isFocusedInList ? 0 : -1}
  ref={refCallback}
  onFocus={() => onFocusInList(globalIndex)}
  onClick={() => onSelect(thread.id)}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(thread.id);
    }
  }}
  className={itemClass}
>
```

### Pattern 4: ThreadItem `<div>` to `<button>` Conversion

**What:** The current `<div className={itemClass} onClick={...}>` is not keyboard accessible. Convert to `<button>`.

**Why:** `<div>` elements are not in the Tab order, don't receive keyboard events by default, and have no implicit ARIA role. Screen readers won't announce them as interactive.

**Important nuance:** The action buttons (rename, delete) inside ThreadItem are currently `opacity: 0` until hover. For keyboard access, they must be visible when the parent thread item is focused. Add:

```css
/* Reveal action buttons on parent focus-within */
.thread-item:focus-within .thread-actions {
  opacity: 1;
}
```

This makes rename/delete buttons reachable via Tab after entering the thread item without requiring hover.

### Pattern 5: Focus Management on State Changes

**What:** Move focus programmatically after thread deletion, creation, etc.

**When to use:** Inside event handlers in ThreadList.tsx after async operations complete.

```tsx
// Source: MDN element.focus() + React useEffect pattern
// After thread deletion in handleDelete():
useEffect(() => {
  if (focusAfterDelete) {
    newThreadBtnRef.current?.focus(); // or next thread ref
    setFocusAfterDelete(false);
  }
}, [focusAfterDelete]);
```

For thread creation (handleNewChat):
```tsx
// After new thread is added and input is mounted:
// Signal to InputArea to focus itself — InputArea already auto-focuses on mount
// The existing useEffect(() => { textareaRef.current?.focus(); }, []); in InputArea handles this
// But it only runs on mount. For thread creation mid-session, call focus() explicitly:
inputAreaRef.current?.focus(); // passed down from AppLayout
```

### Anti-Patterns to Avoid

- **`outline: none` without replacement:** Already present on `.chat-input` and `.thread-item-name-input`. Must be removed. These currently have zero focus indication.
- **`opacity: 0` on focusable children:** `.thread-actions` buttons are Tab-reachable even when invisible. Use `visibility: hidden` if you truly want to exclude them, or expose via `:focus-within` as shown above. Since these are mouse-only per CONTEXT decisions, add `tabIndex={-1}` to rename/delete buttons to exclude them from Tab order entirely.
- **Using `tabIndex={0}` on all thread items simultaneously:** Breaks roving tabindex — only ONE item should be `tabIndex={0}` at any time.
- **`element.dispatchEvent(new Event('focus'))`:** Fires the event but does NOT move browser focus. Always use `element.focus()`.
- **Programmatic focus before DOM update:** Focus calls must happen after React commits the DOM. Use `useEffect` or `requestAnimationFrame` if calling focus synchronously after a `setState`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Focus ring CSS | Per-component custom outlines | Single global `:focus-visible` block in index.css | Per-component outlines create inconsistency and maintenance burden. One rule covers everything. |
| Roving tabindex library | npm package like `react-roving-tabindex` | Plain React useRef + onKeyDown | The pattern is 20 lines; a library adds a dependency for trivial code |
| Custom focus trap | Hand-rolled focus-trap logic for tool panels | Native `<details>/<summary>` already handles Escape | ToolPanel already uses native details element which has built-in keyboard behavior |
| Skip link target management | Complex scroll-to logic | `href="#chat-messages"` + `tabIndex={-1}` on target | Native anchor fragment navigation handles scrolling |

**Key insight:** This phase is 90% CSS and 10% React. The global `:focus-visible` rule does most of the work. The only non-trivial React work is the ThreadList roving tabindex (because it uses `<div>` items not native `<button>` list items with inherent tab stops).

## Common Pitfalls

### Pitfall 1: The `outline: none` trap
**What goes wrong:** Existing `outline: none` on `.chat-input` and `.thread-item-name-input` will override the global `:focus-visible` rule because the component-specific rule has higher specificity.
**Why it happens:** The CSS specificity of `.chat-input:focus` (0,1,1) beats `:focus-visible` (0,0,1).
**How to avoid:** Remove `outline: none` from `.chat-input` and `outline: none` from `.thread-item-name-input`. The global rule replaces them. The `.chat-input:focus { border-color: ... }` rule can stay — it adds a border highlight on top of the focus ring.
**Warning signs:** Tab to textarea and no ring appears despite global rule being present.

### Pitfall 2: ThreadItem div — focus ring appears but Tab doesn't reach it
**What goes wrong:** Adding `:focus-visible` CSS to `.thread-item` when it's a `<div>` — focus rings appear only when `tabIndex={0}` is explicitly set. Without tabIndex, the div is not in Tab order.
**Why it happens:** Only interactive elements (`<a href>`, `<button>`, `<input>`, `<select>`, `<textarea>`) and elements with `tabIndex >= 0` participate in Tab order.
**How to avoid:** Convert ThreadItem's outer div to `<button>` (simplest) or add `tabIndex` explicitly. The button conversion is cleaner because it gets keyboard events and ARIA semantics for free.
**Warning signs:** Tab skips the entire sidebar thread list.

### Pitfall 3: Roving tabindex state desync after thread deletion
**What goes wrong:** `focusedIndex` in ThreadList points to index 3 but thread at index 3 was deleted — `itemRefs.current[3]` is null. `focus()` call throws or does nothing.
**Why it happens:** The flat thread array is recomputed from context state, but `focusedIndex` state hasn't updated yet.
**How to avoid:** Clamp `focusedIndex` to `Math.min(focusedIndex, flatThreads.length - 1)` after deletion. Handle `flatThreads.length === 0` with early return.
**Warning signs:** Console error "Cannot read properties of null (reading 'focus')".

### Pitfall 4: Double-ring on elements with border-radius — box-shadow clips
**What goes wrong:** `box-shadow` for the outer ring may be clipped by `overflow: hidden` on ancestor elements.
**Why it happens:** `box-shadow` does not escape `overflow: hidden` containers. This affects thread items inside `.thread-list` which has `overflow-y: auto`.
**How to avoid:** The `.thread-list` container has `overflow-y: auto` which clips box-shadow on items near the edges. Set `overflow: visible` on the thread list or use `outline` only (single ring) if clipping occurs. Alternatively, add `padding: 2px` to `.thread-list` to give the shadow room.
**Warning signs:** Focus ring on thread items is cut off at the sidebar scroll boundary.

### Pitfall 5: Skip link target not focusable
**What goes wrong:** Clicking "Skip to chat" link moves URL hash but does not visually focus the chat messages container. Screen readers and keyboard users have no indication of where they landed.
**Why it happens:** Non-interactive elements like `<div>` are not focusable by default even with `href="#id"`.
**How to avoid:** Add `tabIndex={-1}` to the `<div className="chat-messages">` so it can receive programmatic focus when the skip link is activated.
**Warning signs:** Skip link activates, URL changes to `#chat-messages`, but focus stays on the skip link.

### Pitfall 6: Thread action buttons reachable but invisible (opacity: 0)
**What goes wrong:** Rename and delete buttons inside ThreadItem are in Tab order but invisible (opacity: 0). WCAG 1.3.3 / good practice: users must be able to see what they're activating.
**Why it happens:** The hover reveal pattern (`.thread-item:hover .thread-actions { opacity: 1 }`) does not trigger on keyboard focus.
**How to avoid:** Two options — (a) add `tabIndex={-1}` to both action buttons to exclude them from keyboard Tab order entirely (they are mouse-only per CONTEXT), or (b) add `.thread-item:focus-within .thread-actions { opacity: 1 }` to reveal them when the item is focused. The CONTEXT decision explicitly marks hover actions as mouse-only, so option (a) is correct: `tabIndex={-1}` on rename/delete buttons.
**Warning signs:** Tabbing within a thread item focuses invisible buttons.

### Pitfall 7: First thread item has tabIndex={0} but sidebar is collapsed
**What goes wrong:** When sidebar is collapsed, the thread list content is hidden (CSS, not DOM removal). The first thread item may still have `tabIndex={0}` and receive Tab focus, opening the sidebar unexpectedly or causing invisible focus.
**Why it happens:** Collapsing sidebar uses CSS width/visibility, not `display: none` or DOM removal.
**How to avoid:** When `collapsed === true`, ensure thread items have `tabIndex={-1}` or are wrapped in a container with `hidden` attribute / `display: none` so they're excluded from Tab order. The existing `{!collapsed && groups.map(...)}` conditional rendering already handles this — items are not in the DOM when collapsed. This pitfall is already avoided.
**Warning signs:** Tab focuses invisible items when sidebar is collapsed.

## Code Examples

### Global Focus Ring CSS Block
```css
/* Source: W3C WCAG C40 + MDN :focus-visible */
/* Add to :root block in index.css */
--atlas-stroke-focus-inner: #ffffff;
--atlas-stroke-focus-outer: #000000;

/* Add to [data-theme="dark"] block in index.css */
/* Dark mode: keep inner white, outer = brand accent */
--atlas-stroke-focus-outer: var(--atlas-accent);

/* Add after @layer base, before @layer components in index.css */
/* Or as first rule inside @layer components */

/* Global focus rings — covers all interactive elements */
:focus-visible {
  outline: 2px solid var(--atlas-stroke-focus-inner);
  outline-offset: 1px;
  box-shadow: 0 0 0 4px var(--atlas-stroke-focus-outer);
  border-radius: inherit;   /* follow element's own border-radius */
}

/* Forced colors (Windows High Contrast) — box-shadow stripped by UA */
@media (forced-colors: active) {
  :focus-visible {
    outline: 2px solid ButtonText;
    outline-offset: 2px;
    box-shadow: none;
  }
}
```

### Remove Existing outline:none Overrides
```css
/* BEFORE (in index.css — remove these) */
.chat-input {
  outline: none;  /* DELETE THIS LINE */
}
.thread-item-name-input {
  outline: none;  /* DELETE THIS LINE */
}

/* AFTER — let the global :focus-visible rule apply */
/* .chat-input:focus { border-color: var(--atlas-accent); }  ← keep this */
```

### ThreadItem as Button with Roving tabIndex
```tsx
// Source: MDN Keyboard-navigable JavaScript widgets
// In ThreadItem.tsx — outer element changes from <div> to <button>
<button
  role="option"
  aria-selected={isActive}
  tabIndex={tabIndexValue}  // passed from ThreadList: 0 for focused item, -1 for others
  ref={refCallback}          // called with (el) => { itemRefs.current[index] = el; }
  className={itemClass}
  onClick={() => onSelect(thread.id)}
  onFocus={() => onFocusChange(index)}  // updates focusedIndex in ThreadList
>
  {/* ... existing content ... */}
  <div className="thread-actions">
    {/* Mouse-only: tabIndex={-1} to exclude from keyboard Tab order */}
    <button tabIndex={-1} className="thread-action-btn" aria-label="Rename conversation" onClick={handleRenameClick}>
      ✏️
    </button>
    <button tabIndex={-1} className="thread-action-btn" aria-label="Delete conversation" onClick={handleDeleteClick}>
      🗑️
    </button>
  </div>
</button>
```

### Skip Link Component
```tsx
// Source: WebAIM skip navigation technique / WCAG 2.4.1
// frontend/src/components/SkipLink.tsx
export function SkipLink() {
  return (
    <a href="#chat-messages" className="skip-link">
      Skip to chat
    </a>
  );
}

// In AppLayout.tsx:
return (
  <div className="app-container">
    <SkipLink />  {/* First focusable element in DOM */}
    <aside className="sidebar" ...>
```

```tsx
// In MessageList.tsx — add id and tabIndex to chat container:
<div
  className="chat-messages"
  id="chat-messages"
  tabIndex={-1}   // allows skip link to focus it
  ref={containerRef}
>
```

### Focus Management After Thread Deletion
```tsx
// Source: React useEffect + element.focus() pattern
// In ThreadList.tsx handleDelete():

async function handleDelete(threadId: number) {
  await deleteThread(threadId);
  threadDispatch({ type: 'REMOVE_THREAD', threadId });

  const remaining = threads.filter((t) => t.id !== threadId);
  const deletedIndex = flatThreads.findIndex(t => t.id === threadId);

  if (remaining.length > 0) {
    // Focus next thread (or last if deleting the last one)
    const nextIndex = Math.min(deletedIndex, remaining.length - 1);
    setFocusAfterDeletion(nextIndex);
    // Select that thread too
    threadDispatch({ type: 'SET_ACTIVE', threadId: remaining[nextIndex].id });
  } else {
    // No threads left — focus "New Chat" button
    newChatBtnRef.current?.focus();
  }
}

// Separate useEffect to fire focus after React re-renders with updated thread list:
useEffect(() => {
  if (focusAfterDeletion !== null) {
    const clamped = Math.min(focusAfterDeletion, itemRefs.current.length - 1);
    if (clamped >= 0) itemRefs.current[clamped]?.focus();
    setFocusAfterDeletion(null);
  }
}, [threads, focusAfterDeletion]);
```

### scroll-margin for Focused Elements
```css
/* Prevents focused elements from being obscured by sticky/fixed headers */
/* Claude's Discretion per CONTEXT.md */
:focus-visible {
  scroll-margin: 8px;
}
/* Or scoped to thread items if header overlap is only concern */
.thread-item:focus-visible {
  scroll-margin-block: 4px;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `:focus` for focus rings | `:focus-visible` | Chrome 86 (2020), Firefox 85 (2021), Safari 15.4 (2022) — now Baseline | `:focus` shows rings on mouse click; `:focus-visible` only shows on keyboard. No polyfill needed in 2026. |
| `box-shadow` only for focus ring | `outline` + `box-shadow` with forced-colors fallback | WCAG 2.2 (2023) + increased Windows usage | box-shadow is stripped in forced-colors mode; outline persists. |
| `tabIndex={0}` on all list items | Roving tabindex (single tabIndex=0 moves) | WAI-APG stable recommendation since 2019 | Single Tab stop per widget dramatically reduces Tab key presses for keyboard users. |
| `outline: none` suppression | Global `:focus-visible` + no suppression | WCAG 2.1 tightened enforcement | Removing outlines without replacement fails WCAG SC 2.4.7. |

**Deprecated/outdated in this codebase:**
- `outline: none` on `.chat-input`: accessibility regression, must be removed
- `outline: none` on `.thread-item-name-input`: accessibility regression, must be removed
- `.chat-input:focus { border-color: ... }`: fine to keep as border change supplement, but cannot replace outline

## Open Questions

1. **Double ring on pill-shaped prompt chips (border-radius: 9999px)**
   - What we know: `border-radius: inherit` in `:focus-visible` will follow the element's radius
   - What's unclear: Whether `box-shadow` outer ring visually reads well on highly rounded elements
   - Recommendation: Test at QA step; if the outer ring looks odd, add `.prompt-chip:focus-visible { border-radius: 24px; }` to cap the radius for the ring

2. **Roving tabindex with thread groups (Today/Yesterday/Older)**
   - What we know: Groups are rendered as separate divs with group headings in between
   - What's unclear: Whether Home/End should jump across groups or stop at group boundaries
   - Recommendation: Flatten all threads to a single index array ignoring group headers — simpler, matches how users think of threads

3. **`outline-offset: 1px` clipping within `overflow: auto` scroll container**
   - What we know: `.thread-list` has `overflow-y: auto` which clips box-shadow
   - What's unclear: How much padding is needed to give box-shadow room on thread items
   - Recommendation: Add `padding: 2px` to `.thread-list` inner padding, or change `overflow: clip` to `overflow: auto` with larger padding. Test at implementation.

4. **`tabIndex={-1}` on `.chat-messages` and skip link — does it interfere with scroll behavior?**
   - What we know: `tabIndex={-1}` on a div allows programmatic focus but doesn't add it to Tab order
   - What's unclear: Whether focusing the scrollable container causes scroll-jump issues
   - Recommendation: Standard pattern, widely used — should not cause issues. Verify during implementation.

## Sources

### Primary (HIGH confidence)
- MDN Web Docs `:focus-visible` — https://developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible — confirmed :focus vs :focus-visible behavior, browser support (Baseline widely available March 2022)
- MDN Keyboard-navigable JavaScript widgets — https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Keyboard-navigable_JavaScript_widgets — roving tabindex pattern with tabIndex management and element.focus()
- W3C WCAG C40 technique — https://www.w3.org/WAI/WCAG21/Techniques/css/C40 — two-color focus indicator using outline + box-shadow
- W3C WCAG 2.2 SC 2.4.13 — https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance-minimum.html — 2px minimum, 3:1 contrast ratio between focused/unfocused states
- W3C APG Listbox pattern — https://www.w3.org/WAI/ARIA/apg/patterns/listbox/ — roving tabindex vs aria-activedescendant, both valid approaches

### Secondary (MEDIUM confidence)
- WebAIM Skip Navigation Links — https://webaim.org/techniques/skipnav/ — visually hidden skip link CSS pattern
- Piccalilli double focus ring article — https://piccalil.li/blog/taking-a-shot-at-the-double-focus-ring-problem-using-modern-css/ — forced-colors media query necessity confirmed

### Tertiary (LOW confidence)
- Darek Kay accessible focus indicator — https://darekkay.com/blog/accessible-focus-indicator/ — community article on forced-colors + outline approach
- TetraLogical visible focus styles — https://tetralogical.com/blog/2023/01/13/foundations-visible-focus-styles/ — confirms box-shadow stripped in forced colors, multiple sources agree → upgraded to MEDIUM

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all CSS/React patterns are stable W3C/MDN-documented
- Architecture patterns: HIGH — focus ring CSS from W3C C40 directly; roving tabindex from MDN
- Pitfalls: HIGH — several derived directly from codebase audit (outline:none on existing elements, div thread items, opacity:0 actions); others from verified MDN/W3C sources
- Skip link: HIGH — WebAIM authoritative source, pattern unchanged since 2000s

**Research date:** 2026-03-30
**Valid until:** 2027-03-30 (CSS/WCAG specs are stable; :focus-visible is now Baseline)
