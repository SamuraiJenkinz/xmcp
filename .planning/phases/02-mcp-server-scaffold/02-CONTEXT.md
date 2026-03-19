# Phase 2: MCP Server Scaffold - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

A runnable MCP server over stdio transport that registers tools correctly, enforces error handling discipline (no raw tracebacks to the LLM), and keeps stdout clean for JSON-RPC. This phase delivers the server skeleton and conventions — actual Exchange tools are implemented in Phases 3-6.

</domain>

<decisions>
## Implementation Decisions

### Error surface
- Raw PowerShell tracebacks always stripped — the LLM only sees sanitized messages
- Transient errors (Exchange unreachable, timeouts) include a retry suggestion in the error message: "This is usually transient — try again in a moment."
- Non-transient errors report the failure without retry guidance

### Claude's Discretion: Error detail level
- Claude determines the right level of detail per error type (category + message, with optional hint)
- Claude determines whether to use structured error codes or free-text messages — optimize for LLM tool-calling reliability

### Tool descriptions
- Tool names use snake_case: get_mailbox_stats, check_mail_flow, etc.
- Descriptions include example queries that would trigger them (e.g. "Use when asked about mailbox size, quota, or last logon")
- Use plain language, not Exchange jargon — say "email address" not "UPN", "user" not "mailbox identity"
- Descriptions under 800 characters each (per roadmap success criteria)

### Logging discipline
- All logging goes to stderr only — stdout is exclusively JSON-RPC
- Every tool call logged: tool name, parameters, duration, and success/failure
- PowerShell commands included in logs (the actual cmdlet being executed)
- No PII redaction — this is an internal tool for Exchange admins who need to see actual identities
- Log format is Claude's discretion

### Startup and lifecycle
- Server refuses to start if Exchange auth fails — fail fast with clear error on stderr
- Startup validates Exchange connection (run a quick cmdlet to confirm reachability)
- Startup banner on stderr: version, auth mode, tool count, Exchange endpoint
- Graceful shutdown on SIGTERM / stdin close — tear down any active PowerShell sessions before exiting

### Claude's Discretion
- Log format choice (structured JSON vs human-readable)
- Error code strategy (structured codes vs free text)
- Error detail level per error type

</decisions>

<specifics>
## Specific Ideas

- The server is a stdio MCP server — `mcp dev` inspector must be able to enumerate tools
- Tool descriptions should help the LLM reliably pick the right tool from a natural language query
- The error wrapping pattern established here becomes the template for all 15 tools in Phases 3-6

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-mcp-server-scaffold*
*Context gathered: 2026-03-19*
