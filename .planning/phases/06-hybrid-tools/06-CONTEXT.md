# Phase 6: Hybrid Tools - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the final hybrid Exchange tools (get_hybrid_config, get_connector_status) completing the MCP server's tool inventory. get_migration_batches has been removed from scope — MMC does not use migration batches. Total tool count is 14 (not 15). All references to "15 tools" across the codebase must be updated.

</domain>

<decisions>
## Implementation Decisions

### Hybrid config scope (get_hybrid_config)
- Full topology: org relationships, federation trust, OAuth config, free/busy sharing settings
- Hybrid mail flow connectors (inbound/outbound to O365) included inline — complete picture in one call, not just references to get_smtp_connectors
- Full OAuth/federation auth details included: token endpoints, certificate thumbprints, delegation trust — critical for troubleshooting hybrid auth failures
- Free/busy and calendar sharing config included: AvailabilityAddressSpace, sharing policies, target delivery domains

### Connector health checks (get_connector_status)
- Live connectivity test against Exchange Online endpoint — confirms hybrid link is working right now
- Scope limited to hybrid send/receive connectors only — not hybrid agents, MRS proxy, or federation endpoints
- TLS certificate details included: issuer, expiry, thumbprint — critical for troubleshooting connector failures
- Simple healthy/unhealthy boolean status per connector with error message if unhealthy

### Cross-tool consistency
- Raw Exchange values passed through as-is (dates as /Date(ms)/, sizes as strings) — same pattern as all 12 existing tools
- RuntimeError for bad input, empty result for valid-but-no-data — matches existing error pattern
- Tool descriptions continue the "does NOT" clause disambiguation and single-quoted example queries convention
- Update all references to "15 tools" → "14 tools" as part of Phase 6 work

### Claude's Discretion
- Org relationship data depth and field selection from Get-OrganizationRelationship
- Exact Exchange cmdlets and field projections for hybrid config retrieval
- How to structure the live connectivity test (Test-ServiceHealth, SMTP test, or similar)

</decisions>

<specifics>
## Specific Ideas

- get_hybrid_config should give a complete hybrid picture in one call — colleagues shouldn't need to chain multiple tool calls to understand hybrid topology
- Connector health should be immediately actionable: healthy or not, with a clear error if not

</specifics>

<deferred>
## Deferred Ideas

- get_migration_batches removed from scope — MMC does not use migration batches. If needed in future, add as a new phase.

</deferred>

---

*Phase: 06-hybrid-tools*
*Context gathered: 2026-03-20*
