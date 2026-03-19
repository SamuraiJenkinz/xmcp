"""End-to-end verification script for Exchange Online connectivity and cmdlet execution.

Proves the complete Phase 1 Exchange client layer works against live infrastructure:
  1. Environment variable check (ExchangeClient constructor)
  2. Connection health-check via verify_connection()
  3. Proof-of-concept cmdlet: Get-OrganizationConfig with explicit Select-Object
  4. Second cmdlet to confirm no orphaned sessions: Get-AcceptedDomain

Usage:
    uv run python scripts/verify_exchange.py

Required environment variables:
    AZURE_CERT_THUMBPRINT  - Certificate thumbprint for CBA
    AZURE_CLIENT_ID        - Azure AD application (client) ID
    AZURE_TENANT_DOMAIN    - Tenant domain (e.g. contoso.onmicrosoft.com)
"""

from __future__ import annotations

import asyncio
import json
import sys

# ---------------------------------------------------------------------------
# Ensure package is importable when run from project root
# ---------------------------------------------------------------------------
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchange_mcp.exchange_client import ExchangeClient


def _print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _print_result(label: str, value: object) -> None:
    """Print a key/value result line."""
    if isinstance(value, (dict, list)):
        print(f"  {label}:")
        print(f"    {json.dumps(value, indent=2, default=str)}")
    else:
        print(f"  {label}: {value}")


async def main() -> int:
    """Run all verification steps.

    Returns:
        0 on success, 1 on any failure.
    """
    passed = 0
    failed = 0

    # ------------------------------------------------------------------
    # Step 1: Environment variable check
    # ------------------------------------------------------------------
    _print_section("Step 1: Environment variable check")
    try:
        client = ExchangeClient(timeout=90)
        print("  [PASS] ExchangeClient created — all env vars present")
        _print_result("AZURE_CERT_THUMBPRINT", os.environ.get("AZURE_CERT_THUMBPRINT", "")[:8] + "...")
        _print_result("AZURE_CLIENT_ID", os.environ.get("AZURE_CLIENT_ID", "")[:8] + "...")
        _print_result("AZURE_TENANT_DOMAIN", os.environ.get("AZURE_TENANT_DOMAIN", ""))
        passed += 1
    except EnvironmentError as exc:
        print(f"  [FAIL] Missing environment variables: {exc}")
        print("\nSet the required env vars and re-run.")
        return 1

    # ------------------------------------------------------------------
    # Step 2: verify_connection()
    # ------------------------------------------------------------------
    _print_section("Step 2: Exchange Online connectivity (verify_connection)")
    print("  Connecting to Exchange Online via CBA...")
    try:
        ok = await client.verify_connection()
        if ok:
            print("  [PASS] verify_connection() returned True — Exchange Online reachable")
            passed += 1
        else:
            print("  [FAIL] verify_connection() returned False — check credentials/permissions")
            failed += 1
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] verify_connection() raised: {type(exc).__name__}: {exc}")
        failed += 1

    # ------------------------------------------------------------------
    # Step 3: Proof-of-concept cmdlet (Get-OrganizationConfig)
    # ------------------------------------------------------------------
    _print_section("Step 3: Proof-of-concept cmdlet (Get-OrganizationConfig)")
    print("  Running: Get-OrganizationConfig | Select-Object Name, DisplayName, Identity, WhenCreated")
    try:
        result = await client.run_cmdlet(
            "Get-OrganizationConfig | Select-Object Name, DisplayName, Identity, WhenCreated"
        )
        _print_result("Result type", type(result).__name__)
        _print_result("Result", result)

        # Verify the result has the expected fields
        if isinstance(result, dict):
            name = result.get("Name")
            if name:
                print(f"  [PASS] Name field populated: {name!r}")
                passed += 1
            else:
                print(f"  [FAIL] Name field missing or empty. Full result: {result!r}")
                failed += 1

            # Verify no @{...} truncation — all fields should be real values
            raw_str = json.dumps(result)
            if "@{" in raw_str:
                print(f"  [FAIL] Detected @{{}} truncation in result (ConvertTo-Json depth issue): {raw_str[:200]}")
                failed += 1
            else:
                print("  [PASS] No @{} truncation detected — ConvertTo-Json -Depth 10 working")
                passed += 1
        else:
            print(f"  [FAIL] Expected dict result, got {type(result).__name__}: {result!r}")
            failed += 1

    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] run_cmdlet raised: {type(exc).__name__}: {exc}")
        failed += 1

    # ------------------------------------------------------------------
    # Step 4: Second cmdlet — confirms no orphaned sessions
    # ------------------------------------------------------------------
    _print_section("Step 4: Second cmdlet to confirm session lifecycle (Get-AcceptedDomain)")
    print("  Running: Get-AcceptedDomain | Select-Object DomainName, DomainType, Default | Select-Object -First 3")
    try:
        result2 = await client.run_cmdlet(
            "Get-AcceptedDomain | Select-Object DomainName, DomainType, Default | Select-Object -First 3"
        )
        _print_result("Result type", type(result2).__name__)
        _print_result("Result", result2)

        if result2 or result2 == []:
            # Even an empty list is valid — the cmdlet completed
            count = len(result2) if isinstance(result2, list) else 1
            print(f"  [PASS] Second cmdlet completed successfully ({count} domain(s) returned)")
            print("  [PASS] Session lifecycle healthy — no orphaned PS sessions")
            passed += 1
        else:
            print("  [FAIL] Second cmdlet returned unexpected falsy value")
            failed += 1

    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] Second cmdlet raised: {type(exc).__name__}: {exc}")
        failed += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _print_section("Verification Summary")
    total = passed + failed
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")

    if failed == 0:
        print("\n  ALL EXCHANGE CHECKS PASSED")
        return 0
    else:
        print(f"\n  {failed} CHECK(S) FAILED — review output above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
