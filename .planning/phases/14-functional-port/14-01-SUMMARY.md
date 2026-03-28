---
phase: 14-functional-port
plan: 01
subsystem: ui
tags: [react, typescript, context-api, use-reducer, fetch-api, sse, rest]

# Dependency graph
requires:
  - phase: 13-infrastructure-scaffold
    provides: Flask catch-all route serving React SPA, ATLAS_UI=react toggle, /api/threads and /api/me endpoints
provides:
  - TypeScript types for all shared data shapes (Thread, RawMessage, DisplayMessage, ToolPanelData, SSEEvent, StreamingMessageState, User)
  - Thread CRUD API client (listThreads, createThread, renameThread, deleteThread, getMessages)
  - User session API client (fetchMe, returns null on 401)
  - AuthContext with user/loading/error state, populated from /api/me on mount
  - ThreadContext with useReducer (6 action types), loads threads on mount
  - ChatContext with useReducer (9 action types), streamingMessage kept separate from messages[]
affects:
  - 14-02 (AppLayout shell)
  - 14-03 (ThreadSidebar component)
  - 14-04 (ChatPanel component)
  - 14-05 (streaming hook)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - useReducer for complex state (threads, chat) instead of useState
    - streamingMessage as separate state field, never merged into messages[] during streaming
    - Context + hook pattern (createContext + useContext wrapper that throws on null)

key-files:
  created:
    - frontend/src/types/index.ts
    - frontend/src/api/threads.ts
    - frontend/src/api/me.ts
    - frontend/src/contexts/AuthContext.tsx
    - frontend/src/contexts/ThreadContext.tsx
    - frontend/src/contexts/ChatContext.tsx
  modified: []

key-decisions:
  - "messages.ts skipped — getMessages lives in threads.ts since endpoint is /api/threads/:id/messages"
  - "streamingMessage is a separate ChatState field, never pushed into messages[] until FINALIZE_STREAMING"
  - "BUMP_THREAD updates updated_at to now() and re-sorts array, consistent with research pattern"
  - "fetchMe returns null (not throws) on 401 — unauthenticated is a valid app state"

patterns-established:
  - "Context pattern: createContext<T | null>(null) + hook that throws on null — all 3 contexts use this"
  - "Reducer actions are discriminated unions exported as TypeAction type — enables typed dispatch in components"
  - "API functions throw on non-2xx (except fetchMe 401) — error handling delegated to callers"

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 14 Plan 01: Types, API Clients, and Context Providers Summary

**TypeScript data layer: 7 shared types, 2 API client modules, and 3 useReducer Context providers (AuthContext, ThreadContext, ChatContext) enabling parallel component development**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-28T20:09:17Z
- **Completed:** 2026-03-28T20:11:05Z
- **Tasks:** 2
- **Files modified:** 6 created, 2 deleted (.gitkeep)

## Accomplishments
- Complete TypeScript type definitions for all shared data shapes including SSE event union type
- Thread CRUD API module and user session API module, both typed and throwing on non-OK responses
- Three Context+Reducer providers establishing the full shared state layer for the React app

## Task Commits

Each task was committed atomically:

1. **Task 1: Create TypeScript types and API client modules** - `72ed445` (feat)
2. **Task 2: Create Context providers with useReducer for auth, threads, and chat** - `61aead0` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `frontend/src/types/index.ts` - Thread, RawMessage, DisplayMessage, ToolPanelData, SSEEvent, StreamingMessageState, User
- `frontend/src/api/threads.ts` - listThreads, createThread, renameThread, deleteThread, getMessages
- `frontend/src/api/me.ts` - fetchMe (returns null on 401, throws on other errors)
- `frontend/src/contexts/AuthContext.tsx` - AuthProvider + useAuth; fetches /api/me on mount
- `frontend/src/contexts/ThreadContext.tsx` - ThreadProvider + useThreads; 6 action types; loads on mount
- `frontend/src/contexts/ChatContext.tsx` - ChatProvider + useChat; 9 action types; streamingMessage separate from messages[]
- `frontend/src/api/.gitkeep` - deleted (placeholder removed)
- `frontend/src/hooks/.gitkeep` - deleted (placeholder removed)

## Decisions Made
- `messages.ts` was skipped — `getMessages` belongs in `threads.ts` since the endpoint is `/api/threads/:id/messages`
- `streamingMessage` is a dedicated state field in ChatContext, never pushed into `messages[]` until `FINALIZE_STREAMING` — this is the critical anti-pattern prevention from the research
- `BUMP_THREAD` updates `updated_at` to current ISO timestamp and re-sorts the array by descending `updated_at`
- `fetchMe` returns `null` on 401 (not throw) — unauthenticated is an expected valid state, not an error

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Data layer is complete and compiles cleanly (`tsc --noEmit` passes with zero errors)
- All context providers, hooks, types, and API functions are ready for import by component plans 14-02 through 14-05
- Plan 14-02 (AppLayout shell) can begin immediately — it depends on AuthProvider, ThreadProvider, ChatProvider, and useAuth/useThreads/useChat

---
*Phase: 14-functional-port*
*Completed: 2026-03-28*
