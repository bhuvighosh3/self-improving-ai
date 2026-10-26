"""Mock CRM tools for the briefing agent."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _load_households() -> list[dict]:
    path = _DATA_DIR / "clients" / "households.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


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
            notes = household.get("crm_notes", [])
            return {"client_id": client_id, "notes": notes[:limit]}
    return {"error": f"Client {client_id} not found"}
