"""Opt-in Gemini acceptance audit for B; consumes API quota and saves actual events.

This is a public fixture smoke test, not hidden evaluation or expert certification.
No offline fallback or scripted model is used by this command.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CASES = {
    "changed": ("CLI-004", "Home purchase down payment and funding options", "changed"),
    "unchanged": ("CLI-002", "Interest rates and bond portfolio duration", "unchanged"),
    "missing_history": ("CLI-003", "ARKK tax-loss harvesting and early retirement",
                        "insufficient_information"),
}


def acceptance_checks(brief: dict, expected_status: str) -> dict:
    """Check integration evidence; model quality still requires human assessment."""
    workflow = brief["workflow"]
    history = workflow.get("quality_history", [])
    trace = workflow["trace"]
    located = {hit["id"] for event in trace if event.get("tool") == "search_sources"
               for hit in event.get("result", {}).get("hits", [])}
    read = {event["result"]["record"]["id"] for event in trace
            if event.get("tool") == "read_source" and event.get("result", {}).get("status") == "ok"}
    return {
        "agent_mode": brief["mode"] == "agent",
        "discovery_completed": workflow.get("discovery", {}).get("complete") is True,
        "agent_selected_tools": any(e.get("origin") == "model_selected" and e.get("event") == "tool_execution" for e in trace),
        "six_sections": [s["id"] for s in brief["sections"]] == [
            "overview", "changes", "portfolio", "priorities", "actions", "confirm"],
        "expected_fixture_status": workflow["work"]["change_status"] == expected_status,
        "retrieved_client_context": {"get_client_profile", "get_holdings", "get_crm_notes"}
                                    <= {e.get("tool") for e in trace if "result" in e},
        "searched_updates": any(e.get("tool") == "search_sources" and "result" in e for e in trace),
        "read_all_located_updates": located <= read,
        "calculator_executed": bool(workflow["calculations"]) and any(
            e.get("event") == "tool_response" and e.get("tool") == "calculate_metrics"
            and e.get("result", {}).get("status") == "ok" for e in trace),
        "model_usage_recorded": any(e.get("event") == "usage" for e in trace),
        "objective_pass": bool(history) and history[-1]["objective"]["verdict"] == "pass",
        "independent_reviewer_pass": bool(history) and history[-1]["semantic"]["verdict"] == "pass",
        "reviewer_usage_recorded": any(e.get("event") == "usage"
                                        and e.get("agent") == "meeting_quality_reviewer" for e in trace),
        "client_agenda": bool(workflow["work"]["client_agenda"]),
    }


async def audit(args) -> int:
    from self_improving_ai.agents.briefing.runtime import generate_agent_brief
    from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
    from self_improving_ai.config import settings

    report = {
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": settings.agent_model,
        "reviewer_model": settings.agent_model,
        "discovery_strategy": settings.briefing_discovery,
        "packages": {name: version(name) for name in ("google-adk", "google-genai")},
        "execution": "live_gemini_no_fallback", "records": [],
        "limitation": "Public synthetic fixture acceptance only. Inspect the full brief and source "
                      "support manually. No real calendar trigger, expert sign-off or learning-gain claim.",
    }
    for name in args.case or ["changed"]:
        client, focus, expected = CASES[name]
        trace = []
        record = {"case": name, "client_id": client, "passed": False, "trace": trace}
        started = perf_counter()
        try:
            brief = await asyncio.wait_for(generate_agent_brief(MeetingBriefRequest(
                client_id=client, meeting_date="2026-11-11", meeting_time="14:00",
                focus=f"{focus}. Verify total managed-account value using the sourced calculator.",
                mode="agent"), trace=trace), timeout=args.timeout)
            record["brief"] = brief
            record["checks"] = acceptance_checks(brief, expected)
            record["passed"] = all(record["checks"].values())
        except Exception as exc:
            # Provider exception text may contain request details; retain a safe type only.
            record["error_type"] = type(exc).__name__
            record["run_id"] = getattr(exc, "briefing_run_id", None)
            record["provider_code"] = getattr(exc, "code", None)
            record["error"] = "Live generation failed. Inspect retained events and backend configuration."
        record["elapsed_seconds"] = round(perf_counter() - started, 2)
        record["model_tokens"] = sum(e.get("usage", {}).get("total_token_count") or 0
                                     for e in trace if e.get("event") == "usage")
        report["records"].append(record)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        args.output.chmod(0o600)
        print(json.dumps({key: record[key] for key in (
            "case", "passed", "elapsed_seconds", "model_tokens")}), flush=True)
        if "error_type" in record:
            break
    return int(any(not r["passed"] for r in report["records"]))


def main() -> int:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True,
                        help="Explicitly allow real Gemini requests and API usage")
    parser.add_argument("--case", action="append", choices=sorted(CASES))
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/briefing/live-acceptance.json")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        parser.error("Configure GOOGLE_API_KEY or GEMINI_API_KEY in the ignored root .env first")
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in {"true", "1"}:
        parser.error("This acceptance command uses the Gemini Developer API; set GOOGLE_GENAI_USE_VERTEXAI=FALSE")
    return asyncio.run(audit(args))


if __name__ == "__main__":
    raise SystemExit(main())
