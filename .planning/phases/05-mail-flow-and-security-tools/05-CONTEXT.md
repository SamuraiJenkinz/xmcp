# Phase 5: Mail Flow and Security Tools - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement six Exchange infrastructure tools: three mail flow tools (check_mail_flow, get_transport_queues, get_smtp_connectors) and three security tools (get_dkim_config, get_dmarc_status, check_mobile_devices). The security tools combine live DNS lookups with Exchange PowerShell data where needed. All tools follow the existing handler pattern from Phases 3-4 (async handler, dispatch table entry, unit tests with mocked ExchangeClient).

</domain>

<decisions>
## Implementation Decisions

### Mail flow tracing (check_mail_flow)
- Both sender and recipient are required parameters — no single-endpoint tracing
- Infer routing path from connector configuration (Get-TransportService, send/receive connector rules) — do NOT send a test message via Test-MailFlow
- Full hop trace: show source → connector → next hop → destination with TLS status per hop
- Identify specific send/receive connectors involved in the route by name
- No actual mail delivery — this is a config-based route analysis tool

### Queue backlog thresholds (get_transport_queues)
- Configurable backlog threshold parameter with a sensible default — flag queues exceeding it
- Return ALL queues across all transport servers, including empty ones (shows full transport topology)
- Organize results per-server — group queues under their transport server name
- Include delivery type breakdown per queue (SmtpDeliveryToMailbox, SmartHostConnectorDelivery, etc.) — not just total counts

### SMTP connector inventory (get_smtp_connectors)
- Return full send and receive connector inventory with auth and TLS configuration
- Claude's Discretion on output structure and field selection

### DKIM configuration (get_dkim_config)
- Combined Exchange + DNS in one call: return Exchange DKIM signing config AND live DNS CNAME record validation
- Optional domain parameter — return all domains by default, filter to one domain if provided
- DNS CNAME lookup validates whether the published records match what Exchange expects

### DMARC/SPF status (get_dmarc_status)
- Pure DNS tool — no PowerShell dependency (uses existing dnspython resolver from Phase 1)
- Return both raw TXT record and parsed policy fields — LLM can reference either
- Claude's Discretion on single vs multi-domain input (determine what's most natural for LLM tool-calling)

### Mobile device partnerships (check_mobile_devices)
- Per-user required — always require a UPN, no org-wide listing
- Return ALL devices ever synced, including stale partnerships — LLM can filter by last sync time
- Include wipe history: remote wipe status, request time, completion time — critical for security incident response
- Full device details: model, OS, user agent alongside device ID, access state, and last sync time

### Claude's Discretion
- get_smtp_connectors output structure and field selection
- get_dmarc_status single vs multi-domain input design
- Default backlog threshold value for get_transport_queues
- Exact cmdlet selection and Select-Object field lists for each handler
- Error handling patterns (follow Phase 3-4 conventions: not-found → friendly error, partial results where appropriate)

</decisions>

<specifics>
## Specific Ideas

- check_mail_flow should feel like a "route tracing" tool, not a "message sending" tool — safe to run in production without side effects
- get_transport_queues backlog flagging should be obvious in the output — the LLM needs to spot problems without doing math
- get_dkim_config combining Exchange config with DNS validation in one call means the LLM can answer "is DKIM working for domain X?" without chaining two tools
- check_mobile_devices wipe history is the security incident use case — "has this user's device been wiped? when?"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-mail-flow-and-security-tools*
*Context gathered: 2026-03-20*
