# Feature Landscape: v1.4 Message Trace & Feedback Analytics

**Domain:** Enterprise AI chat tool — IT engineer audience, Exchange infrastructure context
**Researched:** 2026-04-02
**Milestone scope:** Two feature clusters added to existing Atlas v1.3 application
**Overall confidence:** HIGH (official Microsoft docs verified, existing codebase analyzed)

---

## Feature Cluster 1: Message Trace (Get-MessageTraceV2)

### Context: How This Differs from Existing check_mail_flow

The existing `check_mail_flow` tool answers: "CAN mail flow from Alice to Bob?" It inspects connector configuration, accepted domains, and routing topology. It never touches actual messages.

Message Trace answers: "DID Alice's email to Bob arrive?" It queries actual delivery records: timestamps, statuses, subjects, message IDs. This is the #1 IT helpdesk question for Exchange admins: "Where is my email?"

These are complementary tools. The AI should learn when to use each:
- "Can sales@ email partner@fabrikam.com?" -> check_mail_flow (routing/config)
- "Did Alice's email to Bob arrive yesterday?" -> message_trace (delivery tracking)
- "Alice says Bob never got her email" -> message_trace first, then check_mail_flow if trace shows failure

---

### Table Stakes

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Search by sender address | The most common search pattern. "Trace emails from alice@mmc.com" | Low | ExchangeClient, Get-MessageTraceV2 | SenderAddress parameter, multi-valued |
| Search by recipient address | Second most common. "Did bob get Alice's email?" | Low | ExchangeClient, Get-MessageTraceV2 | RecipientAddress parameter, multi-valued |
| Search by date range | All traces need a time window. Default to last 48h if unspecified | Low | Get-MessageTraceV2 | StartDate/EndDate, max 10 days per query, 90 days total history |
| Display delivery status | The whole point: Delivered, Failed, Pending, Quarantined, FilteredAsSpam, Expanded, GettingStatus | Low | Result parsing | Status is the first thing admins look for |
| Display message subject | Admins need to identify WHICH message. "The one about the budget report" | Low | Result parsing | First 256 chars returned by API |
| Display timestamps (received time) | When did Exchange process it? Critical for "it was sent 2 hours ago" complaints | Low | Result parsing | UTC format from API, present in user-friendly format |
| No-results handling | "No messages found matching your criteria" with helpful suggestions (check spelling, widen date range, check sender/recipient) | Low | Tool response formatting | Very common scenario — typos in email addresses, wrong date range |
| Too-many-results handling | Default 1000 results max, need to summarize not dump. "Found 847 messages from alice@ in the last 2 days. Here are the most recent 10..." | Med | ResultSize parameter, response formatting | AI must summarize, not paste 1000 rows |
| Combined sender+recipient search | "Did Alice's email TO Bob arrive?" requires both parameters | Low | Get-MessageTraceV2 | Most natural user query pattern involves both |
| Error handling for permission issues | Clear message if Exchange permissions are insufficient | Low | ExchangeClient error handling | Admins need to know if it's a permission gap vs no results |
| 10-day query window enforcement | API returns max 10 days per query. If user asks for 30 days, either split into queries or explain the limitation | Med | Tool parameter validation | Get-MessageTraceV2 enforces this server-side, but a good tool explains it proactively |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Search by subject | "Trace the email about Q4 budget" — not just by addresses | Low | Get-MessageTraceV2 Subject + SubjectFilterType params | SubjectFilterType: Contains, StartsWith, EndsWith. Prefer StartsWith/EndsWith per MS docs |
| Search by message ID | IT admins troubleshooting specific NDRs have message IDs from bounce headers | Low | Get-MessageTraceV2 MessageId param | Niche but extremely valuable for escalation scenarios |
| Filter by status | "Show me only failed deliveries from yesterday" | Low | Get-MessageTraceV2 Status param | Multi-valued: Failed, FilteredAsSpam, Quarantined |
| Intelligent date defaulting | If user says "today" or "this morning", compute appropriate StartDate/EndDate. If no date specified, default to last 48 hours | Med | AI prompt engineering + tool parameter logic | 5-10 min delay before messages appear in trace data — note this for "just sent" queries |
| Conversational result presentation | Not a raw table. "Alice sent 3 emails to Bob yesterday. 2 were delivered successfully. 1 was filtered as spam. Here are the details..." | Med | AI system prompt guidance | The AI's natural language summary IS the feature. Tables for details, narrative for summary |
| Trace detail drill-down (Get-MessageTraceDetailV2) | After finding a message, get routing hops, agent actions (transport rules, DLP, malware scan) | High | Second MCP tool (message_trace_detail), MessageTraceId from initial trace | Requires two-step tool calling: trace first, then detail. Very valuable for troubleshooting |
| Smart retry suggestion for Pending status | If status is Pending or GettingStatus, suggest checking again in a few minutes | Low | Status parsing in tool response | "This message is still being processed. Check back in 5-10 minutes for a final status." |
| Cross-reference with check_mail_flow | When trace shows Failed, AI could proactively suggest running check_mail_flow to diagnose routing | Med | AI prompt engineering | Tool chaining: "The delivery failed. Let me check if there's a routing issue between these domains..." |
| IP-based filtering | Search by source IP (FromIP) or destination IP (ToIP) for advanced troubleshooting | Low | Get-MessageTraceV2 FromIP/ToIP params | Power user feature for tracking specific mail servers |
| Pagination for large result sets | Handle >1000 results via StartingRecipientAddress cursor-based pagination | High | Get-MessageTraceV2 pagination mechanism | No native pagination — must use StartingRecipientAddress + EndDate from last record. Complex but needed for busy mailboxes |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Historical search (>90 days) | Get-MessageTraceV2 only covers 90 days. Start-HistoricalSearch is async and returns CSV — completely different UX pattern | Clearly state the 90-day limit. If user needs older data, explain the EAC historical search option |
| Real-time delivery tracking | Message trace data has 5-10 minute lag. Do not promise "real-time" | Set expectations: "Trace data is typically available 5-10 minutes after sending" |
| Message content/body retrieval | Message trace does NOT return email body content. Only metadata (subject, sender, recipient, status, timestamps) | Be explicit: "Message trace shows delivery information, not message content" |
| Attachment information | Not available in trace results | Don't mention attachments in tool description |
| Building a dashboard/chart view | Atlas is conversational, not a dashboard. Message trace results should be presented as text/tables in chat, not as a separate page | Keep everything in the chat flow. Tool panels show raw JSON, AI presents the narrative |
| Automatic re-query loops | Don't automatically re-query for Pending messages on a timer | Let the user ask again when they want an update |
| Bypassing the 100 requests/5min throttle | API rate limit is firm | Implement rate awareness and inform user if throttled |

