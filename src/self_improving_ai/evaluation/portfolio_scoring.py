"""Score bound tool executions and structured final answers against frozen references."""
from __future__ import annotations

import inspect
import json
import math


def value_at(document, path):
    for key in path:
        document = document[key]
    return document


def matches(document, check: dict) -> bool:
    try:
        value = value_at(document, check["path"])
        expected = check["value"]
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            return (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and math.isclose(
                        value, expected, rel_tol=check.get("relative_tolerance", 0),
                        abs_tol=check.get("tolerance", 1e-8)))
        return type(value) is type(expected) and value == expected
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def bound_executions(trace: list[dict]) -> list[dict]:
    """Bind each result to a preceding unique call ID and matching tool name."""
    pending, executions = {}, []
    for position, entry in enumerate(trace):
        if entry.get("kind") == "call":
            if entry.get("id"):
                pending.setdefault(entry["id"], []).append((position, entry))
        elif entry.get("kind") == "result":
            candidates = pending.get(entry.get("id"), [])
            if len(candidates) == 1:
                call_position, call = candidates[0]
                if call.get("tool") == entry.get("tool"):
                    executions.append({**call, "result": entry["result"], "position": call_position})
                    pending[entry["id"]] = []
        elif "arguments" in entry and "result" in entry:
            executions.append({**entry, "position": position})
    return executions


def arguments_match(tool: str, actual: dict, expected: dict) -> bool:
    # Explicit defaults and omitted defaults are equivalent; other extra inputs are not.
    from self_improving_ai.agents.portfolio.service import TASKS

    function = next((fn for fn in TASKS.values() if fn.__name__ == tool), None)
    try:
        if function:
            signature = inspect.signature(function)
            a, b = signature.bind(**actual), signature.bind(**expected)
            a.apply_defaults()
            b.apply_defaults()
            actual, expected = a.arguments, b.arguments
        return json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    except (TypeError, ValueError):
        return False


def score_run(run: dict, reference: dict) -> dict:
    calls = [entry for entry in run.get("trace", []) if entry.get("kind") != "result"]
    executions = bound_executions(run.get("trace", []))
    steps = reference.get("steps", [reference])
    step_results, position, used = [], -1, set()
    for step in steps:
        candidates = [entry for entry in executions if entry["position"] not in used
                      and (not reference.get("steps_ordered", True) or entry["position"] > position)
                      and entry["tool"] == step["tool"]
                      and any(arguments_match(step["tool"], entry["arguments"], args)
                              for args in [step.get("arguments", {}), *step.get("argument_variants", [])])]
        checks = step.get("checks", [step] if "path" in step else [])
        # A final conflicting repeat must not be hidden behind an earlier correct result.
        selected = candidates[-1] if candidates else None
        outcome = bool(selected and checks and all(matches(selected["result"], check) for check in checks))
        if selected:
            position = selected["position"]
            used.add(position)
        step_results.append({"tool": step["tool"], "arguments_correct": selected is not None,
                             "outcome_correct": outcome})
    explicit = run.get("mode") == "explicit_tool_execution"
    final_checks = reference.get("answer_checks", steps[-1].get(
        "checks", [steps[-1]] if "path" in steps[-1] else []))
    final_assessed = not explicit and bool(final_checks)
    answer_ok = None
    if final_assessed:
        try:
            answer = json.loads(run.get("response", ""))
            answer_ok = all(matches(answer, check) for check in final_checks)
        except (TypeError, ValueError):
            answer_ok = False
    expected_error = any(c.get("path", [None])[0] == "error" for c in final_checks)
    status_ok = run.get("status") == ("error" if explicit and expected_error else "success")
    extra = max(0, len(calls) - reference.get("max_calls", len(steps)))
    allowed = steps + reference.get("optional_calls", [])
    trajectory_ok = all(any(call.get("tool") == step["tool"] and any(
        arguments_match(step["tool"], call.get("arguments", {}), args)
        for args in [step.get("arguments", {}), *step.get("argument_variants", [])])
        for step in allowed) for call in calls)
    tool_ok = all(step["arguments_correct"] for step in step_results)
    outcome_ok = all(step["outcome_correct"] for step in step_results)
    return {"tool_and_arguments_correct": tool_ok, "outcome_correct": outcome_ok,
            "steps": step_results, "extra_calls": extra, "run_status_correct": status_ok,
            "trajectory_tools_allowed": trajectory_ok,
            "final_answer_assessed": final_assessed, "final_answer_correct": answer_ok,
            "passed": tool_ok and outcome_ok and status_ok and trajectory_ok and extra == 0
                      and (explicit or (final_assessed and answer_ok is True)),
            "scoring_scope": "structured JSON values, units and provenance; free-form explanation not graded"}

