"""Opt-in real Gemini acceptance through the autonomous calendar worker and B service."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))


async def audit(args):
    from self_improving_ai.config import settings
    from self_improving_ai.dashboard.app import create_meeting_brief
    from self_improving_ai.dashboard.calendar import CalendarSimulation, SimulationCommand
    from audit_live_briefing import acceptance_checks

    engine = CalendarSimulation(settings.db_path, create_meeting_brief)
    event = next(event for event in engine.events if event["id"] == args.event)
    # Use the normal 24-hour window just before the selected meeting. Other eligible
    # events can be queued; process exactly one tick and reopen the selected job.
    now = datetime.fromisoformat(event["starts_at"]) - timedelta(minutes=30)
    state = engine.initial()
    state.update(now=now.isoformat(), enabled=True, mode="agent")
    with engine.db() as db:
        db.execute("UPDATE calendar_simulation SET state=? WHERE id=1", (json.dumps(state),))
    ready_before = {job["id"] for job in engine.state()["preparations"] if job["status"] == "ready"}
    started = perf_counter()
    record = {"tested_at_utc": datetime.now(timezone.utc).isoformat(), "event_id": event["id"],
        "execution": "live_gemini_calendar_worker", "model": settings.agent_model, "passed": False}
    try:
        await asyncio.wait_for(engine.tick(), timeout=args.timeout)
        job = next(job for job in engine.state()["preparations"] if job["event_id"] == event["id"])
        record["job"] = job
        if job["status"] == "ready":
            brief = engine.brief(job["id"])
            record["brief"] = brief
            record["checks"] = acceptance_checks(brief, "changed")
            record["checks"]["calendar_saved_draft"] = job["brief_id"] == brief["id"]
            previous = job["id"]
            reopened = await engine.request_event(event["id"])
            record["checks"]["same_event_retained"] = reopened["id"] == previous and reopened["brief_id"] == brief["id"]
            record["passed"] = all(record["checks"].values())
        else:
            record["error"] = job.get("error")
    except Exception as exc:
        record["error_type"] = type(exc).__name__
    record["elapsed_seconds"] = round(perf_counter() - started, 2)
    trace = record.get("brief", {}).get("workflow", {}).get("trace", [])
    record["model_tokens"] = sum(event.get("usage", {}).get("total_token_count") or 0 for event in trace if event.get("event") == "usage")
    record["token_scope"] = "Recorded usage of the selected retained brief"
    record["new_ready_jobs"] = []
    for job in engine.state()["preparations"]:
        if job["status"] == "ready" and job["id"] not in ready_before:
            prepared = engine.brief(job["id"])
            usage = sum(event.get("usage", {}).get("total_token_count") or 0
                for event in prepared["workflow"]["trace"] if event.get("event") == "usage")
            record["new_ready_jobs"].append({"event_id": job["event_id"], "brief_id": job["brief_id"], "recorded_tokens": usage})
    record["new_ready_job_tokens"] = sum(job["recorded_tokens"] for job in record["new_ready_jobs"])
    await engine.command(SimulationCommand(action="pause"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps({key:record[key] for key in ("passed", "elapsed_seconds", "model_tokens")}))
    return int(not record["passed"])


def main():
    from dotenv import load_dotenv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--event", choices=["CAL-004"], default="CAL-004")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/briefing/discovery-calendar-live.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("SIA_DB_PATH"):
        parser.error("Set SIA_DB_PATH to an isolated database; this command changes its fixture clock")
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        parser.error("Configure the ignored root .env with a Gemini API key")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return asyncio.run(audit(args))


if __name__ == "__main__":
    raise SystemExit(main())
