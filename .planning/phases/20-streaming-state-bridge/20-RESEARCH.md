# Phase 20: Streaming State Bridge - Research

**Researched:** 2026-03-30
**Domain:** React state wiring, Vite dev proxy configuration, SSE streaming lifecycle
**Confidence:** HIGH

## Summary

Phase 20 closes two precisely-diagnosed integration gaps from the v1.2 milestone audit. Neither gap requires new libraries, new patterns, or architectural changes. Both are single-file surgical edits with low blast radius.

**Gap 1 — isStreaming state not bridged:** `AppLayout.tsx` line 19 reads `isStreaming` from `ChatContext` (always `false`) instead of reading the return value from `useStreamingMessage`. The hook returns `isStreaming` correctly on line 224 of `useStreamingMessage.ts`, but `AppLayout` destructures only `{ startStream, cancelStream }` from the hook call. The fix is a one-line change: destructure `isStreaming` from the hook return and use it as the source of truth, replacing or supplementing the context value. All downstream components (`InputArea`, `ThreadList`) are already wired correctly — they will work as soon as they receive a true `isStreaming`.

**Gap 2 — /chat/stream not proxied:** `vite.config.ts` has proxy entries for `/api`, `/login`, `/logout`, `/auth` but not `/chat`. The streaming fetch call in `useStreamingMessage.ts` POSTs to `/chat/stream`. In dev mode, this hits Vite's dev server and returns 404. Fix is adding one entry to the proxy object.

**Primary recommendation:** Destructure `isStreaming` from `useStreamingMessage` in `AppLayout`, dispatch `SET_STREAMING` to context via `useEffect` when the hook's value changes, and add `/chat` proxy to `vite.config.ts`. Remove the `SET_STREAMING` dead code comment once the dispatch is written.

## Standard Stack

No new libraries required. This phase operates entirely within the existing stack.

### Core (already installed)
| Library | Version | Purpose | Relevance |
|---------|---------|---------|-----------|
| React 19 | 19.x | State, hooks, effects | `useEffect` for bridging hook state to context |
| Vite | 5.x | Dev server + proxy | `server.proxy` config for `/chat` |
| TypeScript | 5.x | Type checking | Existing `isStreaming: boolean` types already correct |

### No new dependencies needed
All patterns use React built-ins. The fix is purely wiring — no packages to install.

## Architecture Patterns

### Pattern 1: Hook-to-Context State Bridge via useEffect

**What:** When a hook manages local state that context consumers need, bridge it with `useEffect` dispatching to context on every change.

**When to use:** The hook's state is the authoritative source (it knows when streaming starts/stops). Context is the distribution mechanism for components that don't have direct access to the hook's return value.

**Two valid approaches exist — choose based on component structure:**

**Option A: dispatch SET_STREAMING from AppLayout via useEffect (recommended)**
```typescript
// Source: AppLayout.tsx — bridge hook state to context
const { startStream, cancelStream, isStreaming: hookIsStreaming } = useStreamingMessage({ ... });

useEffect(() => {
  chatDispatch({ type: 'SET_STREAMING', isStreaming: hookIsStreaming });
}, [hookIsStreaming, chatDispatch]);

// InputArea still receives isStreaming from context (no JSX change needed)
// ThreadList reads from context (no JSX change needed)
```

**Option B: pass hook's isStreaming directly as prop (simpler, avoids double source of truth)**
```typescript
// AppLayout.tsx
const { startStream, cancelStream, isStreaming } = useStreamingMessage({ ... });
// Remove: const { isStreaming, dispatch: chatDispatch } = useChat();
// Keep: const { dispatch: chatDispatch } = useChat();

// InputArea already receives isStreaming={isStreaming} as prop — no change
// ThreadList reads isStreaming from context — STILL BROKEN with this option
```

**Option A is correct** because `ThreadList` reads `isStreaming` from `ChatContext` directly (line 18 of `ThreadList.tsx`), not from props. It must receive the real value via context. Option B would fix `InputArea` but leave `ThreadList` broken.

**Confirmed: Option A is the right fix.**

### Pattern 2: Vite Proxy Configuration

**What:** Add `/chat` to the existing proxy block in `vite.config.ts`.

**When to use:** Any Flask route not already proxied that the frontend calls via relative URL.

**Example:**
```typescript
// Source: frontend/vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    '/login': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    '/logout': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    '/auth': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    '/chat': { target: 'http://127.0.0.1:5000', changeOrigin: true },  // ADD THIS
  },
},
```

