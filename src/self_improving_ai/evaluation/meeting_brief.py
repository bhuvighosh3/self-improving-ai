"""Independent artifact/trace evaluator. Hidden references never enter agent runtime.

Run: python -m self_improving_ai.evaluation.meeting_brief --brief-id ID --reference FILE
"""

import argparse
import hashlib
import json
from pathlib import Path

from self_improving_ai.agents.briefing.checks import check_work


def evaluate(brief: dict, reference: dict, follow_ups: list[dict] | None = None) -> dict:
    workflow = brief["workflow"]
    evidence = workflow["evidence"]
    work = {**workflow["work"], "sections": brief["sections"]}
    objective = check_work(work, evidence, workflow["calculations"])
    prose = "\n".join(i["text"] for s in brief["sections"] for i in s["items"])
    errors = []
    if brief["client_id"] != reference["client_id"]:
        errors.append({"stage": "identity", "detail": "Wrong client"})
    for text in reference.get("required_text", []):
        if text.casefold() not in prose.casefold():
            errors.append({"stage": "coverage", "detail": f"Required fact missing: {text}"})
    for text in reference.get("forbidden_text", []):
        if text.casefold() in prose.casefold():
            errors.append({"stage": "expression", "detail": f"Unsupported statement: {text}"})
    for finding in objective["findings"]:
        errors.append({"stage": "evidence_or_calculation", **finding})
    trace = workflow["trace"]
    observed_tools = {e["tool"] for e in trace if "tool" in e}
    missing_tools = set(reference.get("required_tools", [])) - observed_tools
    if missing_tools:
        errors.append({"stage": "retrieval", "detail": f"Missing actual calls: {sorted(missing_tools)}"})
    digest = hashlib.sha256(json.dumps(trace, sort_keys=True).encode()).hexdigest()
    sources = {s["id"] for s in evidence["sources"]}
    initiative = [{"finding": f, "decision": "pending_expert_review"}
                  for f in work["findings"]
                  if f["id"] not in reference.get("routine_finding_ids", [])
                  and set(f["source_ids"]) <= sources]
    follow_records = []
    for follow in follow_ups or []:
        follow_records.append({**follow,
            "new_work": bool(follow.get("new_tool_events")),
            "evidence_status": "pending_expert_review",
            "pre_question_trace_digest": digest})
    return {"brief_id": brief["id"], "rubric_version": reference.get("rubric_version", "proposal-v0.1"),
            "dimensions": {"objective_duties": "fail" if errors else "pass",
                           "analysis_quality": "partial_pending_expert_review",
                           "initiative": "partial_pending_expert_review"},
            "errors": errors, "quality_history": workflow.get("quality_history", []),
            "initiative_candidates": initiative, "follow_ups": follow_records,
            "trace_digest": digest, "trace_events": len(trace),
            "tool_calls": sum("arguments" in e and "tool" in e for e in trace),
            "usage": [e for e in trace if e.get("event") == "usage"],
            "total_score": None,
            "limitations": "Text checks are case assertions, not proof of semantic correctness. "
                           "Priority, usefulness and unexpected discoveries require expert adjudication."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief-id", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from self_improving_ai.agents.briefing.store import DraftStore

    brief = DraftStore().get(args.brief_id)["brief"]
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    result = json.dumps(evaluate(brief, reference), indent=2)
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result)


if __name__ == "__main__":
    main()
