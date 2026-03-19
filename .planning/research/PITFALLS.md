# Domain Pitfalls

**Domain:** Exchange MCP Server + Python Chat App with Kerberos/Azure AD SSO
**Project:** xmcp — Marsh McLennan Exchange MCP Server
**Researched:** 2026-03-19
**Confidence:** HIGH (verified against official MCP spec, Microsoft docs, MSAL docs, Azure OpenAI docs)

---

## Critical Pitfalls

Mistakes that cause rewrites or major incidents.

---

### Pitfall 1: stdout Pollution Kills the MCP Protocol

**What goes wrong:**
The MCP stdio transport uses stdout as the exclusive JSON-RPC message channel. Any non-MCP bytes written to stdout — print statements, logging output, PSSession output bleed, subprocess output — corrupt the message stream. The client receives malformed JSON, the handshake fails, or silently drops messages.

**Why it happens:**
Developers use `print()` for debugging during development. Python libraries (e.g., MSAL) sometimes emit startup banners. Exchange cmdlets can occasionally emit warning text to the output stream if output isn't captured explicitly.

**Consequences:**
- MCP client (Claude Desktop, etc.) cannot parse responses
- Entire server is non-functional from the client's perspective
- Fails silently: client gets no error, just broken behavior
- Very hard to debug because the corruption happens before any tool call

**Prevention:**
- ALL logging must go to stderr only: `logging.basicConfig(stream=sys.stderr)`
- Never use `print()` in production MCP server code
- Suppress all MSAL/library banners via logging level configuration
- Wrap PSSession invocations in `Invoke-Command` with `ErrorAction SilentlyContinue` where safe; capture output explicitly via `$output = ...`
- In the MCP server process, redirect any subprocess stdout to stderr before launching

**Warning signs:**
- Client reports "invalid JSON" or "unexpected token" errors
- MCP handshake never completes
- Works in isolation but breaks when integrated

**Phase:** Phase 1 (MCP server foundation) — must be addressed before any other work

---

### Pitfall 2: PSSession Creation at 2-4 Seconds Makes Concurrent Requests Unacceptable

**What goes wrong:**
Per-call PSSession creation is the intended design (no pooling), but this means every MCP tool call carries a 2-4 second mandatory overhead. If the chat app allows concurrent requests (e.g., the model calls two tools in parallel, or two browser tabs are open), latency compounds linearly. At 80K+ mailboxes, cmdlets like `Get-Mailbox -ResultSize Unlimited` can take 30-60+ seconds and hold the session open the entire time.

**Why it happens:**
WinRM handshake + Exchange module import + Kerberos ticket acquisition = 2-4s minimum. This is not a bug — it is the architecture. The risk is treating this as a background concern rather than a first-class design constraint from day one.

**Consequences:**
- Users experience 4-8 second minimum response time for any Exchange query
- Long-running cmdlets cause HTTP timeout at the chat app layer if timeouts aren't set correctly
- If session is not cleaned up on exception, orphaned PSSessions accumulate; Exchange on-prem has a default limit of 18 concurrent remote sessions per user

**Prevention:**
- Document the 2-4s latency in the tool descriptions so the LLM can set user expectations
- Set explicit timeout values at every layer: PSSession open timeout, cmdlet timeout, MCP call timeout, HTTP timeout in the chat app
- Always wrap PSSession creation and use in try/finally to guarantee `Remove-PSSession` runs on any exit path
- For large queries, use `-ResultSize` parameters to avoid unbounded scans
- Consider a `ResultSize` cap (e.g., 1000) as a hard default on mailbox listing tools — configurable but defaulted

**Warning signs:**
- Chat app shows spinner for >10 seconds on simple queries
- Exchange server logs show large numbers of open WinRM sessions
- Timeouts appearing randomly under moderate load

**Phase:** Phase 1 (design constraint) and Phase 2 (per-tool ResultSize defaults)

---

### Pitfall 3: Kerberos Negative Cache Breaks Delegation After Configuration Changes

