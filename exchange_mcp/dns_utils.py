"""DNS TXT record resolver with TTL-respecting cache, DMARC parser, and SPF parser.

Provides async lookups for DMARC (RFC 7489) and SPF (RFC 7208) records using
the system default DNS resolver. Results are cached per-name for the duration
of the record TTL, then evicted.

Exports:
    get_txt_records  - Low-level async TXT record resolver with TTL cache
    get_dmarc_record - Async DMARC record lookup and parser
    get_spf_record   - Async SPF record lookup and parser
    parse_dmarc      - Pure-function DMARC tag-value parser
    parse_spf        - Pure-function SPF mechanism parser
    clear_cache      - Clear the in-process TTL cache (useful for testing)
"""

from __future__ import annotations

import re
import time
from typing import Any

import dns.asyncresolver
import dns.exception
import dns.rdatatype
import dns.resolver

# ---------------------------------------------------------------------------
# Module-level TTL cache
# name -> (records, expiry_monotonic)
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[list[str], float]] = {}

_DEFAULT_NEGATIVE_TTL = 300  # seconds to cache NXDOMAIN / NoAnswer
_DEFAULT_TTL = 300           # fallback when rrset.ttl is unavailable


# ---------------------------------------------------------------------------
# Low-level resolver
# ---------------------------------------------------------------------------

