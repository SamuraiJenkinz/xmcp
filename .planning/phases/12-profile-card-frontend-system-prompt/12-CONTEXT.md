# Phase 12: Profile Card Frontend + System Prompt - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Inline profile cards rendered as DOM elements in the chat UI when Atlas returns colleague data, plus system prompt updates so Atlas reliably selects the right tool. This phase connects the MCP tool results (Phase 11) to what users actually see in the chat.

</domain>

<decisions>
## Implementation Decisions

### Card layout & content
- Horizontal layout: photo on the left, text details stacked to the right
- Core 4 fields only: name, job title, department, email
- Bordered card style: subtle border and background, clearly distinct from surrounding message text (like a Teams contact card)
- Card must work in both dark mode and light mode (existing CSS variable system)

### Fallback avatar
- Use the existing proxy SVG from Phase 11 — card's `<img>` points to `/api/photo/{id}?name=First+Last`, proxy returns colored initials SVG automatically
- No extra frontend fallback logic needed — the proxy always returns HTTP 200
- Photo displayed as a circle (CSS `border-radius: 50%`)

### System prompt guidance
- Separate "Colleague Lookup" block in the system prompt with its own rules and examples
- Auto-detail on single result: if search_colleagues returns exactly 1 match, Atlas automatically calls get_colleague_profile without waiting for user confirmation
- Multiple results: Atlas presents as a text list (name, title, department), user asks for a specific profile to see the card
- Tool routing approach: Claude's discretion on how to instruct search vs profile selection

### Claude's Discretion
- Whether email on card is a clickable mailto: link or plain text
- Exact system prompt wording for tool selection guidance
- Card sizing and spacing relative to chat messages
- How search result text lists are formatted (numbered, bulleted, etc.)

</decisions>

<specifics>
## Specific Ideas

- Cards should feel like Teams/Outlook contact cards — professional, bordered, compact
- Single search result should feel seamless — user asks "who is Jane Smith?" and gets the card directly without an intermediate step
- Multiple results should be conversational — Atlas lists who it found and lets the user pick

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-profile-card-frontend-system-prompt*
*Context gathered: 2026-03-25*
