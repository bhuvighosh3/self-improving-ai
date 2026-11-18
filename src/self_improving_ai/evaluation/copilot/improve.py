"""Improve the live copilot against the golden set, with every change gated.

Arms, each run on the dev and holdout splits with repeats (the model is not deterministic):
  baseline     no context fixes, empty learned memory (what was deployed)
  hand_fixes   today's date and the client directory in the prompt
  learner      hand fixes plus learned memory, grown in cycles:
                 1. collect the dev cases the current version fails
                 2. Gemini proposes lessons (tool notes, intent corrections, plan templates)
                    from those failed traces and their golden expectations
                 3. the candidate memory is evaluated on dev and holdout
                 4. harness.gate decides on the holdout split only (paired over cases):
                    significant gain, no regressions, no new forbidden calls, calls within budget
The learner never sees holdout cases, so a gain there is a gain on new wording.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from self_improving_ai.evaluation.copilot.runner import run_golden
from self_improving_ai.harness.gate import GateThresholds, decide

LESSON_LIMIT = 6


@dataclass
class ArmResult:
    label: str
    runs: list[list[dict]] = field(default_factory=list)  # per repeat: one score dict per case

    def case_pass(self, split_ids: list[str]) -> dict[str, float]:
        """Share of repeats in which each case passed."""
        out = {}
        for cid in split_ids:
            vals = [next(s for s in run if s["case_id"] == cid)["passed"] for run in self.runs]
            out[cid] = sum(vals) / len(vals)
        return out

    def rate(self, split_ids: list[str]) -> float:
        cp = self.case_pass(split_ids)
        return sum(cp.values()) / len(cp) if cp else 0.0

    def mean_calls(self, split_ids: list[str]) -> float:
        calls = [len(s["calls"]) for run in self.runs for s in run if s["case_id"] in split_ids]
        return sum(calls) / len(calls) if calls else 0.0

    def forbidden_failures(self, split_ids: list[str]) -> float:
        bad = [s["stages"].get("forbidden", 1.0) < 1.0 for run in self.runs for s in run if s["case_id"] in split_ids]
        return sum(bad) / len(self.runs)

    def stage(self, name: str, split_ids: list[str]) -> float:
        vals = [s["stages"].get(name, 0.0) for run in self.runs for s in run if s["case_id"] in split_ids]
        return sum(vals) / len(vals) if vals else 0.0

    def failed_traces(self, split_ids: list[str]) -> list[dict]:
        seen, out = set(), []
        for run in self.runs:
            for s in run:
                if s["case_id"] in split_ids and not s["passed"] and s["case_id"] not in seen:
                    seen.add(s["case_id"])
                    out.append(s)
        return out


async def evaluate_arm(label: str, cases: list[dict], out_dir: Path, repeats: int, concurrency: int,
                       timeout_s: float, runner) -> ArmResult:
    arm = ArmResult(label)
    for rep in range(1, repeats + 1):
        print(f"[{label}] repeat {rep}/{repeats}", flush=True)
        rep_dir = out_dir / label / f"repeat_{rep}"
        await run_golden(cases, rep_dir, concurrency=concurrency, timeout_s=timeout_s, runner=runner)
        arm.runs.append([json.loads(line)["score"] for line in open(rep_dir / "traces.jsonl", encoding="utf-8")])
    return arm


# Proposing lessons

PROPOSER_PROMPT = """You improve a wealth-management copilot by writing short lessons into its memory.
The copilot is an orchestrator that calls these tools (exact names):
{tools}

Below are advisor requests it got wrong. For each you see the request, the expected plan, what it
actually called, what went wrong, and the start of its answer.

{failures}

Its memory already holds:
{memory}

