---
phase: 20
plan: "01"
name: streaming-state-bridge
subsystem: frontend-state
tags: [vite, proxy, SSE, streaming, ChatContext, useEffect, AppLayout]

dependencies:
  requires: [14-01, 14-02, 14-03]
  provides: ["/chat proxy in dev server", "isStreaming bridge from hook to context"]
  affects: [20-02]

tech-stack:
  added: []
  patterns: ["useEffect state bridge from hook to context", "Vite dev server proxy for SSE paths"]

key-files:
  created: []
  modified:
    - frontend/vite.config.ts
    - frontend/src/components/AppLayout.tsx

decisions:
  - id: "/chat covers all sub-paths"
    summary: "Single '/chat' proxy entry proxies /chat/stream and all other sub-paths; no separate /chat/stream entry needed"
  - id: "useEffect bridge is unconditional"
    summary: "No conditional guard on SET_STREAMING dispatch — chatDispatch is idempotent and the one-render lag (<16ms) is acceptable"
  - id: "hookIsStreaming alias"
    summary: "isStreaming from hook aliased as hookIsStreaming to avoid shadowing isStreaming already destructured from useChat()"

metrics:
  duration: "~4 minutes"
  completed: "2026-03-30"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 20 Plan 01: Streaming State Bridge Summary

Two-file fix closing the two root-cause gaps (CHAT-03 and FRAME-08) from the v1.2 milestone audit: missing /chat proxy in Vite dev server, and missing bridge from useStreamingMessage's isStreaming to ChatContext so all consuming components see accurate streaming state.

## What Was Built

### Task 1 — /chat Vite Proxy (FRAME-08)
Added `/chat` proxy entry to `vite.config.ts` server.proxy targeting `http://127.0.0.1:5000` with `changeOrigin: true`. Placed immediately after the `/api` entry. This single entry covers `/chat/stream` and all other sub-paths, so SSE fetch requests in dev mode are correctly forwarded to Flask instead of returning a Vite 404.

### Task 2 — isStreaming State Bridge (CHAT-03)
In `AppLayout.tsx`:
- Added `useEffect` to the React import alongside `useCallback` and `useState`.
- Destructured `isStreaming` from `useStreamingMessage` return as `hookIsStreaming` to avoid shadowing the same-named value already in scope from `useChat()`.
- Added a `useEffect` immediately after the hook call that dispatches `SET_STREAMING` to ChatContext whenever `hookIsStreaming` changes.

ChatContext is now the single authoritative source of `isStreaming` for all consumers:
- `InputArea` receives it as a prop from context (line 113, unchanged).
- `ThreadList` reads it via `useChat()` (line 18, unchanged).

The `SET_STREAMING` action and reducer case in `ChatContext.tsx` were already present and are now actively used.

## Verification

- `npx tsc --noEmit` — zero errors
- `npm run build` — succeeded (389KB bundle, 2251 modules)
- `npx eslint src/components/AppLayout.tsx` — zero lint errors
- `SET_STREAMING` confirmed present in ChatContext.tsx action union (line 28) and reducer (line 104)
- `isStreaming` confirmed still read from `useChat()` in ThreadList.tsx (line 18)

## Deviations from Plan

None — plan executed exactly as written.

## Next Phase Readiness

Phase 20 Plan 02 can now proceed. The streaming state bridge is live and both proxy gaps are closed. Plan 02 targets the Stop button rendering and Escape/thread-switch abort behaviour that depends on these fixes.
