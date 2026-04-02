# Phase 25: Motion Animations - Research

**Researched:** 2026-04-02
**Domain:** React animation with Motion (formerly Framer Motion) — LazyMotion + domAnimation pattern
**Confidence:** HIGH

## Summary

Phase 25 adds entrance animations and micro-interactions to an existing React/Fluent UI 2 app with no current Motion library dependency. The requirements lock in a specific animation stack: the `motion` npm package (formerly framer-motion) using `LazyMotion + domAnimation` for bundle efficiency, and `MotionConfig reducedMotion="user"` as the global accessibility wrapper.

The codebase already has partial CSS animation infrastructure: a `message-enter` keyframe (180ms, fade + 8px translateY, ease-out) and a `prefers-reduced-motion: reduce` override. The new implementation must replace and formalize this with Motion-managed animations for message entrances, while keeping the sidebar width transition as pure CSS (already in place at 200ms, needing minor tuning), and adding a CSS `:active` scale micro-interaction for the feedback buttons.

The critical engineering constraint is ANIM-04: no animation during active SSE streaming. The `streamingMessage` render path already passes `isStreaming={true}` to `AssistantMessage`, making the streaming guard straightforward — only finalized messages (those in the `messages` array) receive entrance animations.

**Primary recommendation:** Install `motion` package, wrap `App.tsx` root with `MotionConfig reducedMotion="user"` + `LazyMotion features={domAnimation}`, replace the CSS `message-enter` animation on `.message` with `m.div` motion components in `AssistantMessage` and `UserMessage`, tune existing sidebar CSS transition to 200-250ms ease-in-out, and add CSS `:active` scale to feedback button wrapper.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| motion | 12.x (latest) | React animation via LazyMotion + m.* components | Official rename of framer-motion; required by locked decisions; 30M monthly downloads |

No other animation library is needed. The sidebar and feedback micro-interactions are pure CSS.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| motion/react-m | (same package) | The `m.*` components used inside LazyMotion boundary | Every animating element inside a LazyMotion boundary |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| motion (LazyMotion) | CSS @keyframes only | Simpler but no declarative initial/animate props; harder to gate streaming; already decided against |
| motion (LazyMotion) | full `motion` component import | +19kb bundle vs LazyMotion; locked decision says LazyMotion |
| CSS :active for feedback | motion whileTap on m.button | Fluent UI Button is a complex component; motion.create() wrapping adds complexity; CSS :active is simpler and sufficient for 100ms scale |

**Installation:**
```bash
npm install motion
```

## Architecture Patterns

### Recommended Project Structure

No new directories needed. Changes are confined to existing files:

```
frontend/src/
├── App.tsx                          # Add MotionConfig + LazyMotion providers
├── index.css                        # Remove CSS message-enter; tune sidebar; add :active scale
├── components/ChatPane/
│   ├── AssistantMessage.tsx         # Wrap outermost div → m.div with initial/animate
│   └── UserMessage.tsx              # Same pattern
└── components/ChatPane/
    └── FeedbackButtons.tsx          # Add CSS class for :active scale (no Motion needed)
```

### Pattern 1: LazyMotion Provider Setup in App.tsx

**What:** Wrap the entire app in `MotionConfig` + `LazyMotion`. Both must be above any `m.*` component in the tree.

**When to use:** Once, at the root, before any `m.*` component renders.

```tsx
// Source: https://motion.dev/docs/react-lazy-motion
// Source: https://motion.dev/docs/react-motion-config
import { LazyMotion, MotionConfig, domAnimation } from 'motion/react';

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domAnimation}>
        <FluentProvider theme={...}>
          {/* rest of app */}
        </FluentProvider>
      </LazyMotion>
    </MotionConfig>
  );
}
```

**Important:** `MotionConfig` and `LazyMotion` are both imported from `"motion/react"`. The `m` components are imported from `"motion/react-m"`.

### Pattern 2: Message Entrance Animation

**What:** Replace the `<div className="message ...">` in `AssistantMessage` and `UserMessage` with an `m.div`. Use `initial`/`animate`/`transition` props.

**When to use:** On every finalized message render. The streaming message (passed `isStreaming={true}`) must NOT receive this animation — render it as a plain `div` or with `initial={false}`.

```tsx
// Source: https://motion.dev/docs/react-animation
import * as m from 'motion/react-m';

// AssistantMessage — 200ms ease-out per ANIM-01
<m.div
  className="message assistant-message"
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.2, ease: 'easeOut' }}
>
  {/* content */}
</m.div>

// UserMessage — 150ms ease-out per ANIM-02
<m.div
  className="message user-message"
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.15, ease: 'easeOut' }}
>
  {/* content */}
</m.div>

// Streaming message — no animation (ANIM-04)
// In AssistantMessage when isStreaming={true}: use plain div
<div className="message assistant-message">
  {/* streaming content */}
</div>
```

