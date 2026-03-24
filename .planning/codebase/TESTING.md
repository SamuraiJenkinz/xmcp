# Testing

## Framework

- **pytest** (>=9.0.2) with **pytest-asyncio** (>=1.3.0)
- `asyncio_mode = "strict"` — explicit `@pytest.mark.asyncio` required
- Custom markers: `network` (live DNS), `exchange` (live Exchange credentials)
- No coverage tool configured

## Test Structure

```
tests/
├── test_ps_runner.py          (69 LOC)   # Real PowerShell subprocess
├── test_exchange_client.py   (366 LOC)   # Mocked ps_runner
├── test_server.py            (230 LOC)   # MCP server handlers
├── test_tool_descriptions.py (321 LOC)   # Tool schema validation
├── test_tools_mailbox.py     (609 LOC)   # Mailbox tool handlers
├── test_tools_dag.py        (1056 LOC)   # DAG tool handlers
├── test_tools_flow.py        (830 LOC)   # Mail flow tool handlers
├── test_tools_hybrid.py      (592 LOC)   # Hybrid tool handlers
├── test_tools_security.py    (587 LOC)   # Security/DNS tool handlers
├── test_dns_utils.py         (302 LOC)   # DNS utility functions
└── test_integration.py       (168 LOC)   # Cross-module integration
```

**Total test code: 5,130 LOC** (52% of total codebase)

## Mocking Patterns

### Primary Mock Target: `ps_runner.run_ps`
```python
from unittest.mock import AsyncMock, patch

@patch("exchange_mcp.exchange_client.ps_runner.run_ps", new_callable=AsyncMock)
async def test_something(mock_run_ps):
    mock_run_ps.return_value = '{"key": "value"}'
    result = await client.run_cmdlet("Get-Something")
```

Most tool tests mock at the `run_ps` level — they test the full chain from tool handler through ExchangeClient but stub out the actual PowerShell subprocess.

### DNS Mocking
```python
@patch("exchange_mcp.dns_utils.dns.asyncresolver.Resolver.resolve", new_callable=AsyncMock)
```

DNS tests mock the `dnspython` resolver to avoid live network calls.

## Test Categories

| Category | Files | What's Tested |
|----------|-------|---------------|
| Unit - PS Runner | `test_ps_runner.py` | Real PowerShell execution (Windows only) |
| Unit - Exchange Client | `test_exchange_client.py` | Auth detection, retry logic, error classification |
| Unit - DNS | `test_dns_utils.py` | DMARC/SPF parsing, cache behavior, error handling |
| Unit - Tools | `test_tools_*.py` (5 files) | Each tool handler with mocked Exchange client |
| Unit - Server | `test_server.py` | MCP protocol handlers, tool listing, error responses |
| Schema | `test_tool_descriptions.py` | All 15 tool schemas validate correctly |
| Integration | `test_integration.py` | Cross-module tool execution paths |

## Test Patterns

### Async Test Pattern
```python
pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_feature():
    result = await some_async_function()
    assert result == expected
```

### Error Path Testing
```python
@pytest.mark.asyncio
async def test_handles_exchange_error(mock_run_ps):
    mock_run_ps.side_effect = RuntimeError("access denied")
    result = await handler(args, client)
    assert "error" in result.lower()
```

### Tool Handler Testing Pattern
```python
# 1. Create ExchangeClient instance
client = ExchangeClient()
# 2. Mock ps_runner.run_ps to return known JSON
# 3. Call handler via TOOL_DISPATCH[name](args, client)
# 4. Assert result structure and content
```

## What's NOT Tested

- **Chat app** (`chat_app/`): No Flask route tests, no SSE tests, no auth flow tests
- **Frontend** (`static/app.js`): No JavaScript tests
- **MCP client bridge** (`mcp_client.py`): No tests for sync-async bridge
- **Context manager** (`context_mgr.py`): No token counting tests
- **Database layer** (`db.py`, `conversations.py`): No SQLite tests
- **End-to-end**: No full chat flow tests (user → Flask → OpenAI → MCP → Exchange)

## Running Tests

```bash
# All tests
uv run pytest

# Skip tests requiring live services
uv run pytest -m "not network and not exchange"

# Specific module
uv run pytest tests/test_tools_mailbox.py -v
```
