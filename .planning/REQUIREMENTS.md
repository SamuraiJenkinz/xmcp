# Requirements: Atlas v1.4 — Message Trace & Feedback Analytics

**Defined:** 2026-04-06
**Core Value:** Any colleague with appropriate access can interrogate Exchange infrastructure through conversational queries against live environment data

## v1.4 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Message Trace

- [x] **TRACE-01**: New MCP tool `get_message_trace` searches Exchange Online message trace by sender, recipient, and date range (default last 24h, max 10 days per query)
- [x] **TRACE-02**: Uses `Get-MessageTraceV2` cmdlet (not deprecated `Get-MessageTrace`)
- [x] **TRACE-03**: Results include subject line, delivery status, received timestamp, sender, recipient, message ID
- [x] **TRACE-04**: All 7 delivery status values handled and presented clearly (Delivered, Failed, Pending, Quarantined, FilteredAsSpam, Expanded, GettingStatus)
- [x] **TRACE-05**: Result count capped (default 100, max 1000) to prevent hangs on broad queries
- [x] **TRACE-06**: Subject line filter parameter for narrowing results before returning
- [x] **TRACE-07**: Routing detail included (FromIP, ToIP, connector name) when available
- [x] **TRACE-08**: Subject lines stripped/truncated to mitigate PII exposure in tool results
- [x] **TRACE-09**: System prompt contrastive description differentiating `get_message_trace` (actual delivery tracking) from `check_mail_flow` (routing topology)
- [x] **TRACE-10**: Tool protected by `role_required` decorator consistent with all other protected routes

### Feedback Analytics

- [ ] **FBAN-01**: New MCP tool `get_feedback_summary` returns vote counts (up/down/total) with date range filter (default last 7 days)
- [ ] **FBAN-02**: `get_feedback_summary` includes daily trend breakdown within the date range
- [ ] **FBAN-03**: New MCP tool `get_low_rated_responses` returns thumbs-down entries with comment text, thread name, and timestamp
- [ ] **FBAN-04**: `get_low_rated_responses` supports limit parameter (default 20) and date range filter
- [ ] **FBAN-05**: New MCP tool `get_feedback_by_tool` correlates feedback votes with which Exchange tool was invoked for that message
- [ ] **FBAN-06**: `get_feedback_by_tool` includes top-N worst-rated tool queries
- [ ] **FBAN-07**: MCP server reads SQLite database in read-only mode (WAL concurrent reader safety)
- [ ] **FBAN-08**: New module `exchange_mcp/feedback_analytics.py` isolates analytics handlers from Exchange tool handlers
- [ ] **FBAN-09**: Tool correlation parses `messages_json` to match `assistant_message_idx` with tool names from tool_calls
- [ ] **FBAN-10**: No per-user voting patterns exposed — all analytics are aggregate only
- [ ] **FBAN-11**: System prompt guidance for presenting analytics results conversationally

### Infrastructure

- [x] **INFRA-01**: Message Tracking RBAC role verified on Atlas service principal before implementation
- [ ] **INFRA-02**: `ATLAS_DB_PATH` environment variable provides database path to MCP server for feedback analytics

## Future Requirements

Deferred to later milestones.

### Message Trace

- **TRACE-11**: Historical message trace beyond 10 days via `Start-HistoricalSearch` (async, up to 90 days)
- **TRACE-12**: Entra ID registered device lookup alongside Exchange ActiveSync (from v1.3 user feedback)

### Feedback Analytics

- **FBAN-12**: Admin-only web dashboard for feedback visualization
- **FBAN-13**: Feedback export to CSV/JSON for external reporting
- **FBAN-14**: Feedback correlation with conversation length/complexity

## Out of Scope

| Feature | Reason |
|---------|--------|
| Historical message trace (>10 days) | Requires async Start-HistoricalSearch with separate polling — different UX pattern |
| Per-user feedback breakdown | Privacy concern — aggregate only for analytics |
| Write access to SQLite from MCP server | Read-only is mandatory for WAL safety; Flask owns writes |
| Separate analytics dashboard UI | Conversational MCP tools are the interface — no new frontend routes |
| Raw Subject line exposure | PII risk — must strip/truncate before including in tool results |
| Message recall/deletion actions | Atlas is read-only; trace is observation only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRACE-01 | Phase 26 | Pending |
| TRACE-02 | Phase 26 | Pending |
| TRACE-03 | Phase 26 | Pending |
| TRACE-04 | Phase 26 | Pending |
| TRACE-05 | Phase 26 | Pending |
| TRACE-06 | Phase 26 | Pending |
| TRACE-07 | Phase 26 | Pending |
| TRACE-08 | Phase 26 | Pending |
| TRACE-09 | Phase 26 | Pending |
| TRACE-10 | Phase 26 | Pending |
| FBAN-01 | Phase 27 | Pending |
| FBAN-02 | Phase 27 | Pending |
| FBAN-03 | Phase 27 | Pending |
| FBAN-04 | Phase 27 | Pending |
| FBAN-05 | Phase 28 | Pending |
| FBAN-06 | Phase 28 | Pending |
| FBAN-07 | Phase 27 | Pending |
| FBAN-08 | Phase 27 | Pending |
| FBAN-09 | Phase 28 | Pending |
| FBAN-10 | Phase 27 | Pending |
| FBAN-11 | Phase 28 | Pending |
| INFRA-01 | Phase 26 | Pending |
| INFRA-02 | Phase 27 | Pending |

**Coverage:**
- v1.4 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-04-06*
*Last updated: 2026-04-02 after roadmap creation*
