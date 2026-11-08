"""Mock CRM tools for the briefing agent."""

from __future__ import annotations

from self_improving_ai.client_store import load_households as _load_households


def get_client_profile(client_id: str) -> dict:
    """Return the client profile including demographics, risk tolerance, and goals.

    Args:
        client_id: The client household identifier.

    Returns:
        Dictionary with client profile fields. Some clients have incomplete data.
    """
    for household in _load_households():
        if household.get("client_id") == client_id:
            return household.get("profile", {})
    return {"error": f"Client {client_id} not found"}


def get_crm_notes(client_id: str, limit: int = 10) -> dict:
    """Return recent CRM interaction notes for a client.

    Args:
        client_id: The client household identifier.
        limit: Maximum number of notes to return.

    Returns:
        Dictionary with a list of notes sorted by date descending.
    """
    for household in _load_households():
        if household.get("client_id") == client_id:
            notes = sorted(household.get("crm_notes", []), key=lambda n: n["date"], reverse=True)
            return {"client_id": client_id, "notes": notes[:limit]}
    return {"error": f"Client {client_id} not found"}
