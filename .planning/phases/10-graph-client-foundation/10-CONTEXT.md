# Phase 10: Graph Client Foundation - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

A verified, isolated Graph API client with confirmed admin consent, correct token acquisition, and all three core operations (token acquire, user search, photo retrieval) tested in isolation. No MCP integration, no UI — just the client module.

</domain>

<decisions>
## Implementation Decisions

### Configuration & secrets
- Graph credentials (client ID, tenant ID, client secret) go in the same .env file alongside existing Exchange/Azure AD vars
- Use the same Azure AD app registration as user SSO — add User.Read.All and ProfilePhoto.Read.All permissions to the existing app
- If Graph credentials are missing at startup: warn and disable Graph features. Other MCP tools continue working normally.

### MSAL instance (Claude's Discretion)
- Whether graph_client.py shares the existing CCA from auth.py or creates its own — Claude decides based on cleanest architecture. (Roadmap success criteria says "its own CCA" — follow that unless there's a strong reason not to.)

### Admin consent verification
- Verify admin consent at startup by attempting token acquisition and decoding the roles claim
- If consent is not granted: log a clear warning with the exact permissions needed and instructions to grant consent. Graph features disabled until restart.
- User is the tenant admin — can grant consent directly
- Whether to include a direct admin consent URL in the log message is Claude's discretion

### Search behavior
- Search matches against displayName and mail fields
- Result shape: id, displayName, mail, jobTitle, department (core set for profile cards)
- Filter to active people only — accountEnabled=true, exclude service accounts, room/shared mailboxes
- Return up to 25 results maximum

### Error handling
- Transient Graph API failures (429, 503): retry up to 3 times with exponential backoff, respect Retry-After headers
- Missing profile photo: get_user_photo_bytes returns None silently — no logging (missing photos are normal)
- Token refresh failure (e.g., expired client secret): log the auth error clearly, disable Graph features. Don't crash the app.
- 10 second timeout on individual Graph API calls

### Claude's Discretion
- MSAL CCA instance strategy (own vs shared) — lean toward own per roadmap success criteria
- Admin consent URL format in log message
- Exact retry backoff timing and jitter

</decisions>

<specifics>
## Specific Ideas

- Reuse the existing Azure AD app registration rather than creating a separate one — simpler admin overhead
- ConsistencyLevel: eventual header required on every Graph search request (from roadmap success criteria)
- Token cached at module level and refreshed automatically before expiry

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-graph-client-foundation*
*Context gathered: 2026-03-24*
