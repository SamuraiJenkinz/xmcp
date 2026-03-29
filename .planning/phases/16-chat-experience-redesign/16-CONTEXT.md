# Phase 16: Chat Experience Redesign - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Redesign message bubbles, input area, streaming states, and welcome screen to deliver a Microsoft Copilot aesthetic. Clear role differentiation, smooth animations, stop-generation button, and prompt suggestion chips. This phase covers the chat interaction layer only — sidebar redesign (Phase 17), profile cards (Phase 18), and accessibility sweep (Phase 19) are separate.

</domain>

<decisions>
## Implementation Decisions

### Message bubble style
- User messages: right-aligned, brand blue (`--atlas-accent`) rounded bubbles with white text, asymmetric corners (14px with sharp bottom-right) — Copilot signature geometry
- Assistant messages: left-aligned, elevated surface (`--atlas-surface-elevated`) cards with primary text, asymmetric corners (14px with sharp top-left) — tonal differentiation, not border-based
- Role differentiation achieved through color + alignment + corner asymmetry — no avatar icons needed
- Bubble max-width: 75% of chat area to prevent full-width stretching
- Structural definition via background tonal shift (Stitch "No-Line" principle) — avoid 1px solid borders on assistant bubbles; use surface tier elevation instead
- Per-message hover reveals: copy button (top-right) and timestamp overlay (bottom edge)
- Timestamp format: relative ("2m ago", "1h ago") for recent, absolute ("Mar 29, 3:42 PM") for older than 24h

### Streaming and animations
- Message entrance animation: fade-in + upward translate (150-200ms, CSS transition) — no layout thrash, applied once on mount
- Streaming text: tokens appear inline with a blinking vertical cursor (`2px --atlas-accent`) at the insertion point — cursor disappears when stream completes
- Thinking/loading state: keep existing 3-dot bouncing animation pattern (already working from Phase 14)
- Tool panel in "running" state: spinning border indicator on the summary bar, tool name in monospace, turns to checkmark badge on completion
- Cancel mid-stream: "[response cancelled]" italic marker appended — matches existing vanilla JS behavior
- No message "typing indicator" for assistant — streaming text IS the indicator

### Input area behavior
- Auto-expanding textarea: starts at 1 line, grows to max ~5 lines, then scrolls internally
- Keyboard: Enter sends message, Shift+Enter inserts newline (existing behavior preserved)
- Send button transforms to Stop button during active streaming — Stop is a filled circle with square icon, uses `--atlas-status-error` color
- Button transition: instant swap (no animation needed), driven by `isStreaming` state
- Placeholder text: "Ask Atlas anything about Exchange..."
- Input bar: centered, max-width 768px, uses `--atlas-surface-elevated` background with subtle rounded corners (8px)
- Input bar uses glassmorphism effect: 0.8 opacity + backdrop-filter blur(20px) — floats above chat scroll without hard edge
- Disabled state during streaming: textarea is read-only while stream is active, re-enables on completion or cancel

### Welcome state and prompt chips
- Centered welcome area: lightning bolt icon (existing Atlas brand) + "How can I help with Exchange today?" heading
- Heading uses `--atlas-text-primary` at display size with tight letter-spacing (-0.02em)
- Four prompt suggestion chips in 2x2 grid below greeting:
  1. "Check mailbox quota" (mailbox icon)
  2. "Trace a message" (search icon)
  3. "DAG health status" (server icon)
  4. "Look up a colleague" (person icon)
- Chips are Fluent 2 card-style: `--atlas-surface-elevated` background, rounded-full corners, `--atlas-text-secondary` text
- Chip hover: shift to next surface tier up (`surface_container_highest` equivalent), subtle transition (100ms)
- Clicking a chip populates the input textarea with that text and auto-submits
- Welcome state disappears as soon as first message is sent (replaced by message list)

### Claude's Discretion
- Exact animation easing curves and timing fine-tuning
- Whether to use Fluent motion tokens (react-motion-components) or pure CSS transitions
- Streaming cursor blink rate and style details
- Exact spacing between message bubbles (suggest 12-16px)
- Whether timestamp hover uses tooltip or inline overlay
- Welcome state icon size and exact vertical positioning

</decisions>

<specifics>
## Specific Ideas

- Copilot-style asymmetric bubble corners are the key visual signature — user sharp bottom-right, assistant sharp top-left
- Stitch design system recommends "tonal depth" over borders: use surface tier elevation for containment instead of 1px borders
- Input bar glassmorphism (backdrop-blur) creates premium floating feel from Stitch "Digital Architect" theme
- Prompt chips should feel inviting to non-technical users (service desk analysts) — use familiar Exchange terminology, not jargon
- The design brief emphasizes dark mode is heavily used by IT ops teams — dark mode is the primary design target, light mode follows
- Desktop-only (1080p-1440p) — no mobile responsive concerns for this phase
- Stitch project created: `projects/16877514821790803864` — visual reference for Copilot-style chat layout, welcome state, and streaming states

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-chat-experience-redesign*
*Context gathered: 2026-03-29*
