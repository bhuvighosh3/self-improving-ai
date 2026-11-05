"""Run the Component C experiment.

    # Offline smoke test (no API calls, deterministic stand-in planner; numbers are not results)
    python -m self_improving_ai.evaluation.orchestrator --planner keyword

    # Real run on Gemini via Vertex AI (reads GOOGLE_* settings from .env)
    python -m self_improving_ai.evaluation.orchestrator --planner gemini --seeds 5

    # Cheap first look: 1 seed, 2 cycles, 40 test cases
    python -m self_improving_ai.evaluation.orchestrator --planner gemini --seeds 1 --cycles 2 --test-limit 40
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

from self_improving_ai.evaluation.orchestrator.runner import (
    AGENTS,
    Experiment,
    RunConfig,
    load_cases,
)
from self_improving_ai.harness.gate import GateThresholds


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--planner", choices=["gemini", "keyword"], default="keyword")
    ap.add_argument("--model", default=None, help="Gemini model (default: settings.agent_model)")
    ap.add_argument("--temperature", type=float, default=0.4)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--cycles", type=int, default=4)
    ap.add_argument("--train-batch", type=int, default=30)
    ap.add_argument("--gate-val", type=int, default=30)
    ap.add_argument("--gate-seeds", type=int, default=5)
    ap.add_argument("--test-limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--agents", default=",".join(AGENTS))
    ap.add_argument("--min-gain-pp", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--promote", action="store_true",
                    help="Adopt the best seed's learned memory into the live store the ADK orchestrator reads")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parents[4] / ".env", override=True)
    if args.planner == "gemini":
        from self_improving_ai.agents.orchestrator.planner import GeminiPlanner

        planner = GeminiPlanner(model=args.model, temperature=args.temperature)
    else:
        from self_improving_ai.agents.orchestrator.planner import KeywordPlanner

        planner = KeywordPlanner()

    out = Path(args.out or f"results/orchestrator/{args.planner}_{time.strftime('%Y%m%d_%H%M%S')}")
    cfg = RunConfig(
        seeds=args.seeds, cycles=args.cycles, train_batch=args.train_batch, gate_val=args.gate_val,
        gate_seeds=args.gate_seeds, concurrency=args.concurrency, test_limit=args.test_limit,
        agents=[a.strip() for a in args.agents.split(",") if a.strip()],
        thresholds=GateThresholds(min_gain_pp=args.min_gain_pp),
    )
    summary = asyncio.run(Experiment(planner, load_cases(), out, cfg).run())
    print((out / "report.md").read_text())
    print(f"Outputs written to {out}")
    if args.promote and "learner" in summary["agents"]:
        from self_improving_ai.agents.orchestrator.memory import MemoryStore, default_store

        rates = summary["agents"]["learner"]["outcome_by_seed"]
        best = summary["seeds"][rates.index(max(rates))]
        memory = MemoryStore(out / f"seed_{best}" / "memory").load()
        version = default_store().adopt(memory, reason=f"promoted from {out} (seed {best}, test pass rate {max(rates):.3f})")
        print(f"Promoted seed {best} memory as live version {version}")
    if summary["agents"].get("learner", {}).get("errors"):
        print(f"Warning: {summary['agents']['learner']['errors']} planner calls failed; see case_results.csv")


if __name__ == "__main__":
    main()
