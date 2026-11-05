"""Run Component A explicitly offline, or use --mode agent for real model calls."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["tool", "agent"], default="tool")
    parser.add_argument("--task", choices=["holdings", "scenarios", "allocation", "risk", "projection", "quote", "history"], default="allocation")
    parser.add_argument("--client", default="CLI-001")
    parser.add_argument("--account", default="")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--simulations", type=int, default=5000)
    parser.add_argument("--stock-target", type=float, help="Decimal stock target, e.g. 0.6")
    parser.add_argument("--target-amount", type=float)
    parser.add_argument("--years", type=int)
    parser.add_argument("--annual-contribution", type=float)
    parser.add_argument("--annual-withdrawal", type=float)
    parser.add_argument("--message", default="Show the Garcia Family CLI-001 allocation drift against its draft target.")
    parser.add_argument("--lessons-file", type=Path, help="Validated lesson-store JSON; only active text is injected")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from self_improving_ai.connection_store import restore_connections
    restore_connections()
    from self_improving_ai.agents.portfolio.service import (
        execute_task,
        run_portfolio_agent,
        save_run,
    )
    if args.mode == "agent":
        lessons = ""
        if args.lessons_file:
            from self_improving_ai.harness.strategies.portfolio_lessons import LessonStore
            lessons = LessonStore(args.lessons_file).active_text()
        run = asyncio.run(run_portfolio_agent(args.message, lessons=lessons))
    else:
        values = {"client_id": args.client}
        if args.task in {"holdings", "allocation", "risk"}:
            values["account_id"] = args.account
        if args.task == "projection":
            values.update(num_simulations=args.simulations, seed=args.seed)
            values.update({key:getattr(args,key) for key in
                           ("target_amount","years","annual_contribution","annual_withdrawal")
                           if getattr(args,key) is not None})
        if args.stock_target is not None:
            if args.task != "allocation":
                parser.error("--stock-target requires --task allocation")
            values["target_stock_weight"] = args.stock_target
        if args.task != "projection" and any(getattr(args,key) is not None for key in
                ("target_amount","years","annual_contribution","annual_withdrawal")):
            parser.error("Goal overrides require --task projection")
        if args.account and args.task not in {"holdings","allocation","risk"}:
            parser.error("This task does not support an account filter")
        if args.task in {"quote", "history"}:
            values = {"symbol": args.symbol}
        if args.task == "history":
            if not args.start or not args.end:
                parser.error("history requires --start and --end")
            values.update(start_date=args.start, end_date=args.end)
        run = execute_task(args.task, values)
    if args.save:
        save_run(run, ROOT / "artifacts/runs")
    print(json.dumps(run, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if run["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
