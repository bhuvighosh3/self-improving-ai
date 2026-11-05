"""Reproducible nominal-USD projections with end-year cash flows and absorbing ruin."""
from __future__ import annotations

import math

import numpy as np

from self_improving_ai.tools.portfolio.allocation import classified_values
from self_improving_ai.tools.portfolio.risk import estimate_portfolio_risk
from self_improving_ai.tools.portfolio.scenarios import (
    PortfolioInputError,
    client_record,
    failure,
    metadata,
)


def probability_interval(successes: int, count: int) -> dict:
    """95% Wilson interval for finite Monte Carlo sampling, not model uncertainty."""
    z = 1.959963984540054
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    radius = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return {"lower": max(0., center - radius), "upper": min(1., center + radius),
            "level": .95, "method": "Wilson", "scope": "Monte Carlo sampling only; excludes model uncertainty"}


def simulate_projection(initial_value: float, target_amount: float, years: int,
                        annual_contribution: float, annual_withdrawal: float,
                        expected_return: float, annual_volatility: float,
                        num_simulations: int = 5000, seed: int = 42) -> dict:
    amounts = (initial_value, target_amount, annual_contribution, annual_withdrawal,
               expected_return, annual_volatility)
    if any(isinstance(v, bool) or not isinstance(v, (float, int))
           or not math.isfinite(v) for v in amounts):
        raise ValueError("All inputs must be finite numbers.")
    if (initial_value < 0 or target_amount <= 0 or annual_contribution < 0
            or annual_withdrawal < 0 or annual_volatility < 0 or expected_return <= -1):
        raise ValueError("Invalid amount or return.")
    if (type(years) is not int or not 1 <= years <= 120
            or type(num_simulations) is not int or not 1 <= num_simulations <= 100000
            or years * num_simulations > 5000000
            or type(seed) is not int or not 0 <= seed <= 2**32-1):
        raise ValueError("Invalid horizon, simulation budget or seed.")
    # Match the mean and standard deviation of SIMPLE annual returns exactly.
    log_variance = math.log1p((annual_volatility / (1 + expected_return)) ** 2)
    log_mean = math.log1p(expected_return) - log_variance / 2
    rng = np.random.default_rng(seed)
    balances = np.full(num_simulations, float(initial_value))
    depleted = np.zeros(num_simulations, dtype=bool)
    history = []
    with np.errstate(over="raise", invalid="raise"):
        for year in range(1, years + 1):
            growth = np.exp(rng.normal(log_mean, math.sqrt(log_variance), num_simulations))
            balances = np.where(depleted, 0, balances * growth
                                + annual_contribution - annual_withdrawal)
            depleted |= (balances < 0) | ((balances == 0) & (annual_withdrawal > 0))
            balances = np.maximum(balances, 0)
            history.append({"year": year, "median": float(np.median(balances)),
                            "depletion_probability": float(np.mean(depleted))})
    successes = int(np.count_nonzero((balances >= target_amount) & ~depleted))
    interval = probability_interval(successes, num_simulations)
    if annual_volatility == 0:
        interval = {"lower": successes / num_simulations, "upper": successes / num_simulations,
                    "level": .95, "method": "deterministic", "scope": "No sampling error; excludes model uncertainty"}
    return {"success_probability": successes / num_simulations,
            "success_count": successes, "success_probability_interval": interval,
            "ending_value_p10": float(np.quantile(balances, .1)),
            "ending_value_median": float(np.median(balances)),
            "ending_value_p90": float(np.quantile(balances, .9)),
            "depletion_probability": float(np.mean(depleted)), "yearly_summary": history,
            "num_simulations": num_simulations, "seed": seed}


def project_financial_goal(client_id: str, num_simulations: int = 5000, seed: int = 42,
                           target_amount: float | None = None, years: int | None = None,
                           annual_contribution: float | None = None,
                           annual_withdrawal: float | None = None) -> dict:
    """Project a household's draft goal using all fixture accounts and annual cash flows.

    Args:
        client_id: Synthetic household ID. Account access restrictions are not modeled.
        num_simulations: Simulation count, 1 to 100000, at most 5 million path-years.
        seed: Reproducible integer random seed, 0 to 4294967295.
        target_amount: Optional explicit nominal USD goal; omitted uses the draft.
        years: Optional explicit horizon, 1 to 120 whole years.
        annual_contribution: Optional explicit end-year contribution in USD, including zero.
        annual_withdrawal: Optional explicit end-year withdrawal in USD, including zero.
    """
    try:
        initial = sum(classified_values(client_id).values())
        stored_goal = client_record("financial_goals.json", "goals", client_id)
        overrides = {key: value for key, value in {
            "target_amount": target_amount, "years": years,
            "annual_contribution": annual_contribution, "annual_withdrawal": annual_withdrawal,
        }.items() if value is not None}
        goal = {**stored_goal, **overrides}
        risk = estimate_portfolio_risk(client_id)
        if risk["status"] != "success":
            return risk
        result = simulate_projection(initial, goal["target_amount"], goal["years"],
                                     goal["annual_contribution"], goal["annual_withdrawal"],
                                     risk["annual_expected_return"], risk["annual_volatility"],
                                     num_simulations, seed)
        return {"status": "success", **metadata(), "client_id": client_id,
                "initial_value": initial, "goal": goal, "risk_inputs": risk,
                "scenario_source": "request_overrides_with_draft_defaults" if overrides else "stored_draft",
                "scenario_overrides": overrides, "stored_goal": stored_goal,
                "input_sources": {key: "request_override" if key in overrides else "stored_draft"
                                  for key in ("target_amount", "years", "annual_contribution", "annual_withdrawal")},
                "model": "iid annual lognormal gross returns matched to simple-return moments",
                "cash_flow_timing": "end_of_year", "inflation_basis": "nominal",
                "rebalancing_assumption": "constant current fixture stock/bond weights",
                "depletion_rule": "absorbing zero; future contributions do not restart failed paths",
                "success_definition": "no depletion and final balance >= target_amount", **result}
    except PortfolioInputError as exc:
        return exc.result
    except (OSError, ValueError, KeyError, TypeError, OverflowError, FloatingPointError):
        return failure("INVALID_PROJECTION_INPUT", "Check scenario inputs and the simulation budget.")
