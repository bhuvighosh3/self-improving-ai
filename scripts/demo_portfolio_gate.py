"""Offline failure-to-rejection demonstration; never claims learned improvement."""
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


async def main():
    from self_improving_ai.agents.portfolio.service import run_portfolio_agent, save_run
    from self_improving_ai.evaluation.portfolio_scoring import score_run
    from self_improving_ai.evaluation.scripted_transport import ReplayModel
    from self_improving_ai.harness.portfolio_experiment import assess_candidate, benchmark_prompt
    from self_improving_ai.harness.strategies.portfolio_lessons import LessonStore
    cases=json.loads((ROOT/"src/self_improving_ai/evaluation/eval_sets/portfolio/development.json").read_text(encoding="utf-8"))["cases"]
    output=ROOT/"artifacts/gate_demo"/uuid4().hex
    observed=cases[7]
    prompt,reference=benchmark_prompt(observed,42)
    run=await run_portfolio_agent(prompt,model=ReplayModel(steps=reference["steps"],inject_wrong_currency=True))
    save_run(run,output/"runs")
    score=score_run(run,reference)
    if score["passed"] or not score["outcome_correct"]:
        raise RuntimeError("The demonstration must expose a final-answer unit error after a correct tool result.")
    observation={"run":run,"reference":reference,"score":score,"fault_injection":"Scripted transport changes final currency to EUR."}
    (output/"observed_failure.json").write_text(json.dumps(observation,indent=2),encoding="utf-8")
    store=LessonStore(output/"lessons.json")
    candidate=store.propose("UNIT_MISMATCH",run["run_id"])
    suite=[{**cases[8],"split":"validation"},{**cases[0],"split":"regression"}]
    def factory(case,seed):
        _,item=benchmark_prompt(case,seed)
        return ReplayModel(steps=item["steps"])
    report=await assess_candidate(store,candidate,suite,output,model_factory=factory)
    if report["gate"]["accepted"]:
        raise RuntimeError("Identical before/after execution must not show an improvement.")
    index={"report":str(output/"paired_report.json"),"observation":str(output/"observed_failure.json"),
           "accepted":False,"reason":report["gate"]["reason"],"paired_records":len(report["records"]),
           "limitation":"Public cases reused for plumbing demonstration only. Scripted model ignores lessons; rejection is expected, not evidence of learned improvement."}
    (ROOT/"artifacts/gate_demo/latest.json").write_text(json.dumps(index,indent=2),encoding="utf-8")
    print(json.dumps(index,indent=2))

if __name__=="__main__":
    asyncio.run(main())