**Key insight on ANIM-04:** `MessageList.tsx` already separates the streaming path — `streamingMessage` is rendered separately with `isStreaming={true}`. `AssistantMessage` can check `isStreaming` and render `m.div` vs `div` conditionally, OR the cleaner approach is: always render `m.div` but pass `initial={false}` when `isStreaming` is true. However, the cleanest approach that avoids any risk of animation mid-stream is a conditional: `isStreaming ? <div> : <m.div>`.

### Pattern 3: Preventing Re-Animation on Re-renders

**What:** Motion animates `initial → animate` only on mount. Subsequent prop changes to the same mounted component do NOT re-trigger the entrance animation unless `key` changes. Since `streamingMessage` content updates continuously, if it were wrapped in `m.div` it would not re-animate on each chunk — but it would animate on first mount. This is why gating on `isStreaming` is the correct approach rather than relying on "animate only fires once."

**When to use:** Always gate `m.div` behind `!isStreaming` for the streaming message path.

### Pattern 4: Sidebar CSS Transition (ANIM-05)

**What:** Pure CSS, no Motion library. Already partially implemented. Needs tuning.

**Current state in `index.css`:**
```css
.sidebar {
  transition: width 200ms ease, min-width 200ms ease;
}
```

**Required change:** The spec says 200-250ms ease-in-out. The current easing is `ease` (equivalent to `cubic-bezier(0.25, 0.1, 0.25, 1.0)`), not `ease-in-out`. Update to:

```css
.sidebar {
  transition: width 225ms ease-in-out, min-width 225ms ease-in-out;
}
```

225ms sits in the middle of the 200-250ms range and matches Fluent 2's preference for symmetric enter/exit transitions on containers. No overflow-hidden content visibility concerns — the collapsed state shows icon-only content by design.

### Pattern 5: Feedback Button Scale Micro-Interaction (ANIM-06)

**What:** 100ms scale press effect on thumb buttons. CSS `:active` approach, not Motion.

**Why CSS instead of Motion `whileTap`:** The `FeedbackButtons` component uses Fluent UI's `<Button>` component. Wrapping it with `motion.create()` is possible (Fluent UI v9 forwards refs) but adds complexity for a trivial effect. CSS `:active` is sufficient, requires zero library involvement, and performs identically at this duration.

```css
/* Add to index.css in the feedback buttons section */
.feedback-scale-btn:active {
  transform: scale(0.88);
  transition: transform 100ms ease-out;
}

.feedback-scale-btn {
  transition: transform 100ms ease-out;
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  .feedback-scale-btn:active {
    transform: none;
  }
}
```

Apply className `"feedback-scale-btn"` to the wrapper `<span>` or `<span>` container around each `<Button>` in `FeedbackButtons.tsx`, since Fluent UI Button renders its own internal structure.

**Alternative:** If a `<span>` wrapper creates accessibility issues (nested interactive elements), the CSS can target the Fluent Button's inner element using Fluent's slot pattern. But a non-interactive wrapper span around each Button is the simplest approach.

### Anti-Patterns to Avoid

- **Animating historical messages on thread switch:** `MessageList.tsx` renders `messages.map(...)` — all existing messages in a thread would animate if `m.div` fires on every mount. This is called out as out of scope. The fix: add a `key` that is stable across thread loads, or (simpler) wrap the `MessageList` `messages.map` in a check that only applies animation to the *last* message. See Don't Hand-Roll section.
- **Using `motion` (full) instead of `m` inside LazyMotion:** Mixing `<motion.div>` inside `<LazyMotion>` negates bundle savings. Only use `m.*` inside the LazyMotion boundary.
- **Calling `motion.create()` inside render:** Must be called at module level, not inside a component function.
- **Both CSS `message-enter` keyframe and `m.div` animation active simultaneously:** Remove the existing CSS `animation: message-enter 180ms ease-out both` from `.message` rule before adding Motion animations. Otherwise both run at once.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reduced motion detection | Custom `useReducedMotion()` hook | `MotionConfig reducedMotion="user"` | Handles OS-level detection automatically; works across all m.* descendants |
| Animation on mount only | `useEffect` + `useState` to add CSS class | `initial`/`animate` props on `m.div` | Motion handles mount lifecycle correctly; no flash-of-unstyled-content |
| Sidebar animation | Any JS animation | Pure CSS `transition` on `width` | Hardware-accelerated; no JS needed; already in place |

**Key insight:** Motion's `initial → animate` pattern is mount-only by default. No custom "has mounted" ref/state pattern is needed.

