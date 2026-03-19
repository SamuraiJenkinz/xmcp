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
    "get_mailbox_stats": _make_stub("get_mailbox_stats"),
    "search_mailboxes": _make_stub("search_mailboxes"),
    "get_shared_mailbox_owners": _make_stub("get_shared_mailbox_owners"),
    "list_dag_members": _make_stub("list_dag_members"),
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