---

### Edge Cases and Error Scenarios

| Scenario | Expected Behavior | Notes |
|----------|-------------------|-------|
| No results found | "No messages found from alice@mmc.com to bob@mmc.com in the last 48 hours. Try widening your date range or checking the email addresses." | Most common edge case. Typos in addresses are the #1 cause |
| Distribution list expansion | Status "Expanded" means message went to a DL. Individual recipients have their own trace entries | Explain what Expanded means — admins often misread this as a problem |
| Multiple deliveries of same message | Same subject, same sender, different MessageTraceIds. Present as separate entries with timestamps | Common with retries, forwarding rules, or DL expansion |
| Message sent to 1000+ recipients | MessageTraceId required for these. Standard sender/recipient search won't work | Guide user to provide MessageTraceId if available |
| Date range >10 days requested | Split into multiple queries or explain the 10-day-per-query limit | "I can search up to 10 days at a time. Let me check the most recent 10 days first." |
| User asks about very recent message (<10 min) | May not appear yet | "Messages typically appear in trace data 5-10 minutes after sending. This one may not be available yet." |
| Quarantined message found | Status is Quarantined — admin may want to release it | Note: releasing quarantined messages is a separate action not in v1.4 scope |
| Hybrid environment (on-prem + cloud) | Get-MessageTraceV2 only covers Exchange Online leg | Note the limitation for MMC's hybrid setup |
| FilteredAsSpam status | Admin needs to know WHY — transport rules? EOP? | This is where trace detail (differentiator) becomes valuable |
| User provides partial email address | "trace emails from alice" without domain | Tool should require full email. AI should ask for clarification |
| Rate limit hit (100 req/5min) | Return friendly error, suggest waiting | "Exchange Online rate limit reached. Please wait a few minutes before running another trace." |

