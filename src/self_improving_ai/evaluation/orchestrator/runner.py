"""Component C experiment: learner versus static, hand-tuned and retrieval-only baselines.

For each seed:
1. Learning: run the learner on batches of training requests, propose memory updates from the
   scored runs, and adopt a candidate only if it passes the adoption gate on a validation
   subset (paired t-test over gate seeds, regression suite, safety, cost).
2. Testing: run all four agents on the test split (seen intents with new phrasings, held-out
   intents, changed tool catalog, and the spreadsheet's suite cases).

Outputs (in --out): summary.json, report.md, stage_scorecard.csv (same layout as the
spreadsheet's Stage Scorecard), suite_results.csv (for the Test Cases sheet), case_results.csv,
learning_curve.csv, and each seed's versioned memory with its audit log.
"""

from __future__ import annotations

import asyncio
import csv
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from self_improving_ai.agents.orchestrator.learner import Trace, propose_updates
from self_improving_ai.agents.orchestrator.memory import (
    MemoryStore,
    OrchestratorMemory,
    scrub,
    similarity,
    tokens,
)
from self_improving_ai.agents.orchestrator.planner import (
    PlanContext,
    Planner,
    load_hand_tuned_notes,
)
from self_improving_ai.evaluation.orchestrator.scoring import (
    STAGE_LABELS,
    STAGES,
    CaseScore,
    score_plan,
)
from self_improving_ai.harness.gate import GateThresholds, decide, paired_t_test
from self_improving_ai.tools.orchestrator.catalog import load_catalog

_DATA = Path(__file__).resolve().parents[2] / "data" / "orchestrator" / "requests.jsonl"
AGENTS = ["static", "hand_tuned", "retrieval", "learner"]
AGENT_LABELS = {"static": "Static", "hand_tuned": "Hand-tuned", "retrieval": "Retrieval-only", "learner": "Learner"}


def load_cases(path: Path = _DATA) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def case_group(case: dict) -> str:
    tags = case.get("tags", [])
    if case.get("catalog") == "v2":
        return "changed_tools"
    if "suite_case" in tags:
        return "suite_cases"
    if "held_out_intent" in tags:
        return "new_intents"
    return "seen_intents_new_phrasing"


@dataclass
class RunConfig:
    seeds: int = 5
    cycles: int = 4
    train_batch: int = 30
    gate_val: int = 30
    gate_seeds: int = 5
    concurrency: int = 8
    test_limit: int | None = None
    agents: list[str] = field(default_factory=lambda: list(AGENTS))
    thresholds: GateThresholds = field(default_factory=GateThresholds)


@dataclass
class Run:
    case: dict
    plan: object
    score: CaseScore
    tokens: int
    error: str = ""