Write at most {limit} new lessons that would fix these failures for similar requests in general,
not only these exact sentences. Never include client names or client IDs. Lesson kinds:
- tool_note: {{"kind": "tool_note", "tool": "<exact tool name>", "note": "<one sentence on when or how to use it>"}}
- intent: {{"kind": "intent", "example": "<a generic request>", "intent": "<snake_case intent>", "note": "<what to do>"}}
- template: {{"kind": "template", "intent": "<snake_case intent>", "steps": [{{"id": 1, "tool": "<exact tool name>", "args": {{"client_id": "<client_id>"}}, "depends_on": []}}]}}
A template with an empty steps list means "answer without tools".
Return JSON only: {{"lessons": [...]}}"""


def _describe_failure(score: dict, case: dict) -> str:
    plan = [("/".join(s["tool"]) if isinstance(s["tool"], list) else s["tool"]) + (" (optional)" if s.get("optional") else "")
            for s in case["plan"]["steps"]] or ["no tool calls"]
    forbidden = case["plan"].get("forbidden")
    return (f"Request: {case['question']}\n"
            f"Expected plan ({case['plan']['order']} order): {', '.join(plan)}"
            + (f"; must not call {', '.join(forbidden)}" if forbidden else "") + "\n"
            f"Actually called: {', '.join(score['calls']) or 'nothing'}\n"
            f"Problems: {'; '.join(score['notes'] + ['missing fact: ' + m for m in score['missing_facts']])}\n"
            f"Answer start: {score['answer'][:300]!r}")


def propose_lessons(failed: list[dict], cases_by_id: dict, memory, client=None, model: str | None = None) -> list[dict]:
    from google.genai import Client, types

    from self_improving_ai.config import settings
    from self_improving_ai.tools.orchestrator.catalog import live_catalog

    tools = "\n".join(f"- {t['name']}({', '.join(p['name'] for p in t['params'])}): {t['description']}"
                      for t in live_catalog().tools)
    mem = memory.render("", live_catalog())
    mem_text = "\n".join(v for v in mem.values() if v) or "(empty)"
    prompt = PROPOSER_PROMPT.format(tools=tools, memory=mem_text, limit=LESSON_LIMIT,
                                    failures="\n\n".join(_describe_failure(s, cases_by_id[s["case_id"]]) for s in failed))
    client = client or Client()
    resp = client.models.generate_content(
        model=model or settings.agent_model, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3, response_mime_type="application/json"))
    return json.loads(resp.text).get("lessons", [])[:LESSON_LIMIT]


def apply_lessons(memory, lessons: list[dict]) -> tuple[object, list[str]]:
    """Candidate = copy of memory plus lessons; memory's own checks scrub names and drop unsafe or unknown-tool lessons."""
    from self_improving_ai.agents.orchestrator.memory import IntentExample
    from self_improving_ai.tools.orchestrator.catalog import live_catalog

    cat = live_catalog()
    cand = memory.copy()
    applied = []
    for lesson in lessons:
        kind = lesson.get("kind")
        if kind == "tool_note" and cat.exists(lesson.get("tool", "")):
            before = len(cand.tool_notes)
            cand.add_tool_note(lesson["tool"], lesson["note"], cat)
            if len(cand.tool_notes) > before:
                applied.append(f"tool note on {lesson['tool']}: {cand.tool_notes[-1].note}")
        elif kind == "intent" and lesson.get("example") and lesson.get("intent"):
            before = len(cand.intent_examples)
            cand.add_intent_example(IntentExample(text=lesson["example"], intent=lesson["intent"],
                                                  kind="correction", note=lesson.get("note", "")))
            if len(cand.intent_examples) > before:
                e = cand.intent_examples[-1]
                applied.append(f"intent '{e.text}' -> {e.intent}: {e.note}")
        elif kind == "template" and lesson.get("intent"):
            steps = [s for s in lesson.get("steps", []) if cat.exists(s.get("tool", ""))]
            if len(steps) == len(lesson.get("steps", [])):
                for i, s in enumerate(steps, 1):
                    s.setdefault("id", i)
                cand.set_plan_template(lesson["intent"], steps)
                applied.append(f"template {lesson['intent']}: " + (", ".join(s["tool"] for s in steps) or "no tools"))
    return cand, applied


def gate(incumbent: ArmResult, candidate: ArmResult, dev: list[str], holdout: list[str],
         thresholds: GateThresholds | None = None):
    """Decide on holdout, paired over cases. Regressions are checked on both splits."""
    inc_h, cand_h = incumbent.case_pass(holdout), candidate.case_pass(holdout)
    regressions = [cid for split in (dev, holdout)
                   for cid, v in incumbent.case_pass(split).items()
                   if v == 1.0 and candidate.case_pass(split)[cid] == 0.0]
    safety = max(0.0, candidate.forbidden_failures(dev + holdout) - incumbent.forbidden_failures(dev + holdout))
    inc_calls = incumbent.mean_calls(dev + holdout) or 1.0
    decision = decide([inc_h[c] for c in holdout], [cand_h[c] for c in holdout],
                      regressions=len(regressions), safety_flags=int(round(safety)),
                      cost_ratio=candidate.mean_calls(dev + holdout) / inc_calls, thresholds=thresholds)
    decision.details["regressed_cases"] = regressions
    return decision