**Note:** `/chat` is a prefix match. This proxies `/chat/stream` and any other `/chat/*` routes to Flask. No SSE-specific proxy configuration is needed — Vite's proxy handles streaming responses transparently via `http-proxy` which supports chunked transfer encoding.

### Pattern 3: SET_STREAMING Dead Code Cleanup

**What:** `SET_STREAMING` action type in `ChatContext.tsx` was dead code — declared in the union type and handled in the reducer, but never dispatched. After implementing Option A above, it becomes live and used code. No removal needed.

**After Phase 20:** `SET_STREAMING` is dispatched from `AppLayout`'s `useEffect`. The action type comment "dead code" (if any) should be removed.

### Anti-Patterns to Avoid

- **Don't remove SET_STREAMING from the reducer:** Once the `useEffect` dispatch is added, the action is actively used. FINALIZE_STREAMING and CANCEL_STREAMING already set `isStreaming: false` in the reducer — the `SET_STREAMING: true` dispatch covers the start transition only.
- **Don't use Option B (prop-only approach):** `ThreadList` reads context directly — a prop-only fix leaves thread-switch abort broken.
- **Don't add SSE-specific headers to the Vite proxy:** `changeOrigin: true` is sufficient. Adding `ws: true` or custom headers would be over-engineering.
- **Don't guard the useEffect with a condition:** The effect should fire on every change to `hookIsStreaming`, including transitions back to `false` (though FINALIZE_STREAMING and CANCEL_STREAMING already handle false transitions in the reducer).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Proxy SSE to Flask | Custom Express middleware | Vite's built-in proxy | Vite proxy supports streaming out of the box |
| State synchronization | Polling or event emitter | `useEffect` + `dispatch` | Standard React pattern, zero overhead |

## Common Pitfalls

### Pitfall 1: Double Source of Truth for isStreaming

**What goes wrong:** After bridging, both the hook's local `isStreaming` and context's `isStreaming` exist. If the `useEffect` fires asynchronously, there's a one-render window where they differ. Components reading context will lag one render behind the hook.

**Why it happens:** React batches state updates, so the hook's `setIsStreaming(true)` and the context's `dispatch({ type: 'SET_STREAMING', isStreaming: true })` are in separate render cycles.

**How to avoid:** This is acceptable and expected. The one-render lag is imperceptible to users (< 16ms). The important thing is that `InputArea` receives `isStreaming` from context (via the existing `const { isStreaming } = useChat()` in `AppLayout`) — by the time the user could press Stop, the state will be synchronized.

**Warning signs:** If Stop button flickers on/off rapidly, check that FINALIZE_STREAMING and CANCEL_STREAMING reducers correctly set `isStreaming: false` (they already do — lines 64, 79, 85, 100 in `ChatContext.tsx`).

### Pitfall 2: cancelStream Does Not Dispatch CANCEL_STREAMING

**What goes wrong:** `cancelStream()` in the hook only calls `abortControllerRef.current?.abort()`. The `onCancel` callback (which dispatches `CANCEL_STREAMING`) is invoked from within the pump loop's abort detection path — not synchronously from `cancelStream`. If `cancelStream` is called when there's no active fetch (edge case), `onCancel` may never fire.

**Why it happens:** The abort triggers `AbortError` in the fetch, which routes to the catch block calling `optionsRef.current.onCancel()`. This is async, not synchronous.

**How to avoid:** This is existing correct behavior and not a Phase 20 concern. The pump loop handles abort → `onCancel` → `CANCEL_STREAMING` → `isStreaming: false` correctly for the normal case. No change needed.

### Pitfall 3: useEffect Dependency Array

**What goes wrong:** If `chatDispatch` is omitted from the `useEffect` dependency array, ESLint's `react-hooks/exhaustive-deps` rule will warn or error.

**How to avoid:** Include both `hookIsStreaming` and `chatDispatch` in the dependency array. `chatDispatch` is stable (from `useReducer`) so it won't cause extra re-runs.

```typescript
useEffect(() => {
  chatDispatch({ type: 'SET_STREAMING', isStreaming: hookIsStreaming });
}, [hookIsStreaming, chatDispatch]);
```

### Pitfall 4: Thread Switch Abort Race

**What goes wrong:** `handleSelectThread` calls `onCancelStream()` synchronously, then immediately dispatches `SET_ACTIVE` and clears messages. If `cancelStream` triggers an async `onCancel` → `CANCEL_STREAMING` dispatch that runs after `SET_MESSAGES`, the cancelled message could be pushed to an already-cleared message list.

**Why it happens:** The abort is async (fetch `AbortError` catch path).

