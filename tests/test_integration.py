"""Integration test suite for the full Phase 1 Exchange MCP client layer.

Tests are divided into two categories:

1. DNS live tests (no credentials required, always runnable with network):
   - test_dns_dmarc_live: DMARC lookup for google.com
   - test_dns_spf_live: SPF lookup for google.com

2. Exchange live tests (require Azure AD / Exchange Online credentials):
   - test_exchange_verify_connection: health-check via ExchangeClient
   - test_exchange_cmdlet_returns_json: run_cmdlet returns parsed dict
   - test_exchange_json_depth: no @{} truncation in deep nested objects

Exchange tests are marked with @pytest.mark.exchange so they can be skipped
in environments without credentials:

    uv run pytest tests/test_integration.py -v -m "not exchange"   # DNS only
    uv run pytest tests/test_integration.py -v                     # all tests

Required environment variables for Exchange tests:
    AZURE_CERT_THUMBPRINT  - Certificate thumbprint for CBA
    AZURE_CLIENT_ID        - Azure AD application (client) ID
    AZURE_TENANT_DOMAIN    - Tenant domain (e.g. contoso.onmicrosoft.com)
"""

from __future__ import annotations

import pytest

from exchange_mcp.dns_utils import clear_cache, get_dmarc_record, get_spf_record


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def fresh_dns_cache():
    """Clear the DNS TTL cache before and after each test that uses it."""
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# DNS live tests — network required, no Exchange credentials needed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.network
async def test_dns_dmarc_live(fresh_dns_cache):
    """get_dmarc_record returns a valid DMARC record for google.com.

    Asserts:
        - found is True
        - policy is one of none/quarantine/reject
        - pct is an integer in 0-100
    """
    result = await get_dmarc_record("google.com")

    assert result["found"] is True, (
        f"Expected found=True for google.com DMARC record, got: {result!r}"
    )
    assert result["domain"] == "google.com"
    assert result.get("policy") in ("none", "quarantine", "reject"), (
        f"Unexpected DMARC policy: {result.get('policy')!r}"
    )
    assert isinstance(result.get("pct"), int), (
        f"Expected int pct, got: {type(result.get('pct')).__name__}"
    )
    assert 0 <= result["pct"] <= 100, f"pct out of range: {result['pct']}"


@pytest.mark.asyncio
@pytest.mark.network
async def test_dns_spf_live(fresh_dns_cache):
    """get_spf_record returns a valid SPF record for google.com.

    Asserts:
        - found is True
        - mechanisms list is non-empty
        - all qualifier is present
    """
    result = await get_spf_record("google.com")

    assert result["found"] is True, (
        f"Expected found=True for google.com SPF record, got: {result!r}"
    )
    assert result["domain"] == "google.com"
    mechanisms = result.get("mechanisms", [])
    assert len(mechanisms) > 0, (
        f"Expected at least one SPF mechanism for google.com, got: {mechanisms!r}"
    )
    assert result.get("all") is not None, (
        "Expected non-None all-qualifier for google.com SPF record"
    )


# ---------------------------------------------------------------------------
# Exchange live tests — require Azure AD / Exchange Online credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.exchange
async def test_exchange_verify_connection():
    """ExchangeClient.verify_connection() returns True against live Exchange Online.

    Requires:
        AZURE_CERT_THUMBPRINT, AZURE_CLIENT_ID, AZURE_TENANT_DOMAIN
    """
    from exchange_mcp.exchange_client import ExchangeClient

    client = ExchangeClient(timeout=90)
    result = await client.verify_connection()

    assert result is True, (
        "verify_connection() returned False — check credentials and Exchange Online permissions"
    )


@pytest.mark.asyncio
@pytest.mark.exchange
async def test_exchange_cmdlet_returns_json():
    """run_cmdlet returns a dict with Name field for Get-OrganizationConfig.

    Asserts:
        - Result is a non-empty dict
        - Name field is present and non-empty
    """
    from exchange_mcp.exchange_client import ExchangeClient

    client = ExchangeClient(timeout=90)
    result = await client.run_cmdlet(
        "Get-OrganizationConfig | Select-Object Name, DisplayName, Identity"
    )

    assert isinstance(result, dict), (
        f"Expected dict from Get-OrganizationConfig, got {type(result).__name__}: {result!r}"
    )
    assert result.get("Name"), (
        f"Expected non-empty Name in result, got: {result!r}"
    )


@pytest.mark.asyncio
@pytest.mark.exchange
async def test_exchange_json_depth():
    """ConvertTo-Json -Depth 10 produces real JSON objects, not truncated @{{}} strings.

    Runs a cmdlet that may return nested objects and verifies none of the
    returned data contains the @{{...}} truncation pattern that PowerShell
    emits when ConvertTo-Json depth is insufficient.
    """
    import json as _json

    from exchange_mcp.exchange_client import ExchangeClient

    client = ExchangeClient(timeout=90)
    result = await client.run_cmdlet(
        "Get-OrganizationConfig | Select-Object Name, DisplayName, WhenCreated"
    )

    # Serialise the result back to a string to check for truncation
    serialised = _json.dumps(result, default=str)

    assert "@{" not in serialised, (
        f"Detected @{{}} truncation in cmdlet output — ConvertTo-Json depth may be "
        f"insufficient. Truncated output: {serialised[:500]}"
    )
    # Also verify we got a real result, not an empty response
    assert result, f"Expected non-empty result from Get-OrganizationConfig, got: {result!r}"
