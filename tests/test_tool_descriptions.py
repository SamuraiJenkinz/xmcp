"""Tests validating the quality, clarity, and uniqueness of Exchange tool descriptions.

Tool descriptions are the primary signal an LLM uses to select the correct tool.
These tests act as a regression guard ensuring descriptions remain unambiguous,
plain-language, and properly structured after any future edits.

Tests:
    1.  test_all_descriptions_under_800_chars
    2.  test_all_descriptions_contain_use_when
    3.  test_all_descriptions_contain_example_query
    4.  test_no_exchange_jargon
    5.  test_tool_names_are_snake_case
    6.  test_no_duplicate_tool_names
    7.  test_input_schemas_are_valid_json_schema
    8.  test_required_params_exist_in_properties
    9.  test_mailbox_stats_vs_search_disambiguation
    10. test_dmarc_vs_dkim_disambiguation
"""

from __future__ import annotations

import re

import pytest

from exchange_mcp.tools import TOOL_DEFINITIONS

# ---------------------------------------------------------------------------
# Helper: tools excluding ping (ping has a minimal description by design)
# ---------------------------------------------------------------------------

EXCHANGE_TOOLS = [t for t in TOOL_DEFINITIONS if t.name != "ping"]


# ---------------------------------------------------------------------------
# 1. test_all_descriptions_under_800_chars
# ---------------------------------------------------------------------------


def test_all_descriptions_under_800_chars() -> None:
    """Every tool description must be at most 800 characters.

    Longer descriptions increase token usage and may get truncated in some
    LLM context windows, reducing tool-selection accuracy.
    """
    failures = []
    for tool in TOOL_DEFINITIONS:
        length = len(tool.description)
        if length > 800:
            failures.append(f"  {tool.name}: {length} chars (limit 800)")

    assert not failures, "Tools with descriptions over 800 chars:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 2. test_all_descriptions_contain_use_when
# ---------------------------------------------------------------------------


def test_all_descriptions_contain_use_when() -> None:
    """Every Exchange tool description must contain 'Use when'.

    The 'Use when' phrase marks the trigger conditions that guide LLM
    tool selection. Descriptions without it lack a clear selection signal.
    """
    failures = []
    for tool in EXCHANGE_TOOLS:
        if "Use when" not in tool.description:
            failures.append(f"  {tool.name}: missing 'Use when' trigger phrase")

    assert not failures, "Tools missing 'Use when':\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 3. test_all_descriptions_contain_example_query
# ---------------------------------------------------------------------------


def test_all_descriptions_contain_example_query() -> None:
    """Every Exchange tool description must contain at least one example query.

    Example queries (text in single quotes) give the LLM concrete natural
    language patterns to match against, improving selection accuracy.
    """
    failures = []
    for tool in EXCHANGE_TOOLS:
        # Look for text enclosed in single quotes — our example query convention
        if not re.search(r"'[^']+'", tool.description):
            failures.append(f"  {tool.name}: no example query found (expected text in single quotes)")

    assert not failures, "Tools missing example queries:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 4. test_no_exchange_jargon
# ---------------------------------------------------------------------------


def test_no_exchange_jargon() -> None:
    """Tool descriptions must use plain language, not Exchange or PowerShell jargon.

    Forbidden terms make descriptions harder for non-experts to read and
    cause inconsistent LLM tool selection when user queries use plain language.

    Forbidden: UPN, 'recipient object', 'mailbox-enabled', 'cmdlet',
               'PowerShell', 'ConvertTo-Json', standalone word 'identity'
               (as it is Exchange admin jargon for 'email address').
    """
    forbidden_exact = [
        "UPN",
        "recipient object",
        "mailbox-enabled",
        "cmdlet",
        "PowerShell",
        "ConvertTo-Json",
    ]
    failures = []

    for tool in TOOL_DEFINITIONS:
        desc = tool.description

        # Case-insensitive exact string matches
        for term in forbidden_exact:
            if term.lower() in desc.lower():
                failures.append(f"  {tool.name}: contains forbidden term '{term}'")

        # 'identity' as a standalone word (word-boundary check, case-insensitive)
        if re.search(r"\bidentity\b", desc, re.IGNORECASE):
            failures.append(f"  {tool.name}: contains forbidden standalone word 'identity'")

    assert not failures, "Tools containing Exchange jargon:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 5. test_tool_names_are_snake_case
# ---------------------------------------------------------------------------


def test_tool_names_are_snake_case() -> None:
    """All tool names must be lowercase snake_case (letters, digits, underscores only).

    Consistent naming helps callers and reduces mapping errors in dispatch.
    """
    failures = []
    for tool in TOOL_DEFINITIONS:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", tool.name):
            failures.append(f"  '{tool.name}': not valid snake_case")

    assert not failures, "Tools with invalid names:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 6. test_no_duplicate_tool_names
# ---------------------------------------------------------------------------


def test_no_duplicate_tool_names() -> None:
    """No two tools in TOOL_DEFINITIONS may share the same name.

    Duplicate names cause silent dispatch table overwrites, where only the
    last definition wins.
    """
    names = [t.name for t in TOOL_DEFINITIONS]
    seen: set[str] = set()
    duplicates: list[str] = []

    for name in names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)

    assert not duplicates, f"Duplicate tool names: {duplicates}"


# ---------------------------------------------------------------------------
# 7. test_input_schemas_are_valid_json_schema
# ---------------------------------------------------------------------------


