"""CRM record retrieval tool for meeting prep agent."""

from __future__ import annotations

from self_improving_ai.crm_store import CrmStore
from self_improving_ai.tools.briefing.contracts import tool_error, valid_client_id
from self_improving_ai.tools.briefing.workspace_sources import current_scope, scoped_crm_read


def get_crm_context(client_id: str) -> dict:
    """Return meeting context for a client: previous meeting date and tasks.

    Args:
        client_id: The client household identifier.

    Returns:
        Dictionary with previous_meeting, tasks, data_as_of, holdings_as_of.
    """
    if not valid_client_id(client_id):
        return tool_error("INVALID_ARGUMENT", "client_id must be a nonempty string")
    scope = current_scope()
    if scope and scope["client_id"] != client_id:
        raise ValueError("Client is locked to the operational snapshot")
    ctx = scoped_crm_read("context:" + client_id, lambda: CrmStore().get_client_context(client_id))
    if ctx is None:
        return tool_error("CLIENT_NOT_FOUND", f"No CRM context for {client_id}")
    global_settings = scoped_crm_read("settings", lambda: CrmStore().get_settings())
    return {
        "status": "ok",
        "client_id": client_id,
        "previous_meeting": ctx.get("previous_meeting"),
        "tasks": ctx.get("tasks", []),
        "data_as_of": global_settings.get("data_as_of"),
        "holdings_as_of": global_settings.get("holdings_as_of"),
        "_provenance": {"source": "firestore/crm_context", "synthetic": False, "read_only": True},
    }


def get_crm_records(client_id: str, kind: str | None = None) -> dict:
    """Retrieve CRM source records (minutes, emails, service updates) for a client.

    Args:
        client_id: The client household identifier.
        kind: Optional filter by record kind (minutes, email, service_update, review_confirmation).

    Returns:
        Dictionary with matching CRM records.
    """
    if not valid_client_id(client_id):
        return tool_error("INVALID_ARGUMENT", "client_id must be a nonempty string")
    scope = current_scope()
    if scope and scope["client_id"] != client_id:
        raise ValueError("Client is locked to the operational snapshot")
    records = scoped_crm_read("records:" + client_id, lambda: CrmStore().list_records(client_id))
    if kind:
        records = [r for r in records if r.get("kind") == kind]
    return {
        "status": "ok" if records else "no_results",
        "client_id": client_id,
        "records": records,
        "_provenance": {"source": "firestore/crm_records", "synthetic": False, "read_only": True},
    }
