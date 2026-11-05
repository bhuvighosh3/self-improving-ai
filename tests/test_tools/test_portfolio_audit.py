import pytest

from self_improving_ai.tools.portfolio.allocation import calculate_allocation_drift
from self_improving_ai.tools.portfolio.projection import (
    probability_interval,
    project_financial_goal,
    simulate_projection,
)
from self_improving_ai.tools.portfolio.risk import estimate_portfolio_risk


def test_requested_target_overrides_stored_target_without_mutating_it():
    result=calculate_allocation_drift("CLI-002",target_stock_weight=.6)
    assert result["asset_classes"]["stock"]["hypothetical_adjustment_usd"]==54820
    assert result["target_source"]=="request_override"
    assert calculate_allocation_drift("CLI-002")["asset_classes"]["stock"]["target_weight"]==.3


@pytest.mark.parametrize("target",[True,-.1,1.1,float("nan"),"60%"])
def test_invalid_targets(target):
    assert calculate_allocation_drift("CLI-001",target_stock_weight=target)["error"]["code"]=="INVALID_TARGET"


def test_projection_overrides_preserve_explicit_zero_and_original_context():
    run=project_financial_goal("CLI-005",100,7,target_amount=100000,years=1,annual_withdrawal=0)
    assert run["goal"]["annual_withdrawal"]==0
    assert run["goal"]["years"]==1
    assert run["stored_goal"]["annual_withdrawal"]==50400
    assert run["input_sources"]["annual_withdrawal"]=="request_override"
    assert run["input_sources"]["annual_contribution"]=="stored_draft"
    assert project_financial_goal("CLI-005",10)["goal"]["annual_withdrawal"]==50400


@pytest.mark.parametrize("function",[calculate_allocation_drift,estimate_portfolio_risk,project_financial_goal])
def test_dependent_tools_preserve_client_error(function):
    assert function("CLI-999")["error"]["code"]=="CLIENT_NOT_FOUND"


def test_wilson_interval_independent_known_reference():
    interval=probability_interval(50,100)
    assert interval["lower"]==pytest.approx(.4038315303659956)
    assert interval["upper"]==pytest.approx(.5961684696340044)
    assert probability_interval(0,5000)["upper"]>0
    assert probability_interval(5000,5000)["lower"]<1


def test_zero_volatility_has_no_sampling_error():
    result=simulate_projection(100,180,3,20,5,.1,0,1,1)
    assert result["success_probability_interval"]["lower"]==1
    assert result["success_probability_interval"]["upper"]==1


@pytest.mark.parametrize("holding", [{"ticker":"AAPL"},{"market_value":True},{"market_value":float("nan")}])
def test_incomplete_holdings_are_not_treated_as_zero(monkeypatch,holding):
    from self_improving_ai.tools.portfolio import holdings
    monkeypatch.setattr(holdings,"_load_households",lambda:[{"client_id":"CLI-001",
        "accounts":[{"account_id":"x","holdings":[holding]}]}])
    result=holdings.get_holdings("CLI-001")
    assert result["error"]["code"]=="INVALID_HOLDINGS"
    assert "total_market_value" not in result

