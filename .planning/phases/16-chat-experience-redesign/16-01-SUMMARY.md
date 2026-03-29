---
phase: 16
plan: 01
subsystem: chat-ui
tags: [css, react, typescript, message-bubbles, animation, copilot-style]
one-liner: "Copilot-style asymmetric message bubbles with accent colors, fade-up entrance animation, and ISO timestamp tracking in DisplayMessage pipeline"

dependency-graph:
  requires: [15-02]
  provides: [message-bubble-visual-identity, entrance-animation, timestamp-data-layer]
  affects: [16-02, 16-03]

tech-stack:
  added: []
  patterns: [copilot-bubble-geometry, css-animation-reduced-motion, display-layer-timestamp-stamping]

key-files:
  created: []
  modified:
    - frontend/src/index.css
    - frontend/src/types/index.ts
    - frontend/src/contexts/ChatContext.tsx
    - frontend/src/components/ChatPane/UserMessage.tsx
    - frontend/src/components/ChatPane/AssistantMessage.tsx
    - frontend/src/components/ChatPane/MessageList.tsx

decisions:
  - id: bubble-max-width-75pct
    choice: "75% max-width per bubble rather than 800px full-width"
    rationale: "Copilot geometry requires role-based alignment; full-width prevents align-self from creating visual separation between user and assistant turns"
  - id: asymmetric-corners
    choice: "border-radius 14px 14px 4px 14px for user, 4px 14px 14px 14px for assistant"
    rationale: "Sharp corner points toward the sender (bottom-right for user, top-left for assistant) — standard Copilot/Teams message geometry"
  - id: no-border-on-assistant
    choice: "No border on .assistant-message — surface elevation only"
    rationale: "Stitch No-Line principle: surface tier bg-elevated provides visual containment without border noise"
  - id: timestamp-display-layer-only
    choice: "Timestamp added to DisplayMessage not RawMessage or StreamingMessageState"
    rationale: "Timestamps are display-layer metadata, not wire format data; streaming state stamps at finalization boundary"

metrics:
  duration: "~2 minutes"
  completed: "2026-03-29"
  tasks-completed: 3
  tasks-total: 3
---

# Phase 16 Plan 01: Message Bubble Redesign Summary

Copilot-style asymmetric message bubbles with accent colors, fade-up entrance animation, and ISO timestamp tracking in DisplayMessage pipeline.

## What Was Built

Restyled the chat message pipeline to deliver the core visual identity of the Phase 16 redesign:

- **User messages** render as right-aligned brand-blue bubbles (`--atlas-accent` background, white text, `border-radius: 14px 14px 4px 14px` — sharp bottom-right)
- **Assistant messages** render as left-aligned elevated-surface cards (`--atlas-bg-elevated` background, `border-radius: 4px 14px 14px 14px` — sharp top-left)
- Both bubble types have `max-width: 75%` with `align-self` overriding flex container alignment
- **Entrance animation** `@keyframes message-enter` fades in with `translateY(8px)` over 180ms, with `prefers-reduced-motion` disabling it
- **Streaming cursor** changed from `--atlas-text-primary` to `--atlas-accent` (brand blue)
- **Timestamps** tracked via `DisplayMessage.timestamp?: string` (ISO 8601), stamped at ADD_USER_MESSAGE, FINALIZE_STREAMING, and CANCEL_STREAMING
- All three message components (`UserMessage`, `AssistantMessage`, `MessageList`) updated to accept and pass through the `timestamp` prop — ready for 16-03 to render the hover overlay

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add message bubble CSS, entrance animation, streaming cursor | 5b7e680 | index.css |
| 2 | Add timestamp to DisplayMessage type and stamp in ChatContext reducer | 1ed13b1 | types/index.ts, ChatContext.tsx |
| 3 | Update message components for timestamp prop pass-through | 2b7388b | UserMessage.tsx, AssistantMessage.tsx, MessageList.tsx |

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| bubble-max-width | 75% per bubble | Role-based alignment requires bounded width; align-self needs non-full-width to create visual separation |
| asymmetric-corners | 14px 14px 4px 14px / 4px 14px 14px 14px | Sharp corner points toward sender — standard Copilot/Teams geometry |
| no-border-on-assistant | Surface elevation only | Stitch No-Line: bg-elevated provides containment without border noise |
| timestamp-scope | DisplayMessage only (not RawMessage) | Display-layer metadata; stamped at finalization boundary, not during streaming |

## Deviations from Plan

None — plan executed exactly as written.

## Next Phase Readiness

- 16-02 (input area redesign) can proceed — `.input-area`, `.chat-input`, `.send-btn` CSS is untouched and ready
- 16-03 (hover actions + timestamp display) can proceed — `timestamp` prop flows through all three components; overlay implementation just needs to read the prop
- No blockers identified
