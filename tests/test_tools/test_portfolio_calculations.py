"""Independent hand/analytic references and critical financial boundaries."""
import io
import math
from http.client import IncompleteRead
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from self_improving_ai.tools.orchestrator.catalog import search_tool_catalog
from self_improving_ai.tools.portfolio import market_data_api as api
from self_improving_ai.tools.portfolio.allocation import calculate_allocation_drift
from self_improving_ai.tools.portfolio.holdings import get_holdings
from self_improving_ai.tools.portfolio.projection import project_financial_goal, simulate_projection
from self_improving_ai.tools.portfolio.risk import estimate_portfolio_risk, portfolio_statistics


def test_garcia_hand_reference_and_cash_conservation():
    result = calculate_allocation_drift("CLI-001")
    assert result["total_market_value"] == 146750
    stock = result["asset_classes"]["stock"]
    assert stock["market_value"] == 117200
    assert stock["drift_percentage_points"] == pytest.approx(19.863713798977855)
    assert stock["hypothetical_adjustment_usd"] == -29150
    assert sum(x["hypothetical_adjustment_usd"] for x in result["asset_classes"].values()) == 0


@pytest.mark.parametrize("client", ["CLI-001", "CLI-002", "CLI-003", "CLI-004", "CLI-005"])
def test_all_clients_calculations_and_draft_labels(client):
    allocation, risk = calculate_allocation_drift(client), estimate_portfolio_risk(client)
    assert allocation["status"] == risk["status"] == "success"
    assert sum(risk["weights"].values()) == pytest.approx(1)
    assert risk["review_status"] == "draft_pending_owner_confirmation"
    assert risk["valuation_date"] is None


def test_invalid_account_never_looks_like_zero_assets():
    result = get_holdings("CLI-001", "ACC-003A")
    assert result["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert "total_market_value" not in result
    assert calculate_allocation_drift("CLI-001", "missing")["status"] == "error"


def test_two_asset_risk_hand_calculation():
    result = portfolio_statistics([.5, .5], [.1, .02], [[.04, 0], [0, .01]])
    assert result["annual_expected_return"] == pytest.approx(.06)
    assert result["annual_volatility"] == pytest.approx(math.sqrt(.0125))


@pytest.mark.parametrize("weights,mu,cov", [
    ([.5, .5], [.1], [[1, 0], [0, 1]]),
    ([.5, .5], [.1, .02], [[1, 2], [2, 1]]),
    ([.5, .5], [.1, .02], [[1, .1], [0, 1]]),
    ([1, 1], [.1, .02], [[1, 0], [0, 1]]),
    ([1], [float("nan")], [[0]]),
])
def test_invalid_covariance_or_weights_rejected(weights, mu, cov):
    with pytest.raises(ValueError):
        portfolio_statistics(weights, mu, cov)


def test_zero_volatility_projection_matches_closed_form():
    # End-year net deposit = 15. 100(1.1)^3 + 15((1.1)^3-1)/.1 = 182.75.
    result = simulate_projection(100, 180, 3, 20, 5, .1, 0, 10, 1)
    assert result["ending_value_median"] == pytest.approx(182.75)
    assert result["success_probability"] == 1


def test_ruin_absorbs_and_does_not_borrow():
    result = simulate_projection(100, 1, 5, 0, 60, 0, 0, 5, 0)
    assert result["ending_value_p90"] == 0
    assert result["success_probability"] == 0
    assert result["depletion_probability"] == 1


def test_seed_reproduction_and_moment_matching():
    args = (100, 100, 1, 0, 0, .1, .2, 50000, 17)
    first = simulate_projection(*args)
    assert first == simulate_projection(*args)
    # Lognormal median = gross mean / sqrt(1 + (gross stdev / mean)^2).
    assert first["ending_value_median"] == pytest.approx(110 / math.sqrt(1 + (.2/1.1)**2), rel=.01)


@pytest.mark.parametrize("count,seed", [(0, 1), (100001, 1), (10, -1), (True, 1)])
def test_projection_invalid_budget(count, seed):
    assert project_financial_goal("CLI-001", count, seed)["status"] == "error"


def test_patel_withdrawals_included():
    result = project_financial_goal("CLI-005", 1000, 42)
    assert result["goal"]["annual_withdrawal"] == 50400
    assert result["ending_value_median"] == 0


def test_truncated_provider_error_body_is_structured(monkeypatch):
    class BrokenBody(io.BytesIO):
        def read(self, *args):
            raise IncompleteRead(b"partial", 10)
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "offline-fake")
    error = HTTPError("https://api.twelvedata.com", 503, "unavailable", {}, BrokenBody())
    with patch.object(api, "urlopen", side_effect=error):
        assert api.get_market_quote("AAPL")["error"]["code"] == "NETWORK_ERROR"


def test_catalog_resolves_packaged_file():
    assert search_tool_catalog("holdings")["matches"]
