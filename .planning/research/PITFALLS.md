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
- LLM hallucinates parameters not in the schema because the description implies capabilities that doesn't implement
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

---

---

# v1.1 Milestone Pitfalls — Microsoft Graph Colleague Lookup

**Milestone:** v1.1 — Colleague Lookup (Graph API user search, profile retrieval, photo proxy)
**Researched:** 2026-03-24
**Confidence:** HIGH (verified against Microsoft Graph official docs, MSAL Python docs, Graph throttling limits)

These pitfalls are specific to adding Microsoft Graph API colleague lookup to the existing Flask app that already has MSAL SSO working. The v1.0 pitfalls above still apply; these extend them for the Graph integration layer.

---

## Critical Pitfalls (v1.1)

---

### Pitfall 16: Client Credentials Scope Must Be `https://graph.microsoft.com/.default` — Not User Scopes

**What goes wrong:**
The existing app uses delegated auth code flow with scopes like `["User.Read"]`. When adding the client credentials flow for Graph API app-only access, developers copy the same scope format. Client credentials flow does not accept individual scopes — only the `.default` suffix on the resource URI. Passing `["User.Read.All"]` to `acquire_token_for_client` returns a token that either fails immediately or returns an empty `scp` claim that Graph rejects with 401.

**Why it happens:**
The two token flows look identical in code — both call MSAL with a list of strings. The distinction that `.default` is mandatory for client credentials is buried in the docs and easy to miss when adapting working auth code.

**Consequences:**
- All Graph API calls return 401 Unauthorized with `InvalidAuthenticationToken`
- The token is issued successfully by Azure AD but is not valid for Graph
- The error message does not tell you the scope is wrong

**Prevention:**
- For client credentials flow, always use `scope=["https://graph.microsoft.com/.default"]` — exactly this string, no others
- The permissions actually granted are determined by the Application permissions configured in the app registration with admin consent, not by what you put in the scope list
- Create a distinct module (e.g., `graph_client.py`) that owns the client credentials token acquisition — do not reuse or mix with the user auth code flow module

**Warning signs:**
- `acquire_token_for_client` succeeds but Graph calls return 401
- Token has `scp` claim (delegated) instead of `roles` claim (application) when decoded
- Changing the scope list doesn't change the error

**Phase:** Graph client module implementation — verify token claim structure before any Graph call

