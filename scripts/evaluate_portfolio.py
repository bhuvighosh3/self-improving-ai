"""Exercise all 15 handoff cases with actual tools and fully intercepted market IO."""
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from self_improving_ai.agents.portfolio.service import execute_task
from self_improving_ai.evaluation.portfolio_scoring import score_run
from self_improving_ai.tools.portfolio import market_data_api as api


def execute_case(case):
    def transport(request, **kwargs):
        if case.get("provider_fixture") == "quote":
            from urllib.parse import parse_qs, urlparse
            symbol = parse_qs(urlparse(request.full_url).query)["symbol"][0]
            payload={"symbol":symbol,"currency":"USD","datetime":"2026-09-30","close":"123.45",
                     "last_quote_at":1790773200,"is_market_open":False}
        elif case.get("provider_fixture") == "history":
            payload={"meta":{"symbol":"AAPL","currency":"USD"},"status":"ok","values":[
                {"datetime":"2026-09-01","close":"101.25"},{"datetime":"2026-09-02","close":"102"},
                {"datetime":"2026-09-03","close":"103.5"}]}
        else:
            raise AssertionError("Unexpected outbound request in offline development evaluation")
        return io.BytesIO(json.dumps(payload).encode())
    traces=[]
    with patch.dict(os.environ,{"TWELVE_DATA_API_KEY":"" if case.get("missing_market_key") else "offline-test-only"}), patch.object(api,"urlopen",side_effect=transport):
        for step in case["steps"]:
            run=execute_task(step["task"],step["arguments"])
            traces.extend(run["trace"])
    run["trace"]=traces
    run["evaluation_environment"]="offline; provider responses are fictional fixtures"
    return run


def main():
    cases=json.loads((ROOT/"src/self_improving_ai/evaluation/eval_sets/portfolio/development.json").read_text(encoding="utf-8"))["cases"]
    records=[]
    for case in cases:
        run=execute_case(case)
        records.append({"case_id":case["id"],"score":score_run(run,case),"run":run})
    report={"mode":"explicit_tool_development_check","split":"development",
            "passed":sum(item["score"]["passed"] for item in records),"total":len(records),
            "records":records,"limitation":"All 15 handoff tool scenarios; no natural-language, live-provider, hidden-test or learning claim."}
    output=ROOT/"artifacts/reports/development_evaluation.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="records"},indent=2))
    return 0 if report["passed"]==report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

