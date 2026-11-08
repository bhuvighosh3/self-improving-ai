"""Direct workspace lookup tools for the orchestrator.

These let the orchestrator answer simple questions (calendar, email, CRM,
client profile, holdings) without delegating to a sub-agent.
"""

from __future__ import annotations

from datetime import datetime, timezone


def get_upcoming_events(client_id: str = "", year: int = 0, month: int = 0) -> dict:
    """Look up calendar events by client or by month.

    Args:
        client_id: Filter events for this client. Leave empty for all.
        year: Calendar year (e.g. 2026). Defaults to the current year.
        month: Calendar month (1-12). Defaults to the current month.

    Returns:
        Dictionary with matching calendar events.
    """
    from self_improving_ai.workspace_store import get_store

    try:
        store = get_store("calendar")
        if client_id:
            events = store.list_events_for_client(client_id)
        else:
            now = datetime.now(timezone.utc)
            year = year or now.year
            month = month or now.month
            events = store.list_events(year, month)
        return {"status": "ok", "events": events, "count": len(events)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def get_recent_emails(client_id: str = "", folder: str = "inbox") -> dict:
    """Look up emails by client or by folder.

    Args:
        client_id: Filter emails for this client. Leave empty for folder view.
        folder: One of inbox, sent, drafts, archive. Defaults to inbox.

    Returns:
        Dictionary with matching emails.
    """
    from self_improving_ai.workspace_store import get_store

    try:
        store = get_store("email")
        if client_id:
            emails = store.list_emails_for_client(client_id)
        else:
            emails = store.list_emails(folder)
        return {"status": "ok", "emails": emails, "count": len(emails)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def get_client_info(client_id: str) -> dict:
    """Return a client's profile: demographics, risk tolerance, goals, and accounts.

    Args:
        client_id: The client household identifier (e.g. CLI-001).

    Returns:
        Dictionary with client profile fields.
    """
    from self_improving_ai.tools.briefing.crm import get_client_profile

    return get_client_profile(client_id)


def get_crm_summary(client_id: str) -> dict:
    """Return CRM summary for a client: notes, last meeting, open tasks.

    Args:
        client_id: The client household identifier.

    Returns:
        Dictionary with CRM notes, context, and tasks.
    """
    from self_improving_ai.tools.briefing.crm import get_crm_notes
    from self_improving_ai.tools.briefing.crm_records import get_crm_context

    notes_result = get_crm_notes(client_id)
    context_result = get_crm_context(client_id)
    if notes_result.get("status") == "error":
        return notes_result
    return {
        "status": "ok",
        "client_id": client_id,
        "notes": notes_result.get("notes", []),
        "previous_meeting": context_result.get("previous_meeting") if context_result.get("status") == "ok" else None,
        "tasks": context_result.get("tasks", []) if context_result.get("status") == "ok" else [],
        "data_as_of": context_result.get("data_as_of") if context_result.get("status") == "ok" else None,
    }


def get_client_holdings(client_id: str, account_id: str = "") -> dict:
    """Return current portfolio holdings for a client.

    Args:
        client_id: The client household identifier.
        account_id: Optional account filter. Returns all accounts if empty.

    Returns:
        Dictionary with holdings and total market value.
    """
    from self_improving_ai.tools.portfolio.holdings import get_holdings

    return get_holdings(client_id, account_id)
