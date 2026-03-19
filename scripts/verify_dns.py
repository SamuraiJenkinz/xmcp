"""End-to-end DNS verification script for DMARC and SPF lookups.

Proves the dns_utils module resolves real DNS records without invoking PowerShell.
Uses google.com as a stable reference domain with well-known published records.

Usage:
    uv run python scripts/verify_dns.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchange_mcp.dns_utils import get_dmarc_record, get_spf_record


async def main() -> int:
    """Run DNS verification checks.

    Returns:
        0 on success, 1 on any failure.
    """
    passed = 0
    failed = 0
    domain = "google.com"

    print("DNS Verification")
    print("=" * 50)

    # ------------------------------------------------------------------
    # Check 1: DMARC record for google.com
    # ------------------------------------------------------------------
    print(f"\nCheck 1: DMARC record for {domain}")
    try:
        dmarc = await get_dmarc_record(domain)
        assert dmarc["found"] is True, f"Expected found=True, got: {dmarc}"
        policy = dmarc.get("policy")
        assert policy in ("none", "quarantine", "reject"), (
            f"Unexpected DMARC policy: {policy!r}"
        )
        print(f"  [PASS] Found DMARC record")
        print(f"  Policy : {policy}")
        print(f"  pct    : {dmarc.get('pct')}")
        print(f"  rua    : {dmarc.get('rua')}")
        passed += 1
    except AssertionError as exc:
        print(f"  [FAIL] Assertion failed: {exc}")
        failed += 1
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] Unexpected error: {type(exc).__name__}: {exc}")
        failed += 1

    # ------------------------------------------------------------------
    # Check 2: SPF record for google.com
    # ------------------------------------------------------------------
    print(f"\nCheck 2: SPF record for {domain}")
    try:
        spf = await get_spf_record(domain)
        assert spf["found"] is True, f"Expected found=True, got: {spf}"
        mechanisms = spf.get("mechanisms", [])
        assert len(mechanisms) > 0, (
            f"Expected at least one SPF mechanism, got: {mechanisms!r}"
        )
        print(f"  [PASS] Found SPF record")
        print(f"  Mechanisms : {json.dumps(mechanisms)}")
        print(f"  All        : {spf.get('all')}")
        passed += 1
    except AssertionError as exc:
        print(f"  [FAIL] Assertion failed: {exc}")
        failed += 1
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] Unexpected error: {type(exc).__name__}: {exc}")
        failed += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 50}")
    print(f"Passed: {passed}/2   Failed: {failed}/2")

    if failed == 0:
        print("\nALL DNS CHECKS PASSED")
        return 0
    else:
        print(f"\n{failed} DNS CHECK(S) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
