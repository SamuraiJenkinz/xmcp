---
phase: 07-chat-app-core
verified: 2026-03-21T19:28:11Z
status: gaps_found
score: 4/5 must-haves verified
re_verification: false
gaps:
  - truth: "The AI response streams to the browser in real-time"
    status: failed
    reason: "Server emits SSE text events with field name delta (chat.py:171) but JavaScript reads event.content (app.js:133) — every chunk arrives as undefined and the fallback empty string silently drops it"
    artifacts:
      - path: "chat_app/chat.py"
        issue: "Line 171 yields _sse({type: text, delta: delta_text}) — field name is delta"
      - path: "chat_app/static/app.js"
        issue: "Line 133 reads event.content not event.delta — event.content is always undefined for text events"
    missing:
      - "Change app.js line 133: event.content to event.delta"
---

# Phase 7: Chat App Core Verification Report

**Phase Goal:** A colleague can log in with their MMC identity, ask an Exchange question in natural language, watch the tool call resolve, and read an AI-composed answer end-to-end
**Verified:** 2026-03-21T19:28:11Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Colleague navigates to app, is redirected to Azure AD login, arrives at chat interface authenticated as themselves | VERIFIED | splash.html has Sign in with Microsoft button linking to /login; auth.py initiates MSAL auth code flow and stores id_token_claims in session; /chat has @login_required; chat.html greets user by display_name |
| 2 | Natural language query triggers correct MCP tool, receives result, produces coherent answer in single round-trip | VERIFIED | run_tool_loop in openai_client.py lines 157-312 iterates completions.create up to 5 times, dispatches tool_calls to call_mcp_tool, appends role=tool results; chat.py /chat/stream calls run_tool_loop then streams final answer |
| 3 | AI response streams to browser in real-time - partial text appears before full response is ready | FAILED | Server sends type:text with field delta at chat.py:171 but JavaScript reads event.content at app.js:133 - event.content is always undefined for text events; the fallback empty string discards every chunk; user sees blank response until stream ends |
| 4 | Conversation exceeding 128K context window is pruned automatically without crashing | VERIFIED | context_mgr.py prune_conversation uses tiktoken o200k_base at _EFFECTIVE_LIMIT=123904 tokens; called in chat.py:124 before every run_tool_loop; preserves system messages and latest user message; returns new list |
| 5 | Azure AD token is validated server-side before any protected endpoint is accessible | VERIFIED | MSAL acquire_token_by_auth_code_flow validates auth code and id_token signature server-side; session[user] set only on success without error key at auth.py:149-172; /chat/stream and /chat/clear both have @login_required |

**Score:** 4/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| chat_app/auth.py | MSAL auth code flow, login_required decorator | VERIFIED | 179 lines, ConfidentialClientApplication, auth_code_flow, id_token_claims, login_required |
| chat_app/app.py | Flask app factory wiring all blueprints | VERIFIED | 104 lines, registers auth_bp and chat_bp, calls init_openai() and init_mcp(app), all 8 routes present |
| chat_app/openai_client.py | run_tool_loop with MCP dispatch | VERIFIED | 332 lines, run_tool_loop up to _MAX_TOOL_ITERATIONS=5, handles tools and legacy functions format |
| chat_app/mcp_client.py | Async MCP bridge with sync wrappers | VERIFIED | 259 lines, background asyncio daemon thread, threading.Lock serializes MCP calls |
| chat_app/context_mgr.py | tiktoken pruning at 128K limit | VERIFIED | 199 lines, _EFFECTIVE_LIMIT=123904, prune_conversation preserves system messages |
| chat_app/chat.py | SSE streaming blueprint | PARTIAL - server correct, wiring gap | 221 lines, /chat/stream emits correct SSE events with field name delta on server side |
| chat_app/static/app.js | SSE consumer and UI | BROKEN - field mismatch | 256 lines, reads event.content instead of event.delta at line 133 - text events silently dropped |
| chat_app/templates/chat.html | Chat interface | VERIFIED | Welcome message with display_name, example queries, form wired to /chat/stream |
| chat_app/templates/splash.html | Branded sign-in page | VERIFIED | Microsoft logo SVG, Sign in with Microsoft button, links to /login |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| splash.html | /login | url_for auth.login | WIRED | Line 13 of splash.html |
| /login | Azure AD | MSAL initiate_auth_code_flow | WIRED | auth.py:117-122 |
| /auth/callback | session[user] | acquire_token_by_auth_code_flow + id_token_claims | WIRED | auth.py:143 and 166 |
| /chat route | @login_required | decorator on app.py:66 | WIRED | Redirects to index if no session[user] |
| /chat/stream | @login_required | decorator on chat.py:79 | WIRED | Both chat endpoints protected |
| chat.py | run_tool_loop | openai_client import | WIRED | chat.py:44, called at line 131 |
| run_tool_loop | call_mcp_tool | mcp_client import | WIRED | openai_client.py:18, called at line 260 |
| chat.py | prune_conversation | context_mgr import | WIRED | chat.py:39, called at line 124 |
| Server SSE text event | Browser appendText | event.delta server vs event.content client | NOT WIRED | chat.py:171 sends delta; app.js:133 reads content - field name mismatch |
| chat.html | app.js | script tag | WIRED | chat.html:34, url_for static app.js |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| Azure AD SSO login flow | SATISFIED | none |
| MCP tool-calling loop end-to-end | SATISFIED | none |
| SSE real-time streaming | BLOCKED | event.delta vs event.content mismatch at app.js:133 |
| 128K context window pruning | SATISFIED | none |
| Server-side token validation | SATISFIED | none |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| chat_app/static/app.js | 133 | event.content reads wrong SSE field name | Blocker | Every streamed text chunk renders as empty string; user never sees streaming text |

### Human Verification Required

#### 1. Confirm authentication redirects correctly on session expiry

**Test:** With an active chat session, delete the server-side session file, then submit a new chat message.
**Expected:** Browser redirects to splash/login page without crashing or showing a raw error.
**Why human:** Session expiry under SSE mid-stream cannot be verified statically.

#### 2. Verify example query buttons trigger a full chat round-trip

**Test:** Click one of the four example query buttons in the welcome message.
**Expected:** The query auto-submits, tool chips appear, a streaming response arrives.
**Why human:** The interaction requires a live browser with a running server.

### Gaps Summary

One gap blocks goal achievement.

Truth 3 (real-time streaming) fails due to a single-word field name mismatch between server and client. The server (chat.py line 171) emits SSE events as type:text with a field named delta. The JavaScript client (app.js line 133) reads event.content, which is always undefined for text events. The fallback empty string silently discards every chunk, producing a blank assistant message for the entire stream duration.

The fix is a one-word change at app.js line 133: event.content to event.delta.

All other four must-haves are fully implemented and correctly wired. Authentication uses MSAL ConfidentialClientApplication with server-side id_token validation and @login_required on all protected routes. The MCP tool loop runs up to 5 iterations, dispatches tool_calls to the Exchange MCP server via a background asyncio thread with a threading.Lock, and returns tool_events for UI rendering. Context pruning uses tiktoken o200k_base at a 123904-token effective limit, called before every AI request, preserving system messages while dropping oldest turns.

---

_Verified: 2026-03-21T19:28:11Z_
_Verifier: Claude (gsd-verifier)_
