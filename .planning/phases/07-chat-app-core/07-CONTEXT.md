# Phase 7: Chat App Core - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Flask chat application with Azure AD SSO, Azure OpenAI tool-calling loop, SSE streaming, and context window management. A colleague logs in, asks an Exchange question in natural language, watches the tool call resolve via streaming, and reads an AI-composed answer. Single conversation per session — multi-thread sidebar and persistence are Phase 8.

</domain>

<decisions>
## Implementation Decisions

### Chat interface layout
- Centered chat column with max-width container and whitespace on sides (ChatGPT/Claude style)
- Auto-expanding textarea input — starts as one line, grows as user types, up to a max height
- Send button alongside textarea
- Header includes: app name/logo + Exchange connection status indicator (connected/disconnected) + user avatar/logout

### Claude's Discretion: Message styling
- Claude decides message visual distinction between user and AI (bubble style, flat alternating, or other)

### Authentication flow UX
- Branded splash page with app description and "Sign in with Microsoft" button before authentication
- Silent re-auth using refresh tokens — user never sees a login prompt unless tokens are fully expired
- Any authenticated MMC Azure AD tenant user can access — no additional group membership required

### Claude's Discretion: Auth error pages
- Claude decides the error experience for unauthorized or failed-auth users

### AI response behavior
- Inline status chips during tool execution — small chip like "Querying get_mailbox_stats..." shown in the response area while the tool runs
- Errors surfaced as natural language explanations — AI explains conversationally what went wrong and suggests corrections
- Multi-tool chaining allowed automatically — AI can call multiple tools in sequence without asking, no step-by-step indication needed
- Conversational helpful tone — friendly but informative, contextualizes raw data for the user

### Conversation structure
- Single conversation per session — no sidebar, no threading (Phase 8 scope)
- Named assistant with identity — give it a name and role in the system prompt (e.g., "You are Atlas, MMC's Exchange infrastructure assistant...")
- Welcome experience: AI greets user by name, shows 3-4 clickable example queries (e.g., "Check mailbox size for...", "Show DAG health", "Check mail flow for...")
- Strict Exchange-only guardrails — AI refuses non-Exchange queries with a clear redirect to Exchange topics

</decisions>

<specifics>
## Specific Ideas

- Welcome greeting should use the authenticated user's display name from Azure AD
- Example queries in the welcome message should be clickable and populate the input field
- Connection status indicator in the header gives colleagues confidence the tool is live and working
- The named assistant persona helps colleagues understand they're talking to a purpose-built tool, not a general chatbot

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-chat-app-core*
*Context gathered: 2026-03-21*
