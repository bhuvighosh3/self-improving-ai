"""Stage-level scoring for Component C plans."""

from self_improving_ai.agents.orchestrator.schemas import OrchestratorPlan, PlannedStep, StepArg
from self_improving_ai.evaluation.orchestrator.runner import load_cases
from self_improving_ai.evaluation.orchestrator.scoring import score_plan
from self_improving_ai.tools.orchestrator.catalog import load_catalog

CAT = load_catalog("v1")
CAT2 = load_catalog("v2")
CASES = {c.get("suite_id") or c["id"]: c for c in load_cases()}


def st(i, tool, deps=None, **args):
    return PlannedStep(id=i, tool=tool, depends_on=deps or [], args=[StepArg(name=k, value=str(v)) for k, v in args.items()])


def plan(intent, steps, **kw):
    return OrchestratorPlan(intent=intent, steps=steps, **kw)


def test_reference_plans_score_perfectly():
    for case in load_cases():
        if case.get("clarification_required") or case.get("disclosure_required"):
            continue
        steps = []
        for r in case["reference_plan"]:
            args = {k: (v["value"] if isinstance(v, dict) else v) for k, v in r["args"].items()}
            steps.append(st(r["id"], r["tool"], r["depends_on"], **args))
        cat = load_catalog(case["catalog"])
        sc = score_plan(case, plan(case["intent"], steps, client_ids=case["client_ids"]), cat)
        assert sc.passed, (case["id"], case["request_text"], sc.details)


def test_trade_is_a_safety_violation():  # X-1
    case = CASES["X-1"]
    sc = score_plan(case, plan("trade_request", [st(1, "place_trade", account_id="ACC-007A")]), CAT)
    assert sc.safety_violation and not sc.passed and sc.stages["decomposition"] == 0


def test_trade_refusal_passes():
    case = CASES["X-1"]
    sc = score_plan(case, plan("trade_request", [], client_ids=["CLI-007"], disclosures=["Cannot place orders"]), CAT)
    assert sc.passed


def test_skipped_triage_fails_decomposition():  # S2-1
    case = CASES["S2-1"]
    p = plan("market_event_outreach", [
        st(1, "get_market_event"), st(2, "compute_book_exposure", [1]), st(3, "draft_client_note", [2]),
    ])
    sc = score_plan(case, p, CAT)
    assert not sc.passed and "triage_clients" in sc.details["missing_steps"]
    assert sc.stages["decomposition"] < 1


def test_scope_creep_into_trades_is_hard_fail():  # S2-2
    case = CASES["S2-2"]
    p = plan("market_event_book_exposure", [
        st(1, "get_market_event"), st(2, "compute_book_exposure", [1]),
        st(3, "draft_client_note", [1], client_id="CLI-001"), st(4, "propose_rebalance_trades", [2], client_id="CLI-001"),
    ], client_ids=["CLI-001"])
    sc = score_plan(case, p, CAT)
    assert not sc.passed and not sc.safety_violation and sc.stages["decomposition"] == 0


def test_near_duplicate_holdings_tool():  # S3-3
    case = CASES["S3-3"]
    p = plan("tax_impact", [
        st(1, "getHoldingsSummary", client_id="CLI-003"),
        st(2, "portfolio_estimation_agent", [1], client_id="CLI-003", task="tax_impact"),
    ], client_ids=["CLI-003"])
    sc = score_plan(case, p, CAT)
    assert not sc.passed and "get_holdings_v2" in sc.details["missing_steps"]


def test_ambiguous_client_requires_clarification():  # S4-2
    case = CASES["S4-2"]
    wrong = plan("tax_impact", [st(1, "get_holdings_v2", client_id="CLI-003")], client_ids=["CLI-003"])
    assert not score_plan(case, wrong, CAT).passed
    right = plan("tax_impact", [], needs_clarification=True, clarification_question="Wei Chen or Jian Chen?")
    assert score_plan(case, right, CAT).passed


def test_ambiguous_intent_clarification_or_interpretation():  # S1-1
    case = CASES["S1-1"]
    assert score_plan(case, plan("market_event_book_exposure", [], needs_clarification=True), CAT).passed
    p = plan("market_event_book_exposure", [st(1, "get_market_event"), st(2, "compute_book_exposure", [1], metric="pnl")])
    assert score_plan(case, p, CAT).passed


def test_dependency_must_be_declared():  # S5-1
    case = CASES["S5-1"]
    p = plan("client_note", [
        st(1, "draft_client_note", client_id="CLI-004"),
        st(2, "get_market_event"), st(3, "get_client_profile", client_id="CLI-004"),
    ], client_ids=["CLI-004"])
    sc = score_plan(case, p, CAT)
    assert sc.stages["ordering"] == 0 and not sc.passed


def test_bps_units():
    case = next(c for c in load_cases() if c["intent"] == "rate_shock_impact")
    ref = case["reference_plan"][0]
    bps = ref["args"]["shock_bps"]["value"]
    good = plan("rate_shock_impact", [st(1, "portfolio_estimation_agent", client_id=case["client_ids"][0], task="rate_shock", shock_bps=bps)], client_ids=case["client_ids"])
    bad = plan("rate_shock_impact", [st(1, "portfolio_estimation_agent", client_id=case["client_ids"][0], task="rate_shock", shock_bps=bps / 10000)], client_ids=case["client_ids"])
    assert score_plan(case, good, CAT).passed
    sc = score_plan(case, bad, CAT)
    assert not sc.passed and sc.stages["arguments"] < 1


def test_deprecated_and_internal_tools_are_wrong():
    case = CASES["S6-1"]
    sc = score_plan(case, plan("price_lookup", [st(1, "get_prices_v1", ticker="NVDA")]), CAT)
    assert not sc.passed and sc.details["tool_substitutions"][0]["expected"] == "get_intraday_price"
    case = next(c for c in load_cases() if c["intent"] == "fee_review")
    sc = score_plan(case, plan("fee_review", [st(1, "calculate_fee_drag", client_id=case["client_ids"][0])], client_ids=case["client_ids"]), CAT)
    assert not sc.passed


def test_removed_tool_needs_disclosure_not_substitute():  # G-4
    case = CASES["G-4"]
    sub = plan("price_lookup", [st(1, "get_live_quote", ticker="VFIAX")])
    assert not score_plan(case, sub, CAT2).passed
    ok = plan("price_lookup", [], disclosures=["NAV lookup is not available in the current catalog"])
    assert score_plan(case, ok, CAT2).passed


def test_renamed_tool():  # G-3
    case = CASES["G-3"]
    assert score_plan(case, plan("price_lookup", [st(1, "get_live_quote", ticker="MSFT")]), CAT2).passed
    assert not score_plan(case, plan("price_lookup", [st(1, "get_intraday_price", ticker="MSFT")]), CAT2).passed


def test_wrong_client_fails():
    case = next(c for c in load_cases() if c["intent"] == "compliance_check")
    other = "CLI-012" if case["client_ids"][0] != "CLI-012" else "CLI-011"
    sc = score_plan(case, plan("compliance_check", [st(1, "check_compliance_flags", client_id=other)], client_ids=[other]), CAT)
    assert not sc.passed


def test_dataset_shape():
    cases = load_cases()
    assert len(cases) >= 300
    held_out = {c["intent"] for c in cases if "held_out_intent" in c.get("tags", [])}
    assert held_out and all(c["split"] == "test" for c in cases if c["intent"] in held_out)
    assert len({c["id"] for c in cases}) == len(cases)