**Source:** [Microsoft Docs: Get access without a user](https://learn.microsoft.com/en-us/graph/auth-v2-service) — HIGH confidence

---

### Pitfall 17: Admin Consent Must Be Re-Granted After Adding New Application Permissions

**What goes wrong:**
The existing app registration has `User.Read` delegated permission for SSO. Adding `User.Read.All` and `ProfilePhoto.Read.All` as Application permissions requires a Global Administrator or Privileged Role Administrator to grant tenant-wide admin consent. Until that consent is granted, `acquire_token_for_client` returns a token that Graph accepts but returns 403 Forbidden on any call that requires those permissions. The error message says "Insufficient privileges" but does not tell you consent is missing.

**Why it happens:**
The developer adds permissions in the Azure portal, sees a green checkmark, and assumes the app has the permissions. But the checkmark means the permission is configured — not that it has been consented to. Application permissions always require explicit admin consent before they take effect.

**Consequences:**
- Graph calls return 403 with `Authorization_RequestDenied`
- The app appears correctly configured but cannot make any Graph calls
- If the developer and the admin are different people, this becomes a blocking dependency

**Prevention:**
- After adding any Application permission in the portal, the admin must click "Grant admin consent for [tenant]" on the API Permissions page — this is a separate step from adding the permission
- Verify consent status by decoding the token from `acquire_token_for_client`: the `roles` claim must contain the permission names (e.g., `"User.Read.All"`, `"ProfilePhoto.Read.All"`)
- Block the photo proxy and search features behind a startup check that verifies Graph access before the app starts serving requests
- Note: when permissions change, the admin must consent again — changing the portal configuration does not automatically re-consent

**Warning signs:**
- Graph returns 403 with `Authorization_RequestDenied` despite correct scope
- Token `roles` claim is empty or missing `User.Read.All`
- Admin says "I granted consent" but the portal timestamp is older than the last permission change

**Phase:** App registration configuration — must be completed with admin before any Graph code is written

**Source:** [Microsoft Docs: Grant tenant-wide admin consent](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent) — HIGH confidence

---

### Pitfall 18: Two MSAL Token Flows on One App Instance Corrupt Each Other's Cache

**What goes wrong:**
The existing app uses `ConfidentialClientApplication` with a per-user `SerializableTokenCache` stored in the Flask session for the auth code flow. If the Graph client credentials flow reuses the same `ConfidentialClientApplication` instance or the same cache, the application token cache (used by `acquire_token_for_client`) and the user token cache (used by `acquire_token_silent`) interfere. The symptom is subtle: silent user token acquisition starts returning the application token (or vice versa), causing 401 errors on user-scoped calls.

**Why it happens:**
MSAL Python uses a single `SerializableTokenCache` object, but client credentials flow uses an application-level token cache that is separate from the user token cache conceptually. However, if the same cache object is shared — or if the same `ConfidentialClientApplication` instance is used for both flows — MSAL may write application tokens into a cache that is later deserialized as a user cache, or fail to find cached tokens where expected.

**Consequences:**
- User SSO stops working silently after Graph calls start
- Graph calls return tokens that appear valid but fail on user-scoped resources
- The bug only appears after both flows have been used at least once, making it hard to reproduce in testing

**Prevention:**
- Use a separate, singleton `ConfidentialClientApplication` instance exclusively for Graph client credentials — do not share it with the user auth flow
- The Graph client CCA should use a separate in-memory application token cache (no `SerializableTokenCache` needed — MSAL caches client credentials tokens in-memory automatically and `acquire_token_for_client` checks the cache by default since MSAL Python 1.23)
- The user auth CCA (in `auth.py`) continues to use the per-user `SerializableTokenCache` from the Flask session as-is
- Keep the Graph client module completely independent: separate file, separate CCA instance, no shared state with `auth.py`

**Warning signs:**
- User auth starts failing after Graph module is added
- `acquire_token_silent` returns None for logged-in users when it previously worked
- Graph call token has a `preferred_username` claim (user token leaked into client creds flow)

**Phase:** Graph client module — isolate from auth.py before writing any Graph calls

**Source:** [MSAL Python docs: Acquiring tokens](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens) — HIGH confidence

---

### Pitfall 19: `$search` on Users Requires `ConsistencyLevel: eventual` Header — Missing Header Returns 400, Not a Useful Error

**What goes wrong:**
The Microsoft Graph `$search` query parameter on directory objects (users, groups) requires the `ConsistencyLevel: eventual` request header. This is because user search is served from a separate eventually-consistent index store, not the primary directory. If this header is omitted, Graph returns `400 Bad Request` with the message "Request header ConsistencyLevel is required" — but the error code is generic and the header name is easy to miss.

**Why it happens:**
`$search` looks identical to standard OData `$filter` in usage. The requirement for a special header is unique to Graph's AAD advanced queries and not present in most other REST APIs. Teams copy examples from Stack Overflow that predate this requirement or that show `$filter` (which does not need the header for basic operations).

**Consequences:**
- `search_colleagues` MCP tool always returns 400 with no results
- The error message does not suggest what is missing
- The tool appears broken when the underlying code is otherwise correct

**Prevention:**
- Always include `ConsistencyLevel: eventual` in the headers of any request using `$search` or advanced `$filter` operators on user objects
- Also include `$count=true` in the query parameters when using `$filter` with advanced operators (not required for `$search` alone, but required for `$filter` with `ne`, `not`, `endsWith`, etc.)
- The `ConsistencyLevel` header must be explicitly re-sent on every paginated follow-up request (`@odata.nextLink`) — it is not preserved automatically
- Test with a simple `$search="displayName:test"` query and verify the response before building the full search logic

**Warning signs:**
- Graph returns 400 with message about `ConsistencyLevel` header
- Search returns 0 results for names that exist in the tenant
- Pagination requests return different errors than the initial request

**Phase:** Graph client module — add header to the module's default request headers before writing any search call

**Source:** [Microsoft Docs: Advanced query capabilities on Microsoft Entra ID objects](https://learn.microsoft.com/en-us/graph/aad-advanced-queries) — HIGH confidence

---

### Pitfall 20: Photo Endpoint Returns 404 for Users Without a Photo — Proxy Must Handle This Gracefully

**What goes wrong:**
`GET /users/{id}/photo/$value` returns `404 Not Found` when the user has no profile photo set. This is correct behavior. If the Flask photo proxy route propagates the 404 to the browser, the chat UI shows a broken image tag. Worse, if the MCP tool calls the proxy and gets a 404, it may set `isError: true` and return an error to the LLM, which then tells the user "I couldn't retrieve the profile" instead of silently showing an avatar fallback.

**Why it happens:**
404 on a binary endpoint feels like a real error. The distinction between "this resource exists but has no photo" and "this user ID is wrong" is semantically important but both return 404. Teams don't test the no-photo case because test users in dev tenants always have photos.

**Consequences:**
- Broken image icons in profile cards for most users in a large enterprise (many users do not upload photos)
- If 404 is treated as an error by the photo proxy, every profile card without a photo shows an error state
- In a tenant with 80,000 users, a significant fraction will have no photo — this is not an edge case

**Prevention:**
- The Flask photo proxy route (`/api/photo/<user_id>`) must catch 404 from Graph and return a consistent SVG or PNG avatar placeholder with a 200 response — never forward the 404
- Do not expose the Graph 404 to the UI or the LLM; the proxy absorbs it
- The placeholder avatar should be a deterministic fallback (e.g., user initials from the display name, or a generic person icon) rather than a broken image
- Separately, `GET /users/{id}/photo` (metadata endpoint, without `$value`) returns a response even when there is no photo: it returns a 1x1 pixel placeholder metadata object. Use the metadata endpoint to check if a photo exists before fetching binary data if you want to avoid the 404 entirely

**Warning signs:**
- Profile cards in the UI show broken image icons
- Browser network tab shows 404 responses from `/api/photo/...`
- LLM reports "failed to get profile" when the user data was retrieved successfully

**Phase:** Photo proxy route implementation — test with a user who has no photo before considering the proxy complete

**Source:** [Microsoft Docs: Get profilePhoto](https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0) — HIGH confidence

---

## Moderate Pitfalls (v1.1)

---

### Pitfall 21: Graph API Throttling at Large Tenant Scale — 429 Without Retry-After Handling Causes Cascading Failures

**What goes wrong:**
At 80,000+ users, MMC is an "L" (large) tenant in Graph's throttling model. The per-app/per-tenant limit is 8,000 resource units per 10 seconds. A `GET /users` call costs 2 RU; a `GET /users/{id}/photo/$value` costs 1 RU. A burst of profile card requests (e.g., a search returning 10 results, each triggering a photo fetch) can consume 20+ RU in under a second. When throttled, Graph returns `429 Too Many Requests` with a `Retry-After` header specifying seconds to wait. If the Flask app does not honor this header and retries immediately, it continues to be throttled and the wait time compounds.

**Why it happens:**
Developers test with a handful of users and never see throttling. The throttling threshold only appears under realistic load with multiple users using the app simultaneously, or when the LLM calls search and profile tools in a single turn.

**Consequences:**
- Graph calls return 429 and all colleague lookups fail
- Retrying immediately without honoring `Retry-After` keeps the app in a throttled state longer
- If `search_colleagues` and `get_colleague_profile` are called together in one LLM turn, the photo fetches for all search results compound the RU cost

**Prevention:**
- Implement a retry wrapper in the Graph client that reads the `Retry-After` response header and sleeps exactly that many seconds before retrying — do not use exponential backoff as a substitute when `Retry-After` is present
- Set `x-ms-throttle-priority: high` on user-initiated search requests; this header causes Graph to throttle background/low-priority requests first
- Use `$select` on user queries to reduce RU cost by 1 per request: `$select=id,displayName,jobTitle,department,mail,officeLocation` brings the cost of a user GET from 1 RU to 0 RU (but the base cost floor means the minimum is still 1 RU)
- Cap search results at 10-15 per query to limit downstream photo fetch volume
- Cache photo binary data in the Flask process (in-memory dict with TTL) to avoid re-fetching photos for users already displayed in the current session

**Warning signs:**
- Graph returns 429 in testing under any load
- `Retry-After` header is present but code retries immediately
- Multiple profile photo requests in quick succession all fail

**Phase:** Graph client module — implement retry handler before any load testing

**Source:** [Microsoft Docs: Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) and [Microsoft Graph service-specific throttling limits](https://learn.microsoft.com/en-us/graph/throttling-limits) — HIGH confidence

---

### Pitfall 22: Large Tenant Pagination — `@odata.nextLink` Must Be Followed, But Token in URL Expires

**What goes wrong:**
Graph user search results are paginated. For a large tenant, even a narrow `$search` query may return results across multiple pages via `@odata.nextLink`. The nextLink URL contains an opaque continuation token. This token has a short expiry (typically 30-60 minutes). If the client stores the nextLink URL and uses it later — or if the pagination loop is interrupted and resumed — the token may have expired and Graph returns 410 Gone or 400 Bad Request.

**Why it happens:**
Teams implement the first page of results, see it working, and either don't implement pagination at all (accepting truncated results) or implement it in a way that stores nextLink across requests. For an 80K-user tenant, "John Smith" might return 40+ results and only the first 10 are shown without pagination.

**Consequences:**
- Search returns only the first page of results (default page size is 10 for `$search` on users)
- Users searching for a common name get incomplete results with no indication that more exist
- If pagination tokens are cached and expire, subsequent page requests fail with cryptic errors

**Prevention:**
- For the `search_colleagues` tool, consume up to 2-3 pages of results in a single tool call (following `@odata.nextLink` immediately) and return a combined result set — do not return the nextLink to the LLM for it to use in a subsequent call
- Cap total results at a sensible limit (e.g., 25 records) across all pages — fetching all pages of a common-name search is unnecessary and expensive
- Never store nextLink URLs in the database or session for later use — consume them immediately or discard them
- Include a `$top=10` parameter to control page size explicitly rather than relying on the default

**Warning signs:**
- Search for a common first name returns exactly 10 results, always
- No `@odata.nextLink` handling in the search implementation
- Stored nextLink URLs return 410 errors after a short delay

**Phase:** `search_colleagues` tool implementation

**Source:** [Microsoft Docs: List users](https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0) — HIGH confidence

---

### Pitfall 23: Photo Binary Data Sent Directly in MCP Tool Response Inflates Context Window

**What goes wrong:**
The `get_colleague_profile` MCP tool retrieves profile data including the photo. If the tool embeds the photo as a base64-encoded string in the tool result, the context window impact is severe: a 96x96 JPEG is approximately 5-15 KB of binary data, which is 6,700-20,000 base64 characters, which is roughly 2,000-5,000 tokens. Returning photos for 10 search results in one tool call would add 20,000-50,000 tokens to the conversation — consuming 15-40% of the context window before the user's next message.

**Why it happens:**
The photo is available from Graph as binary data. The path of least resistance is to fetch it, base64-encode it, and include it in the structured tool result. This appears to work correctly in testing with one or two results but degrades severely under realistic use.

**Consequences:**
- Context window fills rapidly when multiple colleague lookups are performed
- Conversation history becomes unusable after 3-4 profile lookup interactions
- LLM response quality degrades as older context is pruned to make room

**Prevention:**
- Never include photo binary data in the MCP tool result. The tool result must contain only a photo URL that the UI can resolve: `"photo_url": "/api/photo/<user_id>"`
- The Flask app serves the `/api/photo/<user_id>` proxy route that fetches the binary from Graph and returns it to the browser — this keeps binary data entirely out of the LLM context
- The profile card UI renders `<img src="/api/photo/<user_id>">` — the browser fetches the photo separately from the conversation
- The MCP tool result for a colleague profile should be compact structured text: name, title, department, email, office, and the photo_url string — nothing else

**Warning signs:**
- MCP tool result JSON contains a `photo` key with a long base64 string
- Context window usage spikes after a single profile lookup
- Slow response times after 2-3 colleague searches in one conversation

**Phase:** `get_colleague_profile` tool design — define the output schema before implementing the tool

---

### Pitfall 24: Flask Photo Proxy Exposes Unauthenticated Access to All User Photos

**What goes wrong:**
The `/api/photo/<user_id>` proxy route fetches photos from Graph using the app's client credentials token. If this route does not enforce user authentication (via the existing `@login_required` decorator), any unauthenticated request to the URL can retrieve photos for any user ID in the tenant. This is a data exposure risk since profile photos are personal data.

**Why it happens:**
Photo proxy routes are often treated as "just serving images" — static-feeling assets. The `@login_required` decorator is applied to interactive routes but missed on API routes. Additionally, the photo URL is embedded in profile cards rendered for authenticated users, and it "works" without the decorator because the browser cookie for the authenticated session is sent automatically — so the developer never sees the unauthenticated case during testing.

**Consequences:**
- Any person who obtains a user ID (UPN, GUID) — trivially guessable or extracted from API responses — can retrieve their photo without logging in
- Violates MMC's data handling obligations for personal data
- Profile photos may be considered sensitive in some organizational contexts (executive photos, etc.)

**Prevention:**
- Apply `@login_required` (or equivalent auth check) to the `/api/photo/<user_id>` route, just like all other protected routes
- Validate that the `user_id` parameter is a valid UUID or UPN format before making the Graph call — reject arbitrary strings
- Consider restricting photo lookups to user IDs that were returned by a prior search in the current session — but this adds complexity; applying `@login_required` is the minimum required control

**Warning signs:**
- `/api/photo/<user_id>` route does not have `@login_required`
- Photo URLs in the rendered HTML are accessible in an incognito window without cookie

**Phase:** Photo proxy route implementation — apply auth decorator at the same time as the route is created

---

### Pitfall 25: ConfidentialClientApplication for Graph Must Be a Singleton — Recreating It Per-Request Causes Unnecessary Token Fetches

**What goes wrong:**
`acquire_token_for_client` in MSAL Python automatically caches the client credentials token in the `ConfidentialClientApplication` instance's in-memory cache since MSAL Python 1.23. The token lifetime is typically 3600 seconds (1 hour). If a new `ConfidentialClientApplication` instance is created for each Graph request (e.g., inside the Flask route handler or MCP tool handler), the token cache is discarded with each instance, and every Graph call makes a fresh token request to `login.microsoftonline.com`. At scale, this adds 200-500ms of latency per call and risks rate-limiting the token endpoint.

**Why it happens:**
The user auth code in `auth.py` creates a `ConfidentialClientApplication` per request by design (because it loads the per-user cache from the Flask session). This pattern is correct for the user auth flow. If the developer applies the same pattern to the Graph client credentials module, they inadvertently disable token caching.

**Prevention:**
- Create the Graph `ConfidentialClientApplication` instance once at module level (or in a Flask app factory) and reuse it for the lifetime of the process — do not create it inside request handlers
- The in-memory token cache built into the instance will serve cached tokens automatically; `acquire_token_for_client` will only hit the network when the cached token expires
- This is explicitly different from `auth.py` which must create a new CCA per request (to load the per-user session cache)

**Warning signs:**
- `ConfidentialClientApplication(...)` instantiation appears inside a Flask route handler or MCP tool handler function
- Token endpoint (`login.microsoftonline.com`) is called on every Graph API request
- Latency of Graph calls is consistently 400-600ms higher than expected

**Phase:** Graph client module — structure as a module-level singleton before any route integration

**Source:** [MSAL Python docs: Acquiring tokens for your app](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens) — HIGH confidence

---

## Minor Pitfalls (v1.1)

---

### Pitfall 26: Graph Returns `null` for Unlicensed or Partially-Provisioned User Fields

**What goes wrong:**
In a large enterprise with 80,000+ users, many users are service accounts, shared mailboxes, or partially-provisioned users that have no `jobTitle`, `department`, `officeLocation`, or `mobilePhone` set. Graph returns these fields as `null` in the JSON response. If the profile card template or the MCP tool output assumes these fields are present strings, it will render `"None"` or `"null"` in the UI, or crash with a `NoneType has no attribute ...` error when trying to call `.title()` or similar string methods.

**Prevention:**
- Treat all optional Graph user fields as nullable; use `field or ""` or `field if field else "Not provided"` when formatting for display
- Define a `_format_user` helper function that normalizes the Graph user object into a flat dict with empty strings for missing fields — apply this before any field is used
- Do not return `null` values to the LLM in tool results; replace them with empty strings or omit the field entirely

**Phase:** `search_colleagues` and `get_colleague_profile` tool implementation

---

### Pitfall 27: User Search by Department Name Requires Exact Case-Insensitive Match — `$search` Does Not Support Partial Department Names

**What goes wrong:**
Graph's `$search` on users searches `displayName`, `givenName`, `surname`, `email`, and `userPrincipalName` by default. It does not search `department`, `jobTitle`, or `officeLocation` via `$search`. To filter by department, `$filter=department eq 'Human Resources'` is required — but this is a strict equality check, not a partial match. Users searching for "HR" or "human resources" (lowercase) will get zero results from a `$filter` approach if the department is stored as "Human Resources".

**Why it happens:**
The `$search` parameter feels like a full-text search across all fields. In practice, it only covers specific identity fields. The LLM may pass department names as search queries and get unexpected empty results without a useful error.

**Prevention:**
- Document in the tool description that `query` parameter searches by name only — not by department or title
- For department-based queries, use `$filter=startsWith(department, 'query')` with `ConsistencyLevel: eventual` and `$count=true` — this supports case-insensitive prefix matching
- The `search_colleagues` tool should accept both `name` and `department` as separate optional parameters and build the appropriate Graph query for each
- Test with both `$search` (name) and `$filter` (department) to verify both code paths work before shipping

**Phase:** `search_colleagues` tool implementation and description

---

### Pitfall 28: Profile Card in Chat Context Must Not Embed Sensitive Fields the LLM Repeats Back

**What goes wrong:**
The colleague profile retrieved from Graph may include fields that are sensitive in context: direct manager name, mobile phone number, personal email aliases. If these are included in the MCP tool result, the LLM may repeat them verbatim in its response (e.g., "John Smith's mobile number is 0412..."). This exposes PII that the user did not explicitly request and may violate internal data handling policies.

**Why it happens:**
The `User.Read.All` permission gives access to many fields. Developers return all available fields because "more data is better" and it avoids re-fetching. The LLM is not selective about what it surfaces unless the tool result constrains it.

**Prevention:**
- Define an explicit allowlist of fields returned by `get_colleague_profile`: display name, job title, department, office location, work email, and photo URL — nothing else
- Do not return `mobilePhone`, `personalEmail`, `manager`, or extended profile fields in the tool result unless there is a specific requirement for them
- The `$select` parameter in the Graph query should match the allowlist exactly, so Graph does not even return the fields you don't want
- Document the field allowlist in the tool description so the LLM knows what to expect

**Phase:** `get_colleague_profile` tool design — define output schema before implementation

---

## Phase-Specific Warnings (v1.1)

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| App registration | Admin consent not re-granted (Pitfall 17) | Verify `roles` claim in token before writing any Graph code; block on admin consent |
| Graph client module | Wrong scope for client credentials (Pitfall 16) | Use `https://graph.microsoft.com/.default`; decode token to verify `roles` claim present |
| Graph client module | Shared MSAL instance with user auth (Pitfall 18) | Create separate singleton CCA; never import from `auth.py` |
| Graph client module | CCA recreated per request (Pitfall 25) | Instantiate once at module level; verify token endpoint not called on every request |
| `search_colleagues` tool | Missing `ConsistencyLevel` header (Pitfall 19) | Add header to Graph client default headers; test with `$search` before any other query feature |
| `search_colleagues` tool | Pagination not followed (Pitfall 22) | Follow `@odata.nextLink` immediately in the tool handler; cap at 25 results |
| `search_colleagues` tool | Null fields in partial users (Pitfall 26) | Apply `_format_user` normalization; test with service accounts |
| `get_colleague_profile` tool | Photo binary in tool result (Pitfall 23) | Return photo_url string only; never base64-encode photo in tool result |
| `get_colleague_profile` tool | Sensitive PII in tool result (Pitfall 28) | Define and enforce field allowlist via `$select` |
| Photo proxy route | Unauthenticated access (Pitfall 24) | Apply `@login_required`; validate user_id format |
| Photo proxy route | 404 for users without photo (Pitfall 20) | Return placeholder avatar on 404; never forward 404 to browser |
| Graph API calls | Throttling without retry (Pitfall 21) | Implement Retry-After handler; set priority header |

---

## Sources (v1.1)

| Source | Confidence | Used For |
|--------|------------|----------|
| [Microsoft Docs: Get access without a user (client credentials)](https://learn.microsoft.com/en-us/graph/auth-v2-service) | HIGH | Pitfall 16 (scope requirement) |
| [Microsoft Docs: Grant tenant-wide admin consent](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent) | HIGH | Pitfall 17 (admin consent requirement) |
| [MSAL Python: Acquiring tokens](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens) | HIGH | Pitfalls 18, 25 (token cache isolation, singleton) |
| [Microsoft Docs: Advanced query capabilities on Microsoft Entra ID objects](https://learn.microsoft.com/en-us/graph/aad-advanced-queries) | HIGH | Pitfall 19 (ConsistencyLevel header requirement) |
| [Microsoft Docs: Get profilePhoto](https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0) | HIGH | Pitfall 20 (404 for users without photo, binary handling) |
| [Microsoft Docs: Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) | HIGH | Pitfall 21 (Retry-After, throttling recovery) |
| [Microsoft Docs: Microsoft Graph service-specific throttling limits](https://learn.microsoft.com/en-us/graph/throttling-limits) | HIGH | Pitfall 21 (L tenant = 8,000 RU/10s, cost per operation) |
| [Microsoft Docs: List users](https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0) | HIGH | Pitfall 22 (pagination, nextLink) |
| [Microsoft Docs: Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference) | HIGH | Pitfall 17 (application vs delegated permission distinction) |
| [Microsoft Docs: Use $search query parameter](https://learn.microsoft.com/en-us/graph/search-query-parameter) | HIGH | Pitfall 27 (search field scope limitation) |