async def get_txt_records(name: str) -> list[str]:
    """Resolve DNS TXT records for *name*, returning decoded strings.

    Results are cached for the duration of the record TTL so that repeated
    calls within the same process avoid redundant network round-trips.

    Args:
        name: Fully-qualified domain name to resolve (e.g. "_dmarc.google.com").

    Returns:
        List of TXT record strings (may be empty if name does not exist or
        has no TXT records).

    Raises:
        LookupError: On unexpected DNS failures (network errors, SERVFAIL, etc.).
    """
    now = time.monotonic()

    # Cache hit?
    if name in _cache:
        records, expiry = _cache[name]
        if now < expiry:
            return records

    try:
        answer = await dns.asyncresolver.resolve(name, dns.rdatatype.TXT)
        records: list[str] = []
        for rdata in answer:
            # Each rdata may consist of multiple strings (RFC 7208 §3.3)
            decoded = b"".join(rdata.strings).decode("utf-8", errors="replace")
            records.append(decoded)

        ttl: int = _DEFAULT_TTL
        if answer.rrset is not None:
            ttl = int(answer.rrset.ttl) or _DEFAULT_TTL

        _cache[name] = (records, now + ttl)
        return records

    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        # Negative cache to prevent hammering DNS for non-existent names.
        _cache[name] = ([], now + _DEFAULT_NEGATIVE_TTL)
        return []

    except dns.exception.DNSException as exc:
        raise LookupError(
            f"DNS lookup failed for '{name}': {type(exc).__name__}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# DMARC helpers
# ---------------------------------------------------------------------------

async def get_dmarc_record(domain: str) -> dict[str, Any]:
    """Look up the DMARC TXT record for *domain*.

    Args:
        domain: Base domain to query (query target is ``_dmarc.<domain>``).

    Returns:
        Dict with ``found`` key.  If found, additional parsed keys are
        present (see :func:`parse_dmarc`).  If not found::

            {"found": False, "domain": "<domain>"}
    """
    records = await get_txt_records(f"_dmarc.{domain}")
    dmarc_records = [r for r in records if r.strip().lower().startswith("v=dmarc1")]

    if not dmarc_records:
        return {"found": False, "domain": domain}

    # RFC 7489 §6.6.3: use first valid DMARC record
    return {"found": True, "domain": domain, **parse_dmarc(dmarc_records[0])}


async def get_spf_record(domain: str) -> dict[str, Any]:
    """Look up the SPF TXT record for *domain*.

    Args:
        domain: Domain to query TXT records for.

    Returns:
        Dict with ``found`` key.  If found, additional parsed keys are
        present (see :func:`parse_spf`).  If not found::

            {"found": False, "domain": "<domain>"}
    """
    records = await get_txt_records(domain)
    spf_records = [r for r in records if r.strip().lower().startswith("v=spf1")]

    if not spf_records:
        return {"found": False, "domain": domain}

    # RFC 7208 §3.2: multiple SPF records is a permanent error, but we
    # return the first one rather than raising so callers get a usable result.
    return {"found": True, "domain": domain, **parse_spf(spf_records[0])}


# ---------------------------------------------------------------------------
# Pure-function parsers
# ---------------------------------------------------------------------------

def parse_dmarc(txt_record: str) -> dict[str, Any]:
    """Parse a DMARC TXT record string into a structured dictionary.

    Handles tag-value pairs as specified by RFC 7489 §6.3.  Unknown tags are
    silently ignored.

    Args:
        txt_record: Raw DMARC TXT record string, e.g.
            ``"v=DMARC1; p=reject; pct=100; rua=mailto:dmarc@example.com"``

    Returns:
        Dict with the following keys:

        - ``version``          – always ``"DMARC1"``
        - ``policy``           – value of ``p`` tag (e.g. ``"none"``, ``"quarantine"``, ``"reject"``)
        - ``subdomain_policy`` – value of ``sp`` tag; defaults to ``policy`` if absent
        - ``pct``              – percentage of messages to filter (int, 0-100; default 100)
        - ``rua``              – aggregate report URI(s) or ``None``
        - ``ruf``              – forensic report URI(s) or ``None``
        - ``adkim``            – DKIM alignment mode (``"r"`` relaxed or ``"s"`` strict; default ``"r"``)
        - ``aspf``             – SPF alignment mode (``"r"`` or ``"s"``; default ``"r"``)
        - ``raw``              – original record string
    """
    tags: dict[str, str] = {}
    # RFC 7489 §6.3: tags separated by semicolons, optional whitespace around "="
    for token in re.split(r";\s*", txt_record.strip()):
        token = token.strip()
        if "=" in token:
            key, _, value = token.partition("=")
            tags[key.strip().lower()] = value.strip()

    policy = tags.get("p", "none")
    return {
        "version": tags.get("v", "DMARC1").upper(),
        "policy": policy,
        "subdomain_policy": tags.get("sp", policy),
        "pct": int(tags["pct"]) if "pct" in tags else 100,
        "rua": tags.get("rua") or None,
        "ruf": tags.get("ruf") or None,
        "adkim": tags.get("adkim", "r"),
        "aspf": tags.get("aspf", "r"),
        "raw": txt_record,
    }


def parse_spf(txt_record: str) -> dict[str, Any]:
    """Parse an SPF TXT record string into a structured dictionary.

    Tokenises the record according to RFC 7208 §4.  Each token is classified
    as a *mechanism* (include, a, mx, ip4, ip6, ptr, exists, all) or a
    *modifier* (redirect, exp) or the trailing ``all`` qualifier.

    Args:
        txt_record: Raw SPF TXT record string, e.g.
            ``"v=spf1 include:spf.protection.outlook.com ip4:10.0.0.0/8 -all"``

    Returns:
        Dict with the following keys:

        - ``version``    – always ``"spf1"``
        - ``mechanisms`` – list of mechanism strings (e.g. ``["include:example.com", "ip4:10.0.0.0/8"]``)
        - ``all``        – string representing the trailing ``all`` qualifier
                          (``"+all"``, ``"-all"``, ``"~all"``, ``"?all"``) or ``None`` if absent
        - ``raw``        – original record string
    """
    tokens = txt_record.strip().split()

    mechanisms: list[str] = []
    all_qualifier: str | None = None

    # RFC 7208 §4.6.4: qualifier prefixes
    _qualifiers = ("+", "-", "~", "?")
    _mechanism_names = {"include", "a", "mx", "ptr", "ip4", "ip6", "exists", "all", "redirect", "exp"}

    for token in tokens:
        lower = token.lower()

        # Skip the version tag
        if lower == "v=spf1":
            continue

        # Determine qualifier and bare mechanism name
        if token[0] in _qualifiers:
            qualifier = token[0]
            bare = token[1:]
        else:
            qualifier = "+"
            bare = token

        bare_lower = bare.lower()
        # Mechanism name is the part before any ":"
        mech_name = bare_lower.split(":")[0].split("/")[0]

        if mech_name == "all":
            all_qualifier = f"{qualifier}all" if qualifier != "+" else "+all"
            # RFC 7208 §5.1: "all" by itself without qualifier prefix is "+all"
            # We store the canonical form including qualifier.
        elif mech_name in _mechanism_names:
            mechanisms.append(token)  # preserve original casing and qualifier

    return {
        "version": "spf1",
        "mechanisms": mechanisms,
        "all": all_qualifier,
        "raw": txt_record,
    }


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def clear_cache() -> None:
    """Clear the in-process DNS TTL cache.

    Intended for use in tests and situations where stale data must be evicted
    (e.g. after a DNS change that needs immediate reflection).
    """
    _cache.clear()
