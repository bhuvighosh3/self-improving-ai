"""Build PUBLIC development references independently using stdlib arithmetic/RNG.

Never imports portfolio production functions. These are not hidden tasks.
The two Monte Carlo references use 60000 independent paths and broad fixed
tolerances; exact boundary correctness is covered by analytic pytest cases.
"""
import json
import math
import random
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src/self_improving_ai/evaluation/eval_sets/portfolio/development.json"

def check(path, value, tolerance=1e-8):
    return {"path": path.split("."), "value": value, "tolerance": tolerance}

def step(task, args, checks):
    names = {"holdings":"get_holdings","allocation":"calculate_allocation_drift",
             "risk":"estimate_portfolio_risk","projection":"project_financial_goal",
             "quote":"get_market_quote","history":"get_external_price_history"}
    return {"task":task,"tool":names[task],"arguments":args,"checks":checks}

def projection_reference(initial, stock, years, contribution):
    mu = stock * .06 + (1-stock) * .025
    var = stock**2 * .0324 + (1-stock)**2 * .0036 + 2 * stock * (1-stock) * .00108
    log_var = math.log(1 + var / (1+mu)**2)
    log_mean = math.log(1+mu) - log_var/2
    rng = random.Random(9017)
    values = []
    for _ in range(60000):
        value = initial
        for _ in range(years):
            value *= math.exp(rng.gauss(log_mean, math.sqrt(log_var)))
            value += contribution
        values.append(value)
    return median(values), sum(value >= 2000000 for value in values)/len(values)

def main():
    cases = []
    specs = json.loads((ROOT/"src/self_improving_ai/data/portfolio/portfolio_advisor_cases.json").read_text(encoding="utf-8"))["cases"]
    def add(number, steps, **extra):
        spec = specs[number-1]
        cases.append({"id":spec["case_id"],"split":"development","question":spec["question"],
                      "steps":steps,**extra})
    source = check("source","synthetic_portfolio")
    currency = check("currency","USD")
    add(1,[step("holdings",{"client_id":"CLI-001"},[check("total_market_value",146750),source])])
    add(2,[step("holdings",{"client_id":"CLI-003","account_id":"ACC-003A"},[check("total_market_value",230700),source])])
    quote_checks = [check("price",123.45),check("currency","USD"),check("as_of","2026-09-30"),check("timeliness","unverified"),check("source","twelve_data")]
    add(3,[step("holdings",{"client_id":"CLI-001"},[check("total_market_value",146750)]),
           step("quote",{"symbol":"AAPL"},quote_checks)],provider_fixture="quote")
    add(4,[step("quote",{"symbol":"SPY"},quote_checks)],provider_fixture="quote")
    add(5,[step("history",{"symbol":"AAPL","start_date":"2026-09-01","end_date":"2026-09-30"},
               [check("count",3),check("price_type","split_adjusted_close"),check("currency","USD")])],provider_fixture="history")
    w=117200/146750
    add(6,[step("risk",{"client_id":"CLI-001"},[
        check("annual_expected_return",w*.06+(1-w)*.025),
        check("annual_volatility",math.sqrt(w*w*.0324+(1-w)**2*.0036+2*w*(1-w)*.00108)),
        check("return_unit","decimal_arithmetic_annual"),check("volatility_unit","decimal_annual"),source])])
    comparison=[step("allocation",{"client_id":client},[check("client_id",client),check("asset_classes.stock.current_weight",weight),source])
                for client,weight in [("CLI-003",1.),("CLI-002",30800/142700)]]
    comparison_answer=[]
    for index, item in enumerate(comparison):
        comparison_answer.extend({**c,"path":["results",index,*c["path"]]} for c in item["checks"])
    add(7,comparison,answer_checks=comparison_answer,answer_shape="results_array",steps_ordered=False)
    add(8,[step("allocation",{"client_id":"CLI-001"},[
        check("asset_classes.stock.drift_percentage_points",(117200/146750-.6)*100),
        check("asset_classes.stock.hypothetical_adjustment_usd",-29150),currency,source])])
    add(9,[step("allocation",{"client_id":"CLI-002"},[
        check("asset_classes.stock.drift_percentage_points",(30800/142700-.3)*100),
        check("asset_classes.stock.hypothetical_adjustment_usd",12010),currency,source])])
    for n,client,initial,stock,years,contribution in [
        (10,"CLI-001",146750,117200/146750,15,18000),(11,"CLI-003",312700,1.,8,30000)]:
        mid, probability=projection_reference(initial,stock,years,contribution)
        add(n,[step("projection",{"client_id":client},[
            check("initial_value",initial),check("goal.years",years),check("goal.target_amount",2000000),
            check("goal.annual_contribution",contribution),check("cash_flow_timing","end_of_year"),
            check("ending_value_median",mid,mid*.04),check("success_probability",probability,.015),
            check("review_status","draft_pending_owner_confirmation"),currency,source])])
    add(12,[step("holdings",{"client_id":"CLI-999"},[check("error.code","CLIENT_NOT_FOUND")])])
    add(13,[step("quote",{"symbol":"AAPL,SPY"},[check("error.code","INVALID_SYMBOL")])])
    add(14,[step("history",{"symbol":"AAPL","start_date":"2026-09-30","end_date":"2026-09-01"},
                [check("error.code","INVALID_DATE_RANGE")])])
    add(15,[step("quote",{"symbol":"AAPL"},[check("error.code","MISSING_API_KEY")])],missing_market_key=True)
    cases[7]["steps"][0]["argument_variants"]=[{"client_id":"CLI-001","target_stock_weight":.6}]
    cases[8]["steps"][0]["argument_variants"]=[{"client_id":"CLI-002","target_stock_weight":.3}]
    for case in cases[9:11]:
        item=case["steps"][0]
        years=15 if case["id"]=="A-010" else 8
        item["argument_variants"]=[{**item["arguments"],**extra} for extra in
            ({"years":years},{"target_amount":2000000},{"years":years,"target_amount":2000000})]
    for case in cases:
        optional=[]
        for item in case["steps"]:
            if item["task"] in {"allocation","risk","projection"}:
                optional.append({"tool":"get_holdings","arguments":{"client_id":item["arguments"]["client_id"]}})
        if optional:
            case["optional_calls"]=optional
            case["max_calls"]=len(case["steps"])+len(optional)
    DEST.write_text(json.dumps({"split":"development","reference_method":"Independent stdlib arithmetic and 60000-path random.Random(9017) projection references; never calls production tools.",
         "note":"Public checks, not hidden tasks or evidence of learning. Market responses are fictional offline provider packets.",
         "cases":cases},indent=2),encoding="utf-8")
    print(f"Wrote {len(cases)} public references.")

if __name__ == "__main__":
    main()

