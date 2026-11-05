"""Validate one template lesson from a recorded development failure using live Gemini."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence",type=Path,required=True,
                        help="JSON with run and reference keys from a failed development evaluation")
    parser.add_argument("--feedback",choices=["STALE_PRICE","UNIT_MISMATCH","ACCOUNT_NOT_FOUND"],required=True)
    parser.add_argument("--suite",type=Path,required=True,help="Frozen JSON with disjoint validation/regression cases")
    parser.add_argument("--store",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT/".env",override=False)
    from self_improving_ai.connection_store import restore_connections
    restore_connections()
    from self_improving_ai.evaluation.portfolio_scoring import score_run
    from self_improving_ai.harness.portfolio_experiment import assess_candidate
    from self_improving_ai.harness.strategies.portfolio_lessons import LessonStore
    evidence=json.loads(args.evidence.read_text(encoding="utf-8"))
    run,reference=evidence["run"],evidence["reference"]
    if reference.get("split")!="development" or run.get("mode")!="adk_gemini":
        parser.error("Evidence must come from a real-model development run, never validation/hidden or scripted tests.")
    if run.get("status")!="success" or score_run(run,reference)["passed"]:
        parser.error("Evidence must show a completed but incorrectly answered development task.")
    cases=json.loads(args.suite.read_text(encoding="utf-8"))["cases"]
    store=LessonStore(args.store)
    candidate=store.propose(args.feedback,run["run_id"])
    try:
        report=asyncio.run(assess_candidate(store,candidate,cases,args.output))
    except ValueError as exc:
        print(str(exc))
        return 1
    print(json.dumps({"accepted":report["gate"]["accepted"],"reason":report["gate"]["reason"],
                      "report":str(args.output/"paired_report.json")},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