**How to avoid:** This is existing behavior from Phase 14 and is acceptable — the race window is < 1 render. `CANCEL_STREAMING` builds a finalized cancelled message from `streamingMessage` state, and `SET_MESSAGES: []` clears `messages[]` but not `streamingMessage`. The finalized message appends to messages after the clear, which is correct. No change needed here.

## Code Examples

### Fix 1: AppLayout.tsx — Bridge isStreaming from hook to context

```typescript
// frontend/src/components/AppLayout.tsx
// Change lines 19-21 from:
const { isStreaming, dispatch: chatDispatch } = useChat();
const { startStream, cancelStream } = useStreamingMessage({ ... });

// To:
const { dispatch: chatDispatch } = useChat();
const { startStream, cancelStream, isStreaming: hookIsStreaming } = useStreamingMessage({ ... });

// Add after useStreamingMessage call:
useEffect(() => {
  chatDispatch({ type: 'SET_STREAMING', isStreaming: hookIsStreaming });
}, [hookIsStreaming, chatDispatch]);

// InputArea prop stays the same — reads isStreaming from context:
// <InputArea isStreaming={isStreaming} ... />
// But now isStreaming must come from context read, not the hook variable.
// So either keep: const { isStreaming } = useChat() or read from context
// in a separate destructure after the chatDispatch destructure.
```

**Exact implementation approach:**
```typescript
// Keep reading isStreaming from context for JSX (it's already wired to InputArea):
const { isStreaming, dispatch: chatDispatch } = useChat();

// Read hook's isStreaming under a different name:
const { startStream, cancelStream, isStreaming: hookIsStreaming } = useStreamingMessage({ ... });

// Bridge hook → context:
useEffect(() => {
  chatDispatch({ type: 'SET_STREAMING', isStreaming: hookIsStreaming });
}, [hookIsStreaming, chatDispatch]);

// JSX unchanged — InputArea still receives isStreaming={isStreaming} from context
```

This is the minimal change: one `useEffect` added, variable name `hookIsStreaming` added to hook destructure. All JSX unchanged.

### Fix 2: vite.config.ts — Add /chat proxy

```typescript
// frontend/vite.config.ts
// Add to proxy object:
'/chat': { target: 'http://127.0.0.1:5000', changeOrigin: true },
```

### Verification: What becomes true after Fix 1

After the `useEffect` bridge:
- `chatContext.isStreaming` transitions to `true` within 1 render of `startStream()` being called
- `InputArea` receives `isStreaming={true}` — Stop button renders, Escape handler fires
- `ThreadList` reads `isStreaming: true` from context — `handleSelectThread` calls `onCancelStream()` when switching threads
- `AssistantMessage` already uses `isStreaming={true}` hardcoded on the streaming message render (line 73 MessageList.tsx) — no change needed there

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| N/A — this is a bug fix | N/A | N/A | Bridging hook state to context is standard React |

No state-of-the-art changes required. This is straightforward React pattern application.

**Dead code status after Phase 20:**
- `SET_STREAMING` action type: was dead code → becomes live code after `useEffect` dispatch is added

## Open Questions

None. The diagnosis is complete, the fix is deterministic, and no external research is needed.

1. **Should isStreaming be removed from ChatContext entirely?**
   - What we know: Some components (ThreadList) read it from context; removing it would require prop drilling through AppLayout → sidebar → ThreadList
   - What's unclear: Nothing — context is the right distribution mechanism here
   - Recommendation: Keep isStreaming in context, bridge via useEffect

2. **Should the /chat proxy use streaming-specific options?**
   - What we know: Vite's underlying `http-proxy` supports streaming by default; `changeOrigin: true` is sufficient
   - Recommendation: No additional proxy options needed

## Sources

### Primary (HIGH confidence)
- Direct code reading of `AppLayout.tsx`, `useStreamingMessage.ts`, `ChatContext.tsx`, `InputArea.tsx`, `ThreadList.tsx`, `MessageList.tsx`, `vite.config.ts` — all files read in this session
- v1.2-MILESTONE-AUDIT.md — precise gap diagnosis with file references

### Secondary (MEDIUM confidence)
- React documentation pattern: `useEffect` for syncing external state to React state is a standard documented React pattern (React docs: "You Might Not Need an Effect" — this is one of the cases WHERE you do need an effect: syncing with an external system/non-React state)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, existing dependencies confirmed by reading package.json structure
- Architecture: HIGH — code read directly, root cause confirmed, fix is deterministic
- Pitfalls: HIGH — derived from reading actual async flow in useStreamingMessage.ts
- Vite proxy: HIGH — vite.config.ts read directly, one-line fix confirmed

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable codebase, no external dependencies involved)
