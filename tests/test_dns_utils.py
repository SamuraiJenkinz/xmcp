"""Tests for exchange_mcp.dns_utils — DMARC/SPF parsing and DNS resolution.

Two test categories:

1. Pure-function tests (no network access, always run):
   - test_parse_dmarc_full
   - test_parse_dmarc_minimal
   - test_parse_spf_full
   - test_parse_spf_no_all
   - test_parse_spf_hard_fail

2. Async integration tests (require live DNS):
   - test_get_dmarc_record_real
   - test_get_spf_record_real
   - test_get_dmarc_not_found
   - test_cache_returns_same_result
   - test_clear_cache
"""

import pytest

from exchange_mcp.dns_utils import (
    clear_cache,
    get_dmarc_record,
    get_spf_record,
    get_txt_records,
    parse_dmarc,
    parse_spf,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def fresh_cache():
    """Clear the DNS TTL cache before (and after) each test that uses it."""
    clear_cache()
    yield
    clear_cache()


# ===========================================================================
# Pure-function tests — no network required
# ===========================================================================


def test_parse_dmarc_full():
    """parse_dmarc correctly extracts all tag-value pairs from a full record."""
    record = (
        "v=DMARC1; p=reject; sp=quarantine; pct=50; "
        "rua=mailto:dmarc@example.com; ruf=mailto:forensic@example.com; "
        "adkim=s; aspf=s"
    )
    result = parse_dmarc(record)

    assert result["version"] == "DMARC1"
    assert result["policy"] == "reject"
    assert result["subdomain_policy"] == "quarantine"
    assert result["pct"] == 50
    assert result["rua"] == "mailto:dmarc@example.com"
    assert result["ruf"] == "mailto:forensic@example.com"
    assert result["adkim"] == "s"
    assert result["aspf"] == "s"
    assert result["raw"] == record


def test_parse_dmarc_minimal():
    """parse_dmarc applies correct defaults when optional tags are absent."""
    record = "v=DMARC1; p=none"
    result = parse_dmarc(record)

    assert result["version"] == "DMARC1"
    assert result["policy"] == "none"
    # sp defaults to policy when absent
    assert result["subdomain_policy"] == "none"
    # pct defaults to 100
    assert result["pct"] == 100
    # rua/ruf default to None
    assert result["rua"] is None
    assert result["ruf"] is None
    # alignment modes default to relaxed
    assert result["adkim"] == "r"
    assert result["aspf"] == "r"
    assert result["raw"] == record


def test_parse_spf_full():
    """parse_spf extracts mechanisms and all-qualifier from a full record."""
    record = "v=spf1 include:spf.protection.outlook.com ip4:203.0.113.0/24 mx a ~all"
    result = parse_spf(record)

    assert result["version"] == "spf1"
    assert result["raw"] == record
    # Mechanisms should contain include, ip4, mx, a but not the version or all
    mechanisms = result["mechanisms"]
    assert any("include:spf.protection.outlook.com" in m for m in mechanisms)
    assert any("ip4:203.0.113.0/24" in m for m in mechanisms)
    assert "mx" in mechanisms
    assert "a" in mechanisms
    assert result["all"] == "~all"


def test_parse_spf_no_all():
    """parse_spf returns None for all when no all-qualifier is present."""
    record = "v=spf1 include:example.com"
    result = parse_spf(record)

    assert result["version"] == "spf1"
    assert result["all"] is None
    assert any("include:example.com" in m for m in result["mechanisms"])


def test_parse_spf_hard_fail():
    """parse_spf handles -all with no other mechanisms correctly."""
    record = "v=spf1 -all"
    result = parse_spf(record)

    assert result["version"] == "spf1"
    assert result["mechanisms"] == []
    assert result["all"] == "-all"
    assert result["raw"] == record


# ===========================================================================
# Async integration tests — require live DNS
# ===========================================================================


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_dmarc_record_real(fresh_cache):
    """get_dmarc_record returns a found record with non-empty policy for google.com."""
    result = await get_dmarc_record("google.com")

    assert result["found"] is True
    assert result["domain"] == "google.com"
    # google.com is expected to publish a DMARC policy
    assert result.get("policy") in ("none", "quarantine", "reject"), (
        f"Unexpected policy: {result.get('policy')!r}"
    )
    # pct must be an integer in range 0-100
    assert isinstance(result.get("pct"), int)
    assert 0 <= result["pct"] <= 100


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_spf_record_real(fresh_cache):
    """get_spf_record returns a found record with non-empty mechanisms for google.com."""
    result = await get_spf_record("google.com")

    assert result["found"] is True
    assert result["domain"] == "google.com"
    # google.com is expected to publish an SPF record with at least one mechanism
    assert len(result.get("mechanisms", [])) > 0, (
        f"Expected at least one SPF mechanism, got: {result}"
    )
    # all-qualifier should be present (google uses ~all or -all)
    assert result.get("all") is not None


@pytest.mark.asyncio
@pytest.mark.network
async def test_get_dmarc_not_found(fresh_cache):
    """get_dmarc_record returns found=False for a domain with no DMARC record."""
    # Use a subdomain of a domain known not to have a published DMARC record.
    # The _dmarc prefix on a non-existent name will produce NXDOMAIN.
    result = await get_dmarc_record("no-dmarc-record-exists.invalid")

    assert result["found"] is False
    assert "domain" in result


@pytest.mark.asyncio
@pytest.mark.network
async def test_cache_returns_same_result(fresh_cache):
    """Calling get_dmarc_record twice returns identical results (cache hit)."""
    first = await get_dmarc_record("google.com")
    second = await get_dmarc_record("google.com")

    assert first == second, (
        f"Cache inconsistency: first={first!r}, second={second!r}"
    )


@pytest.mark.asyncio
@pytest.mark.network
async def test_clear_cache(fresh_cache):
    """clear_cache() empties the TTL cache so subsequent calls hit DNS again."""
    from exchange_mcp import dns_utils as _module

    # Populate cache with a real lookup
    await get_txt_records("_dmarc.google.com")
    assert "_dmarc.google.com" in _module._cache, "Cache should be populated after lookup"

    # Clear and verify eviction
    clear_cache()
    assert len(_module._cache) == 0, f"Cache should be empty after clear_cache(), got: {_module._cache}"
