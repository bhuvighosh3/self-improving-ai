"""Versioned, explicitly synthetic scenario inputs shared by portfolio tools."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"


class PortfolioInputError(ValueError):
    """Preserve an actionable input error across dependent calculations."""

    def __init__(self, result: dict):
        self.result = result
        super().__init__(result["error"]["message"])


def failure(code: str, message: str) -> dict:
    return {"status": "error", "source": "synthetic_portfolio",
            "error": {"code": code, "message": message, "retryable": False}}


def read_portfolio(name: str) -> dict:
    return json.loads((DATA / "portfolio" / name).read_text(encoding="utf-8"))


def client_record(name: str, key: str, client_id: str) -> dict:
    doc = read_portfolio(name)
    for record in doc[key]:
        if record["client_id"] == client_id:
            return record
    raise ValueError(f"No {key} scenario for client {client_id}.")


def metadata() -> dict:
    assumptions = read_portfolio("market_assumptions.json")
    return {
        "source": "synthetic_portfolio", "currency": "USD",
        "valuation_basis": "sum_of_fixture_market_value",
        "valuation_date": None,
        "assumptions_version": assumptions["version"],
        "review_status": assumptions["review_status"],
        "warnings": [
            "Synthetic demonstration; target and market assumptions are unapproved draft inputs.",
            "Fixture valuation date is unspecified; live quotes do not revalue these holdings.",
            "Stock/bond model excludes security-specific risk, taxes, fees and account restrictions.",
        ],
    }


def get_portfolio_scenarios(client_id: str) -> dict:
    """Read draft targets, goals and invented market assumptions for a synthetic client.

    Args:
        client_id: Household identifier such as CLI-001.
    """
    try:
        return {"status": "success", "client_id": client_id, **metadata(),
                "target": client_record("target_allocations.json", "allocations", client_id),
                "goal": client_record("financial_goals.json", "goals", client_id),
                "market_assumptions": read_portfolio("market_assumptions.json")}
    except (OSError, ValueError, KeyError, TypeError):
        return failure("SCENARIO_UNAVAILABLE", "Could not load the requested client scenario.")
