"""Run the golden set through the live copilot and score each trace and answer.

    # All fast cases (skips the two slow meeting-brief cases)
    python -m self_improving_ai.evaluation.copilot

    # Everything, including meeting briefs (about 3 minutes each)
    python -m self_improving_ai.evaluation.copilot --include-slow

    # A few cases
    python -m self_improving_ai.evaluation.copilot --cases G01 G05 G14 --include-slow

Needs Vertex AI settings (GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION)
and the team's Firestore data (SIA_WORKSPACE_STORE=firestore, SIA_GOOGLE_CLOUD_PROJECT).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="*", help="Case IDs to run (default: all)")
    ap.add_argument("--include-slow", action="store_true", help="Also run the meeting-brief cases")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=300, help="Seconds per question")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    load_dotenv()
    # Keep the copilot's console span printout out of the run log; scores come from the returned steps.
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    trace.set_tracer_provider(TracerProvider())

    from self_improving_ai.evaluation.copilot.runner import load_golden, run_golden

    cases = load_golden()
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
    elif not args.include_slow:
        cases = [c for c in cases if not c.get("slow")]
    out = args.out or Path("results/copilot") / time.strftime("golden_%Y%m%d_%H%M%S")
    print(f"Running {len(cases)} golden cases -> {out}")
    summary = asyncio.run(run_golden(cases, out, concurrency=args.concurrency, timeout_s=args.timeout))
    print(json.dumps({k: summary[k] for k in ("pass_rate", "plan_pass_rate", "stages", "errors")}, indent=2))
    print(f"Report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