**What goes wrong:**
The Kerberos KDC caches denied-access attempts (negative cache) for 15 minutes. After configuring Resource-Based Constrained Delegation (RBCD) or SPN assignments, the target server (Exchange) may continue rejecting delegation for up to 15 minutes even when configuration is correct. This causes "access denied" errors that look like misconfiguration but are actually stale cache.

**Why it happens:**
The KDC negative cache is invisible to administrators. Teams fix a configuration error, test immediately, see failure, and either roll back a correct fix or waste time re-checking AD attributes.

**Consequences:**
- Hours lost diagnosing correctly-configured delegation
- False confidence in a broken configuration (if the fix coincides with cache expiry)
- Production incidents when Kerberos tickets expire during live use (default ticket lifetime is 10 hours)

**Prevention:**
- After any delegation configuration change, wait 15 minutes OR run `klist purge -li 0x3e7` on the intermediate server to clear the Kerberos cache
- Use `klist` to verify ticket acquisition before integration testing
- Document the required SPNs: WinRM uses `WSMAN/<hostname>` and `WSMAN/<FQDN>`; Exchange uses `exchangeMDB` and `exchangeRFR` SPNs — verify all are registered before testing
- Prefer Resource-Based Constrained Delegation (RBCD) over traditional KCD: RBCD does not require Domain Admin and works across domains
- Test delegation separately from application code using `Invoke-Command` with explicit credentials before wiring into the MCP server

**Warning signs:**
- "Access is denied" on WinRM connections that work interactively
- Delegation works on first attempt of the day but fails after Kerberos ticket renewal
- `klist` shows no service ticket for the Exchange server from the MCP server's context

**Phase:** Phase 1 (infrastructure setup) — must be verified and documented before application code

---

### Pitfall 4: Azure AD SSO Token Passed to MCP Server Without Validation Allows Identity Spoofing

**What goes wrong:**
The chat app receives an Azure AD access token after SSO login. If this token is forwarded to the MCP server (or used to initiate the Kerberos delegation chain) without server-side signature validation, an attacker can forge or replay tokens to impersonate any user.

**Why it happens:**
Developers trust that Azure AD issued the token and skip validation on the receiving server. The token arrives as a Bearer header — it looks legitimate. But the MCP server is a separate process and must independently validate the token's signature, issuer, audience, and expiry.

**Consequences:**
- Any user can query mailboxes of other users by manipulating token claims
- At 80K+ mailboxes, this is a significant data exposure risk
- Audit trail shows MCP server identity, not the actual requestor