## Common Pitfalls

### Pitfall 1: Historical Messages Animate on Thread Switch

**What goes wrong:** Every message in `messages.map()` renders fresh when switching threads, triggering entrance animations on 10–20 messages simultaneously — disorienting and contrary to requirements ("animating 20 messages on thread switch is disorienting").

**Why it happens:** React unmounts the old thread's MessageList and mounts a new one; all `m.div` elements fire `initial → animate`.

**How to avoid:** Only animate the most recently added message. Implementation approach: pass an `isNew` boolean prop to `UserMessage`/`AssistantMessage`. In `MessageList`, determine "new" as the last item in `messages` that was added after the current thread loaded. The simplest implementation: track a `lastThreadId` ref; when `activeThreadId` changes, mark all current messages as "not new"; subsequent additions are "new".

**Warning signs:** Seeing all messages slide in when clicking a thread in the sidebar.

### Pitfall 2: Animation Fires During SSE Stream

**What goes wrong:** The streaming `AssistantMessage` (passed `isStreaming={true}`) animates on mount, then the finalized message *also* animates when `FINALIZE_STREAMING` moves it from `streamingMessage` to `messages`. This causes a double-animation: one on stream start, one on stream end.

**Why it happens:** `streamingMessage` component unmounts and `messages` re-renders, creating two mount events.

**How to avoid:** Gate `m.div` only on non-streaming messages. The streaming `AssistantMessage` renders a plain `div`. The finalized message in `messages` renders `m.div`. The transition from streaming → finalized is one animation firing (the final mount), which is the correct behavior per ANIM-04.

**Warning signs:** Fade-in animation visible at the start of a response, before any content arrives.

### Pitfall 3: Removed CSS Keyframe Conflicts

**What goes wrong:** The existing `.message { animation: message-enter 180ms ease-out both; }` CSS rule remains active alongside the new `m.div` initial/animate. Both run simultaneously, causing doubled/glitched animation.

**Why it happens:** Forgetting to remove the existing CSS animation when adding Motion.

**How to avoid:** Remove `animation: message-enter 180ms ease-out both` from `.message` CSS rule and the `@keyframes message-enter` block. Also remove the `@media (prefers-reduced-motion: reduce) { .message { animation: none; } }` rule since MotionConfig handles this now.

**Warning signs:** Message entrance looks stuttered or replays.

### Pitfall 4: LazyMotion strict Mode Catches Mixing

**What goes wrong:** If `strict` is added to `<LazyMotion strict>` in the future, any use of `<motion.div>` instead of `<m.div>` inside the boundary will throw at runtime.

**Why it happens:** `motion.div` bundles all features; `m.div` is the lightweight variant.

**How to avoid:** Always import from `"motion/react-m"` for animated elements. `LazyMotion` and `MotionConfig` import from `"motion/react"`.

### Pitfall 5: Sidebar `overflow: hidden` During Transition

**What goes wrong:** During the CSS width transition, sidebar content (thread list items) may overflow and be clipped at partial widths.

**Why it happens:** The sidebar already has `overflow-y: auto` which helps, but the transition from 260px → 56px passes through widths where partially visible text creates visual noise.

**How to avoid:** The sidebar content already uses `overflow: hidden` on thread list items and `white-space: nowrap` for the collapsed state. Verify this is in place. The pure CSS transition handles this gracefully because the content opacity is managed separately (collapsed mode hides text labels).

## Code Examples

Verified patterns from official sources:

### LazyMotion + MotionConfig Root Setup

```tsx
// Source: https://motion.dev/docs/react-lazy-motion
// Source: https://motion.dev/docs/react-motion-config
import { LazyMotion, MotionConfig, domAnimation } from 'motion/react';

// In App.tsx, wrapping FluentProvider
<MotionConfig reducedMotion="user">
  <LazyMotion features={domAnimation}>
    {children}
  </LazyMotion>
</MotionConfig>
```

### Message Entrance (m.div)

```tsx
// Source: https://motion.dev/docs/react-animation
import * as m from 'motion/react-m';

// AssistantMessage — 200ms ease-out (ANIM-01)
// isStreaming guard implements ANIM-04
{isStreaming ? (
  <div className="message assistant-message">
    {/* content */}
  </div>
) : (
  <m.div
    className="message assistant-message"
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.2, ease: 'easeOut' }}
  >
    {/* content */}
  </m.div>
)}
```

### Sidebar CSS Transition (ANIM-05)

```css
/* Source: existing index.css, adjusted easing per spec */
.sidebar {
  transition: width 225ms ease-in-out, min-width 225ms ease-in-out;
}
```

### Feedback Button Scale (ANIM-06)

