# Phase 25: Motion Animations - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Fluid entrance animations and micro-interactions consistent with the Microsoft Copilot aesthetic, with full prefers-reduced-motion compliance. Covers message entrance animations, sidebar collapse/expand transition, and feedback button micro-interaction. No new UI components or features — motion wrappers on existing elements only.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User deferred all animation decisions to Claude, guided by research into best practices and the Copilot aesthetic. Claude has full flexibility on:

**Animation character:**
- Easing curves and duration philosophy
- How closely to mirror Copilot's motion language vs establishing Atlas-specific feel
- Overall animation subtlety level

**Message entrance:**
- Entrance style (fade, slide, stagger, or combination)
- Behavior during active SSE streaming vs completed messages
- Duration and easing for user messages vs assistant messages

**Sidebar transition:**
- CSS transition vs layout animation approach
- Collapse/expand speed and easing curve
- Whether content fades during transition

**Feedback micro-interaction:**
- Thumb button press feel (scale, color, ripple, or combination)
- Noticeability level — subtle confirmation vs prominent feedback
- Duration and easing for the interaction

**Constraints from roadmap (non-negotiable):**
- Assistant messages: fade-in + slide-up, 200ms ease-out
- User messages: same pattern, 150ms
- No animation during active SSE streaming
- Sidebar: smooth CSS width change, 200-250ms ease-in-out
- Feedback thumb: 100ms scale micro-interaction
- MotionConfig reducedMotion="user" wraps all motion globally
- LazyMotion + domAnimation (no framer-motion package)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — user wants research-driven, best-practice decisions aligned with Microsoft Copilot's motion language.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-motion-animations*
*Context gathered: 2026-04-02*
