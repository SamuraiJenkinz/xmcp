# Phase 21: App Role Access Control - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Gate the application so only authenticated users holding the `Atlas.User` App Role can access the chat interface. All other authenticated users see an access denied page. Unauthenticated users are redirected to login. All API endpoints enforce the same role check. This phase does NOT add new UI features, role management, or admin dashboards.

</domain>

<decisions>
## Implementation Decisions

### Access Denied page
- Friendly but clear tone: "You don't have access yet" — helpful, not cold or corporate
- Minimal shell layout: centered Fluent 2 card on blank page, no sidebar or app chrome — clearly a gate, not the app
- Dark/light mode support (follows system/existing theme preference)

### Admin contact flow
- mailto link pre-fills both subject and body (e.g., Subject: "Atlas Access Request", Body: "Hi, I'd like access to Atlas. My UPN is jane.doe@mercer.com")
- One-click "Copy UPN" button alongside the mailto link
- Admin email address: config-driven via environment variable (so it can change without code deploys)

### Endpoint denial responses
- 403 responses use structured JSON: `{"error": "forbidden", "message": "Atlas.User role required", "required_role": "Atlas.User"}`
- All 403 denials are logged with UPN, endpoint, and timestamp for admin visibility

### Claude's Discretion
- Whether to show display name + UPN or UPN only on the Access Denied page (based on what's available from the session)
- Whether to include a one-liner explaining what Atlas is
- Whether to show the role name (Atlas.User) on the denied page (internal audience — Claude judges exposure risk)
- Copy UPN feedback mechanism (toast vs inline text swap — pick what fits Fluent 2 patterns)
- 401 vs 403 response shape differentiation (same shape with different code, or different shapes — based on what the React frontend needs)
- SSE /chat/stream denial approach (403 JSON before stream starts vs SSE error event — based on existing SSE client error handling)
- Auth loading state while role is checked (spinner vs skeleton — pick what fits Copilot aesthetic)
- Session expiry behavior (silent redirect vs modal warning — pick least disruptive)
- Network error handling on /api/me (auto-retry vs immediate error — pick resilient approach)
- Role caching strategy (every page load vs session cache — balance security vs performance)

</decisions>

<specifics>
## Specific Ideas

- User selected the "friendly but clear" mockup: heading "You don't have access yet", subtext about Atlas being available to IT engineers with the right permissions, then account details and action buttons
- Minimal shell (no app chrome) was explicitly preferred over full Atlas branding — the denied page should feel like a gate, not the app itself
- Structured JSON for 403s was explicitly chosen over minimal — include the required role name in API responses
- Denial audit logging was explicitly requested — admins want to see who's trying to access

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-app-role-access-control*
*Context gathered: 2026-04-02*