---

## Feature Cluster 2: Feedback Analytics (MCP Tools)

### Context: What Already Exists

The feedback table stores per-message thumbs up/down with optional comment (max 500 chars), linked to thread_id and assistant_message_idx. Created/updated timestamps. Indexed by (thread_id, assistant_message_idx) and (user_id, vote, created_at DESC).

Messages are stored as OpenAI-format JSON in messages.messages_json, which includes `tool_calls` in assistant messages. This means correlating feedback with tools requires parsing the JSON to find which tools were called near the voted-on assistant message.

Current feedback is per-user, per-thread. There is NO cross-user aggregation yet. The new analytics tools will query across all users' feedback (admin-level visibility).

### Important Design Decision: Who Can See Analytics?

Feedback analytics must be admin-level. Individual users should only see their own feedback (already works). The new analytics MCP tools should aggregate across ALL users, so they need elevated access or a separate permission model. Given Atlas already has role-based access (Azure AD App Roles), this could be gated behind an admin role.

---

### Table Stakes

| Feature | Why Expected | Complexity | Dependency | Notes |
|---------|--------------|------------|------------|-------|
| Total vote counts (up/down) | "How is Atlas doing?" — the most basic metric | Low | SQLite COUNT + GROUP BY on feedback table | SELECT vote, COUNT(*) FROM feedback GROUP BY vote |
| Vote counts by date range | "How was feedback this week?" | Low | feedback.created_at filtering | Allow today, this week, this month, last 30 days, custom range |
| Thumbs-down with comments | "What are people complaining about?" — the actionable data | Low | SELECT from feedback WHERE vote='down' AND comment IS NOT NULL | Comments are the gold. Show most recent N, not just counts |
| Satisfaction rate (% thumbs up) | Single number: "82% positive feedback" | Low | Simple math on counts | Present as percentage. "Atlas has an 82% satisfaction rate this week (45 thumbs up, 10 thumbs down)" |
| Time-filtered queries | "Show feedback from the last 7 days" vs "all time" | Low | WHERE created_at >= datetime(...) | Every analytics query needs a time dimension |
| Feedback count (total interactions rated) | "How many messages have been rated?" vs "how many messages total" | Low | COUNT on feedback table | Context matters: 55 ratings out of 2000 messages = 2.75% feedback rate |

### Differentiators

