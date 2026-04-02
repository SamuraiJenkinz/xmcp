---
phase: 22
plan: "02"
name: "Per-Message Feedback Frontend"
subsystem: "frontend"
tags: ["react", "fluent-ui", "feedback", "accessibility", "aria", "context"]
one-liner: "FeedbackButtons component with Fluent ThumbLike/ThumbDislike icons, comment Popover, optimistic ChatContext state, and ARIA live region wired into AssistantMessage, MessageList, and ThreadList"

dependency-graph:
  requires: ["22-01"]
  provides:
    - "FeedbackButtons component with thumbs up/down, Popover comment flow, ARIA live region"
    - "feedbackMap in ChatContext with SET_FEEDBACK_MAP and SET_FEEDBACK_VOTE actions"
    - "Feedback votes fetched on thread select, delete-next, and new chat"
    - "Feedback buttons hidden during SSE streaming (isStreaming guard)"
  affects:
    - "Future phases: any feature reading feedbackMap from ChatContext"

tech-stack:
  added: []
  patterns:
    - "bundleIcon from @fluentui/react-icons for filled/regular icon toggle"
    - "Popover/PopoverSurface/PopoverTrigger from @fluentui/react-components for comment flow"
    - "Optimistic dispatch + async backend call pattern for instant UI response"
    - ".sr-only CSS for visually-hidden ARIA live region"

key-files:
  created:
    - frontend/src/api/feedback.ts
    - frontend/src/components/ChatPane/FeedbackButtons.tsx
  modified:
    - frontend/src/types/index.ts
    - frontend/src/contexts/ChatContext.tsx
    - frontend/src/components/ChatPane/AssistantMessage.tsx
    - frontend/src/components/ChatPane/MessageList.tsx
    - frontend/src/components/Sidebar/ThreadList.tsx
    - frontend/src/index.css

decisions:
  - "Used ThumbLikeFilled/ThumbLikeRegular (not 16-sized) with bundleIcon — the 16-sized variants are in font atoms, not the main SVG icon chunks exported by @fluentui/react-icons"
  - "handleCommentDismiss persists thumbs-down without comment when Popover closes without Submit — avoids losing vote intent on accidental dismiss"
  - "getFeedbackForThread called in handleSelectThread, handleDelete (next-thread branch), and handleNewChat (empty votes) — no useEffect initial load since ThreadList has no separate mount effect for first thread"

metrics:
  duration: "~20 minutes"
  completed: "2026-04-02"
  tasks-total: 2
  tasks-completed: 2
---

# Phase 22 Plan 02: Per-Message Feedback Frontend Summary

## What Was Built

Full frontend implementation of the per-message feedback feature. IT engineers can thumbs-up or thumbs-down any completed assistant message. Votes persist to the backend and restore when switching threads.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Feedback types, API module, ChatContext, sr-only CSS | a201047 | feedback.ts, types/index.ts, ChatContext.tsx, index.css |
| 2 | FeedbackButtons component + integration wiring | d5370a6 | FeedbackButtons.tsx, AssistantMessage.tsx, MessageList.tsx, ThreadList.tsx |

## Decisions Made

1. **ThumbLike icon variant**: Used `ThumbLikeFilled`/`ThumbLikeRegular` (not `ThumbLike16*`) via `bundleIcon`. The 16-sized variants exist only in the font atoms sub-package, not in the main SVG chunks re-exported by `@fluentui/react-icons`. The standard-sized icons with `size="small"` on the Button produce equivalent visual output.

2. **Popover dismiss behavior**: `handleCommentDismiss` always persists the thumbs-down vote (without comment) when the Popover closes without a Submit click. This prevents the vote being silently lost if the user accidentally closes the popover — the vote is already optimistically set in ChatContext.

3. **No mount useEffect for initial thread**: The plan mentioned adding a feedback fetch to the "initial thread load useEffect" in ThreadList. After reading the code, no such useEffect exists — the first thread's messages are loaded by `handleSelectThread` when the user clicks. The `handleSelectThread` path already has feedback loading added.

## Behaviors Implemented

- Thumbs up and thumbs down buttons appear on hover inside `.message-hover-actions` next to CopyButton on completed assistant messages
- Feedback buttons absent while SSE stream active (`isStreaming` guard in AssistantMessage)
- Clicking a thumb fills the icon immediately (optimistic dispatch to `SET_FEEDBACK_VOTE`) then calls `submitFeedback`
- Clicking the same button a second time retracts — icon returns to unfilled, DELETE sent to backend
- Clicking thumbs-down opens a Fluent `Popover` with optional `Textarea` (500 char limit); Submit or dismiss both persist the vote
- ARIA live region (`role="status"`, `aria-live="polite"`) announces "Feedback submitted" via `.sr-only` span
- Vote state restored when switching threads (`getFeedbackForThread` → `SET_FEEDBACK_MAP`)
- Switching from thumbs-up to thumbs-down (or vice versa) works in one click — no intermediate retraction needed

## Deviations from Plan

None — plan executed exactly as written, with one adaptation: icon size variant adjusted from `ThumbLike16*` to `ThumbLikeFilled`/`ThumbLikeRegular` (documented above) since the 16-size exports are not available from the main package entry point.

## Next Phase Readiness

- Backend endpoints (`GET/POST/DELETE /api/threads/:id/feedback/:idx`) are live from 22-01
- Frontend feedback UI is fully wired and builds cleanly
- Phase 22 is complete — no blockers for subsequent phases
