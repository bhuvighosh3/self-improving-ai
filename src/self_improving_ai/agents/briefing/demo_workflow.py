"""Observable deterministic counterpart of the three skills for offline demonstrations."""

from copy import deepcopy
import json

from self_improving_ai.agents.briefing.checks import check_work
from self_improving_ai.tools.briefing.context import prepare_context
from self_improving_ai.tools.briefing.calculator import calculate
from self_improving_ai.agents.briefing.ledger import register_calculation


def enrich_demo(brief: dict, meeting_type: str) -> dict:
    evidence = prepare_context(brief["client_id"], meeting_type, brief["focus"])
    existing = {s["id"]: {**s, "client_id": brief["client_id"], "read_state": "full"}
                for s in brief["sources"]}
    existing.update({s["id"]: s for s in evidence["sources"]})
    evidence["sources"] = list(existing.values())
    sections = deepcopy(brief["sections"])
    by_id = {s["id"]: s for s in sections}
    calculations, item_calculations = [], {}
    holdings = json.loads(existing["HOLDINGS"]["content"])
    positions = [(a, h, p) for a, account in enumerate(holdings["accounts"])
                 for h, p in enumerate(account["holdings"])]

    def operand(field, sid="HOLDINGS"):
        return {"source_id": sid, "field": field, "currency": "USD"}

    def compute(operation, operands):
        result = calculate(operation, operands, evidence["sources"])
        register_calculation(evidence, calculations, result)
        evidence["trace"].append({"tool": "calculate_metrics",
                                  "arguments": {"operation": operation, "operands": operands},
                                  "result": result})
        return result["id"]

    if positions:
        total_id = compute("sum", [operand(f"accounts.{a}.holdings.{h}.market_value") for a, h, _ in positions])
        item_calculations["household"] = [total_id]
        for item in by_id["portfolio"]["items"]:
            if item["id"].startswith("position-"):
                for a, h, p in positions:
                    account = holdings["accounts"][a]["account_id"]
                    if item["title"] == f"{p['ticker']} · {account}":
                        item_calculations[item["id"]] = [compute("difference", [
                            operand(f"accounts.{a}.holdings.{h}.market_value"),
                            operand(f"accounts.{a}.holdings.{h}.cost_basis")])]
            if item["id"] == "concentration":
                ticker = item["text"].split(":", 1)[0]
                numerator = compute("sum", [operand(f"accounts.{a}.holdings.{h}.market_value")
                                            for a, h, p in positions if p["ticker"] == ticker])
                ratio = compute("ratio", [operand("value", numerator), operand("value", total_id)])
                item_calculations[item["id"]] = [numerator, ratio]
    changes, comparisons = [], []
    for event in evidence["trace"]:
        if event["tool"] != "read_source" or event["result"]["status"] != "ok":
            continue
        record = event["result"]["record"]
        comparison = record.get("comparison")
        if comparison and comparison["baseline_source_id"] in existing:
            comparisons.append({"field": comparison["field"], "old_value": comparison["old"],
                                "new_value": comparison["new"],
                                "source_ids": [comparison["baseline_source_id"], record["id"]],
                                "certainty": comparison["certainty"]})
            changes.append({"id": record["id"], "title": comparison["field"],
                            "text": f"Previously: {comparison['old']}. Updated intention: {comparison['new']}.",
                            "source_ids": [comparison["baseline_source_id"], record["id"]]})
    by_id["changes"]["items"] = changes + by_id["changes"]["items"]
    if changes:
        update = changes[0]
        insert_at = 1 if by_id["priorities"]["items"][0]["id"] == "priority-focus" else 0
        by_id["priorities"]["items"].insert(insert_at, {
            "id": "workflow-change", "title": "Confirm the changed goal and funding",
            "text": update["text"], "source_ids": update["source_ids"],
            "why": "The client explicitly raised a changed intention after the prior meeting.",
            "question": "What amount, payment date and external funding can the client confirm?"})
    complete = all(value in {"checked", "ok"} for value in evidence["coverage"].values())
    by_id["confirm"]["items"].append({
        "id": "workflow-coverage", "title": "Preparation coverage",
        "text": ("The scoped synthetic review confirms no significant changes; confirm current facts at the meeting."
                 if complete else "Available records do not establish complete client, investment and service history. "
                 "Missing updates are not evidence of no change. Confirm remaining circumstances with the client."),
        "source_ids": []})
    by_id["priorities"]["items"].append({
        "id": "workflow-routine", "title": "Routine meeting review",
        "text": "; ".join(evidence["routine_items"]), "source_ids": ["PROFILE", "TASKS"],
        "why": "Routine goal progress and unfinished commitments remain relevant even without confirmed changes.",
        "question": "Which goal assumptions or service commitments need confirmation?"})
    findings, claims = [], []
    for section in sections:
        for item in section["items"]:
            cid = "CLAIM-" + section["id"] + "-" + item["id"]
            item["claim_ids"] = [cid]
            kind = ("calculation" if item["id"] in item_calculations else
                    "unknown" if section["id"] == "confirm" or not item["source_ids"] else
                    "judgment" if section["id"] == "priorities" else "fact")
            claims.append({"id": cid, "text": item["text"], "kind": kind,
                           "source_ids": item["source_ids"], "calculation_ids": item_calculations.get(item["id"], []),
                           "rationale": item.get("why", ""),
                           "uncertainty": "Synthetic dated records; confirm current circumstances."})
            if section["id"] == "priorities":
                findings.append({"id": "FINDING-" + item["id"], "claim": item["title"],
                    "origin": "client_change" if item["id"] == "workflow-change" else "routine",
                    "source_ids": item["source_ids"] or ["PROFILE"],
                    "rationale": item["why"], "uncertainty": "Coverage is limited to available fixtures.",
                    "priority": "important" if item["id"] == "workflow-change" else "routine",
                    "question": item["question"]})
    work = {"change_status": "changed" if changes else "unchanged" if complete else "insufficient_information",
            "changes": comparisons,
            "context_summary": "Prior context and subsequent available records reviewed; coverage remains limited.",
            "findings": findings, "claims": claims, "sections": sections,
            "client_agenda": [i["title"] for i in by_id["priorities"]["items"]]}
    report = check_work(work, evidence, calculations)
    report["semantic_support"] = "not_model_reviewed_offline_demo"
    return {**brief, "sections": sections, "sources": evidence["sources"],
            "meeting_type": meeting_type, "workflow": {"version": "v1", "work": work,
            "evidence": evidence, "calculations": calculations, "quality": report,
            "limitations": ["Offline rules, not autonomous LLM analysis"],
            "trace": evidence["trace"]}}
