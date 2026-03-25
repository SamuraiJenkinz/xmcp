# Requirements: Exchange Infrastructure MCP Server — v1.1 Colleague Lookup

**Defined:** 2026-03-24
**Core Value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data

## v1.1 Requirements

### Graph Infrastructure

- [x] **GRAPH-01**: Graph API client authenticates via MSAL client credentials flow (isolated from SSO)
- [x] **GRAPH-02**: Azure AD app registration has User.Read.All and ProfilePhoto.Read.All application permissions with admin consent
- [x] **GRAPH-03**: Graph API token is cached at module level and refreshed automatically

### Colleague Search

- [x] **SRCH-01**: User can search for colleagues by name via natural language ("look up John Smith")
- [x] **SRCH-02**: Search returns top results with name, job title, department, and email
- [x] **SRCH-03**: Search handles empty results with a clear message
- [x] **SRCH-04**: Search uses `$search` with `ConsistencyLevel: eventual` header

### Profile Display

- [x] **PROF-01**: User can request detailed profile for a specific colleague
- [ ] **PROF-02**: Profile is rendered as an inline card with photo, name, job title, department, and email
- [x] **PROF-03**: Photo is served via Flask proxy route (`GET /api/photo/<user_id>`) with `@login_required`
- [ ] **PROF-04**: Users without photos get a fallback avatar (initials or generic icon)
- [x] **PROF-05**: Photo binary data never enters the LLM context — tools return `photo_url` string only

### MCP Integration

- [x] **MCP-01**: `search_colleagues` tool registered in MCP server with input schema
- [x] **MCP-02**: `get_colleague_profile` tool registered in MCP server with input schema
- [ ] **MCP-03**: System prompt updated to describe colleague lookup capabilities
- [ ] **MCP-04**: Profile card rendered as DOM element from tool result JSON (not AI-generated markdown)

## Future Requirements

### v1.2 Candidates

- **SRCH-05**: Search by department
- **PROF-06**: Operating company badge (Marsh/Mercer/OW/GC)
- **PROF-07**: Office location on profile card
- **PROF-08**: Phone numbers on profile card
- **PROF-09**: Manager name on profile card

## Out of Scope

| Feature | Reason |
|---------|--------|
| Presence/availability status | High permission sensitivity, ephemeral data, creates real-time monitoring expectations |
| Org chart traversal | Scope creep, not aligned with Exchange tool focus |
| Direct Graph access from browser | Security risk — token must stay server-side |
| Write operations on user profiles | Read-only tool policy (consistent with v1.0 Exchange tools) |
| Photo upload/modification | Out of scope for a read-only lookup tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GRAPH-01 | Phase 10 | Complete |
| GRAPH-02 | Phase 10 | Complete |
| GRAPH-03 | Phase 10 | Complete |
| SRCH-01 | Phase 11 | Complete |
| SRCH-02 | Phase 11 | Complete |
| SRCH-03 | Phase 11 | Complete |
| SRCH-04 | Phase 10 | Complete |
| PROF-01 | Phase 11 | Complete |
| PROF-02 | Phase 12 | Pending |
| PROF-03 | Phase 11 | Complete |
| PROF-04 | Phase 12 | Pending |
| PROF-05 | Phase 11 | Complete |
| MCP-01 | Phase 11 | Complete |
| MCP-02 | Phase 11 | Complete |
| MCP-03 | Phase 12 | Pending |
| MCP-04 | Phase 12 | Pending |

**Coverage:**
- v1.1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 — phase assignments added*
