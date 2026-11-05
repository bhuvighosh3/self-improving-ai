"""Annual stock/bond risk from explicit invented assumptions, not live-price inference."""
from __future__ import annotations

import numpy as np

from self_improving_ai.tools.portfolio.allocation import classified_values
from self_improving_ai.tools.portfolio.scenarios import (
    PortfolioInputError,
    failure,
    metadata,
    read_portfolio,
)


def portfolio_statistics(weights, expected_returns, covariance) -> dict:
    if any(isinstance(entry, (bool, np.bool_)) for value in (weights, expected_returns, covariance)
           for entry in np.asarray(value, dtype=object).flat):
        raise ValueError("Booleans are not financial inputs.")
    w, mu, cov = (np.asarray(value, dtype=float) for value in (weights, expected_returns, covariance))
    if (w.ndim != 1 or len(w) == 0 or mu.shape != w.shape or cov.shape != (len(w), len(w))
            or not all(np.all(np.isfinite(value)) for value in (w, mu, cov))
            or np.any(w < 0) or not np.isclose(w.sum(), 1, atol=1e-9, rtol=0)
            or np.any(mu <= -1) or not np.allclose(cov, cov.T, atol=1e-12, rtol=0)):
        raise ValueError("Invalid weights, annual returns or covariance dimensions/symmetry.")
    if np.min(np.linalg.eigvalsh(cov)) < -1e-12:
        raise ValueError("Covariance must be positive semidefinite.")
    return {"annual_expected_return": float(w @ mu),
            "annual_volatility": float(np.sqrt(max(0.0, float(w @ cov @ w)))),
            "return_unit": "decimal_arithmetic_annual", "volatility_unit": "decimal_annual"}


def estimate_portfolio_risk(client_id: str, account_id: str = "") -> dict:
    """Estimate stock/bond return and volatility using draft synthetic assumptions.

    Args:
        client_id: Synthetic household identifier.
        account_id: Optional account filter, empty for all household accounts.
    """
    try:
        values = classified_values(client_id, account_id)
        inputs = read_portfolio("market_assumptions.json")
        classes = inputs["asset_classes"]
        if set(classes) != set(values) or len(classes) != len(values):
            raise ValueError("Asset-class labels do not align.")
        weights = [values[key] / sum(values.values()) for key in classes]
        stats = portfolio_statistics(weights, inputs["annual_expected_returns"],
                                     inputs["annual_covariance"])
        return {"status": "success", **metadata(), "client_id": client_id,
                "account_id": account_id or None, "model_level": inputs["model_level"],
                "weights": dict(zip(classes, weights, strict=True)), **stats}
    except PortfolioInputError as exc:
        return exc.result
    except (OSError, ValueError, TypeError, KeyError, np.linalg.LinAlgError):
        return failure("INVALID_RISK_INPUT", "Check holdings and the draft market assumptions.")
