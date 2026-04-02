# Phase 22: Per-Message Feedback - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

IT engineers can vote thumbs up or down on any completed assistant message, with votes persisted to SQLite against the user's identity for future analytics. A thumbs-down vote opens an optional freetext comment popover. This phase covers the feedback UI, the backend endpoints, and the SQLite schema. Analytics dashboards, reporting, or feedback-driven model tuning are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User has delegated all implementation decisions to Claude, guided by research of best practices for conversational AI feedback interfaces. The following areas are open:

**Button placement & visibility**
- Where thumbs appear relative to the message and existing copy button
- Hover-only vs always-visible behavior
- Spacing and visual weight

**Vote interaction & states**
- Visual feedback on click (filled icon, animation)
- Toggle/retract behavior
- Whether switching directly from thumbs-up to thumbs-down is supported (or requires retract first)

**Thumbs-down comment flow**
- Popover layout, placeholder text, submit/cancel actions
- Character limit (if any)
- Whether submitting an empty comment is equivalent to a vote without comment

**Feedback persistence & identity**
- One vote per message per user enforcement
- Restoring filled state on page reload (fetch existing votes on thread load)
- User identification in the feedback record (UPN from session)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — user wants decisions driven by best practices research for conversational AI feedback patterns (e.g., ChatGPT, Copilot, Gemini feedback UX).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 22-per-message-feedback*
*Context gathered: 2026-04-02*
