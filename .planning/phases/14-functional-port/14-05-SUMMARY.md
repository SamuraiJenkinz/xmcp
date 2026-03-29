---
phase: 14-functional-port
plan: 05
subsystem: ui
tags: [react, fluent-ui, sse, streaming, dark-mode, auth-guard, provider-composition]

# Dependency graph
requires:
  - phase: 14-01
    provides: AuthContext, ThreadContext, ChatContext, all types
  - phase: 14-02
    provides: useStreamingMessage hook with SSE, parseHistoricalMessages
  - phase: 14-03
    provides: ThreadList component with sidebar thread CRUD
  - phase: 14-04
    provides: MessageList and all ChatPane rendering components
provides:
  - InputArea: auto-resize textarea, Enter/Shift+Enter/Escape shortcuts, Send/Stop toggle
  - Header: user info, dark mode toggle (synced to FluentProvider + data-theme), logout link
  - AppLayout: top-level layout wiring ThreadList + MessageList + InputArea + useStreamingMessage
  - App.tsx: FluentProvider > AuthProvider > AuthGuard > ThreadProvider > ChatProvider > AppLayout
  - Full functional parity with vanilla JS atlas chat application
  - Phase 14 gate cleared — all 7 regression smoke tests passed (human-verified)
affects: [15-visual-redesign, 16-fluent-ui-migration, 17-fluent-ui-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Theme state lifted to App.tsx root, passed down to FluentProvider and Header via props
    - AuthGuard as inner component inside AuthProvider, outside ThreadProvider — enforces auth before context initialization
    - data-theme attribute set on documentElement at module load (before React render) for CSS variable hydration
    - useStreamingMessage callbacks dispatch to both ChatContext and ThreadContext from AppLayout
    - import type enforcement required for verbatimModuleSyntax — all type-only imports must use import type syntax

key-files:
  created:
    - frontend/src/components/ChatPane/InputArea.tsx
    - frontend/src/components/ChatPane/Header.tsx
    - frontend/src/components/AppLayout.tsx
  modified:
    - frontend/src/App.tsx
    - frontend/src/hooks/useStreamingMessage.ts (import type fix)
    - frontend/src/utils/parseHistoricalMessages.ts (import type fix)

key-decisions:
  - "Theme state owned by App.tsx, passed as props — avoids context for a single-value concern"
  - "AuthGuard redirects on user === null (not loading) — prevents flash redirect during auth fetch"
  - "data-theme set on module load before React renders — CSS variables work without FOUC"
  - "import type required in useStreamingMessage.ts and parseHistoricalMessages.ts — verbatimModuleSyntax enforcement"

patterns-established:
  - "Provider nesting order: FluentProvider > AuthProvider > AuthGuard > ThreadProvider > ChatProvider > AppLayout"
  - "Dual-context dispatch in AppLayout: streaming callbacks dispatch to both ChatContext and ThreadContext"
  - "import type syntax required for all type-only imports in this codebase (verbatimModuleSyntax)"

# Metrics
duration: 20min
completed: 2026-03-28
---

# Phase 14 Plan 05: App Layout Wiring and Integration Summary

**InputArea + Header + AppLayout + App.tsx root wiring closes the functional port — all 5 React components connected through shared contexts, SSE streaming verified end-to-end, dark mode and auth guard in place, full parity with vanilla JS confirmed by human smoke test**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-28T00:00:00Z
- **Completed:** 2026-03-28T00:20:00Z
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint, approved)
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments
- Delivered InputArea with controlled textarea, 200px max auto-resize matching app.js resizeInput(), Enter/Shift+Enter/Escape keyboard shortcuts, and Send/Stop button toggle gated on isStreaming
- Delivered Header with user display name, sun/moon dark mode toggle synced to both FluentProvider webLightTheme/webDarkTheme and data-theme CSS attribute, and logout link to existing Flask /logout route
- Delivered AppLayout wiring all prior components (ThreadList, MessageList, InputArea, Header) together with useStreamingMessage dispatching to both ChatContext and ThreadContext
- Rewrote App.tsx with correct provider nesting (FluentProvider > AuthProvider > AuthGuard > ThreadProvider > ChatProvider) and theme state at root level
- Human verification confirmed full functional parity: streaming, thread CRUD, markdown rendering, tool panels, profile cards, copy-to-clipboard (DEBT-02), dark mode persistence, keyboard shortcuts all working