| Feature | Value Proposition | Complexity | Dependency | Notes |
|---------|-------------------|------------|------------|-------|
| Feedback correlated with Exchange tools | "Which tools get the best/worst feedback?" | High | Parsing messages_json to extract tool_calls near the assistant_message_idx, then joining with feedback | This is the killer feature. Requires: (1) for each feedback row, load messages_json from the thread, (2) find the assistant message at that index, (3) look backwards to find which tool_calls the AI invoked to produce that response, (4) aggregate. See detailed design below. |
| Trend analysis (satisfaction over time) | "Is Atlas getting better or worse?" | Med | GROUP BY date bucketing (daily/weekly) | Show trend direction: "Satisfaction improved from 75% to 88% over the last month" |
| Per-tool satisfaction ranking | "get_dag_health gets 95% thumbs up, check_mail_flow gets 60%" | High | Same tool correlation as above, then per-tool aggregation | Requires significant sample size per tool to be meaningful. Flag if N < 5 |
| Recent negative feedback list | "Show me the last 10 thumbs-down with their comments" | Low | Simple query, ordered by created_at DESC | Most immediately actionable analytics view |
| Feedback rate (% of messages that get rated) | "Only 3% of messages get feedback — should we prompt more?" | Med | Requires counting total assistant messages across all threads (parsing messages_json) | Useful meta-metric about the feedback system itself |
| Daily/weekly summary | "Give me this week's feedback summary" — single command for a digest | Med | Combination of counts, rate, recent complaints | The AI should compose a narrative: "This week: 23 ratings (18 up, 5 down). 78% positive. The 5 negative ratings mentioned: slow response (2), incorrect DAG info (1), confusing output (2)." |
| User engagement metrics | "How many unique users gave feedback this month?" | Low | COUNT(DISTINCT user_id) | Helps assess if feedback represents broad opinion or one vocal user |
| Most-rated threads/topics | "Which conversations get the most feedback?" | Med | GROUP BY thread_id with join to threads table | Identifies which types of questions generate the most reaction |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Individual user identification in analytics | Privacy concern — don't show "User john.smith gave 15 thumbs down" | Aggregate only. Show counts, not who voted what. user_id is for ownership, not surveillance |
| Real-time analytics dashboard | Atlas is conversational, not a BI tool | Analytics are queried on-demand via chat: "Show me this week's feedback" |
| Sentiment analysis on comments | Over-engineering for 500-char comments. The vote IS the sentiment | Just show the comments. Let the human admin interpret |
| Automated alerting on negative feedback | Outside scope — Atlas is a query tool, not a monitoring system | Admin asks when they want to check. No push notifications |
| Feedback editing by admins | Admins should not modify user feedback | Read-only analytics. Feedback is user-generated truth |
| Export to CSV/Excel from analytics | v1.3 already has conversation export. Don't add a separate analytics export path | If needed later, it's a separate feature. Chat-based analytics is sufficient for now |
| Predictive analytics ("feedback will decline next week") | ML on small datasets is noise, not signal | Descriptive analytics only. Show what happened, not what might happen |
| Comparing feedback across different Atlas instances | Only one instance exists at MMC | Single-instance design |

---

### Feedback-to-Tool Correlation: Design Considerations

This is the most complex feature and deserves detailed analysis.

**The Problem:**
- Feedback row says: thread_id=42, assistant_message_idx=3, vote=down
- We need to know: which MCP tools did the AI call to generate assistant message #3?

**The Data Path:**
1. Load `messages_json` from `messages` table for thread_id=42
2. Parse the JSON array of OpenAI-format messages
3. Find the assistant message at index 3 (counting only content-bearing assistant messages, per the schema comment)
4. Look at the preceding messages in the array — the assistant message with `tool_calls` and subsequent `tool` role messages
5. Extract tool names from the `tool_calls[].function.name` fields

**Complexity Factors:**
- The assistant_message_idx is 0-based counting only "content-bearing assistant messages" — not all messages in the array. The indexing logic must match exactly what the frontend uses.
- A single assistant response may involve multiple tool calls (e.g., AI calls get_mailbox_details AND check_mail_flow in one turn).
- Some assistant messages may have NO tool calls (pure conversational responses).
- The messages_json can be large for long conversations.

**Recommended Approach:**
- Build the correlation at query time, not at write time. The feedback table stays simple.
- Create a Python utility function that, given a thread's messages_json and an assistant_message_idx, returns the list of tool names invoked for that response.
- For aggregate analytics, iterate over all feedback rows, resolve tool names for each, then aggregate. This is O(N * M) where N = feedback rows and M = average messages per thread. Acceptable for the expected data volume (hundreds, not millions).
- Cache results if performance becomes an issue later.

**Alternative (rejected): Denormalize tool names into feedback table.**
- Would require schema migration and changing the feedback write path.
- Adds coupling between feedback and message format.
- Premature optimization for the expected data volume.

