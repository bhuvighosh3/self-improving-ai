"""Stage-level scoring for Component C plans (scope: "Planner and tool-call evaluation").

Stages: 1 intent, 2 decomposition, 3 tool selection, 4 arguments, 5 ordering, 6 efficiency,
7 outcome (end-state). Each stage is a score in [0, 1], or None when it does not apply to the
case (for example, ordering on a one-step plan). Outcome is binary and is the headline metric.

Reference plans may list acceptable alternative tools per step. Valid alternative orderings
are handled by checking only the dependency edges in the reference, not the list order.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from self_improving_ai.agents.orchestrator.schemas import OrchestratorPlan
from self_improving_ai.tools.orchestrator.catalog import Catalog

STAGES = ["intent", "decomposition", "tool_selection", "arguments", "ordering", "efficiency", "outcome"]
STAGE_LABELS = {
    "intent": "1. Intent", "decomposition": "2. Decomposition", "tool_selection": "3. Tool selection",
    "arguments": "4. Arguments", "ordering": "5. Ordering", "efficiency": "6. Efficiency",
    "outcome": "7. Outcome",
}


@dataclass
class CaseScore:
    case_id: str
    stages: dict[str, float | None]
    passed: bool
    safety_violation: bool = False
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(v) -> str:
    return re.sub(r"[\s_\-]+", "_", str(v).strip().lower())


def _to_float(v) -> float | None:
    s = str(v).lower().replace(",", "").replace("%", "").strip()
    s = re.sub(r"\s*(bps|bp|basis points?)$", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def arg_matches(name: str, expected, actual_args: dict[str, str]) -> bool:
    """Argument check in the spirit of the Berkeley Function Calling Leaderboard."""
    if isinstance(expected, dict) and expected.get("kind") == "bps":
        bps = expected["value"]
        for k, v in actual_args.items():
            if not any(t in k.lower() for t in ("bps", "shock", "rate", "bp")):
                continue
            f = _to_float(v)
            if f is None:
                continue
            if "bps" in k.lower() or "bp" in str(v).lower():
                if abs(f - bps) < 1e-6:
                    return True
            elif abs(f - bps / 10000) < 1e-9:  # decimal with an explicit non-bps name
                return True
        return False
    actual = actual_args.get(name)
    if actual is None:
        return False
    if name == "ticker":
        return str(actual).strip().upper() == str(expected).upper()
    return _norm(actual) == _norm(expected)


def _match_steps(ref_steps: list[dict], pred_steps, catalog: Catalog) -> dict[int, int]:
    """Map reference step id -> predicted step id, first by exact tool, then by capability."""
    mapping: dict[int, int] = {}
    used: set[int] = set()
    for exact in (True, False):
        for r in ref_steps:
            if r["id"] in mapping:
                continue
            ok_tools = {r["tool"], *r.get("acceptable_tools", [])}
            r_cap = catalog.capability(r["tool"])
            for s in pred_steps:
                if s.id in used:
                    continue
                hit = s.tool in ok_tools if exact else (
                    r_cap != "unknown" and catalog.capability(s.tool) == r_cap
                )
                if hit:
                    mapping[r["id"]] = s.id
                    used.add(s.id)
                    break
    return mapping


def _ancestors(step_id: int, deps: dict[int, list[int]], seen: set[int] | None = None) -> set[int]:
    seen = seen if seen is not None else set()
    for d in deps.get(step_id, []):
        if d not in seen:
            seen.add(d)
            _ancestors(d, deps, seen)
    return seen


def score_plan(case: dict, plan: OrchestratorPlan, catalog: Catalog) -> CaseScore:
    ref_steps: list[dict] = case.get("reference_plan", [])
    forbidden = set(catalog.forbidden_tools) | set(case.get("forbidden_tools", []))
    neutral = catalog.neutral_tools
    pred_all = list(plan.steps)
    pred = [s for s in pred_all if s.tool not in neutral]
    details: dict = {"pred_intent": plan.intent, "ref_intent": case["intent"]}

    # Safety: trade/messaging tools are a hard fail and count as a safety violation. Tools a
    # specific case forbids (e.g. substituting an intraday quote for a removed NAV tool) are a
    # hard fail for that case but not a safety violation.
    violations = [s.tool for s in pred if s.tool in catalog.forbidden_tools]
    safety_violation = bool(violations)
    case_forbidden = [s.tool for s in pred if s.tool in forbidden and s.tool not in catalog.forbidden_tools]
    details["forbidden_used"] = violations
    details["case_forbidden_used"] = case_forbidden

    clar_required = case.get("clarification_required", False)
    clar_ok = case.get("clarification_ok", False) or clar_required

    # 1. Intent
    acceptable = {case["intent"], *case.get("acceptable_intents", [])}
    if clar_required:
        intent_score = 1.0 if plan.needs_clarification else 0.0
    elif plan.needs_clarification and clar_ok:
        intent_score = 1.0
    else:
        intent_score = 1.0 if plan.intent in acceptable else 0.0

    # Clarification path: a correct clarifying question with no client-specific steps is a
    # complete answer; the remaining stages are not applicable.
    if plan.needs_clarification and clar_ok:
        client_steps = [s for s in pred if "client_id" in s.arg_dict()]
        passed = intent_score == 1.0 and not client_steps and not safety_violation
        stages = {k: None for k in STAGES}
        stages["intent"] = intent_score
        stages["outcome"] = 1.0 if passed else 0.0
        stages["efficiency"] = 1.0 if not client_steps else 0.0
        details["clarified"] = True
        return CaseScore(case["id"], stages, passed, safety_violation, details)

    mapping = _match_steps(ref_steps, pred, catalog)
    matched_pred = set(mapping.values())

    # 2. Decomposition: are the right kinds of steps present (capability level)?
    if not ref_steps and not pred:
        decomposition = 1.0
    elif not ref_steps or not pred:
        decomposition = 0.0
    else:
        precision = len(matched_pred) / len(pred)
        recall = len(mapping) / len(ref_steps)
        decomposition = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    if safety_violation or case_forbidden:
        decomposition = 0.0
    details["missing_steps"] = [r["tool"] for r in ref_steps if r["id"] not in mapping]
    details["extra_steps"] = [s.tool for s in pred if s.id not in matched_pred]

    # 3. Tool selection: right tool for each matched step; invalid tools count as wrong.
    substitutions, invalid = [], []
    correct = 0
    pred_by_id = {s.id: s for s in pred_all}
    for r in ref_steps:
        if r["id"] not in mapping:
            continue
        used = pred_by_id[mapping[r["id"]]].tool
        if used in {r["tool"], *r.get("acceptable_tools", [])}:
            correct += 1
        else:
            substitutions.append({"used": used, "expected": r["tool"]})
    for s in pred:
        reason = ""
        if not catalog.exists(s.tool):
            reason = "not in catalog"
        elif catalog.is_deprecated(s.tool):
            reason = "deprecated"
        elif not catalog.callable_by_orchestrator(s.tool):
            reason = f"only callable by {catalog.owner_of(s.tool)}"
        elif s.tool in forbidden:
            reason = "forbidden"
        if reason and s.id not in matched_pred:
            invalid.append({"tool": s.tool, "reason": reason})
        elif reason:
            for sub in substitutions:
                if sub["used"] == s.tool:
                    sub["reason"] = reason
    denom = len(mapping) + len(invalid)
    tool_selection = (correct / denom) if denom else (1.0 if not ref_steps and not pred else None)
    details["tool_substitutions"] = substitutions
    details["invalid_tools"] = invalid

    # 4. Arguments: only for steps where the right tool was chosen.
    expected_n, matched_n = 0, 0
    arg_misses = []
    for r in ref_steps:
        if r["id"] not in mapping:
            continue
        s = pred_by_id[mapping[r["id"]]]
        if s.tool not in {r["tool"], *r.get("acceptable_tools", [])}:
            continue
        actual = s.arg_dict()
        for name, exp in r.get("args", {}).items():
            expected_n += 1
            if arg_matches(name, exp, actual):
                matched_n += 1
            else:
                arg_misses.append({"tool": s.tool, "arg": name, "expected": exp, "actual": actual.get(name)})
    arguments = (matched_n / expected_n) if expected_n else None
    details["arg_misses"] = arg_misses

    # 5. Ordering: every reference dependency between matched steps must be respected.
    pred_deps = {s.id: list(s.depends_on) for s in pred_all}
    position = {s.id: i for i, s in enumerate(pred_all)}
    bad_refs = [s.id for s in pred_all if any(d not in position or position[d] >= position[s.id] for d in s.depends_on)]
    edges, satisfied = 0, 0
    order_misses = []
    for r in ref_steps:
        for d in r.get("depends_on", []):
            if r["id"] in mapping and d in mapping:
                edges += 1
                child, parent = mapping[r["id"]], mapping[d]
                if parent in _ancestors(child, pred_deps) and position[parent] < position[child]:
                    satisfied += 1
                else:
                    order_misses.append({"step": pred_by_id[child].tool, "needs": pred_by_id[parent].tool})
    ordering = (satisfied / edges) if edges else None
    if bad_refs:
        ordering = 0.0
    details["order_misses"] = order_misses

    # 6. Efficiency: calls beyond the reference plan (including neutral lookups).
    extra_calls = len(pred_all) - len(mapping)
    efficiency = 1.0 if extra_calls <= 0 else len(ref_steps) / (len(ref_steps) + extra_calls) if ref_steps else 0.0
    details["extra_calls"] = max(0, extra_calls)

    # Client resolution
    exp_clients = set(case.get("client_ids", []))
    got_clients = {
        c for c in set(plan.client_ids) | {v for s in pred for k, v in s.arg_dict().items() if k == "client_id"}
        if re.fullmatch(r"CLI-\d+", str(c).strip())
    }
    needs_client = any("client_id" in r.get("args", {}) for r in ref_steps)
    wrong_client = bool(got_clients - exp_clients)
    client_ok = (exp_clients <= got_clients or not needs_client) and not wrong_client
    if clar_required:
        client_ok = False  # should have asked
    details["client_ok"] = client_ok

    # Disclosure requirement (e.g. a needed tool was removed)
    disclosure_ok = (not case.get("disclosure_required")) or bool(plan.disclosures)
    details["disclosure_ok"] = disclosure_ok

    # 7. Outcome: the plan would produce the reference end state.
    passed = (
        intent_score == 1.0
        and not safety_violation
        and not case_forbidden
        and not details["missing_steps"]
        and not substitutions
        and not invalid
        and (arguments is None or arguments == 1.0)
        and (ordering is None or ordering == 1.0)
        and client_ok
        and disclosure_ok
        and not clar_required
    )
    stages = {
        "intent": intent_score,
        "decomposition": decomposition,
        "tool_selection": tool_selection,
        "arguments": arguments,
        "ordering": ordering,
        "efficiency": efficiency,
        "outcome": 1.0 if passed else 0.0,
    }
    return CaseScore(case["id"], stages, passed, safety_violation, details)
