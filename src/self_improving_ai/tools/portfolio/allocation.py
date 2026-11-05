"""Fixture valuation and hypothetical asset-class rebalancing; no order execution."""
from __future__ import annotations

import math

from self_improving_ai.tools.portfolio.holdings import get_holdings
from self_improving_ai.tools.portfolio.scenarios import (
    PortfolioInputError,
    client_record,
    failure,
    metadata,
    read_portfolio,
)


def classified_values(client_id: str, account_id: str = "") -> dict:
    holdings = get_holdings(client_id, account_id)
    if "error" in holdings:
        raise PortfolioInputError(holdings)
    assets = read_portfolio("asset_class_map.json")["assets"]
    values = {"stock": 0.0, "bond": 0.0}
    for account in holdings["accounts"]:
        for holding in account["holdings"]:
            amount = holding["market_value"]
            if isinstance(amount, bool) or not isinstance(amount, (float, int)):
                raise ValueError("Invalid holding value.")
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("Holdings must have finite nonnegative values.")
            values[assets[holding["ticker"]]["asset_class"]] += amount
    if sum(values.values()) <= 0:
        raise ValueError("A positive portfolio value is required.")
    return values


def calculate_allocation_drift(client_id: str, account_id: str = "",
                               target_stock_weight: float | None = None) -> dict:
    """Compare fixture stock/bond values against the client's draft target.

    Targets are household-wide; an account filter illustrates that same target
    for a selected account and does not imply an approved account mandate.
    Args:
        client_id: Synthetic household ID.
        account_id: Optional account ID; empty aggregates all household accounts.
        target_stock_weight: Optional explicit stock weight as a decimal, e.g. 0.6.
            Bond weight is 1 minus this value. Omit to use the stored draft target.
    """
    try:
        values = classified_values(client_id, account_id)
        target = client_record("target_allocations.json", "allocations", client_id)["weights"]
        if target_stock_weight is not None:
            if (isinstance(target_stock_weight, bool)
                    or not isinstance(target_stock_weight, (int, float))
                    or not math.isfinite(target_stock_weight) or not 0 <= target_stock_weight <= 1):
                return failure("INVALID_TARGET", "Stock target must be a decimal between 0 and 1.")
            target = {"stock": target_stock_weight, "bond": 1 - target_stock_weight}
        if set(target) != set(values) or any(
            isinstance(v, bool) or not isinstance(v, (float, int))
            or not math.isfinite(v) or not 0 <= v <= 1 for v in target.values()
        ) or not math.isclose(sum(target.values()), 1, abs_tol=1e-9, rel_tol=0):
            raise ValueError("Invalid target weights.")
        total = sum(values.values())
        classes = {key: {"market_value": value, "current_weight": value / total,
                         "target_weight": target[key],
                         "drift_percentage_points": (value / total - target[key]) * 100,
                         "hypothetical_adjustment_usd": total * target[key] - value}
                   for key, value in values.items()}
        return {"status": "success", **metadata(), "client_id": client_id,
                "account_id": account_id or None, "total_market_value": total,
                "asset_classes": classes,
                "target_source": "request_override" if target_stock_weight is not None else "stored_draft",
                "target_scope": "selected_account" if account_id else "client_all_accounts",
                "account_target_is_illustrative": bool(account_id),
                "adjustment_convention": "positive=add; negative=reduce; asset-class amounts only"}
    except PortfolioInputError as exc:
        return exc.result
    except (OSError, ValueError, KeyError, TypeError):
        return failure("INVALID_PORTFOLIO", "Check the client, account, holdings and target scenario.")