**Prevention:**
- The MCP server (or its HTTP gateway) must validate the JWT: check `iss` (issuer), `aud` (audience must match the server's own App ID), `exp`, and `nbf`
- Use `msal` or `azure-identity` for token validation — never roll your own JWT parser
- The UPN extracted from the validated token must be the identity used to construct the Kerberos delegation call — never trust a client-supplied UPN
- Configure MSAL `ConfidentialClientApplication` with the correct tenant ID, not `common`, to prevent cross-tenant token acceptance

**Warning signs:**
- MCP server accepts any well-formed JWT without checking `aud`
- Chat app passes raw token as a URL parameter or in a non-standard header
- No token expiry check before initiating PSSession

**Phase:** Phase 2 (authentication integration) — security gate before any user data access

---

### Pitfall 5: Exchange PowerShell Output is .NET Objects, Not JSON — Serialization Causes Silent Data Loss

**What goes wrong:**
Exchange cmdlets return rich .NET objects (e.g., `Microsoft.Exchange.Data.Directory.Recipient.Mailbox`). When these are implicitly serialized via `ConvertTo-Json` (default depth of 2), nested objects are truncated to their type name string rather than their value. Properties like `EmailAddresses` (a collection) become `"EmailAddresses": "Microsoft.Exchange.Data.ProxyAddressCollection"` — a useless string.

**Why it happens:**
`ConvertTo-Json` has a default `-Depth 2`. Exchange objects have deeply nested properties. Teams use the default and get truncated output silently — no error, just wrong data.

**Consequences:**
- MCP tools return data that looks correct but is missing key fields
- LLM makes incorrect decisions based on truncated output
- Hard to catch in testing if you only test simple string properties

**Prevention:**
- Always explicitly select the fields you need: `Get-Mailbox user | Select-Object DisplayName, PrimarySmtpAddress, EmailAddresses, ...`
- Convert `EmailAddresses` (ProxyAddressCollection) explicitly: `$mb.EmailAddresses | ForEach-Object { $_.ToString() }`
- Use `ConvertTo-Json -Depth 10` when you must serialize nested objects
- Define explicit output schemas for each tool — know exactly what fields are returned and verify them during development

**Warning signs:**
- Tool output contains strings like `"Microsoft.Exchange.Data..."` instead of values
- `ConvertTo-Json` output is suspiciously small for an object you know is complex
- Tests pass on simple mailboxes but fail on mailboxes with many proxy addresses

**Phase:** Phase 2 (tool implementation) — define output schema per tool before implementation

---

## Moderate Pitfalls

Mistakes that cause delays or significant technical debt.

---

### Pitfall 6: MCP Tool Descriptions That Are Too Vague or Too Long Degrade LLM Tool Selection

**What goes wrong:**
The LLM chooses tools based on their `description` and `inputSchema`. Vague descriptions ("gets mailbox info") cause the LLM to pick the wrong tool or call tools unnecessarily. Descriptions over 1,024 characters are truncated by Azure OpenAI (this is a hard limit per the official documentation).

**Why it happens:**
Developers write descriptions as developer documentation rather than as LLM guidance. Enterprise tools often have many overlapping capabilities that need clear disambiguation.

**Consequences:**
- LLM calls `Get-Mailbox` when it should call `Get-MailboxStatistics` (or vice versa)
- LLM hallucinates parameters not in the schema because the description implies capabilities that aren't implemented
- Tool selection errors produce confusing responses even when the underlying Exchange call works correctly

**Prevention:**
- Keep each tool description under 800 characters (leave buffer before the 1,024 limit)
- Use the format: "What it does. When to use it (not when to use [related tool]). What the key output fields mean."
- For Exchange tools specifically, distinguish: `Get-Mailbox` (configuration/identity) vs `Get-MailboxStatistics` (size/usage) vs `Get-MessageTrackingLog` (message flow) — these are commonly confused
- Test tool selection by asking the model the same question multiple ways and checking that it consistently picks the correct tool

**Warning signs:**
- LLM calls a tool with parameters not in its schema
- Same query alternates between two similar tools across conversations
- LLM produces "I don't have a tool for that" when a matching tool exists

**Phase:** Phase 2 (tool design) — write descriptions before implementing tools

---

### Pitfall 7: MSAL Token Cache Not Persisted Across Python Process Restarts Forces Re-Authentication

**What goes wrong:**
MSAL's default token cache is in-memory. When the chat app Python process restarts (deploy, crash, auto-restart), all cached tokens are lost. Every user must re-authenticate interactively. In enterprise environments with Conditional Access policies (MFA required), this is disruptive.

**Why it happens:**
The MSAL documentation shows in-memory cache as the default example. Teams ship with the default, forget to add persistence, and only notice in production when restarts cause authentication prompts.

**Consequences:**
- Users are prompted for MFA mid-session after a deploy
- In a corporate environment where WAM (Web Account Manager) is involved, token prompts may fail non-interactively
- Session state inconsistency if some users have tokens and others don't

**Prevention:**
- Use MSAL's `SerializableTokenCache` with a file or database backend from day one
- For a server-side web app, store the token cache per-user in a server-side session store (Redis, database), not a local file
- Register a cache serialization hook: `app.token_cache.deserialize(...)` on startup, `app.token_cache.serialize()` after every token acquisition
- Test the full authentication flow after a process restart in development

**Warning signs:**
- Users report "it asked me to sign in again" after any deployment
- Token cache is an empty dict after server restart
- MSAL `acquire_token_silent` always returns None

**Phase:** Phase 3 (chat app authentication) — wire up persistent cache before any user testing

---

### Pitfall 8: CredSSP Should Never Be Used — It Stores Credentials on the Intermediate Server

**What goes wrong:**
CredSSP is the "easy" solution for the PowerShell second-hop problem. It works. It is also explicitly not recommended by Microsoft security documentation because it caches the user's plaintext-equivalent credentials on the intermediate server (the MCP server). If that server is compromised, all delegated credentials are exposed.

**Why it happens:**
CredSSP solves the double-hop problem in 5 minutes. KCD/RBCD takes more time and requires AD changes. Under deadline pressure, teams choose CredSSP and never revisit it.

**Consequences:**
- Full credential exposure on the MCP server host
- Violates Marsh McLennan security policy (assumed — enterprise environments universally prohibit CredSSP)
- CredSSP does not work with members of the Protected Users security group (which privileged accounts are often added to)
- Audit finding that requires emergency remediation

**Prevention:**
- Use Resource-Based Constrained Delegation exclusively — never CredSSP
- Document the RBCD configuration in infrastructure-as-code (Terraform/Bicep/PowerShell script) so it is reproducible
- If RBCD is too complex for a phase, use a dedicated service account with specific Exchange RBAC roles rather than delegated user credentials — accept the loss of per-user identity temporarily

**Warning signs:**
- Any mention of `Enable-WSManCredSSP` in setup documentation
- Any `Authentication CredSSP` in `New-PSSession` calls

**Phase:** Phase 1 (infrastructure) — architecture decision that cannot be changed later without significant rework

---

### Pitfall 9: Azure OpenAI Tool Call Response Not Appended to Messages Array Breaks Multi-Turn Tool Use

**What goes wrong:**
The Azure OpenAI tool calling protocol requires that after a tool call, the assistant's response message (containing `tool_calls`) AND the tool result messages (with `role: "tool"`) must both be appended to the messages array before the next API call. If either is missing, the API returns a validation error or the model loses context of what it called.

**Why it happens:**
The example code pattern is subtle: the assistant message with `tool_calls` must be appended first (even though it has `content: null`), then each tool result. Teams forget to append the assistant message, or append results in the wrong order, or forget to include `tool_call_id` on results.

**Consequences:**
- API returns `400 Bad Request` with cryptic error about tool messages
- Multi-step tool use (where the model calls a tool, gets a result, then calls another tool) breaks
- Conversation history becomes inconsistent, causing the model to repeat questions

**Prevention:**
- Use this exact pattern:
  ```python
  # 1. Append the assistant message (even if content is None)
  messages.append(response.choices[0].message)
  # 2. For each tool call, append the tool result
  for tool_call in response.choices[0].message.tool_calls:
      result = execute_tool(tool_call)
      messages.append({
          "role": "tool",
          "tool_call_id": tool_call.id,  # REQUIRED
          "name": tool_call.function.name,
          "content": result
      })
  ```
- Write a helper function that handles this pattern — never inline it
- Test with two consecutive tool calls to verify the messages array is correct

**Warning signs:**
- `400 Bad Request` errors that mention "tool" or "function" messages
- Model asks the same question again after receiving a tool result
- `tool_call_id` missing or mismatched

**Phase:** Phase 4 (LLM integration) — verify before any end-to-end testing

---

### Pitfall 10: MCP isError Flag Not Set Causes LLM to Treat Exchange Errors as Valid Data

**What goes wrong:**
The MCP protocol distinguishes between two error modes: protocol-level errors (the tool doesn't exist, invalid arguments) and tool execution errors (Exchange returned an error, PSSession failed). Tool execution errors must be returned as successful responses with `isError: true` and a descriptive message. If `isError` is omitted and the error message is returned as normal text content, the LLM treats the error message as a valid Exchange response and may summarize it as if it were real data.

**Why it happens:**
Developers handle exceptions, format an error message, and return it as text content — which looks correct. The `isError` field feels optional. But it is the signal the LLM uses to know whether to retry, rephrase, or report an error to the user.

**Consequences:**
- LLM tells users "The mailbox was not found" in a way that sounds like a valid query result rather than an error
- LLM does not retry or suggest alternatives when it should
- Error messages from Exchange (which can include internal server names and stack traces) are exposed to users

**Prevention:**
- Every tool implementation must have two code paths: success (return data, `isError: false`) and failure (return sanitized error, `isError: true`)
- Sanitize Exchange error messages before returning them — strip internal hostnames, GUIDs, and stack trace details
- Test every tool with invalid inputs (non-existent mailbox, permission denied, timeout) to verify error paths

**Warning signs:**
- Returning `{"content": [{"type": "text", "text": "Error: ..."}]}` without `"isError": true`
- Tool handler has a single catch-all that returns the raw exception message

**Phase:** Phase 2 (tool implementation) — error handling pattern must be established in first tool, applied to all subsequent

---

### Pitfall 11: Conversation History Growth Hits Context Window Silently

**What goes wrong:**
The chat app appends every message, tool call, and tool result to the messages array. Exchange tool results can be large (e.g., listing mailbox statistics for 100 mailboxes). Over a long conversation, the messages array grows until it exceeds the model's context window. `gpt-4o-mini` has a 128K token context window — large but not infinite. When the limit is hit, the API returns a `400 context_length_exceeded` error or silently truncates (depending on configuration).

**Why it happens:**
Early in development, conversations are short. The problem only appears after sustained use or when tools return large datasets. By then, the conversation history management has not been designed in.

**Consequences:**
- Chat app crashes with a cryptic 400 error mid-conversation
- Silently truncated context causes the model to forget earlier conversation turns
- Users lose conversation context without explanation

**Prevention:**
- Implement a token counting strategy from the start: use `tiktoken` to count tokens before each API call
- Define a context window budget (e.g., 100K tokens max, leaving 28K for the response)
- Implement a conversation pruning strategy: keep system message, recent N turns, and summarize older turns rather than dropping them
- For Exchange tool results, enforce maximum result sizes at the tool level (not after the fact)
- Test with conversations that span 20+ turns including multiple tool calls

**Warning signs:**
- API returns `context_length_exceeded` error
- Model references events from earlier in the conversation incorrectly
- Token usage per request growing linearly with no cap

**Phase:** Phase 4 (LLM integration) — design the context management strategy before building the chat UI

---

## Minor Pitfalls

Mistakes that cause annoyance or debugging time but are fixable.

---

### Pitfall 12: Exchange Cmdlet Throttling in Large Environments

**What goes wrong:**
Exchange Server on-premises enforces PowerShell throttling policies that limit the number of concurrent connections and the rate of cmdlet execution per user. In an 80K+ mailbox environment, policies may be more restrictive than defaults. The error message (`The server did not respond to the remote operation...` or `Cmdlet failed because of a transient failure`) is generic and does not clearly indicate throttling.

**Prevention:**
- Check the throttling policy applied to the service account used by the MCP server: `Get-ThrottlingPolicy` / `Get-ThrottlingPolicyAssociation`
- Use `-ResultSize` on all listing cmdlets to avoid unbounded scans that hold connections open
- Add retry logic with exponential backoff on WinRM connection errors

**Phase:** Phase 2 (tool implementation)

---

### Pitfall 13: MSAL Conditional Access Claims Challenge Not Handled in Python Web App

**What goes wrong:**
Azure AD Conditional Access policies (MFA step-up, device compliance) can require a claims challenge mid-session. MSAL's `acquire_token_silent` returns an error with `error: "interaction_required"` and a `claims` value. If the app doesn't handle this by redirecting to interactive authentication with the claims challenge included, the user gets a generic error and cannot complete the requested action.

**Prevention:**
- Check `result.get("error") == "interaction_required"` after every `acquire_token_silent` call
- When this occurs, redirect to interactive login with `claims=result.get("claims")`
- Test with a Conditional Access policy enabled in a dev tenant

**Phase:** Phase 3 (authentication integration)

---

### Pitfall 14: WinRM Default Port 5985 (HTTP) vs 5986 (HTTPS) Mismatch in Hybrid Environment

**What goes wrong:**
Exchange hybrid environments often have mixed WinRM configurations. Some servers accept only HTTPS (5986), others accept HTTP (5985). A PSSession created to the wrong port fails with a connection error, but the error message says "connection refused" not "wrong port". Additionally, using HTTP in production is a security issue that requires explicit Allow configuration.

**Prevention:**
- Explicitly configure the WinRM port in the PSSession connection URI: `http://exchangeserver.domain.com:5985/PowerShell`
- Document the chosen port in configuration and require HTTPS in production
- Verify the WinRM listener configuration on the Exchange server: `winrm enumerate winrm/config/Listener`

**Phase:** Phase 1 (infrastructure setup)

---

### Pitfall 15: Flask/FastAPI Development Server Used in Production

**What goes wrong:**
The Python chat app is often prototyped using Flask's or FastAPI's built-in development server. This server is single-threaded or has very limited concurrency. Under the 2-4 second PSSession latency, a single blocked request causes all other requests to queue. The development server also has no process management, logging, or crash recovery.

**Prevention:**
- Use `gunicorn` (with `uvicorn` workers for async) or similar from the start, even in development
- Configure multiple workers: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app`
- This is not a post-MVP optimization — it affects basic usability given PSSession latency

**Phase:** Phase 3 (chat app foundation)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| MCP server scaffold | stdout pollution (Pitfall 1) | Configure logging to stderr immediately; add test that verifies no stdout output except valid JSON |
| PSSession lifecycle | Orphaned sessions (Pitfall 2) | Always use try/finally for session cleanup; test exception paths |
| Kerberos setup | Negative cache (Pitfall 3) | Wait 15 min or purge cache after every configuration change; document SPNs |
| First tool implementation | .NET object serialization (Pitfall 5) | Define explicit Select-Object fields; test with mailboxes that have complex proxy addresses |
| Tool descriptions | LLM tool selection (Pitfall 6) | Write all 15 tool descriptions before implementing any; test selection accuracy |
| Authentication integration | Token validation (Pitfall 4) | Implement token validation before any protected endpoint is reachable |
| MSAL setup | Cache persistence (Pitfall 7), Conditional Access (Pitfall 13) | Implement SerializableTokenCache and interaction_required handler in same phase |
| LLM integration | Messages array management (Pitfall 9), Context growth (Pitfall 11) | Implement tool call helper function and token counting before first end-to-end test |
| Error handling | isError flag (Pitfall 10) | Template first tool with error handling pattern; code review to enforce across all tools |
| Infrastructure | CredSSP prohibition (Pitfall 8), WinRM port (Pitfall 14) | Infrastructure checklist before any application code |
| Chat app server | Dev server in production (Pitfall 15) | Use production WSGI server from day one |

---

## Sources

| Source | Confidence | Used For |
|--------|------------|----------|
| MCP Specification: Tools (modelcontextprotocol.io/docs/concepts/tools) | HIGH | Pitfalls 1, 6, 10 |
| MCP Specification: Transports (modelcontextprotocol.io/docs/concepts/transports) | HIGH | Pitfall 1 |
| Microsoft Docs: Making the second hop in PowerShell Remoting | HIGH | Pitfalls 3, 8 |
| Microsoft Docs: Kerberos Constrained Delegation Overview | HIGH | Pitfall 3 |
| Microsoft Docs: MSAL Python error handling | HIGH | Pitfalls 4, 7, 13 |
| Microsoft Docs: Azure OpenAI Function Calling | HIGH | Pitfalls 6, 9, 11 |
| Microsoft Docs: Azure OpenAI Quotas and Limits | HIGH | Pitfall 11 (128 tool limit, 1024 char description limit) |
| Microsoft Docs: Connect to Exchange Online PowerShell | HIGH | Pitfall 2 (session management patterns) |
| Microsoft Docs: Exchange Management Shell | HIGH | Pitfalls 2, 5, 12 |
| Microsoft Docs: MSAL Python overview | HIGH | Pitfalls 7, 13 |
