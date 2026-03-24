# Conventions

## Code Style

- **Python 3.11+** with `from __future__ import annotations` in every module
- **Type hints** on function signatures — return types, parameter types
- **`TYPE_CHECKING` guard** for import-only type references (`exchange_mcp/tools.py`)
- **No formatter config** in pyproject.toml — no black/ruff formatting enforced
- **Line length**: Generally ~88-100 chars, no strict enforcement
- **Docstrings**: Module-level and function-level, Google/numpy hybrid style with `Args:`, `Returns:`, `Raises:` sections

## Import Organization

```python
# 1. Standard library
import asyncio
import json
import logging

# 2. Third-party
from flask import Flask, jsonify
from mcp.server import Server
import mcp.types as types

# 3. Local
from exchange_mcp.exchange_client import ExchangeClient
from chat_app.config import Config
```

- `from __future__ import annotations` always first
- No import sorting tool configured — manual ordering

## Logging

- Every module: `logger = logging.getLogger(__name__)`
- MCP server: `logging.basicConfig(stream=sys.stderr)` — MUST be before any imports to prevent stdout corruption
- Chat app: Standard Flask logging
- Log levels: `logger.info()` for operations, `logger.error()` for failures, `logger.warning()` for degraded states
- Structured context in messages: `"Tool %s completed in %.1fs", name, elapsed`

## Error Handling Patterns

### Pattern 1: String-Based Error Classification
```python
# Used in server.py and exchange_client.py
_TRANSIENT_PATTERNS = ("timeout", "connection", "network", ...)
_NON_TRANSIENT_PATTERNS = ("authentication", "access denied", ...)

error_lower = str(error).lower()
if any(p in error_lower for p in _NON_TRANSIENT_PATTERNS):
    raise immediately  # No retry
elif any(p in error_lower for p in _TRANSIENT_PATTERNS):
    retry with backoff
```

### Pattern 2: Graceful Degradation
```python
# Used in app.py for OpenAI and MCP initialization
try:
    init_openai()
except Exception as exc:
    logger.error("...failed (degraded mode): %s", exc)
```

### Pattern 3: Exception Hierarchy
- `RuntimeError` — PowerShell errors, Exchange errors
- `TimeoutError` — subprocess timeouts
- `json.JSONDecodeError` — malformed PS output
- No custom exception classes

## Function Design

- **Async**: All Exchange/MCP tools are `async def` — `await` through the stack
- **Sync wrappers**: `mcp_client.py` bridges async MCP to sync Flask via `run_coroutine_threadsafe`
- **Constants as module globals**: `_MAX_TOOL_ITERATIONS`, `DEFAULT_TIMEOUT`, `_EFFECTIVE_LIMIT`
- **Private helpers**: Prefixed with `_` — `_encode_command()`, `_auto_name()`, `_user_id()`

## Configuration Pattern

```python
class Config:
    ATTR: type = os.environ.get("ENV_VAR", "default")

    @classmethod
    def update_from_secrets(cls, secrets: dict) -> None:
        if secrets.get("KEY"):
            cls.ATTR = secrets["KEY"]
```

- Class attributes with env var defaults
- `update_from_secrets()` overlay from AWS Secrets Manager
- No pydantic, no dataclass — plain class with `from_object()` Flask integration

## Testing Conventions

- Async tests: `@pytest.mark.asyncio` decorator + `asyncio_mode = "strict"` in pyproject.toml
- Mocking: `unittest.mock.patch` / `AsyncMock` for `ps_runner.run_ps`
- Fixtures: Inline per-test, no shared conftest.py fixtures
- Test markers: `@pytest.mark.network` (DNS), `@pytest.mark.exchange` (live Exchange)
- No parametrize usage — separate test functions per scenario

## Blueprint Pattern

```python
bp = Blueprint("name_bp", __name__)

@bp.route("/path", methods=["GET"])
@login_required
def handler():
    ...
```

- All routes use `@login_required` except login/callback
- User ID from `session.get("user", {}).get("oid", "")`
- JSON responses via `flask.jsonify()`

## Database Access Pattern

```python
db = get_db()  # Per-request from Flask g object
db.execute("SQL", (params,))
db.commit()  # Explicit — close_db does NOT commit
```

- SQLite Row factory for dict-like access
- WAL mode enabled per connection
- Auto-bootstrap schema on first run