## Task Commits

Each task was committed atomically:

1. **Task 1: Create InputArea with auto-resize, keyboard shortcuts, and streaming integration** - `2ccede5` (feat)
2. **Task 2: Create Header, AppLayout, and wire App.tsx with all providers** - `47337a1` (feat)
3. **STATE.md update — tasks 1-2 complete, paused at checkpoint** - `48c398f` (docs)

**Plan metadata:** (docs: complete plan — this commit)

## Files Created/Modified
- `frontend/src/components/ChatPane/InputArea.tsx` - Auto-resize textarea (200px max), Enter to send, Shift+Enter newline, Escape to cancel stream, Send/Stop button toggle, auto-focus on mount
- `frontend/src/components/ChatPane/Header.tsx` - User displayName/email, sun/moon dark mode toggle, logout link; accepts theme + onToggleTheme props
- `frontend/src/components/AppLayout.tsx` - Sidebar (ThreadList) + chat pane (Header + MessageList + InputArea) layout; owns handleSend and handleCancel; wires useStreamingMessage to both contexts
- `frontend/src/App.tsx` - Rewritten: theme state at root, FluentProvider > AuthProvider > AuthGuard > ThreadProvider > ChatProvider > AppLayout provider nesting
- `frontend/src/hooks/useStreamingMessage.ts` - Fixed type-only imports to use `import type` (verbatimModuleSyntax)
- `frontend/src/utils/parseHistoricalMessages.ts` - Fixed type-only imports to use `import type` (verbatimModuleSyntax)

## Decisions Made
- **Theme state at App.tsx root:** FluentProvider requires the theme prop at its own level. Lifting to App.tsx is the only correct placement — passing it down to Header and FluentProvider via props avoids a dedicated theme context for a single scalar value.
- **AuthGuard redirects on `user === null` not `!user`:** Distinguishes the unauthenticated state from the loading state; prevents a flash redirect to /login while the auth fetch is in flight.
- **data-theme attribute set at module load:** A top-level `document.documentElement.setAttribute('data-theme', ...)` call runs before React renders, preventing a flash of unstyled content for users whose localStorage has dark mode set.
- **import type fix in pre-existing files:** `verbatimModuleSyntax` in tsconfig requires `import type` for type-only imports. Two files from earlier plans (useStreamingMessage.ts, parseHistoricalMessages.ts) used value-import style for types, blocking `npm run build`. Fixed as a Rule 3 blocking issue.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed value-import style for types in useStreamingMessage.ts and parseHistoricalMessages.ts**
- **Found during:** Task 2 (App.tsx wiring — running `npm run build` verification)
- **Issue:** TypeScript `verbatimModuleSyntax` enforcement requires `import type` for type-only imports. Both files used `import { SSEEvent, ToolPanelData }` (value-import syntax) for types. Production build failed with TS1484 errors.
- **Fix:** Changed to `import type { SSEEvent, ToolPanelData }` in both files
- **Files modified:** `frontend/src/hooks/useStreamingMessage.ts`, `frontend/src/utils/parseHistoricalMessages.ts`
- **Verification:** `npm run build` completed successfully after fix
- **Committed in:** `47337a1` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix was required for production build correctness. No scope creep.

## Issues Encountered
None beyond the import type deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 14 functional port is complete. All 5 plans shipped. All 7 regression smoke tests passed (human-verified at checkpoint).
- Phase 15 (Visual Redesign) can begin. The React app is the active UI target — ATLAS_UI=react is production-ready.
- Open concerns carried forward:
  - [Phase 13 gate]: Verify IIS ARR responseBufferLimit="0" before production deployment if ARR is in serving path
  - [Phase 17 evaluate]: @fluentui-copilot/react-copilot-chat fitness for Atlas tool panels — spike at Phase 16/17 start
  - [Phase 17 prereq]: Confirm thread created_at column exists in SQLite schema before sidebar recency grouping

---
*Phase: 14-functional-port*
*Completed: 2026-03-28*