def test_input_schemas_are_valid_json_schema() -> None:
    """Every tool's inputSchema must have 'type': 'object', 'properties', and 'required'.

    These three fields are required by the MCP spec for tool schemas.
    Missing fields cause SDK validation errors at call time.
    """
    failures = []
    for tool in TOOL_DEFINITIONS:
        schema = tool.inputSchema
        if schema.get("type") != "object":
            failures.append(f"  {tool.name}: inputSchema missing 'type': 'object'")
        if "properties" not in schema:
            failures.append(f"  {tool.name}: inputSchema missing 'properties'")
        if "required" not in schema:
            failures.append(f"  {tool.name}: inputSchema missing 'required'")

    assert not failures, "Tools with invalid inputSchema:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 8. test_required_params_exist_in_properties
# ---------------------------------------------------------------------------


def test_required_params_exist_in_properties() -> None:
    """Every parameter listed in 'required' must exist in 'properties'.

    A required parameter absent from properties causes MCP SDK validation
    errors and prevents the tool from being called at all.
    """
    failures = []
    for tool in TOOL_DEFINITIONS:
        schema = tool.inputSchema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for param in required:
            if param not in properties:
                failures.append(
                    f"  {tool.name}: required param '{param}' not in properties"
                )

    assert not failures, "Tools with required params missing from properties:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# 9. test_mailbox_stats_vs_search_disambiguation
# ---------------------------------------------------------------------------


def test_mailbox_stats_vs_search_disambiguation() -> None:
    """get_mailbox_stats and search_mailboxes must use non-overlapping trigger language.

    get_mailbox_stats: a single named user's details (size, quota, last login).
    search_mailboxes: find/list multiple mailboxes by filter.

    Overlap risk: both relate to mailboxes. The descriptions must make
    clear that one is 'one specific person' and the other is 'find many'.
    """
    stats_tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_mailbox_stats")
    search_tool = next(t for t in TOOL_DEFINITIONS if t.name == "search_mailboxes")

    stats_desc = stats_tool.description.lower()
    search_desc = search_tool.description.lower()

    # get_mailbox_stats must signal "one specific user" intent
    assert any(
        phrase in stats_desc for phrase in ["single", "one specific", "specific user", "one user"]
    ), (
        "get_mailbox_stats description must clarify it operates on one specific user "
        "(missing 'single', 'one specific', 'specific user', or 'one user')"
    )

    # search_mailboxes must signal "find many / list" intent
    assert any(
        phrase in search_desc for phrase in ["find", "list", "multiple", "enumerate"]
    ), (
        "search_mailboxes description must clarify it finds/lists multiple mailboxes "
        "(missing 'find', 'list', 'multiple', or 'enumerate')"
    )

    # get_mailbox_stats must reference search_mailboxes in its does-NOT clause
    assert "search_mailboxes" in stats_desc, (
        "get_mailbox_stats description must reference search_mailboxes in its disambiguation clause"
    )

    # search_mailboxes must reference get_mailbox_stats in its does-NOT clause
    assert "get_mailbox_stats" in search_desc, (
        "search_mailboxes description must reference get_mailbox_stats in its disambiguation clause"
    )


# ---------------------------------------------------------------------------
# 10. test_dmarc_vs_dkim_disambiguation
# ---------------------------------------------------------------------------


def test_dmarc_vs_dkim_disambiguation() -> None:
    """get_dmarc_status and get_dkim_config must use non-overlapping trigger language.

    get_dmarc_status: DMARC policy and SPF record, resolved via DNS lookup.
    get_dkim_config: DKIM signing config and CNAME records from Exchange.

    Overlap risk: both relate to 'email authentication'. The descriptions must
    make clear which technology each tool covers and signal to NOT use the
    other for a given query.
    """
    dmarc_tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_dmarc_status")
    dkim_tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_dkim_config")

    dmarc_desc = dmarc_tool.description.lower()
    dkim_desc = dkim_tool.description.lower()

    # get_dmarc_status must mention SPF or policy
    assert any(phrase in dmarc_desc for phrase in ["spf", "policy", "dmarc"]), (
        "get_dmarc_status description must mention SPF, policy, or DMARC"
    )

    # get_dmarc_status must reference get_dkim_config in its does-NOT clause
    assert "get_dkim_config" in dmarc_desc, (
        "get_dmarc_status description must reference get_dkim_config in its disambiguation clause"
    )

    # get_dkim_config must mention signing or selectors
    assert any(phrase in dkim_desc for phrase in ["signing", "selector", "cname", "dkim"]), (
        "get_dkim_config description must mention DKIM signing, selectors, or CNAME records"
    )

    # get_dkim_config must reference get_dmarc_status in its does-NOT clause
    assert "get_dmarc_status" in dkim_desc, (
        "get_dkim_config description must reference get_dmarc_status in its disambiguation clause"
    )

    # The two tools must trigger on different keywords
    # DMARC tool should trigger on "policy" or "spf" or "authentication policy"
    # DKIM tool should trigger on "signing" or "selector" or "dkim enabled"
    assert "policy" in dmarc_desc or "spf" in dmarc_desc, (
        "get_dmarc_status must include 'policy' or 'SPF' as triggers to distinguish from DKIM"
    )
    assert "signing" in dkim_desc or "selector" in dkim_desc, (
        "get_dkim_config must include 'signing' or 'selector' as triggers to distinguish from DMARC"
    )
