"""Run golden questions through the live copilot and save traces, scores and a report."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from self_improving_ai.evaluation.copilot.scoring import STAGES, score_case, summarize

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "data/orchestrator/golden_copilot.json"


def load_golden(path: Path = GOLDEN_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def calendar_lookup(client_id: str) -> list:
    """Ground truth for next_event facts. Reads all events and filters here, because the
    Firestore query by client_id ordered by date needs a composite index the project lacks."""
    from self_improving_ai.workspace_store import get_store
    store = get_store("calendar")
    if hasattr(store, "collection"):
        return [{**d.to_dict(), "id": d.id} for d in store.collection.get()
                if (d.to_dict() or {}).get("client_id") == client_id]
    return store.list_events_for_client(client_id)


def build_runner():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from self_improving_ai.agents.orchestrator.agent import orchestrator

    return Runner(app_name=orchestrator.name, agent=orchestrator, session_service=InMemorySessionService())


async def run_one(runner, case: dict, timeout_s: float) -> dict:
    """One fresh session per question, like a new advisor chat."""
    from self_improving_ai.agents.briefing.application import briefing_request_scope
    from self_improving_ai.agents.orchestrator.runtime import run_copilot

    user_id, session_id = "golden-eval", f"golden-{case['id']}-{uuid.uuid4().hex[:8]}"
    await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
    start = time.monotonic()
    for attempt in (1, 2):
        try:
            with briefing_request_scope(None):
                result = await asyncio.wait_for(
                    run_copilot(runner=runner, message=case["question"], session_id=session_id, user_id=user_id),
                    timeout=timeout_s)
            result["error"] = None
            break
        except Exception as exc:  # a failed run is a result, not a crash
            result = {"steps": [], "response_parts": [], "error": f"{type(exc).__name__}: {exc}"[:500]}
            transient = any(code in str(exc) for code in ("429", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE"))
            if attempt == 2 or not transient:
                break
            # Retry once in a fresh session after a provider hiccup; it says nothing about the copilot.
            session_id = f"{session_id}-retry"
            await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
            await asyncio.sleep(10)
    result["seconds"] = round(time.monotonic() - start, 1)
    return result


async def run_golden(cases: list[dict], out_dir: Path, *, concurrency: int = 2, timeout_s: float = 300,
                     runner=None, events_for=calendar_lookup, today: date | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = runner or build_runner()
    today = today or date.today()
    gate = asyncio.Semaphore(concurrency)
    traces: dict[str, dict] = {}

    raw = open(out_dir / "raw_runs.jsonl", "w", encoding="utf-8")

    async def go(case):
        async with gate:
            traces[case["id"]] = await run_one(runner, case, timeout_s)
            r = traces[case["id"]]
            # Saved as soon as each question finishes, so a later failure cannot lose the run.
            raw.write(json.dumps({"id": case["id"], "run": r}, default=str) + "\n")
            raw.flush()
            print(f"  {case['id']} {r['seconds']:>6}s {'ERROR ' + r['error'] if r['error'] else 'done'}", flush=True)

    try:
        await asyncio.gather(*(go(c) for c in cases))
    finally:
        raw.close()

    scores = []
    with open(out_dir / "traces.jsonl", "w", encoding="utf-8") as fh:
        for case in cases:
            run = traces[case["id"]]
            sc = score_case(case, run, events_for=events_for, today=today)
            if run["error"]:
                sc.notes.append(f"run error: {run['error']}")
            scores.append(sc)
            fh.write(json.dumps({"case": case, "run": run, "score": sc.to_dict()}, default=str) + "\n")

    summary = summarize(scores)
    summary.update({"run_date": today.isoformat(), "created": datetime.now().isoformat(timespec="seconds"),
                    "median_seconds": sorted(traces[c["id"]]["seconds"] for c in cases)[len(cases) // 2],
                    "errors": sum(1 for c in cases if traces[c["id"]]["error"])})
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_report(cases, scores, traces, summary), encoding="utf-8")
    return summary


def render_report(cases, scores, traces, summary) -> str:
    pct = lambda x: f"{100 * x:.0f}%"
    lines = [f"# Copilot golden-set results ({summary['run_date']})", "",
             f"**{sum(s.passed for s in scores)}/{len(scores)} passed** "
             f"(plan correct on {sum(s.plan_passed for s in scores)}). "
             f"Median time {summary['median_seconds']} s, {summary['errors']} run errors.", "",
             "## By stage", "", "| " + " | ".join(STAGES) + " |", "|" + "---|" * len(STAGES),
             "| " + " | ".join(pct(summary["stages"][k]) for k in STAGES) + " |", "",
             "## By category", "", "| Category | Cases | Pass |", "|---|---|---|"]
    lines += [f"| {c} | {v['cases']} | {pct(v['pass_rate'])} |" for c, v in summary["by_category"].items()]
    lines += ["", "## Cases", "", "| ID | Question | Pass | Calls | Time | What went wrong |", "|---|---|---|---|---|---|"]
    for case, sc in zip(cases, scores):
        problems = "; ".join(sc.notes + [f"missing fact: {m}" for m in sc.missing_facts]) or ""
        calls = ", ".join(sc.calls) or "(none)"
        lines.append(f"| {sc.case_id} | {case['question']} | {'yes' if sc.passed else 'no'} | {calls} | "
                     f"{traces[case['id']]['seconds']} s | {problems.replace('|', '/')} |")
    return "\n".join(lines) + "\n"
