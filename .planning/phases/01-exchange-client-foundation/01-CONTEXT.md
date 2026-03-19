# Phase 1: Exchange Client Foundation - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Async PowerShell subprocess runner for Exchange Online, with app-only Azure AD authentication (client secret), DNS utilities for DMARC/SPF, and JSON output parsing. This is the foundational client layer that every MCP tool in later phases depends on. No UI, no MCP protocol, no tools — just the verified client.

**Key correction from roadmap:** Target is Exchange Online (not on-premises). Authentication uses Azure AD app registration with client secret, not Basic Auth over WinRM. The ExchangeOnlineManagement PowerShell module is used instead of legacy PSSession remoting.

</domain>

<decisions>
## Implementation Decisions

### Credential & connection handling
- Credentials stored in environment variables: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- Azure AD app-only authentication with client secret (Connect-ExchangeOnline with app context)
- Fail-fast at startup: run a lightweight Exchange cmdlet on init to validate credentials before accepting calls
- Health-check function (`verify_connection()`) exposed on the client for downstream phases to surface as UI button or API endpoint
- Exchange Online endpoint — no server URI needed, the EXO module handles endpoint resolution

### Output & parsing contract
- Claude's Discretion: return type (raw dicts vs typed objects) — pick what fits MCP tool pattern best
- Client enforces a default ResultSize cap on cmdlets that return collections; callers can override
- Claude's Discretion: error representation (exceptions vs result wrapper) — pick best pattern for MCP tool handlers
- Claude's Discretion: raw PowerShell output logging strategy

### Timeout & failure behavior
- 60-second default timeout per cmdlet call
- Retry transient failures (throttling, network errors) up to 3 times with exponential backoff; skip retries for auth errors or invalid input
- Kill subprocess immediately on timeout — no grace period
- Claude's Discretion: Exchange Online throttling state tracking and exposure

### DNS resolver design
- Phase 1 supports DMARC and SPF record lookups only (TXT records); DKIM deferred to Phase 5
- Cache DNS results respecting record TTL
- Parse records into structured data (e.g., `dmarc.policy='reject'`, `spf.mechanisms=[...]`)
- Use system default DNS resolver — no custom DNS server configuration

</decisions>

<specifics>
## Specific Ideas

- "There should be a button to confirm connectivity" — captured as `verify_connection()` health-check function that later phases can expose through UI or API
- This is Exchange Online, not on-premises — the entire connection model shifts from Basic Auth/WinRM to Azure AD app-only auth via ExchangeOnlineManagement module

</specifics>

<deferred>
## Deferred Ideas

- DKIM DNS lookups (CNAME + selector records) — deferred to Phase 5 when get_dkim_config is implemented
- AWS Secrets Manager for credential storage — could replace env vars in a future hardening pass
- Kerberos Constrained Delegation — already noted in STATE.md as deferred to v2

</deferred>

---

*Phase: 01-exchange-client-foundation*
*Context gathered: 2026-03-19*
