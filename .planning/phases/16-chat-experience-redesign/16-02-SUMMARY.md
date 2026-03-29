---
phase: 16
plan: "02"
subsystem: chat-ux
tags: [css, glassmorphism, streaming, welcome-state, prompt-chips, react]

dependency-graph:
  requires: ["16-01"]
  provides: ["glassmorphism-input-bar", "stop-button", "welcome-state", "prompt-chips"]
  affects: ["16-03"]

tech-stack:
  added: []
  patterns:
    - "color-mix() for glassmorphism with opacity control"
    - "@supports fallback for backdrop-filter"
    - "readOnly vs disabled for streaming textarea state"
    - "CSS ::before pseudo-element for icon-only buttons"
    - "Conditional component rendering on empty state"
    - "Optional callback prop with ?. safe-call for chip wiring"

file-tracking:
  created: []
  modified:
    - "frontend/src/index.css"
    - "frontend/src/components/ChatPane/InputArea.tsx"
    - "frontend/src/components/ChatPane/MessageList.tsx"
    - "frontend/src/components/AppLayout.tsx"

decisions:
  - context: "Stop button icon"
    choice: "CSS ::before pseudo-element (white square) on .stop-btn"
    rationale: "No external icon dependency; pure CSS, zero DOM nodes; accessible via aria-label"
  - context: "Textarea during streaming"
    choice: "readOnly={isStreaming} not disabled"
    rationale: "readOnly preserves visual state (no gray-out), allows cursor placement, prevents input without disabling"
  - context: "Glassmorphism backdrop"
    choice: "color-mix(in srgb, --atlas-bg-elevated 80%, transparent) + backdrop-filter"
    rationale: "color-mix gives alpha control without rgba hardcoding; @supports fallback for Firefox/Safari fallback"
  - context: "Chip wiring"
    choice: "onChipSend optional prop on MessageList, passed handleSend from AppLayout"
    rationale: "Reuses existing handleSend path which handles thread creation for null activeThreadId; no duplication"

metrics:
  duration: "~2 minutes"
  tasks-completed: 3
  tasks-total: 3
  completed: "2026-03-29"
---

# Phase 16 Plan 02: Input Area Redesign + Welcome State Summary

**One-liner:** Glassmorphism floating input bar with CSS stop button, readOnly streaming state, and welcome prompt chip grid wired through AppLayout.

## What Was Built

Three coordinated changes transform the input zone from a generic text input into a polished Copilot-style interaction area:

1. **Glassmorphism input bar** — `.input-area` now floats centered at max-width 768px with `color-mix()` + `backdrop-filter: blur(20px)` for the frosted glass effect. A `@supports not (backdrop-filter)` fallback provides solid `--atlas-bg-elevated` for unsupported browsers.

2. **Circular stop button** — `.stop-btn` replaces the text "Stop" button. A pure CSS `::before` pseudo-element renders a white 12×12px square on a red (`--atlas-status-error`) circle. The button is never disabled during streaming — user can always cancel.

3. **ReadOnly textarea during streaming** — `readOnly={isStreaming}` preserves visual state without gray-out. `disabled={disabled && !isStreaming}` still disables when no active thread exists outside a stream.

4. **Welcome state** — `MessageList` conditionally renders a centered welcome panel when `messages.length === 0 && streamingMessage === null`. Shows a lightning bolt icon, heading, and a 2×2 grid of prompt chips. Each chip calls `onChipSend?.()` which is wired to `handleSend` in AppLayout — auto-creating a thread if needed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Restyle input area CSS, add stop btn + welcome state CSS | 6d80d28 | index.css |
| 2 | InputArea: readOnly streaming, stop btn icon, new placeholder | da4d1ee | InputArea.tsx |
| 3 | Welcome state in MessageList, onChipSend through AppLayout | 3b83b51 | MessageList.tsx, AppLayout.tsx |

## Decisions Made

- **Stop button icon via CSS pseudo-element** — No icon library needed. The `::before` rule on `.stop-btn` renders a white square on the red circle. Accessible via `aria-label="Stop generating"`.
- **readOnly not disabled during streaming** — `disabled` grays out the textarea and blocks cursor placement. `readOnly` keeps it visually active while preventing keystrokes. The `disabled` prop from AppLayout (`!activeThreadId`) only fires when there is genuinely no active thread and streaming hasn't started.
- **color-mix() for glassmorphism alpha** — Avoids hardcoded rgba values; the 80% mix uses the active theme's `--atlas-bg-elevated` token so dark/light modes both work correctly.
- **onChipSend wired to handleSend** — The same `handleSend` already handles `null activeThreadId` by creating a thread first. No special chip handler needed.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- `npx tsc --noEmit` — zero errors
- `npx vite build --mode development` — clean build (382.62 kB JS, 16.86 kB CSS)
- `.input-area` has `backdrop-filter: blur(20px)` and `max-width: 768px` — confirmed
- `.stop-btn` has `border-radius: 50%` and `background-color: var(--atlas-status-error)` — confirmed
- `.welcome-state`, `.prompt-chips-grid`, `.prompt-chip` all present — confirmed
- `readOnly={isStreaming}` and correct placeholder in InputArea.tsx — confirmed
- Welcome state conditional on `messages.length === 0 && streamingMessage === null` — confirmed
- `<MessageList onChipSend={handleSend} />` in AppLayout.tsx — confirmed

## Next Phase Readiness

Plan 16-03 (message timestamp display, message footer, copy button polish) can proceed. The welcome state disappears the moment the first message enters the `messages[]` array, so transition is seamless. The glassmorphism input bar layout does not conflict with the chat-pane flex column — the bar floats above the canvas background naturally.