---

### Edge Cases and Error Scenarios

| Scenario | Expected Behavior | Notes |
|----------|-------------------|-------|
| No feedback data yet | "No feedback has been submitted yet." | New deployment or fresh database |
| Very few ratings (N < 10) | Show data but caveat: "Based on only 7 ratings — this may not be representative" | Small sample warning |
| All feedback is positive | "100% satisfaction rate (23 thumbs up, 0 thumbs down). No negative feedback to review." | Good news is still news |
| Tool correlation with no tool calls | Some assistant messages are pure text (greetings, clarifications). Report as "No tool invoked" or "General conversation" | Don't skip these — they tell a story about non-tool interactions |
| Deleted threads with orphan feedback | Feedback has ON DELETE CASCADE from threads. If thread is deleted, feedback goes too | Historical analytics may lose data if threads are deleted. This is acceptable — don't add soft-delete complexity |
| Multiple tools in one response | "The assistant called get_mailbox_details AND get_dag_health for this response" | Count feedback for EACH tool involved, or track as a "multi-tool" response. Recommend counting for each tool. |
| Feedback on very old threads | messages_json format may have evolved. Tool correlation must handle format variations gracefully | Defensive parsing. If format is unrecognizable, skip tool correlation for that entry |
| Time zone handling | feedback.created_at is UTC. Analytics should present in a user-friendly way | "This week" should be computed server-side in UTC. Don't try to localize — the data is UTC, present it consistently |
| High volume of thumbs-down in short period | Could indicate a real issue (e.g., Exchange connection down). AI should note unusual patterns | "There were 12 thumbs-down in the last hour, compared to an average of 2 per day. This may indicate a service issue." |

---

## Feature Dependencies

```
Message Trace:
  ExchangeClient (exists) --> Get-MessageTraceV2 tool --> AI presentation
  Get-MessageTraceV2 tool --> Get-MessageTraceDetailV2 tool (optional, for drill-down)
  check_mail_flow (exists) <-- cross-reference on failure (AI prompt guidance)

Feedback Analytics:
  feedback table (exists) --> analytics query tools (new)
  messages table (exists) --> tool correlation logic (new)
  analytics query tools --> AI presentation (system prompt guidance)

No dependencies between the two clusters -- they can be built in parallel.
```

---

## MVP Recommendation

### Build First (Phase 1 of v1.4)

**Message Trace:**
1. `message_trace` MCP tool — Get-MessageTraceV2 with sender, recipient, date range, status filter
2. No-results and too-many-results handling
3. AI system prompt guidance for when to use message_trace vs check_mail_flow
4. Subject search (low effort, high value)

**Feedback Analytics:**
1. `get_feedback_stats` MCP tool — vote counts, satisfaction rate, by date range
2. `get_feedback_comments` MCP tool — recent thumbs-down with comments
3. Basic time filtering (today, this week, this month, all time)

### Build Second (Phase 2 of v1.4)

**Message Trace:**
4. `message_trace_detail` MCP tool — Get-MessageTraceDetailV2 for routing hop drill-down
5. Message ID search
6. Status-only filtering
7. Rate limit awareness

**Feedback Analytics:**
4. Tool correlation logic (the hard part)
5. `get_feedback_by_tool` MCP tool — per-tool satisfaction ranking
6. Trend analysis (satisfaction over time)
7. Daily/weekly summary composition

### Defer to Post-v1.4

- IP-based trace filtering (FromIP/ToIP) — niche power-user feature
- Pagination for >1000 trace results — wait until someone actually hits this
- Feedback rate metric — requires counting all assistant messages, expensive
- Most-rated threads/topics — interesting but not actionable yet

---

## Presentation Patterns for Conversational AI

Since Atlas is conversational (not a dashboard), how the AI presents results matters enormously.

### Message Trace Presentation

