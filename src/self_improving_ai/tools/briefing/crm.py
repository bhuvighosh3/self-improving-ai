"""Mock CRM tools for the briefing agent."""

from __future__ import annotations

import json
from pathlib import Path

from self_improving_ai.tools.briefing.contracts import provenance, tool_error, valid_client_id, valid_limit

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_households() -> list[dict]:
    path = _DATA_DIR / "clients" / "households.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_client_profile(client_id: str) -> dict:
    """Return the client profile including demographics, risk tolerance, and goals.

    Args:
        client_id: The client household identifier.

    Returns:
        Dictionary with client profile fields. Some clients have incomplete data.
    """
    if not valid_client_id(client_id):
        return tool_error("INVALID_ARGUMENT", "client_id must be a nonempty string")
    try:
        households = _load_households()
        metadata = provenance("clients/households.json", _DATA_DIR)
    except (OSError, ValueError, KeyError):
        return tool_error("DATA_UNAVAILABLE", "Client fixture data is unavailable")
    for household in households:
        if household.get("client_id") == client_id:
            return {**household.get("profile", {}), "_provenance": metadata}
    return tool_error("CLIENT_NOT_FOUND", f"Client {client_id} not found")


def get_crm_notes(client_id: str, limit: int = 10) -> dict:
    """Return recent CRM interaction notes for a client.

    Args:
        client_id: The client household identifier.
        limit: Maximum number of notes to return.

    Returns:
        Dictionary with a list of notes sorted by date descending.
    """
    if not valid_client_id(client_id) or not valid_limit(limit):
        return tool_error("INVALID_ARGUMENT", "Provide a client_id and an integer limit from 0 to 100")
    try:
        households = _load_households()
        metadata = provenance("clients/households.json", _DATA_DIR)
    except (OSError, ValueError, KeyError):
        return tool_error("DATA_UNAVAILABLE", "CRM fixture data is unavailable")
    for household in households:
        if household.get("client_id") == client_id:
            notes = sorted((note for note in household.get("crm_notes", [])
                            if note["date"] <= metadata["as_of"]
                            and note.get("recorded_at", note["date"])[:10] <= metadata["as_of"]),
                           key=lambda note: note["date"], reverse=True)
            return {"status": "ok", "client_id": client_id, "notes": notes[:limit],
                    "total_available": len(notes), "truncated": len(notes) > limit,
                    "_provenance": metadata}
    return tool_error("CLIENT_NOT_FOUND", f"Client {client_id} not found")
