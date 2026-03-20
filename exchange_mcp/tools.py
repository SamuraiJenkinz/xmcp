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
                        "Only return queues with message count above this number. "
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
            "Exchange for a domain: whether signing is enabled, selector names, and the "
            "CNAME records needed in DNS. "
            "Use when asked about DKIM signing setup: 'Is DKIM enabled for contoso.com?', "
            "'What are the DKIM selectors?', 'Show DKIM signing config'. "
            "Does NOT check DMARC policy or SPF — use get_dmarc_status for that."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain name to check DKIM configuration for.",
                }
            },
            "required": ["domain"],
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
    "get_dag_health": _make_stub("get_dag_health"),
    "get_database_copies": _make_stub("get_database_copies"),
    "check_mail_flow": _make_stub("check_mail_flow"),
    "get_transport_queues": _make_stub("get_transport_queues"),
    "get_smtp_connectors": _make_stub("get_smtp_connectors"),
    "get_dkim_config": _make_stub("get_dkim_config"),
    "get_dmarc_status": _make_stub("get_dmarc_status"),
    "check_mobile_devices": _make_stub("check_mobile_devices"),
    "get_hybrid_config": _make_stub("get_hybrid_config"),
    "get_migration_batches": _make_stub("get_migration_batches"),
    "get_connector_status": _make_stub("get_connector_status"),
}
