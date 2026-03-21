---
phase: 07-chat-app-core
plan: 01
subsystem: ui
tags: [flask, waitress, flask-session, msal, openai, tiktoken, boto3, python-dotenv, sse, jinja2]

# Dependency graph
requires:
  - phase: 06-hybrid-tools
    provides: Complete MCP server with 14 Exchange tools + ping; the chat app will connect to this as MCP client
provides:
  - Flask application factory (create_app) with Waitress entry point and filesystem sessions
  - Config class loading from env vars with update_from_secrets classmethod
  - Secrets loader with AWS Secrets Manager + .env fallback
  - Base/splash/chat Jinja2 templates (branded Atlas identity, sign-in page, chat interface)
  - style.css centered 768px column layout with ChatGPT-style message bubbles and tool chips
  - app.js SSE streaming skeleton via fetch ReadableStream, auto-expanding textarea, Ctrl+Enter
  - Updated pyproject.toml with all Phase 7 dependencies (msal, openai, tiktoken, flask-session, boto3, python-dotenv)
affects:
  - 07-02-auth (registers MSAL login/callback/logout on this app factory)
  - 07-03-openai-client (uses Config.CHATGPT_ENDPOINT, Config.AZURE_OPENAI_API_KEY)
  - 07-04-mcp-client (spawns exchange_mcp subprocess; bridges async calls into Flask)
  - 07-05-chat-routes (adds /chat/stream SSE endpoint; app.js already expects this)
  - 07-06-context-mgr (uses tiktoken; operates on Flask session conversation list)

# Tech tracking
tech-stack:
  added:
    - msal>=1.35.1 (Azure AD auth code flow — used in 07-02)
    - openai>=2.29.0 (Azure OpenAI chat completions — used in 07-03/07-05)
    - tiktoken>=0.12.0 (token counting for context pruning — used in 07-06)
    - flask-session>=0.8.0 (filesystem-backed sessions to bypass 4KB cookie limit)
    - boto3>=1.42.73 (AWS Secrets Manager for production secret loading)
    - python-dotenv>=1.2.2 (dev .env fallback in secrets loader)
  patterns:
    - Flask application factory pattern (create_app returns Flask instance)
    - Config class as static container loaded from environment — update_from_secrets overwrites at startup
    - Secrets loader try/except cascade: AWS Secrets Manager → dotenv .env → os.environ
    - Stub routes for login/logout in app.py to prevent url_for BuildError before 07-02 wires MSAL
    - fetch-based SSE reading (not native EventSource) — required for POST body in chat stream

key-files:
  created:
    - chat_app/__init__.py
    - chat_app/app.py
    - chat_app/config.py
    - chat_app/secrets.py
    - chat_app/templates/base.html
    - chat_app/templates/splash.html
    - chat_app/templates/chat.html
    - chat_app/static/style.css
    - chat_app/static/app.js
  modified:
    - pyproject.toml (added 6 new dependencies)
    - uv.lock (resolved 21 new packages)

key-decisions:
  - "Stub login/logout routes in app.py prevent url_for BuildError before MSAL auth is wired in 07-02"
  - "fetch-based SSE (not native EventSource) because /chat/stream requires POST body with message payload"
  - "SESSION_FILE_DIR defaults to /tmp/flask-sessions; config docs confirm Windows needs a real path"
  - "Static Config class with classmethod update_from_secrets — simpler than dataclass or pydantic for this pattern"

patterns-established:
  - "Config pattern: class with class-level defaults from os.environ; update_from_secrets classmethod overwrites at startup"
  - "Secrets cascade: try boto3 Secrets Manager → except all → try dotenv load_dotenv → return os.environ dict"
  - "App factory: create_app() loads secrets, updates config, creates session dir, initializes Session(app), registers routes"
  - "SSE parsing: fetch ReadableStream reader, buffer split on double-newline, parse data: JSON lines"
  - "Tool chip UX: spinning chip shown per tool call, marked done when text starts arriving"

# Metrics
duration: 4min
completed: 2026-03-21
---

# Phase 7 Plan 01: Chat App Foundation Summary