```css
/* Source: CSS :active pattern — no Motion needed */
.feedback-scale-btn {
  transition: transform 100ms ease-out;
  display: contents; /* or inline-flex depending on layout needs */
}
.feedback-scale-btn:active {
  transform: scale(0.88);
}
@media (prefers-reduced-motion: reduce) {
  .feedback-scale-btn { transition: none; }
  .feedback-scale-btn:active { transform: none; }
}
```

Note: `display: contents` makes the span transparent to layout, so the Fluent Button renders at its natural size while the span receives the `:active` event. Test this approach — if `:active` doesn't propagate correctly through the span, use a wrapping `div` with `display: inline-flex` instead.

### ReducedMotion Behavior Reference

```tsx
// Source: https://motion.dev/docs/react-accessibility
// When reducedMotion="user":
// - transform animations (y: 8 → 0) are DISABLED for users with prefers-reduced-motion
// - opacity animations PERSIST (fade still works)
// - Net effect: reduced-motion users get instant placement, no slide
// The existing CSS media query on .message can be REMOVED (MotionConfig handles it)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `framer-motion` package | `motion` package (import from `"motion/react"`) | Late 2024 | Same API, new package name; framer-motion still works but unmaintained |
| `<motion.div>` globally | `<LazyMotion>` + `<m.div>` | v6+ (established) | 34kb → 15kb bundle for domAnimation features |
| Manual `useReducedMotion` hook | `MotionConfig reducedMotion="user"` | Available since v4+ | Automatic, no per-component code needed |

**Deprecated/outdated:**
- `"framer-motion"` import: replaced by `"motion/react"`. Old package still installs but points to legacy code.
- Manual `prefers-reduced-motion` CSS overrides for Motion-managed animations: not needed when using `MotionConfig reducedMotion="user"`. Keep the CSS override only for CSS-managed animations (sidebar transition, feedback button).

## Open Questions

1. **Historical message animation gate — exact mechanism**
   - What we know: The requirement states only new messages animate; thread-switch bulk renders must not animate.
   - What's unclear: The simplest implementation mechanism — whether to pass `isNew` prop, use a context timestamp, or use `AnimatePresence` with a thread key.
   - Recommendation: Track `lastSwitchTime` in ChatContext or ThreadContext. In `MessageList`, compare each message's `timestamp` to `lastSwitchTime`; only messages with `timestamp >= lastSwitchTime` get `m.div`. This is clean and avoids adding a new prop to every message component.

2. **Feedback button `:active` and display: contents**
   - What we know: `display: contents` makes a span transparent to layout, allowing `:active` propagation.
   - What's unclear: Whether Fluent UI's internal Button structure captures the `:active` state on its own elements before the wrapper span, which could prevent the span from receiving `:active`.
   - Recommendation: Test during implementation. If `display: contents` span doesn't work, wrap in `div` with `display: inline-flex` and verify layout. A CSS class on the Fluent Button's internal `<button>` element via `className` prop is the cleanest if direct styling is needed.

## Sources

### Primary (HIGH confidence)
- `https://motion.dev/docs/react-lazy-motion` — LazyMotion API, domAnimation feature set, import paths
- `https://motion.dev/docs/react-motion-config` — MotionConfig reducedMotion prop options
- `https://motion.dev/docs/react-accessibility` — What reducedMotion="user" enables/disables
- `https://motion.dev/docs/react-animation` — initial/animate/transition API
- `https://motion.dev/docs/react-motion-component` — motion.create(), initial={false} behavior
- `https://motion.dev/docs/react-reduce-bundle-size` — domAnimation vs domMax feature sets, exact bundle sizes

### Secondary (MEDIUM confidence)
- `https://fluent2.microsoft.design/motion` — Fluent 2 motion principles (ease-out, natural, consistent); no numeric tokens found
- npm search: `motion` package current version 12.x, `framer-motion` deprecated in favor of `motion`

### Tertiary (LOW confidence)
- WebSearch: CSS `:active` scale micro-interaction pattern — widely documented, cross-verified with MDN principles
- WebSearch: Fluent UI v9 Button + motion.create() — indirect evidence that v9 forwards refs; not officially documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — motion package is officially documented, locked by prior decisions, version verified
- Architecture: HIGH — all patterns verified against official motion.dev documentation
- Pitfalls: HIGH for double-animation and streaming guard (directly observed in codebase); MEDIUM for historical message animation gate (pattern is sound, exact implementation TBD)
- Sidebar CSS: HIGH — already partially implemented in codebase, only easing tweak needed
- Feedback micro-interaction: HIGH for CSS :active approach; MEDIUM for display:contents behavior

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (motion API is stable; 30-day window)
