"""Opt-in live acceptance cases. Uses locally saved credentials; writes no keys.

This consumes model/market API quota. It is a public acceptance audit, not hidden
research evaluation. Natural-language explanations also need human review.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def cases():
    return [
        ("name_only_chinese", "请用中文说明 Garcia Family 当前配置与草案 60/40 目标的偏离，并说明数据与假设。",
         "calculate_allocation_drift", {"client_id":"CLI-001"}, [("total_market_value",146750)]),
        ("comparison_identity", "Compare Chen Household's stock concentration with Thompson Trust. Return JSON with a results array of the full allocation tool objects in that order.",
         "comparison", {}, []),
        ("explicit_target", "For Thompson Trust CLI-002, use a hypothetical 60% stock and 40% bond target, not its stored target. Show the class adjustments.",
         "calculate_allocation_drift", {"client_id":"CLI-002","target_stock_weight":.6}, [("asset_classes.stock.hypothetical_adjustment_usd",54820)]),
        ("zero_cashflow", "For Patel CLI-005, project a $100,000 target over 1 year. Set annual withdrawals to exactly zero and annual contributions to exactly zero. Use 5000 paths and seed 42; explain the overrides.",
         "project_financial_goal", {"client_id":"CLI-005","years":1,"target_amount":100000,"annual_withdrawal":0,"annual_contribution":0}, [("goal.annual_withdrawal",0),("goal.annual_contribution",0),("goal.years",1)]),
        ("invalid_account", "Show Garcia CLI-001 holdings for account ACC-NOT-FOUND. Do not substitute a different account.",
         "get_holdings", {"client_id":"CLI-001","account_id":"ACC-NOT-FOUND"}, [("error.code","ACCOUNT_NOT_FOUND")]),
        ("conflicting_identity", "Calculate allocation for Chen Household, client CLI-002.", "no_financial_call", {}, []),
        ("ambiguous_client", "What is my client's expected portfolio return?", "no_financial_call", {}, []),
        ("unsupported_account_goal", "For Chen CLI-003 project ONLY account ACC-003A toward $2M in 8 years. Do not include any other accounts.", "no_projection", {}, []),
        ("scenario_inspection", "Show the stored draft goal, stock/bond targets and market assumptions for Okafor CLI-004. Do not run projections.",
         "get_portfolio_scenarios", {"client_id":"CLI-004"}, [("client_id","CLI-004"),("review_status","draft_pending_owner_confirmation")]),
        ("live_quote", "Get the latest available AAPL quote from the external provider. State date, currency, source and whether real-time status is verified.",
         "get_market_quote", {"symbol":"AAPL"}, [("source","twelve_data"),("timeliness","unverified")]),
        ("live_history", "Get SPY daily history from 2026-10-26 through 2026-10-30 inclusive. State whether these prices include reinvested dividends.",
         "get_external_price_history", {"symbol":"SPY","start_date":"2026-10-26","end_date":"2026-10-30"}, [("source","twelve_data"),("price_type","split_adjusted_close"),("data_end","2026-10-30")]),
        ("fixture_and_live_separate", "Show Garcia CLI-001's total fixture portfolio value and separately the latest AAPL external quote. Do not revalue the portfolio with that quote.",
         "combined", {}, []),
    ]


def value_at(value, path):
    for key in path.split("."):
        value=value[key]
    return value


def assess(run, kind, arguments, values):
    from self_improving_ai.evaluation.portfolio_scoring import bound_executions
    executions=bound_executions(run["trace"])
    checks={"execution_success":run["status"]=="success","nonempty_answer":bool(run["response"].strip())}
    if kind in {"no_financial_call","no_projection"}:
        checks["scope_respected"]=not any(entry["tool"] in (
            {"get_holdings","calculate_allocation_drift","estimate_portfolio_risk","project_financial_goal"}
            if kind=="no_financial_call" else {"project_financial_goal"}) for entry in executions)
    elif kind=="comparison":
        try:
            answer=json.loads(run["response"])["results"]
            checks["client_order"]=[row["client_id"] for row in answer]==["CLI-003","CLI-002"]
            checks["correct_concentrations"]=abs(answer[0]["asset_classes"]["stock"]["current_weight"]-1)<1e-8 and abs(answer[1]["asset_classes"]["stock"]["current_weight"]-30800/142700)<1e-8
            checks["both_tools_executed"]={entry["arguments"].get("client_id") for entry in executions if entry["tool"]=="calculate_allocation_drift"}=={"CLI-003","CLI-002"}
        except (KeyError,IndexError,TypeError,ValueError):
            checks["valid_comparison"]=False
    elif kind=="combined":
        checks["fixture_unchanged"]=any(entry["tool"]=="get_holdings" and entry["result"].get("total_market_value")==146750 for entry in executions)
        checks["separate_external_quote"]=any(entry["tool"]=="get_market_quote" and entry["result"].get("source")=="twelve_data" and entry["result"].get("status")=="success" for entry in executions)
    else:
        matched=[entry for entry in executions if entry["tool"]==kind and all(entry["arguments"].get(key)==value for key,value in arguments.items())]
        checks["tool_and_arguments"]=bool(matched)
        for path,expected in values:
            try:
                checks[path]=bool(matched) and value_at(matched[-1]["result"],path)==expected
            except (KeyError,TypeError):
                checks[path]=False
    return checks


async def audit(args):
    from self_improving_ai.agents.portfolio.service import run_portfolio_agent
    from self_improving_ai.config import settings
    settings.portfolio_model=args.model  # This process only; no saved setting changes.
    records=[]
    selected=[case for case in cases() if not args.case or case[0] in args.case]
    for index,(name,prompt,kind,arguments,values) in enumerate(selected):
        if index:
            await asyncio.sleep(args.pause)
        run=await run_portfolio_agent(prompt)
        checks=assess(run,kind,arguments,values)
        records.append({"case":name,"checks":checks,"passed":all(checks.values()),"run":run})
        report={"tested_at_utc":datetime.now(timezone.utc).isoformat(),"model":args.model,
                "passed":sum(record["passed"] for record in records),"total":len(records),
                "model_tokens":sum(record["run"]["model_tokens"] for record in records),
                "records":records,"limitation":"Public acceptance cases. Checks cover actual tools and selected fields; prose is reviewed separately. No hidden-task or learning-gain claim."}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"case":name,"passed":all(checks.values()),"checks":checks,"seconds":round(run["elapsed_seconds"],2),"error":run.get("result",{}).get("error")}),flush=True)
    return int(any(not record["passed"] for record in records))


def main():
    from dotenv import load_dotenv

    from self_improving_ai.connection_store import restore_connections
    load_dotenv(ROOT/".env",override=False)
    restore_connections()
    from self_improving_ai.agents.portfolio.model_catalog import FREE_TIER_MODEL_IDS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",choices=sorted(FREE_TIER_MODEL_IDS),default="gemini-3.5-flash-lite")
    parser.add_argument("--case",action="append",choices=[case[0] for case in cases()])
    parser.add_argument("--pause",type=float,default=6,help="Seconds between requests")
    parser.add_argument("--output",type=Path,default=ROOT/"artifacts/live/current/acceptance.json")
    args=parser.parse_args()
    logging.disable(logging.CRITICAL)
    return asyncio.run(audit(args))


if __name__=="__main__":
    raise SystemExit(main())
