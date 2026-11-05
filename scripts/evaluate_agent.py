"""Score local-data Agent cases with real Gemini or explicitly scripted offline transport."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


async def evaluate(args):
    from self_improving_ai.agents.portfolio.service import run_portfolio_agent, save_run
    from self_improving_ai.evaluation.portfolio_scoring import score_run
    from self_improving_ai.harness.portfolio_experiment import benchmark_prompt
    cases=json.loads((ROOT/"src/self_improving_ai/evaluation/eval_sets/portfolio/development.json").read_text(encoding="utf-8"))["cases"]
    local=[case for case in cases if all(step["tool"] not in {"get_market_quote","get_external_price_history"} for step in case["steps"])]
    records=[]
    for index,case in enumerate(local):
        if args.mode=="live" and index:
            await asyncio.sleep(getattr(args,"pause_seconds",15))
        prompt,reference=benchmark_prompt(case,42)
        model=None
        if args.mode=="scripted":
            from self_improving_ai.evaluation.scripted_transport import ReplayModel
            model=ReplayModel(steps=reference["steps"],answer_shape=case.get("answer_shape","last_result"))
        run=await run_portfolio_agent(prompt,model=model)
        save_run(run,args.output/"runs")
        records.append({"case_id":case["id"],"reference":reference,"score":score_run(run,reference),"run":run})
        print(json.dumps({"case_id":case["id"],"passed":records[-1]["score"]["passed"],
                          "status":run["status"],"seconds":round(run["elapsed_seconds"],2)}),flush=True)
        if run.get("result",{}).get("error",{}).get("code") in {"MISSING_MODEL_CONFIGURATION","MODEL_RATE_LIMITED"}:
            break
    report={"mode":"adk_scripted_transport_test" if args.mode=="scripted" else "adk_gemini",
            "passed":sum(record["score"]["passed"] for record in records),
            "completed":len(records),"planned":len(local),"records":records,
            "limitation":"Public development suite. Scripted mode verifies dispatch and scoring only; no language quality or learning claim. Free-form explanations are not graded."}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"report.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="records"},indent=2))
    return 0 if report["passed"]==len(local) else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=["live","scripted"],default="live")
    parser.add_argument("--output",type=Path,default=ROOT/"artifacts/live/current/development")
    parser.add_argument("--pause-seconds",type=float,default=15,help="Pause between live cases to reduce free-tier bursts")
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT/".env",override=False)
    from self_improving_ai.connection_store import restore_connections
    restore_connections()
    return asyncio.run(evaluate(args))

if __name__=="__main__":
    raise SystemExit(main())