async def run_improvement(cases: list[dict], out_dir: Path, *, repeats: int = 2, cycles: int = 2,
                          concurrency: int = 4, timeout_s: float = 300, promote: bool = False) -> dict:
    from self_improving_ai.agents.orchestrator.agent import set_context_fixes
    from self_improving_ai.agents.orchestrator.memory import MemoryStore, OrchestratorMemory, default_store, use_memory
    from self_improving_ai.evaluation.copilot.runner import build_runner

    out_dir.mkdir(parents=True, exist_ok=True)
    dev = [c["id"] for c in cases if c.get("split") == "dev"]
    holdout = [c["id"] for c in cases if c.get("split") == "holdout"]
    by_id = {c["id"]: c for c in cases}
    runner = build_runner()
    args = dict(cases=cases, out_dir=out_dir, repeats=repeats, concurrency=concurrency, timeout_s=timeout_s, runner=runner)
    store = MemoryStore(out_dir / "memory")
    log = {"repeats": repeats, "dev_cases": len(dev), "holdout_cases": len(holdout), "arms": {}, "cycles": []}

    def record(arm: ArmResult):
        log["arms"][arm.label] = {
            "dev_pass": arm.rate(dev), "holdout_pass": arm.rate(holdout),
            "mean_calls": arm.mean_calls(dev + holdout),
            "stages": {k: arm.stage(k, dev + holdout) for k in ("tools", "args", "order", "forbidden", "calls", "facts")},
            "case_pass": arm.case_pass(dev + holdout)}
        (out_dir / "improvement.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")

    try:
        set_context_fixes(False)
        use_memory(OrchestratorMemory())
        record(await evaluate_arm("baseline", **args))

        set_context_fixes(True)
        incumbent = await evaluate_arm("hand_fixes", **args)
        record(incumbent)
        memory = OrchestratorMemory()
        store.adopt(memory, reason="hand fixes, empty memory")

        for cycle in range(1, cycles + 1):
            failed = incumbent.failed_traces(dev)
            entry = {"cycle": cycle, "dev_failures": [s["case_id"] for s in failed]}
            if not failed:
                entry["decision"] = "nothing to learn: all dev cases pass"
                log["cycles"].append(entry)
                break
            lessons = propose_lessons(failed, by_id, memory)
            candidate_mem, applied = apply_lessons(memory, lessons)
            entry.update({"proposed": lessons, "applied": applied})
            if not applied:
                entry["decision"] = "no usable lessons"
                log["cycles"].append(entry)
                continue
            use_memory(candidate_mem)
            cand = await evaluate_arm(f"learner_cycle_{cycle}", **args)
            record(cand)
            decision = gate(incumbent, cand, dev, holdout)
            entry["gate"] = decision.to_dict()
            if decision.adopt:
                memory, incumbent = candidate_mem, cand
                store.adopt(memory, reason=f"cycle {cycle}", gate=decision.to_dict())
            else:
                store.reject(decision.reason, cycle=cycle, gate=decision.to_dict())
                use_memory(memory)
            log["cycles"].append(entry)
            (out_dir / "improvement.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")

        log["final"] = incumbent.label
        if promote and incumbent.label.startswith("learner"):
            default_store().adopt(memory, reason="promoted from golden-set improvement run", run=str(out_dir))
    finally:
        use_memory(None)
        set_context_fixes(True)
    (out_dir / "improvement.json").write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    (out_dir / "report.md").write_text(render_improvement(log), encoding="utf-8")
    return log


def render_improvement(log: dict) -> str:
    pct = lambda x: f"{100 * x:.0f}%"
    lines = ["# Copilot improvement on the golden set", "",
             f"{log['dev_cases']} dev and {log['holdout_cases']} holdout cases, {log['repeats']} repeats per arm. "
             "The learner only learns from dev failures; the gate decides on holdout.", "",
             "| Arm | Dev pass | Holdout pass | Calls per question | Right tools | Right args | Facts |",
             "|---|---|---|---|---|---|---|"]
    for label, a in log["arms"].items():
        st = a["stages"]
        lines.append(f"| {label} | {pct(a['dev_pass'])} | {pct(a['holdout_pass'])} | {a['mean_calls']:.1f} | "
                     f"{pct(st['tools'])} | {pct(st['args'])} | {pct(st['facts'])} |")
    for c in log["cycles"]:
        lines += ["", f"## Learner cycle {c['cycle']}", "",
                  f"Dev failures it learned from: {', '.join(c['dev_failures']) or 'none'}", ""]
        lines += [f"- {a}" for a in c.get("applied", [])] or ["- (no lessons applied)"]
        g = c.get("gate")
        if g:
            lines += ["", f"Gate: **{g['reason']}** (holdout gain {g['mean_gain_pp']:+.1f} pts, p = {g['p_value']:.3f}, "
                          f"regressions {g['details']['regressions']}, call ratio {g['details']['cost_ratio']:.2f})"]
        elif c.get("decision"):
            lines += ["", c["decision"]]
    lines += ["", f"Final version: **{log.get('final', '?')}**"]
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse
    import asyncio
    import time

    from dotenv import load_dotenv
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--include-slow", action="store_true", help="Also run the meeting-brief cases")
    ap.add_argument("--promote", action="store_true", help="Adopt the final learned memory into the app's store")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    load_dotenv()
    trace.set_tracer_provider(TracerProvider())

    from self_improving_ai.evaluation.copilot.runner import load_golden

    cases = [c for c in load_golden() if a.include_slow or not c.get("slow")]
    out = a.out or Path("results/copilot") / time.strftime("improve_%Y%m%d_%H%M%S")
    print(f"Improving on {len(cases)} cases -> {out}")
    asyncio.run(run_improvement(cases, out, repeats=a.repeats, cycles=a.cycles, concurrency=a.concurrency,
                                timeout_s=a.timeout, promote=a.promote))
    print(f"Report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