**Flask app factory with Waitress, filesystem sessions (flask-session), AWS Secrets Manager loader, and full Atlas chat UI (base/splash/chat templates + style.css + app.js SSE skeleton)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-21T18:55:19Z
- **Completed:** 2026-03-21T19:00:06Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- All 6 Phase 7 dependencies installed and verified importable (msal, openai, tiktoken, flask-session, boto3, python-dotenv)
- Flask app factory creates without errors; filesystem sessions prevent 4KB cookie overflow for MSAL token caches
- Three templates render correctly: splash.html (sign-in page with Microsoft SVG button), chat.html (welcome message + example chips), base.html (header with status indicator)
- app.js implements full SSE streaming logic skeleton via fetch ReadableStream (not native EventSource — POST needed), auto-expanding textarea, example query auto-submit, Ctrl+Enter shortcut, tool chip rendering with spinner
- 199 existing tests continue to pass (zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies and create chat_app package with config and secrets modules** - `269c81d` (feat)
2. **Task 2: Create Flask app factory with Waitress, session init, templates, and static files** - `c7b0d15` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `chat_app/__init__.py` - Package marker
- `chat_app/config.py` - Config class: env var defaults + update_from_secrets classmethod
- `chat_app/secrets.py` - load_secrets(): AWS Secrets Manager try/except → dotenv → os.environ
- `chat_app/app.py` - create_app() factory with Session(app), stub login/logout, splash/chat routes + main() Waitress entry point
- `chat_app/templates/base.html` - Shared layout with header (Atlas logo, status indicator, user name, sign out link)
- `chat_app/templates/splash.html` - Branded sign-in page with Microsoft logo SVG and "Sign in with Microsoft" button
- `chat_app/templates/chat.html` - Chat interface with welcome message, 4 example query chips, auto-expanding textarea input area
- `chat_app/static/style.css` - 768px centered column, ChatGPT-style user/assistant bubbles, tool chip with CSS spinner, fixed input bar
- `chat_app/static/app.js` - SSE via fetch ReadableStream, auto-expand textarea, example query auto-submit, Ctrl+Enter, tool chip lifecycle
- `pyproject.toml` - Added msal, openai, tiktoken, flask-session, boto3, python-dotenv
- `uv.lock` - 21 new packages resolved

## Decisions Made
- **Stub login/logout in app.py:** Prevents `BuildError: Could not build url for endpoint 'login'` in templates before MSAL auth routes are wired in 07-02. The stubs redirect harmlessly to index/session clear.
- **fetch-based SSE not EventSource:** Native `EventSource` only supports GET requests. `/chat/stream` requires POST body with the user's message. Implemented as fetch + ReadableStream reader with manual SSE line parsing.
- **SESSION_FILE_DIR defaults to /tmp/flask-sessions:** Works on both Linux (production) and Windows dev environments. The directory is created with `os.makedirs(exist_ok=True)` at app startup.
- **Static Config class:** Straightforward class-level defaults from os.environ. `update_from_secrets` is a classmethod that overwrites selected attributes in-place at startup. Simpler than dataclass/pydantic for this use case and matches the pattern the rest of Phase 7 expects.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `uv` not on PATH in bash shell — used full path `/c/Users/taylo/uv_install/uv.exe`. This is a shell environment issue; standard project operation is unaffected as the project's `.venv` is fully configured.

## User Setup Required
None — no external service configuration required for this scaffold. AWS Secrets Manager credentials and Azure AD env vars are loaded at runtime, not compile time.

## Next Phase Readiness
- Flask app factory is ready for auth blueprint registration (07-02)
- Config class has all required MSAL fields (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, AZURE_AUTHORITY)
- Config class has all required OpenAI fields (CHATGPT_ENDPOINT, AZURE_OPENAI_API_KEY, API_VERSION, OPENAI_MODEL)
- app.js `/chat/stream` POST endpoint contract is established — 07-05 must implement this route
- Stub login/logout routes must be replaced/overridden by MSAL blueprint in 07-02
- Blocker from research: API_VERSION=2023-05-15 may not support `tools` parameter — verify in 07-03

---
*Phase: 07-chat-app-core*
*Completed: 2026-03-21*
