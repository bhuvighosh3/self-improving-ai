"""Mock portfolio holdings tools."""

from __future__ import annotations

import math

from self_improving_ai.client_store import load_households as _load_households


def get_holdings(client_id: str, account_id: str = "") -> dict:
    """Return current holdings for a client (optionally filtered by account).

    Args:
        client_id: The client household identifier.
        account_id: Optional account to filter. Returns all accounts if empty.

    Returns:
        Dictionary with account_id, holdings list, and total market value.
    """
    try:
        households = _load_households()
    except (OSError, ValueError):
        return {"status":"error", "error":{"code":"HOLDINGS_UNAVAILABLE",
                "message":"Could not load the holdings fixture.","retryable":False}}
    for household in households:
        if household.get("client_id") == client_id:
            accounts = household.get("accounts", [])
            if account_id:
                accounts = [a for a in accounts if a.get("account_id") == account_id]
                if not accounts:
                    return {"status": "error", "error": {"code": "ACCOUNT_NOT_FOUND",
                            "message": "Account does not belong to this client.", "retryable": False}}
            try:
                amounts = [h["market_value"] for a in accounts for h in a["holdings"]]
                if not amounts or any(isinstance(value, bool) or not isinstance(value, (int,float))
                                      or not math.isfinite(value) or value < 0 for value in amounts):
                    raise ValueError("Invalid fixture values")
                total = sum(amounts)
                if not math.isfinite(total):
                    raise ValueError("Invalid fixture total")
            except (KeyError, TypeError, ValueError):
                return {"status":"error", "error":{"code":"INVALID_HOLDINGS",
                        "message":"Holdings need explicit finite nonnegative market values.","retryable":False}}
            return {
                "status": "success", "source": "synthetic_portfolio",
                "currency": "USD",
                "valuation_basis": "sum_of_fixture_market_value", "valuation_date": None,
                "client_id": client_id,
                "client_name": household.get("profile", {}).get("name"),
                "accounts": accounts,
                "total_market_value": total,
            }
    return {"status": "error", "error": {"code": "CLIENT_NOT_FOUND",
            "message": "Client not found.", "retryable": False}}
