"""Tool definitions and dispatch table for the Exchange MCP server.

Provides:
    TOOL_DEFINITIONS  -- list of all 16 mcp.types.Tool objects (15 Exchange + ping)
    TOOL_DISPATCH     -- dict mapping tool name to async handler callable

The dispatch table is the single point of truth for routing:
    handler = TOOL_DISPATCH[name]
    result  = await handler(arguments, client)

All 15 Exchange tool handlers are stubs that raise NotImplementedError until
the Phase 3-6 implementations replace them.  The ping handler is fully
implemented here.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import mcp.types as types

from exchange_mcp import dns_utils

if TYPE_CHECKING:
    from exchange_mcp.exchange_client import ExchangeClient


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[types.Tool] = [
    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------
    types.Tool(
        name="ping",
        description=(
            "Test server connectivity and confirm the Exchange MCP server is running. "
            "Use when asked whether the server is up, if Exchange tools are available, "
            "or to troubleshoot connectivity before running other tools."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),

    # ------------------------------------------------------------------
    # Mailbox tools (Phase 3)
    # ------------------------------------------------------------------
    types.Tool(
        name="get_mailbox_stats",
        description=(
            "Returns size, item count, quota limits, last logon time, and database "
            "location for one specific user's mailbox. "
            "Use when asked about a single person's mailbox: 'How full is alice@contoso.com?', "
            "'When did Bob last log in?', 'Is Jane near her quota?'. "
            "Does NOT search or list multiple mailboxes — use search_mailboxes for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "email_address": {
                    "type": "string",
                    "description": "The email address of the mailbox to inspect.",
                }
            },
            "required": ["email_address"],
        },
    ),
    types.Tool(
        name="search_mailboxes",
        description=(
            "Finds and lists multiple mailboxes matching a filter by database, mailbox "
            "type, or display name pattern. Returns names, addresses, and types. "
            "Use when asked to enumerate or find mailboxes: 'List all shared mailboxes', "
            "'Which mailboxes are on DB01?', 'Find mailboxes with Sales in the name'. "
            "Does NOT return size or quota details for a specific user — use get_mailbox_stats for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filter_type": {
                    "type": "string",
                    "enum": ["database", "type", "name"],
                    "description": (
                        "How to filter mailboxes. "
                        "'database' finds mailboxes on a specific database, "
                        "'type' filters by mailbox type (e.g. SharedMailbox), "
                        "'name' searches by display name."
                    ),
                },
                "filter_value": {
                    "type": "string",
                    "description": "The value to filter by (database name, type, or partial name).",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of mailboxes to return. Default is 100.",
                },
            },
            "required": ["filter_type", "filter_value"],
        },
    ),
    types.Tool(
        name="get_shared_mailbox_owners",
        description=(
            "Returns the list of users who have full-access permissions on a specific "
            "shared mailbox, along with each person's permission type. "
            "Use when asked who has access to a shared mailbox: 'Who can read the finance inbox?', "
            "'Who manages the support@contoso.com mailbox?', 'List delegates for the HR mailbox'. "
            "Does NOT find or list shared mailboxes — use search_mailboxes with type=SharedMailbox for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "email_address": {
                    "type": "string",
                    "description": "The email address of the shared mailbox.",
                }
            },
            "required": ["email_address"],
        },
    ),

    # ------------------------------------------------------------------
    # DAG and Database tools (Phase 4)
    # ------------------------------------------------------------------
    types.Tool(
        name="list_dag_members",
        description=(
            "Returns the server inventory for a database availability group (DAG): "
            "which servers are members, their names, and operational status. "
            "Use when asked which servers belong to a DAG: 'What servers are in DAG01?', "
            "'How many nodes does the DAG have?', 'List all DAG members'. "
            "Does NOT check replication health or queue lengths — use get_dag_health for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "dag_name": {
                    "type": "string",
                    "description": (
                        "Name of the DAG to inspect. "
                        "If omitted, returns members for all DAGs in the environment."
                    ),
                }
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_dag_health",
        description=(
            "Returns replication health for a database availability group (DAG): "
            "copy queue lengths, content index state, replay queue lengths, and copy status. "
            "Use when asked about DAG health or replication: 'Is DAG01 healthy?', "
            "'Are there replication errors?', 'What is the copy queue length on EX01?'. "
            "Does NOT list which servers are in the DAG — use list_dag_members for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "dag_name": {
                    "type": "string",
                    "description": "The name of the DAG to check.",
                }
            },
            "required": ["dag_name"],
        },
    ),
    types.Tool(
        name="get_database_copies",
        description=(
            "Returns all copies of a specific mailbox database across DAG members: "
            "activation preference, copy queue length, replay queue length, and status. "
            "Use when asked about a specific database's copies: 'Which server holds the active "
            "copy of MBX-DB01?', 'How many copies exist for the Sales database?', "
            "'What is the replication lag for DB02?'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "database_name": {
                    "type": "string",
                    "description": "The name of the mailbox database to inspect.",
                }
            },
            "required": ["database_name"],
        },
    ),

    # ------------------------------------------------------------------
    # Mail flow tools (Phase 5)
    # ------------------------------------------------------------------
    types.Tool(
        name="check_mail_flow",
        description=(
            "Tests whether email can flow from a specific sender to a specific recipient "
            "by tracing the routing path and checking for delivery restrictions. "
            "Use when asked about email delivery between two people: 'Can Alice email Bob?', "
            "'Why is mail from sales@contoso.com blocked to partner@fabrikam.com?', "
            "'Verify routing between these two addresses'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sender": {
                    "type": "string",
                    "description": "The sender's email address.",
                },
                "recipient": {
                    "type": "string",
                    "description": "The recipient's email address.",
                },
            },
            "required": ["sender", "recipient"],
        },
    ),
    types.Tool(
        name="get_transport_queues",
        description=(
            "Returns the current state of email sending queues on Exchange servers: "
            "message backlog counts, queue types, and next hop destinations. "
            "Use when asked about email backlogs or stuck messages: 'Are there emails stuck "
            "in the queue?', 'Is there a mail backlog on EX02?', 'How many messages are queued?'. "
            "Does NOT test routing between two addresses — use check_mail_flow for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "Name of the Exchange server to check. If omitted, checks all servers.",
                },
                "backlog_threshold": {
                    "type": "integer",
                    "description": (
                        "Message count threshold for backlog flagging. "
                        "Queues above this count are flagged with over_threshold: true. "
                        "Default is 100."
                    ),
                },
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_smtp_connectors",
        description=(
            "Returns Send and Receive connectors configured in Exchange: address spaces, "
            "permissions, authentication settings, and enabled status. "
            "Use when asked about SMTP connector configuration: 'What connectors are set up?', "
            "'How is outbound email routed?', 'What relays or smart hosts are configured?', "
            "'Show me the Receive connector settings'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "connector_type": {
                    "type": "string",
                    "enum": ["send", "receive", "all"],
                    "description": (
                        "Which connectors to return: 'send', 'receive', or 'all'. "
                        "Default is 'all'."
                    ),
                }
            },
            "required": [],
        },
    ),

    # ------------------------------------------------------------------
    # Security tools (Phase 5)
    # ------------------------------------------------------------------
    types.Tool(
        name="get_dkim_config",
        description=(
            "Returns the DKIM (DomainKeys Identified Mail) signing configuration from "
            "Exchange for a domain: whether signing is enabled, selector names, the "
            "CNAME records needed in DNS, and whether those CNAMEs are correctly published. "
            "Use when asked about DKIM signing setup: 'Is DKIM enabled for contoso.com?', "
            "'What are the DKIM selectors?', 'Show DKIM signing config'. "
            "If omitted, returns configuration for all domains. "
            "Does NOT check DMARC policy or SPF — use get_dmarc_status for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": (
                        "The domain name to check DKIM configuration for. "
                        "If omitted, returns configuration for all domains."
                    ),
                }
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_dmarc_status",
        description=(
            "Returns the DMARC policy and SPF record for a domain by querying DNS directly. "
            "Shows the policy action (none/quarantine/reject), alignment mode, and reporting addresses. "
            "Use when asked about email authentication policy: 'Does contoso.com have DMARC?', "
            "'What happens to emails that fail authentication?', 'Check SPF and DMARC for fabrikam.com'. "
            "Does NOT check DKIM signing configuration — use get_dkim_config for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain name to check DMARC status for.",
                }
            },
            "required": ["domain"],
        },
    ),
    types.Tool(
        name="check_mobile_devices",
        description=(
            "Returns the phones and tablets that have synced with a user's mailbox "
            "via ActiveSync or Outlook Mobile, including device type, model, and last sync time. "
            "Use when asked about a user's connected mobile devices: 'What phones does Alice have "
            "connected?', 'When did Bob's iPhone last sync?', 'Audit mobile access for this mailbox'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "email_address": {
                    "type": "string",
                    "description": "The email address of the user whose devices to check.",
                }
            },
            "required": ["email_address"],
        },
    ),

    # ------------------------------------------------------------------
    # Hybrid tools (Phase 6)
    # ------------------------------------------------------------------
    types.Tool(
        name="get_hybrid_config",
        description=(
            "Returns the full Exchange hybrid topology: organization relationships, "
            "federation trust details, OAuth configuration, and which domains are hybrid-enabled. "
            "Use when asked about the overall hybrid setup: 'How is Exchange hybrid configured?', "
            "'What domains are in the hybrid relationship?', 'Show the federation trust settings'. "
            "Does NOT test whether hybrid connectors are currently working — use get_connector_status for that."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="get_migration_batches",
        description=(
            "Returns mailbox migration batches: their names, status, progress percentage, "
            "number of mailboxes completed, and any per-mailbox errors. "
            "Use when asked about mailbox migrations: 'How many users have been migrated?', "
            "'Is the Wave2 migration batch still running?', 'Which migrations failed?', "
            "'Show all active migration batches'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["active", "completed", "failed", "all"],
                    "description": (
                        "Filter batches by status: 'active', 'completed', 'failed', "
                        "or 'all'. Default is 'all'."
                    ),
                }
            },
            "required": [],
        },
    ),
    types.Tool(
        name="get_connector_status",
        description=(
            "Checks whether Exchange hybrid connectors are currently working by running "
            "a live test against Exchange Online: reports inbound and outbound connector "
            "health, last successful mail time, and any recent errors. "
            "Use when asked if hybrid mail flow is working right now: 'Are the hybrid connectors up?', "
            "'Is mail flowing between on-premises and cloud?', 'Test the hybrid connector health'. "
            "Does NOT return the hybrid topology or federation settings — use get_hybrid_config for that."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
]


# ---------------------------------------------------------------------------
# Shared helpers (used by Phase 3-6 tool handlers)
# ---------------------------------------------------------------------------

_UPN_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _validate_upn(email: str) -> None:
    """Raise RuntimeError if email does not match a basic UPN pattern."""
    if not _UPN_RE.match(email):
        raise RuntimeError(
            f"'{email}' is not a valid email address. "
            "Expected format: user@domain.com"
        )


def _escape_ps_single_quote(value: str) -> str:
    """Escape single quotes for PowerShell string literals by doubling them."""
    return value.replace("'", "''")


def _format_size(byte_count: int | None) -> str | None:
    """Convert raw byte count to human-friendly size string.

    Returns None if byte_count is None (handles missing data from Exchange).
    """
    if byte_count is None:
        return None
    if byte_count >= 1_073_741_824:  # 1 GB
        return f"{byte_count / 1_073_741_824:.1f} GB"
    elif byte_count >= 1_048_576:  # 1 MB
        return f"{byte_count / 1_048_576:.1f} MB"
    elif byte_count >= 1_024:  # 1 KB
        return f"{byte_count / 1_024:.1f} KB"
    return f"{byte_count} B"


# ---------------------------------------------------------------------------
# Mailbox tool handlers (Phase 3)
# ---------------------------------------------------------------------------

async def _get_mailbox_stats_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return size, quota, last logon, and database for a single mailbox."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    email = arguments.get("email_address", "").strip()
    _validate_upn(email)
    safe = _escape_ps_single_quote(email)

    # Call 1: size + logon stats (Get-MailboxStatistics)
    stats_cmdlet = (
        f"Get-MailboxStatistics -Identity '{safe}' | Select-Object "
        "DisplayName, ItemCount, LastLogonTime, Database, "
        "@{Name='TotalItemSizeBytes';Expression={"
        "[long]($_.TotalItemSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))"
        "}}"
    )

    # Call 2: quota limits (Get-Mailbox)
    quota_cmdlet = (
        f"Get-Mailbox -Identity '{safe}' | Select-Object "
        "PrimarySmtpAddress, RecipientTypeDetails, "
        "ProhibitSendQuota, ProhibitSendReceiveQuota, IssueWarningQuota"
    )

    try:
        stats_raw = await client.run_cmdlet_with_retry(stats_cmdlet)
        quota_raw = await client.run_cmdlet_with_retry(quota_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No mailbox found for '{email}'. "
                "Check the email address and try again."
            ) from None
        raise

    # Normalize single-result dict vs list
    stats = stats_raw if isinstance(stats_raw, dict) else (stats_raw[0] if stats_raw else {})
    quota = quota_raw if isinstance(quota_raw, dict) else (quota_raw[0] if quota_raw else {})

    return {
        "email_address": email,
        "display_name": stats.get("DisplayName"),
        "mailbox_type": quota.get("RecipientTypeDetails"),
        "database": stats.get("Database"),
        "total_size": _format_size(stats.get("TotalItemSizeBytes")),
        "total_size_bytes": stats.get("TotalItemSizeBytes"),
        "item_count": stats.get("ItemCount"),
        "last_logon": stats.get("LastLogonTime"),
        "quotas": {
            "issue_warning": str(quota.get("IssueWarningQuota") or ""),
            "prohibit_send": str(quota.get("ProhibitSendQuota") or ""),
            "prohibit_send_receive": str(quota.get("ProhibitSendReceiveQuota") or ""),
        },
    }


async def _get_shared_mailbox_owners_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return full access, send-as, and send-on-behalf delegates for a mailbox."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    email = arguments.get("email_address", "").strip()
    _validate_upn(email)
    safe = _escape_ps_single_quote(email)

    # Query 1: Full Access permissions
    # -IncludeUserWithDisplayName adds UserDisplayName field (Exchange Online)
    # Where-Object filters: FullAccess only, no Deny entries, no system accounts
    fa_cmdlet = (
        f"Get-MailboxPermission -Identity '{safe}' -IncludeUserWithDisplayName | "
        "Where-Object { $_.AccessRights -contains 'FullAccess' -and "
        "$_.Deny -eq $false -and "
        "$_.User -notlike 'NT AUTHORITY\\*' -and "
        "$_.User -notlike 'S-1-5-*' -and "
        "$_.User -ne 'SELF' } | "
        "Select-Object User, UserDisplayName, IsInherited"
    )

    # Query 2: Send As permissions
    sa_cmdlet = (
        f"Get-RecipientPermission -Identity '{safe}' -AccessRights SendAs | "
        "Where-Object { $_.Trustee -notlike 'NT AUTHORITY\\*' -and "
        "$_.Trustee -ne 'SELF' } | "
        "Select-Object Trustee, IsInherited"
    )

    # Query 3: Send on Behalf — from the mailbox object itself
    sob_cmdlet = (
        f"Get-Mailbox -Identity '{safe}' | Select-Object GrantSendOnBehalfTo"
    )

    try:
        fa_raw = await client.run_cmdlet_with_retry(fa_cmdlet)
        sa_raw = await client.run_cmdlet_with_retry(sa_cmdlet)
        sob_raw = await client.run_cmdlet_with_retry(sob_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No mailbox found for '{email}'. "
                "Check the email address and try again."
            ) from None
        raise

    # Normalize single-result dict vs list for FullAccess and SendAs
    fa_list = fa_raw if isinstance(fa_raw, list) else ([fa_raw] if isinstance(fa_raw, dict) and fa_raw else [])
    sa_list = sa_raw if isinstance(sa_raw, list) else ([sa_raw] if isinstance(sa_raw, dict) and sa_raw else [])

    # SendOnBehalf is a single mailbox object with GrantSendOnBehalfTo property
    sob_data = sob_raw if isinstance(sob_raw, dict) else (sob_raw[0] if sob_raw else {})
    sob_raw_list = sob_data.get("GrantSendOnBehalfTo") or []
    # GrantSendOnBehalfTo can be a single string or a list
    sob_entries = sob_raw_list if isinstance(sob_raw_list, list) else [sob_raw_list]

    def _fa_entry(r: dict) -> dict:
        return {
            "display_name": r.get("UserDisplayName"),
            "identity": str(r.get("User", "")),
            "inherited": bool(r.get("IsInherited", False)),
            "via_group": None,  # Exchange does not expose source group
        }

    def _sa_entry(r: dict) -> dict:
        return {
            "display_name": None,  # Get-RecipientPermission has no display name field
            "identity": str(r.get("Trustee", "")),
            "inherited": bool(r.get("IsInherited", False)),
            "via_group": None,
        }

    def _sob_entry(dn: str) -> dict:
        return {
            "display_name": None,  # DN/UPN value; would need Get-Recipient to resolve
            "identity": dn,
            "inherited": False,  # GrantSendOnBehalfTo has no inheritance concept
            "via_group": None,
        }

    full_access = [_fa_entry(r) for r in fa_list]
    send_as = [_sa_entry(r) for r in sa_list]
    send_on_behalf = [_sob_entry(dn) for dn in sob_entries if dn]

    return {
        "mailbox": email,
        "full_access": full_access,
        "full_access_count": len(full_access),
        "send_as": send_as,
        "send_as_count": len(send_as),
        "send_on_behalf": send_on_behalf,
        "send_on_behalf_count": len(send_on_behalf),
    }


async def _search_mailboxes_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Search for mailboxes by database, type, or display name pattern."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    filter_type = arguments.get("filter_type", "")
    filter_value = arguments.get("filter_value", "").strip()
    max_results = int(arguments.get("max_results") or 100)

    if not filter_value:
        raise RuntimeError(
            "filter_value is required. Provide a database name, mailbox type, or display name to search for."
        )

    safe_val = _escape_ps_single_quote(filter_value)
    select_fields = "DisplayName, PrimarySmtpAddress, RecipientTypeDetails, Database"

    # Request one extra to detect truncation
    result_size = max_results + 1

    if filter_type == "database":
        cmdlet = (
            f"Get-Mailbox -Database '{safe_val}' -ResultSize {result_size} "
            f"| Select-Object {select_fields}"
        )
    elif filter_type == "type":
        cmdlet = (
            f"Get-Mailbox -RecipientTypeDetails {safe_val} -ResultSize {result_size} "
            f"| Select-Object {select_fields}"
        )
    elif filter_type == "name":
        # Strip trailing wildcard — ANR is already a prefix match
        anr_val = safe_val.rstrip("*")
        cmdlet = (
            f"Get-Mailbox -Anr '{anr_val}' -ResultSize {result_size} "
            f"| Select-Object {select_fields}"
        )
    else:
        raise RuntimeError(
            f"Unknown filter_type '{filter_type}'. "
            "Valid values are: database, type, name"
        )

    try:
        raw = await client.run_cmdlet_with_retry(cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            return {
                "results": [],
                "count": 0,
                "truncated": False,
                "message": f"No mailboxes matched the filter '{filter_value}'.",
            }
        raise

    # Normalize single-result dict vs list
    results = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) and raw else [])

    truncated = len(results) > max_results
    results = results[:max_results]

    if not results:
        return {
            "results": [],
            "count": 0,
            "truncated": False,
            "message": f"No mailboxes matched the filter '{filter_value}'.",
        }

    mailboxes = [
        {
            "display_name": r.get("DisplayName"),
            "email_address": r.get("PrimarySmtpAddress"),
            "mailbox_type": r.get("RecipientTypeDetails"),
            "database": r.get("Database"),
        }
        for r in results
    ]

    result_dict: dict[str, Any] = {
        "results": mailboxes,
        "count": len(mailboxes),
        "truncated": truncated,
    }
    if truncated:
        result_dict["message"] = (
            f"Results capped at {max_results}. Narrow your search to see all matches."
        )
    return result_dict


# ---------------------------------------------------------------------------
# DAG and Database tool handlers (Phase 4)
# ---------------------------------------------------------------------------

async def _list_dag_members_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return DAG server inventory with operational status and database counts."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    dag_name = arguments.get("dag_name", "").strip()
    if not dag_name:
        raise RuntimeError(
            "dag_name is required. Provide the name of the DAG to inspect."
        )
    safe = _escape_ps_single_quote(dag_name)

    # Call 1: DAG metadata — member list, witness info, operational servers
    # -Status switch required for OperationalServers and PrimaryActiveManager
    # Servers property is ADObjectId collection — project via ForEach-Object { $_.Name }
    dag_cmdlet = (
        f"Get-DatabaseAvailabilityGroup -Identity '{safe}' -Status | Select-Object "
        "Name, "
        "@{Name='Members';Expression={@($_.Servers | ForEach-Object { $_.Name })}}, "
        "WitnessServer, WitnessDirectory, "
        "@{Name='OperationalServers';Expression={@($_.OperationalServers | ForEach-Object { $_.Name })}}, "
        "@{Name='PrimaryActiveManager';Expression={$_.PrimaryActiveManager.ToString()}}"
    )

    try:
        dag_raw = await client.run_cmdlet_with_retry(dag_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No DAG found with name '{dag_name}'. "
                "Check the DAG name and try again."
            ) from None
        raise

    # Normalize single-result dict
    dag = dag_raw if isinstance(dag_raw, dict) else (dag_raw[0] if dag_raw else {})

    members = dag.get("Members") or []
    if isinstance(members, str):
        members = [members]  # Single-member DAG returns a string
    operational = dag.get("OperationalServers") or []
    if isinstance(operational, str):
        operational = [operational]
    operational_set = set(operational)

    # Call 2: Per-member enrichment — AD site, Exchange version
    # Call 3: Per-member database counts — mounted vs passive copies
    server_details = []
    for member_name in members:
        safe_member = _escape_ps_single_quote(member_name)

        # Get-ExchangeServer for version and site
        svr_cmdlet = (
            f"Get-ExchangeServer -Identity '{safe_member}' | Select-Object "
            "Name, "
            "@{Name='AdminDisplayVersion';Expression={$_.AdminDisplayVersion.ToString()}}, "
            "@{Name='Site';Expression={$_.Site.ToString()}}, "
            "ServerRole"
        )

        # Get-MailboxDatabaseCopyStatus for database counts
        db_count_cmdlet = (
            f"Get-MailboxDatabaseCopyStatus -Server '{safe_member}' | Select-Object "
            "Status"
        )

        try:
            svr_raw = await client.run_cmdlet_with_retry(svr_cmdlet)
            db_count_raw = await client.run_cmdlet_with_retry(db_count_cmdlet)
        except RuntimeError:
            # Unreachable server — include with error status per CONTEXT.md decision
            server_details.append({
                "name": member_name,
                "operational": member_name in operational_set,
                "site": None,
                "exchange_version": None,
                "server_role": None,
                "active_database_count": None,
                "passive_database_count": None,
                "error": f"Unable to query server '{member_name}'",
            })
            continue

        svr = svr_raw if isinstance(svr_raw, dict) else (svr_raw[0] if svr_raw else {})
        db_copies = db_count_raw if isinstance(db_count_raw, list) else (
            [db_count_raw] if isinstance(db_count_raw, dict) and db_count_raw else []
        )

        active_count = sum(1 for c in db_copies if c.get("Status") == "Mounted")
        passive_count = len(db_copies) - active_count

        server_details.append({
            "name": member_name,
            "operational": member_name in operational_set,
            "site": svr.get("Site"),
            "exchange_version": svr.get("AdminDisplayVersion"),
            "server_role": svr.get("ServerRole"),
            "active_database_count": active_count,
            "passive_database_count": passive_count,
            "error": None,
        })

    return {
        "dag_name": dag.get("Name", dag_name),
        "member_count": len(members),
        "witness_server": dag.get("WitnessServer"),
        "witness_directory": dag.get("WitnessDirectory"),
        "primary_active_manager": dag.get("PrimaryActiveManager"),
        "members": server_details,
    }


async def _get_database_copies_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return all copies of a named database with activation preferences and size."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    database_name = arguments.get("database_name", "").strip()
    if not database_name:
        raise RuntimeError(
            "database_name is required. Provide the name of the mailbox database to inspect."
        )
    safe = _escape_ps_single_quote(database_name)

    # Call 1: Copy status for all copies of the database
    copies_cmdlet = (
        f"Get-MailboxDatabaseCopyStatus -Identity '{safe}' | Select-Object "
        "Name, Status, CopyQueueLength, ReplayQueueLength, "
        "ContentIndexState, LastCopiedLogTime, LastInspectedLogTime, "
        "LastReplayedLogTime, MailboxServer"
    )

    # Call 2: Authoritative activation preferences + database size + mounted info
    # ActivationPreference from Get-MailboxDatabaseCopyStatus is UNRELIABLE (known bug)
    # Get-MailboxDatabase returns ActivationPreference as a dictionary: {ServerName: Preference}
    # -Status switch required for DatabaseSize and Mounted fields
    # ByteQuantifiedSize requires extraction: "553.9 GB (594,718,752,768 bytes)"
    db_cmdlet = (
        f"Get-MailboxDatabase -Identity '{safe}' -Status | Select-Object "
        "Name, Mounted, MountedOnServer, "
        "@{Name='DatabaseSizeBytes';Expression={"
        "[long]($_.DatabaseSize.ToString().Split('(')[1].Split(' ')[0].Replace(',',''))"
        "}}, "
        "@{Name='DatabaseSize';Expression={$_.DatabaseSize.ToString().Split('(')[0].Trim()}}, "
        "ActivationPreference"
    )

    try:
        copies_raw = await client.run_cmdlet_with_retry(copies_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No database found with name '{database_name}'. "
                "Check the database name and try again."
            ) from None
        raise

    try:
        db_raw = await client.run_cmdlet_with_retry(db_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No database found with name '{database_name}'. "
                "Check the database name and try again."
            ) from None
        raise

    # Normalize
    copies = copies_raw if isinstance(copies_raw, list) else (
        [copies_raw] if isinstance(copies_raw, dict) and copies_raw else []
    )
    db_info = db_raw if isinstance(db_raw, dict) else (db_raw[0] if db_raw else {})

    if not copies:
        raise RuntimeError(
            f"No database copies found for '{database_name}'. "
            "The database may not exist or has no copies configured."
        )

    # Build activation preference lookup from Get-MailboxDatabase
    # ActivationPreference serializes as a dict {ServerName: int} or list of key-value pairs
    act_pref_raw = db_info.get("ActivationPreference") or {}
    act_pref_map: dict[str, int] = {}
    if isinstance(act_pref_raw, dict):
        # Direct dict: {"EX01": 1, "EX02": 2}
        act_pref_map = {k: int(v) for k, v in act_pref_raw.items()}
    elif isinstance(act_pref_raw, list):
        # List of dicts: [{"Key": "EX01", "Value": 1}, ...]
        for entry in act_pref_raw:
            if isinstance(entry, dict) and "Key" in entry and "Value" in entry:
                act_pref_map[str(entry["Key"])] = int(entry["Value"])

    copy_details = []
    for c in copies:
        status = c.get("Status", "")
        server = c.get("MailboxServer", "")
        copy_details.append({
            "name": c.get("Name"),
            "server": server,
            "status": status,
            "is_mounted": status == "Mounted",
            "activation_preference": act_pref_map.get(server),
            "copy_queue_length": c.get("CopyQueueLength"),
            "replay_queue_length": c.get("ReplayQueueLength"),
            "content_index_state": c.get("ContentIndexState"),
            "last_copied_log_time": c.get("LastCopiedLogTime"),
            "last_inspected_log_time": c.get("LastInspectedLogTime"),
            "last_replayed_log_time": c.get("LastReplayedLogTime"),
        })

    return {
        "database_name": db_info.get("Name", database_name),
        "database_size": _format_size(db_info.get("DatabaseSizeBytes")),
        "database_size_bytes": db_info.get("DatabaseSizeBytes"),
        "mounted_on_server": db_info.get("MountedOnServer"),
        "copy_count": len(copy_details),
        "copies": copy_details,
    }


async def _get_dag_health_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return replication health report for all database copies in a DAG."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    dag_name = arguments.get("dag_name", "").strip()
    if not dag_name:
        raise RuntimeError(
            "dag_name is required. Provide the name of the DAG to check."
        )
    safe = _escape_ps_single_quote(dag_name)

    # Step 1: Get DAG member list
    # Only need member names — use minimal Select-Object
    dag_cmdlet = (
        f"Get-DatabaseAvailabilityGroup -Identity '{safe}' | Select-Object "
        "@{Name='Members';Expression={@($_.Servers | ForEach-Object { $_.Name })}}"
    )

    try:
        dag_raw = await client.run_cmdlet_with_retry(dag_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "couldn't find" in msg or "could not find" in msg or "object not found" in msg:
            raise RuntimeError(
                f"No DAG found with name '{dag_name}'. "
                "Check the DAG name and try again."
            ) from None
        raise

    dag = dag_raw if isinstance(dag_raw, dict) else (dag_raw[0] if dag_raw else {})
    members = dag.get("Members") or []
    if isinstance(members, str):
        members = [members]

    # Step 2: Per-server replication health (partial results pattern)
    # Each server call is isolated — failures produce error entries, not tool failure
    server_results = []
    for member_name in members:
        safe_member = _escape_ps_single_quote(member_name)

        health_cmdlet = (
            f"Get-MailboxDatabaseCopyStatus -Server '{safe_member}' | Select-Object "
            "Name, Status, CopyQueueLength, ReplayQueueLength, "
            "ContentIndexState, LastCopiedLogTime, LastInspectedLogTime, "
            "LastReplayedLogTime, MailboxServer"
        )

        try:
            health_raw = await client.run_cmdlet_with_retry(health_cmdlet)
        except RuntimeError as exc:
            server_results.append({
                "server": member_name,
                "copies": [],
                "error": f"Unable to query server '{member_name}': {exc}",
            })
            continue

        copies = health_raw if isinstance(health_raw, list) else (
            [health_raw] if isinstance(health_raw, dict) and health_raw else []
        )

        copy_details = []
        for c in copies:
            status = c.get("Status", "")
            copy_details.append({
                "name": c.get("Name"),
                "status": status,
                "is_mounted": status == "Mounted",
                "copy_queue_length": c.get("CopyQueueLength"),
                "replay_queue_length": c.get("ReplayQueueLength"),
                "content_index_state": c.get("ContentIndexState"),
                "last_copied_log_time": c.get("LastCopiedLogTime"),
                "last_inspected_log_time": c.get("LastInspectedLogTime"),
                "last_replayed_log_time": c.get("LastReplayedLogTime"),
            })

        server_results.append({
            "server": member_name,
            "copies": copy_details,
            "error": None,
        })

    return {
        "dag_name": dag_name,
        "member_count": len(members),
        "servers": server_results,
    }


# ---------------------------------------------------------------------------
# Mail flow and security tool handlers (Phase 5)
# ---------------------------------------------------------------------------


async def _check_mail_flow_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Trace routing path between sender and recipient via connector config."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    sender = arguments.get("sender", "").strip()
    recipient = arguments.get("recipient", "").strip()
    if not sender:
        raise RuntimeError(
            "sender is required. Provide the sender's email address."
        )
    if not recipient:
        raise RuntimeError(
            "recipient is required. Provide the recipient's email address."
        )
    _validate_upn(sender)
    _validate_upn(recipient)

    recipient_domain = recipient.split("@")[1].lower()
    sender_domain = sender.split("@")[1].lower()

    # Call 1: Check accepted domains to detect internal routing
    accepted_cmdlet = "Get-AcceptedDomain | Select-Object DomainName, DomainType, Default"

    # Call 2: Send connectors for outbound route matching
    # AddressSpaces, SmartHosts, SourceTransportServers are multi-valued collections
    # -- must use ForEach-Object { $_.ToString() } projection
    send_cmdlet = (
        "Get-SendConnector | Select-Object "
        "Name, Enabled, "
        "@{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}}, "
        "DNSRoutingEnabled, "
        "@{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}, "
        "RequireTLS, TlsDomain, Fqdn, "
        "@{Name='SourceTransportServers';Expression={@($_.SourceTransportServers | ForEach-Object { $_.Name })}}"
    )

    # Call 3: Receive connectors for inbound context
    recv_cmdlet = (
        "Get-ReceiveConnector | Select-Object "
        "Name, Enabled, AuthMechanism, PermissionGroups, RequireTLS, "
        "TransportRole, Server, Fqdn"
    )

    try:
        accepted_raw = await client.run_cmdlet_with_retry(accepted_cmdlet)
        send_raw = await client.run_cmdlet_with_retry(send_cmdlet)
        recv_raw = await client.run_cmdlet_with_retry(recv_cmdlet)
    except RuntimeError:
        raise

    # Normalize results
    accepted_list = accepted_raw if isinstance(accepted_raw, list) else (
        [accepted_raw] if isinstance(accepted_raw, dict) and accepted_raw else []
    )
    send_list = send_raw if isinstance(send_raw, list) else (
        [send_raw] if isinstance(send_raw, dict) and send_raw else []
    )
    recv_list = recv_raw if isinstance(recv_raw, list) else (
        [recv_raw] if isinstance(recv_raw, dict) and recv_raw else []
    )

    # Check if recipient domain is an accepted domain (internal routing)
    accepted_domains = {
        (d.get("DomainName") or "").lower() for d in accepted_list
    }
    is_internal = recipient_domain in accepted_domains
    sender_is_internal = sender_domain in accepted_domains

    # Match send connectors for the recipient domain
    matching_connectors = []
    for conn in send_list:
        if not conn.get("Enabled"):
            continue
        for addr_space in (conn.get("AddressSpaces") or []):
            # AddressSpaces are strings like "SMTP:contoso.com;1" or "SMTP:*;1"
            addr_lower = addr_space.lower()
            # Extract domain portion (before semicolon cost separator)
            addr_domain = addr_lower.split(";")[0]
            # Strip "smtp:" prefix if present
            if ":" in addr_domain:
                addr_domain = addr_domain.split(":", 1)[1]
            addr_domain = addr_domain.strip()

            if (addr_domain == recipient_domain or
                    addr_domain == "*" or
                    (addr_domain.startswith("*.") and
                     recipient_domain.endswith(addr_domain[1:]))):
                matching_connectors.append({
                    "name": conn.get("Name"),
                    "address_spaces": conn.get("AddressSpaces"),
                    "dns_routing_enabled": conn.get("DNSRoutingEnabled"),
                    "smart_hosts": conn.get("SmartHosts"),
                    "require_tls": conn.get("RequireTLS"),
                    "tls_domain": conn.get("TlsDomain"),
                    "fqdn": conn.get("Fqdn"),
                    "source_transport_servers": conn.get("SourceTransportServers"),
                })
                break

    # Build routing summary
    if is_internal:
        routing_type = "internal"
        routing_description = (
            f"Internal delivery: '{recipient_domain}' is an accepted domain. "
            "Mail routes directly to the recipient's mailbox database via SmtpDeliveryToMailbox."
        )
    elif matching_connectors:
        primary = matching_connectors[0]
        if primary.get("smart_hosts"):
            next_hop = f"Smart host(s): {', '.join(primary['smart_hosts'])}"
        elif primary.get("dns_routing_enabled"):
            next_hop = f"DNS routing to {recipient_domain}"
        else:
            next_hop = "Unknown next hop"
        routing_type = "external"
        routing_description = (
            f"Outbound via send connector '{primary['name']}'. "
            f"Next hop: {next_hop}. "
            f"TLS required: {primary.get('require_tls', False)}."
        )
    else:
        routing_type = "unroutable"
        routing_description = (
            f"No send connector matches domain '{recipient_domain}'. "
            "Mail to this domain may be undeliverable."
        )

    return {
        "sender": sender,
        "recipient": recipient,
        "recipient_domain": recipient_domain,
        "sender_domain": sender_domain,
        "sender_is_internal": sender_is_internal,
        "recipient_is_internal": is_internal,
        "routing_type": routing_type,
        "routing_description": routing_description,
        "matching_send_connectors": matching_connectors,
        "matching_connector_count": len(matching_connectors),
        "receive_connectors": [
            {
                "name": r.get("Name"),
                "enabled": r.get("Enabled"),
                "auth_mechanism": r.get("AuthMechanism"),
                "permission_groups": r.get("PermissionGroups"),
                "require_tls": r.get("RequireTLS"),
                "transport_role": r.get("TransportRole"),
                "server": r.get("Server"),
                "fqdn": r.get("Fqdn"),
            }
            for r in recv_list
        ],
        "accepted_domains": sorted(accepted_domains),
    }


async def _get_transport_queues_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return transport queue depths across all servers with backlog flagging."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    server_name = arguments.get("server_name", "").strip()
    threshold = int(arguments.get("backlog_threshold") or 100)

    if server_name:
        # Query single server
        server_names = [server_name]
    else:
        # Discover all transport servers
        ts_cmdlet = "Get-TransportService | Select-Object Name"
        try:
            ts_raw = await client.run_cmdlet_with_retry(ts_cmdlet)
        except RuntimeError:
            raise

        ts_list = ts_raw if isinstance(ts_raw, list) else (
            [ts_raw] if isinstance(ts_raw, dict) and ts_raw else []
        )
        server_names = [s.get("Name") for s in ts_list if s.get("Name")]

    if not server_names:
        return {
            "servers": [],
            "server_count": 0,
            "total_queue_count": 0,
            "total_message_count": 0,
            "backlog_threshold": threshold,
            "servers_with_backlog": [],
        }

    # Per-server queue query (partial results pattern)
    server_results = []
    total_queues = 0
    total_messages = 0
    servers_with_backlog = []

    for sname in server_names:
        safe_server = _escape_ps_single_quote(sname)
        queue_cmdlet = (
            f"Get-Queue -Server '{safe_server}' -ResultSize Unlimited | Select-Object "
            "Identity, MessageCount, DeliveryType, NextHopDomain, "
            "NextHopCategory, Status, LastError, Velocity"
        )

        try:
            q_raw = await client.run_cmdlet_with_retry(queue_cmdlet)
        except RuntimeError as exc:
            server_results.append({
                "server": sname,
                "queues": [],
                "queue_count": 0,
                "total_messages": 0,
                "has_backlog": False,
                "error": f"Unable to query queues on '{sname}': {exc}",
            })
            continue

        queues = q_raw if isinstance(q_raw, list) else (
            [q_raw] if isinstance(q_raw, dict) and q_raw else []
        )

        queue_entries = []
        server_total = 0
        server_has_backlog = False
        for q in queues:
            count = int(q.get("MessageCount") or 0)
            over = count > threshold
            if over:
                server_has_backlog = True
            server_total += count
            queue_entries.append({
                "identity": q.get("Identity"),
                "message_count": count,
                "over_threshold": over,
                "delivery_type": q.get("DeliveryType"),
                "next_hop_domain": q.get("NextHopDomain"),
                "next_hop_category": q.get("NextHopCategory"),
                "status": q.get("Status"),
                "last_error": q.get("LastError"),
                "velocity": q.get("Velocity"),
            })

        total_queues += len(queue_entries)
        total_messages += server_total
        if server_has_backlog:
            servers_with_backlog.append(sname)

        server_results.append({
            "server": sname,
            "queues": queue_entries,
            "queue_count": len(queue_entries),
            "total_messages": server_total,
            "has_backlog": server_has_backlog,
            "error": None,
        })

    return {
        "servers": server_results,
        "server_count": len(server_results),
        "total_queue_count": total_queues,
        "total_message_count": total_messages,
        "backlog_threshold": threshold,
        "servers_with_backlog": servers_with_backlog,
    }


async def _get_smtp_connectors_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return send and/or receive connector inventory with auth and TLS config."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    connector_type = (arguments.get("connector_type") or "all").strip().lower()
    if connector_type not in ("send", "receive", "all"):
        raise RuntimeError(
            f"Invalid connector_type '{connector_type}'. "
            "Valid values are: send, receive, all"
        )

    send_connectors = []
    receive_connectors = []

    if connector_type in ("send", "all"):
        send_cmdlet = (
            "Get-SendConnector | Select-Object "
            "Name, Enabled, "
            "@{Name='AddressSpaces';Expression={@($_.AddressSpaces | ForEach-Object { $_.ToString() })}}, "
            "DNSRoutingEnabled, "
            "@{Name='SmartHosts';Expression={@($_.SmartHosts | ForEach-Object { $_.ToString() })}}, "
            "RequireTLS, TlsDomain, TlsCertificateName, Fqdn, MaxMessageSize, "
            "@{Name='SourceTransportServers';Expression={@($_.SourceTransportServers | ForEach-Object { $_.Name })}}, "
            "CloudServicesMailEnabled, UseExternalDNSServersEnabled"
        )

        try:
            send_raw = await client.run_cmdlet_with_retry(send_cmdlet)
        except RuntimeError:
            raise

        send_list = send_raw if isinstance(send_raw, list) else (
            [send_raw] if isinstance(send_raw, dict) and send_raw else []
        )

        send_connectors = [
            {
                "name": c.get("Name"),
                "enabled": c.get("Enabled"),
                "address_spaces": c.get("AddressSpaces"),
                "dns_routing_enabled": c.get("DNSRoutingEnabled"),
                "smart_hosts": c.get("SmartHosts"),
                "require_tls": c.get("RequireTLS"),
                "tls_domain": c.get("TlsDomain"),
                "tls_certificate_name": c.get("TlsCertificateName"),
                "fqdn": c.get("Fqdn"),
                "max_message_size": str(c.get("MaxMessageSize") or "") if c.get("MaxMessageSize") else None,
                "source_transport_servers": c.get("SourceTransportServers"),
                "cloud_services_mail_enabled": c.get("CloudServicesMailEnabled"),
                "use_external_dns": c.get("UseExternalDNSServersEnabled"),
            }
            for c in send_list
        ]

    if connector_type in ("receive", "all"):
        recv_cmdlet = (
            "Get-ReceiveConnector | Select-Object "
            "Name, Enabled, "
            "@{Name='Bindings';Expression={@($_.Bindings | ForEach-Object { $_.ToString() })}}, "
            "@{Name='RemoteIPRanges';Expression={@($_.RemoteIPRanges | ForEach-Object { $_.ToString() })}}, "
            "AuthMechanism, PermissionGroups, RequireTLS, TlsCertificateName, "
            "TransportRole, Server, Fqdn, MaxMessageSize, MaxRecipientsPerMessage"
        )

        try:
            recv_raw = await client.run_cmdlet_with_retry(recv_cmdlet)
        except RuntimeError:
            raise

        recv_list = recv_raw if isinstance(recv_raw, list) else (
            [recv_raw] if isinstance(recv_raw, dict) and recv_raw else []
        )

        receive_connectors = [
            {
                "name": c.get("Name"),
                "enabled": c.get("Enabled"),
                "bindings": c.get("Bindings"),
                "remote_ip_ranges": c.get("RemoteIPRanges"),
                "auth_mechanism": c.get("AuthMechanism"),
                "permission_groups": c.get("PermissionGroups"),
                "require_tls": c.get("RequireTLS"),
                "tls_certificate_name": c.get("TlsCertificateName"),
                "transport_role": c.get("TransportRole"),
                "server": c.get("Server"),
                "fqdn": c.get("Fqdn"),
                "max_message_size": str(c.get("MaxMessageSize") or "") if c.get("MaxMessageSize") else None,
                "max_recipients_per_message": c.get("MaxRecipientsPerMessage"),
            }
            for c in recv_list
        ]

    result: dict[str, Any] = {"connector_type_filter": connector_type}
    if connector_type in ("send", "all"):
        result["send_connectors"] = send_connectors
        result["send_connector_count"] = len(send_connectors)
    if connector_type in ("receive", "all"):
        result["receive_connectors"] = receive_connectors
        result["receive_connector_count"] = len(receive_connectors)

    return result


async def _get_dkim_config_handler(
    arguments: dict[str, Any], client: ExchangeClient | None
) -> dict[str, Any]:
    """Return DKIM signing config with live DNS CNAME validation."""
    if client is None:
        raise RuntimeError("Exchange client is not available.")

    domain = arguments.get("domain", "").strip().lower()

    if domain:
        safe = _escape_ps_single_quote(domain)
        dkim_cmdlet = (
            f"Get-DkimSigningConfig -Identity '{safe}' | Select-Object "
            "Name, Enabled, Status, Selector1CNAME, Selector2CNAME, "
            "KeyCreationTime, RotateOnDate"
        )
    else:
        dkim_cmdlet = (
            "Get-DkimSigningConfig | Select-Object "
            "Name, Enabled, Status, Selector1CNAME, Selector2CNAME, "
            "KeyCreationTime, RotateOnDate"
        )

    try:
        raw = await client.run_cmdlet_with_retry(dkim_cmdlet)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if domain and ("couldn't find" in msg or "could not find" in msg or "object not found" in msg):
            raise RuntimeError(
                f"No DKIM signing configuration found for domain '{domain}'."
            ) from None
        raise

    configs = raw if isinstance(raw, list) else (
        [raw] if isinstance(raw, dict) and raw else []
    )

    results = []
    for cfg in configs:
        cfg_domain = (cfg.get("Name") or "").lower()
        sel1_expected = cfg.get("Selector1CNAME")
        sel2_expected = cfg.get("Selector2CNAME")

        # DNS CNAME validation
        # _SENTINEL distinguishes "DNS error (unknown)" from "NXDOMAIN/NoAnswer (not published)"
        _SENTINEL = object()
        sel1_published = None
        sel2_published = None
        sel1_match = None
        sel2_match = None

        if cfg_domain:
            sel1_result = _SENTINEL
            sel2_result = _SENTINEL

            try:
                sel1_result = await dns_utils.get_cname_record(
                    f"selector1._domainkey.{cfg_domain}"
                )
            except LookupError:
                pass  # DNS error — leave match as None (unknown)

            try:
                sel2_result = await dns_utils.get_cname_record(
                    f"selector2._domainkey.{cfg_domain}"
                )
            except LookupError:
                pass

            # Only update published/match when DNS call succeeded (not sentinel)
            if sel1_result is not _SENTINEL:
                sel1_published = sel1_result
                if sel1_published is not None and sel1_expected is not None:
                    sel1_match = (
                        sel1_published.lower().rstrip(".")
                        == sel1_expected.lower().rstrip(".")
                    )
                elif sel1_published is None and sel1_expected is not None:
                    sel1_match = False  # Expected but not published

            if sel2_result is not _SENTINEL:
                sel2_published = sel2_result
                if sel2_published is not None and sel2_expected is not None:
                    sel2_match = (
                        sel2_published.lower().rstrip(".")
                        == sel2_expected.lower().rstrip(".")
                    )
                elif sel2_published is None and sel2_expected is not None:
                    sel2_match = False  # Expected but not published

        results.append({
            "domain": cfg_domain,
            "enabled": cfg.get("Enabled"),
            "status": cfg.get("Status"),
            "selector1_cname_expected": sel1_expected,
            "selector1_cname_published": sel1_published,
            "selector1_dns_match": sel1_match,
            "selector2_cname_expected": sel2_expected,
            "selector2_cname_published": sel2_published,
            "selector2_dns_match": sel2_match,
            "key_creation_time": cfg.get("KeyCreationTime"),
            "rotate_on_date": cfg.get("RotateOnDate"),
        })

    return {
        "domains": results,
        "domain_count": len(results),
    }


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------


async def _ping_handler(arguments: dict[str, Any], client: ExchangeClient | None) -> dict[str, Any]:
    """Return a simple pong response to confirm the server is running."""
    return {"status": "pong"}


def _make_stub(tool_name: str):
    """Return an async stub function that raises NotImplementedError for tool_name."""

    async def _stub(arguments: dict[str, Any], client: ExchangeClient | None) -> dict[str, Any]:
        raise NotImplementedError(f"Tool '{tool_name}' is not yet implemented.")

    _stub.__name__ = f"_stub_{tool_name}"
    return _stub


TOOL_DISPATCH: dict[str, Any] = {
    "ping": _ping_handler,
    "get_mailbox_stats": _get_mailbox_stats_handler,
    "search_mailboxes": _search_mailboxes_handler,
    "get_shared_mailbox_owners": _get_shared_mailbox_owners_handler,
    "list_dag_members": _list_dag_members_handler,
    "get_dag_health": _get_dag_health_handler,
    "get_database_copies": _get_database_copies_handler,
    "check_mail_flow": _check_mail_flow_handler,
    "get_transport_queues": _get_transport_queues_handler,
    "get_smtp_connectors": _get_smtp_connectors_handler,
    "get_dkim_config": _get_dkim_config_handler,
    "get_dmarc_status": _make_stub("get_dmarc_status"),
    "check_mobile_devices": _make_stub("check_mobile_devices"),
    "get_hybrid_config": _make_stub("get_hybrid_config"),
    "get_migration_batches": _make_stub("get_migration_batches"),
    "get_connector_status": _make_stub("get_connector_status"),
}
