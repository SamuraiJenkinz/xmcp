# Phase 4: DAG and Database Tools - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Three tools for querying Exchange DAG infrastructure: list_dag_members (server inventory with status), get_dag_health (replication health per database copy), and get_database_copies (all copies of a named database with failover details). These tools return structured JSON consumed by the LLM — no direct user-facing UI.

</domain>

<decisions>
## Implementation Decisions

### Health status interpretation
- Pass through raw Exchange replication status values (Healthy, DisconnectedAndHealthy, FailedAndSuspended, etc.) — no simplification to traffic-light model
- No top-level summary object — return per-copy details only, LLM aggregates
- Queue lengths (CopyQueueLength, ReplayQueueLength) returned as raw integers — no interpretation thresholds
- Content index state included per copy (Healthy, Crawling, Failed, etc.)

### Database copy detail level
- Activation preference number included per copy (1 = first to activate on failover)
- Active/mounted copy flagged explicitly (is_mounted or status: Mounted field)
- Timestamps included: last inspected log time, last copied log time, last replayed log time
- Database size included in get_database_copies output

### DAG member enrichment
- Active Directory site name included per server
- Database counts per server: active (mounted) and passive counts
- Witness server and witness directory included at the DAG level
- Exchange version/build number included per server

### Error and edge cases
- DAG name not found returns isError: true with clear message
- Database name not found returns isError: true with clear message
- Unreachable DAG member servers included in results with error status (partial results preferred over omission)
- DAG name always required as explicit parameter — no auto-discovery
- Database with zero copies returns isError: true (abnormal state)

### Claude's Discretion
- Exact PowerShell cmdlet selection and parameter ordering
- JSON output field naming conventions (follow patterns from Phase 3)
- Shared helper extraction if patterns repeat across the three tools

</decisions>

<specifics>
## Specific Ideas

- Follow the same pass-through philosophy as Phase 3 (raw Exchange values, LLM interprets) — no date parsing, no value interpretation
- Pattern: "raw data in, LLM reasons about it" — consistent with get_mailbox_stats approach

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-dag-and-database-tools*
*Context gathered: 2026-03-20*
