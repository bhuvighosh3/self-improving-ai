"""Turn scored training runs into proposed memory updates for Component C.

The feedback signal on training tasks is the labelled reference (the "simulated advisor
correction" in the scope). Updates are proposed on a copy of memory; the improvement
harness decides whether that candidate is adopted.
"""

from __future__ import annotations

from dataclasses import dataclass

from self_improving_ai.agents.orchestrator.memory import IntentExample, OrchestratorMemory
from self_improving_ai.agents.orchestrator.schemas import OrchestratorPlan
from self_improving_ai.evaluation.orchestrator.scoring import CaseScore
from self_improving_ai.tools.orchestrator.catalog import Catalog


@dataclass
class Trace:
    """One run, as stored in the experience store."""

    case: dict
    plan: OrchestratorPlan
    score: CaseScore
    catalog_version: str


def _tool_reason(catalog: Catalog, used: str, expected: str) -> str:
    t_used, t_exp = catalog.get(used), catalog.get(expected)
    if t_used is None:
        return f"{used} does not exist in the catalog"
    if t_used.get("caveat"):
        return t_used["caveat"]
    if not catalog.callable_by_orchestrator(used):
        return f"only {catalog.owner_of(used)} can call it"
    if t_exp:
        return f"{expected} is the one that {t_exp['description'][0].lower()}{t_exp['description'][1:]}"
    return ""


def propose_updates(traces: list[Trace], memory: OrchestratorMemory, catalog: Catalog) -> tuple[OrchestratorMemory, list[str]]:
    """Return a candidate memory and a human-readable list of the changes it contains."""
    cand = memory.copy()
    changes: list[str] = []
    for t in traces:
        case, plan, sc = t.case, t.plan, t.score
        d = sc.details
        ref_intent = case["intent"]

        # 1. Intent memory
        if case.get("clarification_required") and not plan.needs_clarification:
            cand.add_intent_example(IntentExample(
                text=case["request_text"], intent=ref_intent, kind="correction",
                wrong_intent=plan.intent,
                note="The client name matched more than one household: ask which client before planning",
            ))
            changes.append(f"intent lesson: ambiguous client in '{case['id']}'")
        elif sc.stages["intent"] == 0.0:
            cand.add_intent_example(IntentExample(
                text=case["request_text"], intent=ref_intent, kind="correction", wrong_intent=plan.intent,
            ))
            changes.append(f"intent correction: {plan.intent} -> {ref_intent}")
        elif sc.passed:
            cand.add_intent_example(IntentExample(text=case["request_text"], intent=ref_intent))

        # 2. Tool notes
        for sub in d.get("tool_substitutions", []):
            used, exp = sub["used"], sub["expected"]
            reason = _tool_reason(catalog, used, exp)
            if catalog.exists(used):
                cand.add_tool_note(used, f"Do not use {used} for {ref_intent}; use {exp} instead. {reason}".strip(), catalog)
                changes.append(f"tool note: {used} -> {exp}")
        for inv in d.get("invalid_tools", []):
            tool = inv["tool"]
            if inv["reason"] == "forbidden":
                cand.add_tool_note(tool, "Never call this tool. The copilot does not execute trades or send messages.", catalog)
            elif inv["reason"].startswith("only callable by"):
                owner = catalog.owner_of(tool)
                cand.add_tool_note(tool, f"Never call this directly; it is internal to {owner}. Delegate to {owner}.", catalog)
            elif inv["reason"] == "deprecated":
                cand.add_tool_note(tool, f"Never call: {catalog.get(tool).get('caveat', 'deprecated')}", catalog)
            else:
                continue
            changes.append(f"tool note: avoid {tool} ({inv['reason']})")
        for fb in d.get("forbidden_used", []):
            if catalog.exists(fb):
                cand.add_tool_note(fb, "Never call this tool. The copilot does not execute trades or send messages.", catalog)
        for miss in d.get("arg_misses", []):
            exp = miss["expected"]
            if isinstance(exp, dict) and exp.get("kind") == "bps":
                cand.add_tool_note(miss["tool"], "shock_bps is in basis points (25 means 0.25%), not a decimal.", catalog)
                changes.append("tool note: shock_bps units")
        if case["intent"] == "price_lookup" and any(s["expected"] == "get_fund_nav" for s in d.get("tool_substitutions", [])):
            cand.add_tool_note("get_intraday_price", "Returns only the previous close for mutual funds; for mutual funds call get_fund_nav and state the as-of date.", catalog)

        # 3. Plan templates
        structural_miss = d.get("missing_steps") or d.get("order_misses") or sc.stages.get("ordering") == 0.0
        ref = case.get("reference_plan", [])
        if case.get("clarification_required"):
            pass
        elif structural_miss or (sc.safety_violation and not ref):
            cand.set_plan_template(ref_intent, ref)
            changes.append(f"plan template: {ref_intent}")
        elif sc.passed and ref_intent not in cand.plan_templates:
            cand.set_plan_template(ref_intent, [
                {"id": s.id, "tool": s.tool, "args": {a.name: a.value for a in s.args},
                 "depends_on": s.depends_on}
                for s in plan.steps if s.tool not in catalog.neutral_tools
            ])
    return cand, sorted(set(changes))
