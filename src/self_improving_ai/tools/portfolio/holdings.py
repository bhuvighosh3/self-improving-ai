"""Mock portfolio holdings tools."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_households() -> list[dict]:
    path = _DATA_DIR / "clients" / "households.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def get_holdings(client_id: str, account_id: str = "") -> dict:
    """Return current holdings for a client (optionally filtered by account).

    Args:
        client_id: The client household identifier.
        account_id: Optional account to filter. Returns all accounts if empty.

    Returns:
        Dictionary with account_id, holdings list, and total market value.
    """
    for household in _load_households():
        if household.get("client_id") == client_id:
            accounts = household.get("accounts", [])
            if account_id:
                accounts = [a for a in accounts if a.get("account_id") == account_id]
            return {
                "client_id": client_id,
                "accounts": accounts,
                "total_market_value": sum(
                    h.get("market_value", 0)
                    for a in accounts
                    for h in a.get("holdings", [])
                ),
            }
    return {"error": f"Client {client_id} not found"}
