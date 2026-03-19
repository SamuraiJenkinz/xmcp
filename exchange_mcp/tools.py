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
            "Returns size, item count, quota limits, and last logon time for a single "
            "Exchange Online mailbox. "
            "Use when asked about how full a mailbox is, how many emails a user has, "
            "when someone last logged into their mailbox, or whether a user is near "
            "their quota."
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
            "Searches Exchange Online mailboxes using a filter and returns matching "
            "mailbox names, addresses, and types. "
            "Use when asked to find all mailboxes of a certain type, search by display "
            "name, or look up mailboxes stored in a specific database."
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
            "Returns the list of users who have full-access permissions on a shared "
            "mailbox, along with their permission type. "
            "Use when asked who owns or has access to a shared mailbox, who manages a "
            "team inbox, or who can read a distribution email address."
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
            "Lists the servers that belong to a Database Availability Group (DAG), "
            "including each server's operational status. "
            "Use when asked which servers are in a DAG, how many nodes a DAG has, "
            "or to get an overview of all DAGs in the environment."
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
            "Returns the health status of a Database Availability Group (DAG), "
            "including replication state, operational servers, and any active alerts. "
            "Use when asked whether a DAG is healthy, if replication is working, or "
            "to diagnose DAG-related failures."
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
            "Returns the copies of a specific mailbox database across DAG members, "
            "including each copy's activation preference, queue length, and status. "
            "Use when asked about database replication, which server hosts the active "
            "copy, or how many copies exist for a database."
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
            "Tests whether email can flow between a sender and recipient by tracing "
            "the routing path and checking for delivery restrictions. "
            "Use when asked if someone can send email to another person, why emails "
            "are being blocked, or to verify mail routing between two addresses."
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
            "Returns the current state of transport queues on Exchange servers, "
            "including message backlog counts and queue types. "
            "Use when asked if there is a mail backlog, whether emails are stuck, "
            "or to check queue depth on a specific server."
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
            "Returns the Send and/or Receive connectors configured in Exchange, "
            "including their address spaces, permissions, and enabled status. "
            "Use when asked what SMTP connectors are configured, how outbound email "
            "is routed, or what relays are permitted."
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
            "Returns the DKIM (DomainKeys Identified Mail) signing configuration for "
            "a domain, including whether it is enabled and the selector details. "
            "Use when asked if DKIM is set up, whether email signing is active, "
            "or to check DKIM selectors for a domain."
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
            "Returns the DMARC (Domain-based Message Authentication) policy and "
            "alignment status for a domain. "
            "Use when asked about email authentication policy, whether DMARC is "
            "enforced, or what happens to emails that fail SPF/DKIM checks."
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
            "Returns the mobile devices (phones and tablets) that have synced with "
            "a user's mailbox via ActiveSync or Outlook mobile, including device type "
            "and last sync time. "
            "Use when asked what devices a user has connected, when a phone last "
            "synced, or to audit mobile access for a mailbox."
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
            "Returns the Exchange Hybrid configuration, including the hybrid connector "
            "settings and the on-premises/cloud relationship details. "
            "Use when asked about hybrid Exchange setup, how on-premises and cloud are "
            "connected, or to verify the hybrid wizard configuration."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    types.Tool(
        name="get_migration_batches",
        description=(
            "Returns the current mailbox migration batches, including their status, "
            "progress, and any errors. "
            "Use when asked how many users have been migrated, whether a migration "
            "batch is running, or to check the status of a specific migration."
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
            "Returns the status of Exchange hybrid connectors, including inbound and "
            "outbound connector health and recent activity. "
            "Use when asked whether hybrid connectors are working, if mail is flowing "
            "between on-premises and cloud, or to check connector health."
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