class Experiment:
    def __init__(self, planner: Planner, cases: list[dict], out: Path, cfg: RunConfig):
        self.planner = planner
        self.cases = cases
        self.out = Path(out)
        self.cfg = cfg
        self.sem = asyncio.Semaphore(cfg.concurrency)
        self.hand_notes = load_hand_tuned_notes()
        self.out.mkdir(parents=True, exist_ok=True)

    # Contexts for each agent variant

    def context(self, agent: str, case: dict, memory: OrchestratorMemory | None, experience: list[Run]) -> PlanContext:
        catalog = load_catalog(case.get("catalog", "v1"))
        if agent == "static":
            return PlanContext()
        if agent == "hand_tuned":
            return PlanContext(guidance=self.hand_notes)
        if agent == "retrieval":
            q = tokens(scrub(case["request_text"]))
            scored = []
            for r in experience:
                if r.score.passed:
                    scored.append((similarity(q, tokens(scrub(r.case["request_text"]))), r))
            scored.sort(key=lambda x: -x[0])
            examples = [(r.case["request_text"], r.plan.model_dump(exclude_defaults=True)) for s, r in scored[:3] if s > 0.2]
            return PlanContext(examples=examples)
        if agent == "learner":
            blocks = (memory or OrchestratorMemory()).render(case["request_text"], catalog)
            return PlanContext(**blocks)
        raise ValueError(agent)

    async def run_one(self, agent: str, case: dict, seed: int, memory, experience) -> Run:
        catalog = load_catalog(case.get("catalog", "v1"))
        ctx = self.context(agent, case, memory, experience)
        async with self.sem:
            res = await self.planner.plan(case["request_text"], catalog, ctx, seed=seed)
        sc = score_plan(case, res.plan, catalog)
        return Run(case, res.plan, sc, res.input_tokens + res.output_tokens, res.error)

    async def run_many(self, agent: str, cases: list[dict], seed: int, memory=None, experience=None) -> list[Run]:
        return await asyncio.gather(*[self.run_one(agent, c, seed, memory, experience or []) for c in cases])

    # Learning

    async def gate_eval(self, memory: OrchestratorMemory, val: list[dict], seed: int) -> dict:
        per_seed, per_case, tok, safety = [], {}, 0, 0
        for g in range(self.cfg.gate_seeds):
            runs = await self.run_many("learner", val, seed * 1000 + g, memory)
            per_seed.append(sum(r.score.passed for r in runs) / len(runs))
            for r in runs:
                per_case.setdefault(r.case["id"], []).append(r.score.passed)
                tok += r.tokens
                safety += r.score.safety_violation
        solved = {cid for cid, v in per_case.items() if sum(v) > len(v) / 2}
        return {"rates": per_seed, "solved": solved, "tokens": tok, "safety": safety}

    async def learn(self, seed: int) -> tuple[OrchestratorMemory, list[Run], list[dict]]:
        rng = random.Random(seed)
        train = [c for c in self.cases if c["split"] == "train"]
        val = [c for c in self.cases if c["split"] == "val"]
        rng.shuffle(train)
        val_gate = rng.sample(val, min(self.cfg.gate_val, len(val)))
        store = MemoryStore(self.out / f"seed_{seed}" / "memory")
        memory = OrchestratorMemory()
        store.adopt(memory, reason="initial empty memory")
        current = await self.gate_eval(memory, val_gate, seed)
        curve = [{"seed": seed, "cycle": 0, "val_pass_rate": statistics.mean(current["rates"]),
                  "decision": "initial", "memory_version": memory.version, **memory.size()}]
        experience: list[Run] = []
        for cycle in range(1, self.cfg.cycles + 1):
            start = ((cycle - 1) * self.cfg.train_batch) % max(1, len(train))
            batch = (train + train)[start:start + self.cfg.train_batch]
            runs = await self.run_many("learner", batch, seed * 100 + cycle, memory)
            experience.extend(runs)
            traces = [Trace(r.case, r.plan, r.score, r.case.get("catalog", "v1")) for r in runs if not r.error]
            cand, changes = propose_updates(traces, memory, load_catalog("v1"))
            train_rate = sum(r.score.passed for r in runs) / len(runs)
            if not changes:
                store.reject("no changes proposed", cycle=cycle)
                curve.append({"seed": seed, "cycle": cycle, "train_pass_rate": train_rate,
                              "val_pass_rate": statistics.mean(current["rates"]), "decision": "no_change",
                              "memory_version": memory.version, **memory.size()})
                continue
            cand_eval = await self.gate_eval(cand, val_gate, seed)
            regressions = len(current["solved"] - cand_eval["solved"])
            cost_ratio = cand_eval["tokens"] / current["tokens"] if current["tokens"] else 1.0
            decision = decide(current["rates"], cand_eval["rates"], regressions, cand_eval["safety"],
                              cost_ratio, self.cfg.thresholds)
            gate_info = {"cycle": cycle, "changes": changes, "gate": decision.to_dict()}
            if decision.adopt:
                store.adopt(cand, reason=decision.reason, **gate_info)
                memory, current = cand, cand_eval
            else:
                store.reject(decision.reason, **gate_info)
            curve.append({"seed": seed, "cycle": cycle, "train_pass_rate": train_rate,
                          "val_pass_rate": statistics.mean(current["rates"]),
                          "candidate_val_pass_rate": statistics.mean(cand_eval["rates"]),
                          "decision": decision.reason, "p_value": decision.p_value,
                          "regressions": regressions, "memory_version": memory.version, **memory.size()})
        return memory, experience, curve

    # Full experiment

    async def run(self) -> dict:
        t0 = time.time()
        test = [c for c in self.cases if c["split"] == "test"]
        if self.cfg.test_limit:
            rng = random.Random(0)
            suite = [c for c in test if "suite_case" in c.get("tags", [])]
            rest = [c for c in test if c not in suite]
            test = suite + rng.sample(rest, min(len(rest), max(0, self.cfg.test_limit - len(suite))))
        results: dict[str, dict[int, list[Run]]] = {a: {} for a in self.cfg.agents}
        curves: list[dict] = []
        stale_notes: dict[int, list[str]] = {}
        for seed in range(1, self.cfg.seeds + 1):
            memory, experience, curve = await self.learn(seed)
            curves.extend(curve)
            stale_notes[seed] = sorted({n.tool for n in memory.stale_tool_notes(load_catalog("v2"))})
            for agent in self.cfg.agents:
                results[agent][seed] = await self.run_many(agent, test, seed, memory, experience)
            print(f"seed {seed}: " + ", ".join(
                f"{a}={sum(r.score.passed for r in results[a][seed]) / len(test):.2f}" for a in self.cfg.agents))
        summary = self.summarize(results, test, curves, stale_notes, time.time() - t0)
        self.write_outputs(results, test, curves, summary)
        return summary

    def summarize(self, results, test, curves, stale_notes, elapsed) -> dict:
        seeds = sorted(next(iter(results.values())).keys())
        groups = sorted({case_group(c) for c in test})
        out: dict = {"n_test_cases": len(test), "seeds": seeds, "elapsed_s": round(elapsed, 1), "agents": {}}
        for agent, by_seed in results.items():
            a = {"outcome_by_seed": [], "stages": {}, "groups": {}, "tokens_per_task": [], "safety_violations": 0, "errors": 0}
            for s in seeds:
                runs = by_seed[s]
                a["outcome_by_seed"].append(sum(r.score.passed for r in runs) / len(runs))
                a["tokens_per_task"].append(sum(r.tokens for r in runs) / len(runs))
                a["safety_violations"] += sum(r.score.safety_violation for r in runs)
                a["errors"] += sum(bool(r.error) for r in runs)
            for st in STAGES:
                per_seed = []
                for s in seeds:
                    vals = [r.score.stages[st] for r in by_seed[s] if r.score.stages[st] is not None]
                    per_seed.append(statistics.mean(vals) if vals else None)
                a["stages"][st] = per_seed
            for g in groups:
                a["groups"][g] = [
                    statistics.mean([r.score.passed for r in by_seed[s] if case_group(r.case) == g]) for s in seeds
                ]
            a["outcome_mean"] = statistics.mean(a["outcome_by_seed"])
            out["agents"][agent] = a
        if "learner" in results:
            learner = out["agents"]["learner"]["outcome_by_seed"]
            comps = {}
            for b in results:
                if b == "learner":
                    continue
                base = out["agents"][b]["outcome_by_seed"]
                entry = {"mean_gain_pp": round(100 * (statistics.mean(learner) - statistics.mean(base)), 2),
                         "beats_on_every_seed": all(x > y for x, y in zip(learner, base))}
                if len(seeds) >= 2:
                    _, t, p = paired_t_test(base, learner)
                    entry.update({"t": t, "p_value": p})
                comps[b] = entry
            out["learner_vs_baselines"] = comps
            out["learner_beats_all_baselines_every_seed"] = all(c["beats_on_every_seed"] for c in comps.values())
            stage_wins = {}
            for st in STAGES:
                l = out["agents"]["learner"]["stages"][st]
                ok = True
                for b in results:
                    if b == "learner":
                        continue
                    bs = out["agents"][b]["stages"][st]
                    ok = ok and all(x is not None and y is not None and x > y for x, y in zip(l, bs))
                stage_wins[st] = ok
            out["learner_beats_all_baselines_by_stage"] = stage_wins
        out["stale_tool_notes_after_catalog_change"] = stale_notes
        out["learning_curve"] = curves
        return out

    def write_outputs(self, results, test, curves, summary) -> None:
        seeds = summary["seeds"]
        (self.out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
        with (self.out / "stage_scorecard.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Stage", "Agent", *[f"Seed {s}" for s in seeds], "Mean"])
            for st in STAGES:
                for agent in results:
                    vals = summary["agents"][agent]["stages"][st]
                    clean = [v for v in vals if v is not None]
                    w.writerow([STAGE_LABELS[st], AGENT_LABELS[agent],
                                *[("" if v is None else round(v, 4)) for v in vals],
                                round(statistics.mean(clean), 4) if clean else ""])
        with (self.out / "suite_results.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Suite ID", "Request", *[f"{AGENT_LABELS[a]} pass rate" for a in results], "Result", "Observed behavior (learner, seed 1)"])
            suite = [c for c in test if "suite_case" in c.get("tags", [])]
            for c in suite:
                rates = []
                for a in results:
                    runs = [r for s in seeds for r in results[a][s] if r.case["id"] == c["id"]]
                    rates.append(sum(r.score.passed for r in runs) / len(runs))
                learner_runs = [r for r in results.get("learner", {}).get(seeds[0], []) if r.case["id"] == c["id"]]
                obs = ""
                if learner_runs:
                    p = learner_runs[0].plan
                    obs = f"intent={p.intent}; clarify={p.needs_clarification}; steps={[s.tool for s in p.steps]}; disclosures={len(p.disclosures)}"
                result = "Pass" if "learner" in results and rates[list(results).index("learner")] == 1.0 else "Fail"
                w.writerow([c["suite_id"], c["request_text"], *[round(r, 2) for r in rates], result, obs])
        with (self.out / "case_results.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["case_id", "group", "intent", "agent", "seed", "passed", "pred_intent", "steps", *STAGES, "error"])
            for a in results:
                for s in seeds:
                    for r in results[a][s]:
                        w.writerow([r.case["id"], case_group(r.case), r.case["intent"], a, s, int(r.score.passed),
                                    r.plan.intent, " > ".join(st.tool for st in r.plan.steps),
                                    *[("" if r.score.stages[k] is None else round(r.score.stages[k], 3)) for k in STAGES],
                                    r.error])
        with (self.out / "learning_curve.csv").open("w", newline="") as f:
            keys = sorted({k for row in curves for k in row})
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(curves)
        (self.out / "report.md").write_text(render_report(summary))


def render_report(s: dict) -> str:
    lines = ["# Component C evaluation", "",
             f"Test cases: {s['n_test_cases']}. Seeds: {len(s['seeds'])}.", "",
             "## End-to-end pass rate (outcome stage)", "",
             "| Agent | Mean | Per seed | Tokens/task | Safety violations |", "|---|---|---|---|---|"]
    for a, d in s["agents"].items():
        lines.append(f"| {AGENT_LABELS[a]} | {d['outcome_mean']:.3f} | "
                     f"{', '.join(f'{x:.2f}' for x in d['outcome_by_seed'])} | "
                     f"{statistics.mean(d['tokens_per_task']):.0f} | {d['safety_violations']} |")
    lines += ["", "## Pass rate by test group (mean over seeds)", ""]
    groups = sorted(next(iter(s["agents"].values()))["groups"])
    lines.append("| Agent | " + " | ".join(groups) + " |")
    lines.append("|---" * (len(groups) + 1) + "|")
    for a, d in s["agents"].items():
        lines.append(f"| {AGENT_LABELS[a]} | " + " | ".join(f"{statistics.mean(d['groups'][g]):.3f}" for g in groups) + " |")
    lines += ["", "## Stage means", "", "| Stage | " + " | ".join(AGENT_LABELS[a] for a in s["agents"]) + " |",
              "|---" * (len(s["agents"]) + 1) + "|"]
    for st in STAGES:
        row = []
        for a, d in s["agents"].items():
            vals = [v for v in d["stages"][st] if v is not None]
            row.append(f"{statistics.mean(vals):.3f}" if vals else "n/a")
        lines.append(f"| {STAGE_LABELS[st]} | " + " | ".join(row) + " |")
    if "learner_vs_baselines" in s:
        lines += ["", "## Learner versus baselines", ""]
        for b, c in s["learner_vs_baselines"].items():
            p = f", p={c['p_value']:.4f}" if "p_value" in c else ""
            lines.append(f"- vs {AGENT_LABELS[b]}: {c['mean_gain_pp']:+.1f} pp{p}; beats on every seed: {c['beats_on_every_seed']}")
        lines.append(f"- Beats every baseline on every seed: {s['learner_beats_all_baselines_every_seed']}")
    return "\n".join(lines) + "\n"
