---
phase: 14-functional-port
plan: 04
subsystem: ui
tags: [react, react-markdown, rehype-sanitize, markdown, streaming, copy-clipboard, tool-panels]

# Dependency graph
requires:
  - phase: 14-01
    provides: DisplayMessage, ToolPanelData, StreamingMessageState types and ChatContext
  - phase: 14-02
    provides: ChatContext dispatch actions for streaming and finalized messages
provides:
  - MarkdownRenderer component (react-markdown + rehype-sanitize)
  - CopyButton with lazy getText() for streaming/historical parity (DEBT-02 fix)
  - ToolPanel with native details/summary, JSON pretty-print, copy button
  - UserMessage plain-text renderer
  - AssistantMessage with tool panel routing, contentRef copy, streaming cursor
  - ProfileCard ported from app.js addProfileCard()
  - SearchResultCard ported from app.js addSearchCards()
  - MessageList with auto-scroll-near-bottom behavior
affects: [14-05, 15-visual-redesign, 17-fluent-ui-polish]

# Tech tracking
tech-stack:
  added:
    - react-markdown@^10.1.0
    - rehype-sanitize@^6.0.0
  patterns:
    - Lazy getText() prop on CopyButton enables clipboard access during streaming (DEBT-02 fix pattern)
    - contentRef + useEffect pattern in AssistantMessage syncs ref to latest prop without stale closure
    - Tool panel routing by tool name inside AssistantMessage (not MessageList)
    - Auto-scroll only when isNearBottom (<100px from bottom) to preserve user scroll position

key-files:
  created:
    - frontend/src/components/ChatPane/MarkdownRenderer.tsx
    - frontend/src/components/ChatPane/ToolPanel.tsx
    - frontend/src/components/ChatPane/UserMessage.tsx
    - frontend/src/components/ChatPane/AssistantMessage.tsx
    - frontend/src/components/ChatPane/ProfileCard.tsx
    - frontend/src/components/ChatPane/SearchResultCard.tsx
    - frontend/src/components/ChatPane/MessageList.tsx
    - frontend/src/components/shared/CopyButton.tsx
  modified:
    - frontend/package.json (added react-markdown, rehype-sanitize)
    - frontend/package-lock.json (124 new packages)

key-decisions:
  - "CopyButton accepts getText: () => string — lazy evaluation at click time, not static string (DEBT-02 fix)"
  - "ToolPanel uses native <details>/<summary> — no Fluent UI Accordion (locked decision from research)"
  - "rehypeSanitize as last plugin in rehypePlugins array (required for correct sanitization order)"
  - "Tool panel routing lives in AssistantMessage, not MessageList (single responsibility)"
  - "Auto-scroll threshold is 100px from bottom — matches app.js scroll behavior"

patterns-established:
  - "Lazy prop pattern: () => string instead of string for clipboard targets during streaming"
  - "contentRef + useEffect for always-current ref to props that change during streaming"
  - "Tool name string matching for card routing (get_colleague_profile, search_colleagues)"

# Metrics
duration: 12min
completed: 2026-03-28
---

# Phase 14 Plan 04: Message Rendering Components Summary

**8 React components porting all chat message rendering from vanilla JS to React, with react-markdown replacing the custom regex parser and DEBT-02 clipboard fix via lazy getText() on CopyButton**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-28T00:00:00Z
- **Completed:** 2026-03-28T00:12:00Z
- **Tasks:** 2
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments
- Replaced custom regex markdown parser with react-markdown + rehype-sanitize
- Fixed DEBT-02: CopyButton accepts `getText: () => string` (lazy evaluation at click time), making clipboard work identically on streaming and historical messages
- Ported all 4 app.js card/panel renderers (ProfileCard, SearchResultCard, ToolPanel, AssistantMessage tool routing)
- MessageList consumes ChatContext directly with near-bottom auto-scroll, renders both finalized and streaming messages

## Task Commits

Each task was committed atomically:

1. **Task 1: Install react-markdown + rehype-sanitize; create MarkdownRenderer, CopyButton, ToolPanel** - `bbdf861` (feat)
2. **Task 2: Create UserMessage, AssistantMessage, ProfileCard, SearchResultCard, MessageList** - `69616db` (feat)

**Plan metadata:** (docs: complete plan — pending)

## Files Created/Modified
- `frontend/src/components/ChatPane/MarkdownRenderer.tsx` - react-markdown wrapper with rehypeSanitize last in plugin array
- `frontend/src/components/shared/CopyButton.tsx` - Lazy getText() clipboard button, 1500ms "Copied!" feedback
- `frontend/src/components/ChatPane/ToolPanel.tsx` - Native details/summary, JSON pretty-print, result copy
- `frontend/src/components/ChatPane/UserMessage.tsx` - Plain text render, no markdown (matches app.js)
- `frontend/src/components/ChatPane/AssistantMessage.tsx` - Markdown + tool panel routing + streaming cursor + copy
- `frontend/src/components/ChatPane/ProfileCard.tsx` - Photo + name/title/dept/email, ported from addProfileCard()
- `frontend/src/components/ChatPane/SearchResultCard.tsx` - Results list with separator dots, ported from addSearchCards()
- `frontend/src/components/ChatPane/MessageList.tsx` - ChatContext consumer, auto-scroll, streaming message render
- `frontend/package.json` - Added react-markdown, rehype-sanitize
- `frontend/package-lock.json` - 124 packages added

## Decisions Made
- **CopyButton lazy getText():** Accepts `() => string` not `string`. Called at click time so streaming content is always current. This is the DEBT-02 fix — the old vanilla JS approach referenced a DOM element that didn't exist for historical messages loaded from DB.
- **ToolPanel uses native details/summary:** No Fluent UI Accordion. Locked decision from research phase.
- **rehypeSanitize last in plugins array:** Required for correct sanitization; plugins process left-to-right, sanitizer must be final.
- **Tool routing in AssistantMessage:** get_colleague_profile → ProfileCard, search_colleagues → SearchResultCard, all others → ToolPanel. Routing by tool name, not result shape.
- **contentRef pattern in AssistantMessage:** useRef + useEffect tracks latest content so CopyButton's getText closure is never stale, even during streaming.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 8 message rendering components are complete and TypeScript-clean
- MessageList is ready to be mounted inside ChatPane (14-05 task)
- ProfileCard photo URL uses `/api/photo/:id?name=` — requires backend photo endpoint (already exists in app.py)
- All CSS class names match existing app.css (profile-card, search-result-card, tool-panel, etc.) — no CSS changes needed in this phase

---
*Phase: 14-functional-port*
*Completed: 2026-03-28*
