# Phase 11: MCP Tools + Photo Proxy - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Two new MCP tools (`search_colleagues`, `get_colleague_profile`) registered and callable via the LLM tool-calling loop, plus a Flask photo proxy route (`/api/photo/<user_id>`) that serves colleague photos securely with placeholder fallback. This phase bridges the Graph client (Phase 10) to the chat UI (Phase 12).

</domain>

<decisions>
## Implementation Decisions

### Search results shape
- Max 10 results per search
- Fields per result: name, jobTitle, department, email (core 4 only — no ID in search results)
- Search query matches against displayName and mail (not just name)
- No matches returns a human-readable message string (e.g., "No colleagues found matching 'xyz'"), not an empty array

### Profile detail depth
- Full profile includes: name, jobTitle, department, email, officeLocation, businessPhones, manager displayName
- Missing fields are omitted from the result (no null keys) — LLM naturally says "no department listed"
- photo_url is always included (points to the proxy route)

### Photo proxy behavior
- Placeholder for users without a photo: SVG with initials on a colored background (generated server-side, no external assets)
- Photos cached with a TTL (e.g., 1 hour) to reduce Graph API calls
- Request 96x96 size from Graph API (`/photos/96x96/$value`) — small payload, appropriate for profile cards
- Proxy returns HTTP 200 with placeholder image when user has no photo (not 404)
- Unauthenticated requests return 401/302-to-login

### Tool naming & descriptions
- Tool names: `search_colleagues` and `get_colleague_profile` (colleague terminology)
- Tool descriptions include LLM usage hints (e.g., "Use for name lookups", "Use when you have a specific user ID from search results")
- `get_colleague_profile` accepts user ID only (not email) — LLM gets IDs from search results
- Search parameter named `query` (signals it searches across name and email)

### Claude's Discretion
- Cache implementation strategy (in-memory dict, disk, etc.)
- Cache TTL duration (suggested ~1 hour)
- Initials SVG color palette and generation approach
- Exact tool description wording
- Error handling for Graph API failures within tools

</decisions>

<specifics>
## Specific Ideas

- Search results deliberately exclude user ID — the LLM must call `get_colleague_profile` to get detailed info, which naturally includes the photo_url. This keeps search results lightweight.
- The "no matches" message should be a plain string the LLM can relay conversationally, not a structured error object.
- Initials placeholder should feel personal — colored background with the person's initials, not a generic silhouette.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-mcp-tools-photo-proxy*
*Context gathered: 2026-03-24*
