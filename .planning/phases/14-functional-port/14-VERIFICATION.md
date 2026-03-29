---
phase: 14-functional-port
verified: 2026-03-29T12:59:34Z
status: gaps_found
score: 21/22 must-haves verified
gaps:
  - truth: Profile cards render with photo or initials placeholder
    status: partial
    reason: ProfileCard onError only hides the img with no initials fallback. 14-04-PLAN.md line 164 requires onerror fallback to initials.
    artifacts:
      - path: frontend/src/components/ChatPane/ProfileCard.tsx
        issue: onError hides img but does not render initials fallback
    missing:
      - Compute initials from displayName (first letters of first/last word)
      - Render a sibling div.profile-card-initials when photo fails
      - CSS or React state to toggle initials vs photo
---

# Phase 14: Functional Port Verification Report

**Phase Goal:** All existing chat features run in React components with identical behavior: SSE streaming, thread management, message rendering, tool panels, profile cards, input area. DEBT-01 and DEBT-02 fixed during the port.

**Verified:** 2026-03-29T12:59:34Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Sending a message streams tokens; Escape cancels with [response cancelled] | VERIFIED | useStreamingMessage.ts: fetch POST /chat/stream with ReadableStream pump; CANCEL_STREAMING appends the text; InputArea Escape calls onCancel() when isStreaming |
| 2 | Thread CRUD and auto-naming; switching threads loads correct history with tool panels (DEBT-01) | VERIFIED | ThreadList.tsx handles all CRUD; getMessages + parseHistoricalMessages pairs tool_calls with tool results |
| 3 | Copy-to-clipboard on new and historical messages (DEBT-02) | VERIFIED | CopyButton accepts getText function; AssistantMessage passes contentRef.current; ToolPanel passes result |
| 4 | Tool panels expand/collapse; profile cards render with photo or initials placeholder | PARTIAL | ToolPanel uses native details/summary (VERIFIED); ProfileCard hides photo on error with no initials fallback (FAILED) |
| 5 | All components compile and pass TypeScript checks | VERIFIED | npm run build: 0 errors, 380.95 kB bundle; npx tsc --noEmit: 0 errors |

**Score:** 4.5/5 truths verified (1 partial)

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| frontend/src/types/index.ts | VERIFIED | Thread, RawMessage, ToolPanelData, DisplayMessage, SSEEvent (5 variants), StreamingMessageState, User |
| frontend/src/api/threads.ts | VERIFIED | listThreads, createThread, renameThread, deleteThread, getMessages |
| frontend/src/api/me.ts | VERIFIED | fetchMe returns User or null on 401 |
| frontend/src/contexts/AuthContext.tsx | VERIFIED | fetchMe() in useEffect; exposes user, loading, error |
| frontend/src/contexts/ThreadContext.tsx | VERIFIED | useReducer with 6 action types; listThreads loaded on mount |
| frontend/src/contexts/ChatContext.tsx | VERIFIED | 9 action types; FINALIZE_STREAMING and CANCEL_STREAMING both produce DisplayMessage |
| frontend/src/hooks/useStreamingMessage.ts | VERIFIED | fetch+ReadableStream pump; all 5 SSE event types; AbortController in useRef; rAF batching |
| frontend/src/utils/parseHistoricalMessages.ts | VERIFIED | Look-ahead pairs tc.id with tool_call_id; pendingToolPanels accumulate across multi-turn loops (DEBT-01) |
| frontend/src/components/Sidebar/ThreadList.tsx | VERIFIED | Maps threads array; handleSelectThread loads history via getMessages + parseHistoricalMessages |
| frontend/src/components/Sidebar/ThreadItem.tsx | VERIFIED | Controlled input with value/onChange/onBlur; zero contentEditable occurrences |
| frontend/src/components/ChatPane/UserMessage.tsx | VERIFIED | Renders content as text node, no markdown |
| frontend/src/components/ChatPane/AssistantMessage.tsx | VERIFIED | MarkdownRenderer + rehype-sanitize; contentRef.current for accurate copy during streaming |
| frontend/src/components/ChatPane/MarkdownRenderer.tsx | VERIFIED | react-markdown with rehypePlugins=[rehypeSanitize] |
| frontend/src/components/ChatPane/ToolPanel.tsx | VERIFIED | Native details/summary elements for expand/collapse |
| frontend/src/components/shared/CopyButton.tsx | VERIFIED | Props: { getText: () => string }; navigator.clipboard.writeText(getText()) |
| frontend/src/components/ChatPane/ProfileCard.tsx | PARTIAL | Photo wired to /api/photo/id?name=...; onError hides img with no initials fallback |
| frontend/src/components/ChatPane/SearchResultCard.tsx | VERIFIED | Parses resultJson.results array; renders name/jobTitle/dept/email per item |
| frontend/src/components/ChatPane/MessageList.tsx | VERIFIED | Maps messages array; renders streamingMessage separately with isStreaming=true |
| frontend/src/components/ChatPane/InputArea.tsx | VERIFIED | Math.min(scrollHeight, 200)px; Enter sends, Shift+Enter newline, Escape cancels when streaming |
| frontend/src/App.tsx - provider nesting | VERIFIED | FluentProvider > AuthProvider > AuthGuard > ThreadProvider > ChatProvider > AppLayout |
| frontend/src/App.tsx - dark mode | VERIFIED | localStorage key atlas-theme; data-theme attribute toggled and initialized from storage |

## Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| AppLayout.tsx handleSend | /chat/stream | startStream(message, threadId) | WIRED |
| useStreamingMessage | ReadableStream pump | fetch POST /chat/stream | WIRED |
| SSE text event | ChatContext APPEND_STREAMING_CHUNK | rAF-batched onText callback | WIRED |
| SSE thread_named event | ThreadContext RENAME_THREAD + BUMP_THREAD | onThreadNamed callback | WIRED |
| SSE done event | ChatContext FINALIZE_STREAMING | onDone callback | WIRED |
| AbortController | useRef not useState | useRef AbortController null at hook line 22 | WIRED |
| Text delta batching | requestAnimationFrame | pendingTextRef + scheduleFlush | WIRED |
| ThreadList thread switch | parseHistoricalMessages | getMessages + SET_MESSAGES | WIRED |
| Escape key | cancelStream | InputArea onKeyDown then onCancel | WIRED |
| CANCEL_STREAMING | [response cancelled] suffix | chatReducer | WIRED |
| ProfileCard photo error | initials fallback | onError handler | NOT WIRED - img hidden, no fallback rendered |

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| SSE streaming with real-time tokens | SATISFIED | - |
| Escape cancels stream, appends [response cancelled] | SATISFIED | - |
| Thread CRUD (create, rename, delete) | SATISFIED | - |
| Thread auto-naming via thread_named SSE event | SATISFIED | - |
| Thread switch renders correct history with tool panels (DEBT-01) | SATISFIED | - |
| Copy-to-clipboard on new and historical messages (DEBT-02) | SATISFIED | - |
| Tool panels expand/collapse with native details element | SATISFIED | - |
| Profile cards with photo or initials placeholder | PARTIAL | Initials fallback missing from ProfileCard |
| Search result cards render colleague matches | SATISFIED | - |
| npm run build succeeds | SATISFIED | 0 errors, 380.95 kB bundle |
| npx tsc --noEmit passes | SATISFIED | 0 errors |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| frontend/src/components/ChatPane/ProfileCard.tsx | 42-44 | onError hides img with no initials rendered | Warning | Profile cards show blank avatar area when photo unavailable |

No TODO/FIXME/placeholder patterns found in any component file. No empty return null patterns blocking rendering.

## Human Verification Required

### 1. First Token Arrival Latency
**Test:** Send a message and observe time to first visible character in the streaming bubble
**Expected:** First text token appears within 3 seconds
**Why human:** Network and backend response time cannot be verified from static analysis

### 2. Escape Key Cancel During Live Stream
**Test:** While a response is actively streaming, press Escape in the input area
**Expected:** Streaming stops; [response cancelled] appended to message bubble
**Why human:** Requires live streaming state to verify keyboard event wiring end-to-end

### 3. Historical Tool Panels on Thread Switch
**Test:** Switch to a thread that previously used get_colleague_profile or search_colleagues
**Expected:** ProfileCard or SearchResultCard renders inline in the historical message
**Why human:** Requires backend data with stored tool call history

### 4. Dark Mode Persistence Across Reload
**Test:** Toggle dark mode, reload the page
**Expected:** Page loads in dark mode; localStorage key atlas-theme survives reload
**Why human:** localStorage behavior requires browser runtime

## Gaps Summary

One gap identified. ProfileCard renders the photo correctly from /api/photo/id?name=... but when the image fails to load, the onError handler only sets style.display = none. No initials fallback element is rendered. The plan (14-04-PLAN.md line 164) explicitly required onerror fallback to initials and the success criterion states photo or initials placeholder.

Fix scope: compute initials from displayName (e.g. first characters of first and last word), use React useState to track photo load failure, and conditionally render either the img or a div.profile-card-initials containing the computed initials.

All other 21 of 22 must-haves are fully verified. The build and TypeScript checks pass with zero errors.

---

_Verified: 2026-03-29T12:59:34Z_
_Verifier: Claude (gsd-verifier)_
