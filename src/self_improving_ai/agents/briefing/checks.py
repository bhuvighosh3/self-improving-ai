"""Independent objective checks; semantic evidence support needs a separate reviewer."""

from pydantic import ValidationError

from self_improving_ai.agents.briefing.workflow_models import AgentWork
from self_improving_ai.tools.briefing.calculator import calculate

SECTION_IDS = {"overview", "changes", "portfolio", "priorities", "actions", "confirm"}


def check_work(work: dict, evidence: dict, calculations: list[dict]) -> dict:
    findings = []

    def flag(code, location, reason):
        findings.append({"code": code, "location": location, "reason": reason,
                         "severity": "blocking"})

    try:
        parsed = AgentWork.model_validate(work)
    except ValidationError as exc:
        return {"verdict": "revise", "findings": [{"code": "SCHEMA", "severity": "blocking",
                "location": "work", "reason": str(exc)}], "reviewer": "objective_rules"}
    sources = {s["id"]: s for s in evidence["sources"]}
    if any(s.get("client_id") != evidence["client_id"] for s in sources.values()):
        flag("CLIENT_MISMATCH", "sources", "Source belongs to a different client")
    for sid, source in sources.items():
        if source.get("recorded_at", source.get("date") or "")[:10] > evidence["as_of"]:
            flag("FUTURE_SOURCE", sid, "Source was not visible at the cutoff")
    calc_ids = set()
    for record in calculations:
        try:
            verified = calculate(record["operation"], record["operands"], evidence["sources"])
            if verified != record:
                raise ValueError("Calculation differs from original inputs")
            derived = sources.get(record["id"])
            if derived and derived.get("kind") == "calculation":
                import json

                if json.loads(derived["content"]) != record:
                    raise ValueError("Derived source differs from actual calculation")
            calc_ids.add(record["id"])
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            flag("CALCULATION", record.get("id", "unknown"), str(exc))
    claims = {c.id: c for c in parsed.claims}
    if len(claims) != len(parsed.claims):
        flag("DUPLICATE_CLAIM", "claims", "Claim IDs must be unique")
    if {s.id for s in parsed.sections} != SECTION_IDS:
        flag("SECTIONS", "sections", "Six distinct sections are required")
    for claim in parsed.claims:
        if claim.kind != "unknown" and not claim.source_ids:
            flag("MISSING_EVIDENCE", claim.id, "Claim needs original sources")
        if claim.kind == "calculation" and not claim.calculation_ids:
            flag("MISSING_CALCULATION", claim.id, "Derived number needs a registered calculation")
        if claim.kind == "judgment" and (not claim.rationale.strip() or not claim.uncertainty.strip()):
            flag("JUDGMENT_BOUNDARY", claim.id, "Judgment needs rationale and uncertainty")
        if set(claim.source_ids) - sources.keys():
            flag("UNKNOWN_SOURCE", claim.id, "Claim references an unread source")
        if set(claim.calculation_ids) - calc_ids:
            flag("UNKNOWN_CALCULATION", claim.id, "Claim references an unregistered calculation")
    for finding in parsed.findings:
        if set(finding.source_ids) - sources.keys():
            flag("UNKNOWN_SOURCE", finding.id, "Finding references an unread source")
    for change in parsed.changes:
        if set(change.source_ids) - sources.keys():
            flag("UNKNOWN_SOURCE", change.field, "Comparison references an unread source")
        if change.old_value == change.new_value:
            flag("IDENTICAL_COMPARISON", change.field, "Identical values are not a change")
    if parsed.change_status == "changed" and not parsed.changes:
        flag("MISSING_COMPARISON", "changes", "Changed status needs an old/new comparison")
    for section in parsed.sections:
        ids = set()
        for item in section.items:
            if section.id == "priorities" and (not item.why.strip() or not item.question.strip()):
                flag("AGENDA_PURPOSE", item.id, "Agenda topic needs rationale and a concrete question")
            if item.id in ids:
                flag("DUPLICATE_ITEM", item.id, "Item IDs must be unique in a section")
            ids.add(item.id)
            if set(item.source_ids) - sources.keys() or set(item.claim_ids) - claims.keys():
                flag("UNRESOLVED_REFERENCE", item.id, "Item has unresolved evidence or claims")
    if parsed.change_status == "unchanged" and any(
        status not in {"checked", "ok"} for status in evidence["coverage"].values()
    ):
        flag("MISSING_IS_NOT_UNCHANGED", "change_status", "Incomplete coverage cannot establish no change")
    if parsed.change_status == "changed" and not any(f.origin != "routine" for f in parsed.findings):
        flag("CHANGE_WITHOUT_FINDING", "findings", "Changed status needs a supported change finding")
    return {"verdict": "revise" if findings else "pass", "findings": findings,
            "reviewer": "objective_rules", "semantic_support": "requires_independent_review"}
