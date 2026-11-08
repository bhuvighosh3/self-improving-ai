"""Model-authored content assembled into a server-owned six-section document."""

from copy import deepcopy
from typing import Literal

from pydantic import Field, create_model

from self_improving_ai.agents.briefing.workflow_models import AgentWork, ContextChange, StrictModel

CONTRACT_VERSION = "content-v4-workspace-integration"
SECTIONS = {
    "overview": "Client Overview", "changes": "Recent Changes & Requests",
    "portfolio": "Portfolio Highlights", "priorities": "Discussion Priorities",
    "actions": "Open Actions", "confirm": "Items to Confirm",
}


def work_schema(evidence: dict, calculations: list):
    """The writer selects evidence and writes content; it never invents graph IDs."""
    source = Literal[tuple(sorted(s["id"] for s in evidence["sources"]))]
    calc_ids = tuple(sorted(r["id"] for r in calculations))
    calc_field = (list[Literal[calc_ids]], Field(default_factory=list)) if calc_ids else (
        list[str], Field(default_factory=list, max_length=0))
    claim = create_model("ContentClaim", __base__=StrictModel,
        text=(str, Field(min_length=1, max_length=1500)),
        kind=(Literal["fact", "calculation", "judgment", "unknown"], ...),
        source_ids=(list[source], ...), calculation_ids=calc_field,
        rationale=(str, ""), uncertainty=(str, ""))
    item = create_model("ContentItem", __base__=claim,
        title=(str, Field(min_length=1, max_length=200)), why=(str, ""), question=(str, ""))
    agenda = create_model("AgendaContent", __base__=item,
        why=(str, Field(min_length=1, max_length=500)), question=(str, Field(min_length=1, max_length=500)))
    sections = create_model("SixSectionContent", __base__=StrictModel, **{
        key: (list[agenda if key == "priorities" else item], Field(min_length=1, max_length=20))
        for key in SECTIONS})
    change = create_model("SourcedChange", __base__=ContextChange,
                          source_ids=(list[source], Field(min_length=2)))
    finding = create_model("ContentFinding", __base__=StrictModel,
        claim=(str, ...), origin=(Literal["routine", "client_change", "investment_service_change"], ...),
        source_ids=(list[source], Field(min_length=1)), rationale=(str, Field(min_length=1)),
        uncertainty=(str, Field(min_length=1)), priority=(Literal["urgent", "important", "routine"], ...),
        question=(str, ...))
    return create_model("MeetingContent", __base__=StrictModel,
        change_status=(Literal["changed", "unchanged", "insufficient_information"], ...),
        context_summary=(str, ...), changes=(list[change], Field(default_factory=list)),
        findings=(list[finding], Field(min_length=1)), sections=(sections, ...),
        client_agenda=(list[str], Field(min_length=1)))


def assemble_work(content: dict) -> dict:
    """Generate IDs and links without changing the model's assertions."""
    result = deepcopy(content)
    claims, sections = [], []
    for section_id, title in SECTIONS.items():
        items = []
        for index, authored in enumerate(content["sections"][section_id], 1):
            item_id = f"{section_id}-{index}"
            claim_id = f"CLAIM-{item_id}"
            claims.append({key: authored[key] for key in (
                "text", "kind", "source_ids", "calculation_ids", "rationale", "uncertainty")} | {"id": claim_id})
            items.append({"id": item_id, "title": authored["title"], "text": authored["text"],
                "source_ids": list(authored["source_ids"]),
                "claim_ids": [claim_id], "why": authored.get("why", ""),
                "question": authored.get("question", ""), "priority": index if section_id == "priorities" else None})
        sections.append({"id": section_id, "title": title, "items": items})
    result.update(sections=sections, claims=claims, findings=[
        {**finding, "id": f"FINDING-{i}"} for i, finding in enumerate(content["findings"], 1)])
    return AgentWork.model_validate(result).model_dump()


def content_from_work(work: dict) -> dict:
    """Represent a valid canonical draft as content for targeted revision."""
    result = {key: deepcopy(value) for key, value in work.items() if key not in {"sections", "claims"}}
    claims = {claim["id"]: claim for claim in work["claims"]}
    if any(len(item["claim_ids"]) != 1 for section in work["sections"] for item in section["items"]):
        raise ValueError("Content revision requires one atomic claim per item")
    result["findings"] = [{k: v for k, v in f.items() if k != "id"} for f in work["findings"]]
    result["sections"] = {section["id"]: [{
        "title": item["title"], "text": item["text"], "why": item.get("why", ""),
        "question": item.get("question", ""), **{
            k: v for k, v in claims[item["claim_ids"][0]].items() if k not in {"id", "text"}},
    } for item in section["items"]] for section in work["sections"]}
    return result