**Single result:**
> "Alice's email to Bob with subject 'Q4 Budget Report' was **delivered successfully** on April 1 at 2:34 PM UTC."

**Multiple results — summary first, then details:**
> "I found 5 emails from alice@mmc.com to bob@mmc.com in the last 48 hours:
> - 4 delivered successfully
> - 1 filtered as spam
>
> | Time (UTC) | Subject | Status |
> |---|---|---|
> | Apr 1 14:34 | Q4 Budget Report | Delivered |
> | Apr 1 10:12 | Meeting Notes | Delivered |
> | Mar 31 16:45 | FW: Vendor Quote | FilteredAsSpam |
> | ... | ... | ... |"

**No results:**
> "No messages found from alice@mmc.com to bob@mmc.com in the last 48 hours. A few things to check:
> - Verify the email addresses are correct
> - Try a wider date range (I can search up to 90 days back)
> - The message may still be processing if it was sent in the last few minutes"

**Failed delivery:**
> "Alice's email to bob@external.com **failed to deliver** on April 1 at 3:15 PM UTC. Subject: 'Partnership Proposal'. Would you like me to check the mail flow configuration between these domains to see if there's a routing issue?"

### Feedback Analytics Presentation

**Summary:**
> "This week's feedback summary: **82% positive** (41 thumbs up, 9 thumbs down) from 14 unique users.
>
> The 9 negative ratings included these comments:
> - 'Response was too slow' (3 mentions)
> - 'DAG health info was wrong' (1)
> - 'Didn't understand my question' (2)
> - No comment provided (3)"

**Per-tool (when available):**
> "Tool satisfaction this month:
> | Tool | Thumbs Up | Thumbs Down | Satisfaction |
> |---|---|---|---|
> | get_mailbox_details | 28 | 2 | 93% |
> | get_dag_health | 15 | 4 | 79% |
> | check_mail_flow | 8 | 5 | 62% |
> | search_mailboxes | 12 | 1 | 92% |
>
> Note: check_mail_flow has the lowest satisfaction. The negative comments mention 'confusing output' and 'not enough detail'."

---

## IMPORTANT: Get-MessageTraceV2 Migration Note

**Get-MessageTrace was deprecated September 1, 2025.** The replacement is Get-MessageTraceV2, which requires Exchange Online PowerShell V3 module version 3.7.0+.

Key differences from the legacy cmdlet:
- 90-day history (up from 10 days in old cmdlet)
- 10-day max per query window (same)
- 5000 max results (up from 1000 default, was configurable)
- No PageSize — use StartingRecipientAddress/EndDate for cursor-based pagination
- SubjectFilterType parameter (Contains/StartsWith/EndsWith) — new
- 100 requests per 5-minute throttle window
- Status values include new GettingStatus value

**Build against Get-MessageTraceV2 from day one. Do not use the deprecated Get-MessageTrace.**

---

## Sources

- [Get-MessageTraceV2 official documentation](https://learn.microsoft.com/en-us/powershell/module/exchangepowershell/get-messagetracev2?view=exchange-ps) (HIGH confidence, updated Feb 2025)
- [Message trace in Exchange Admin Center](https://learn.microsoft.com/en-us/exchange/monitoring/trace-an-email-message/message-trace-modern-eac) (HIGH confidence)
- [Message Trace FAQ](https://learn.microsoft.com/en-us/exchange/monitoring/trace-an-email-message/message-trace-faq) (HIGH confidence)
- [Get-MessageTraceV2 GA announcement](https://techcommunity.microsoft.com/blog/exchange/announcing-general-availability-ga-of-the-new-message-trace-in-exchange-online/4420243) (HIGH confidence)
- [Chatbot Analytics metrics guide](https://hiverhq.com/blog/chatbot-analytics) (MEDIUM confidence — general patterns, not Atlas-specific)
- Existing codebase: chat_app/feedback.py, chat_app/schema.sql, exchange_mcp/tools.py (HIGH confidence — direct code analysis)
