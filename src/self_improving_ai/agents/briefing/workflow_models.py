"""Validated, observable work products; never private model reasoning."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Finding(StrictModel):
    id: str
    claim: str
    origin: Literal["routine", "client_change", "investment_service_change"]
    source_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    uncertainty: str = Field(min_length=1)
    priority: Literal["urgent", "important", "routine"]
    question: str


class Claim(StrictModel):
    id: str
    text: str
    kind: Literal["fact", "calculation", "judgment", "unknown"]
    source_ids: list[str]
    calculation_ids: list[str]
    rationale: str
    uncertainty: str


class ContextChange(StrictModel):
    field: str
    old_value: str
    new_value: str
    source_ids: list[str] = Field(min_length=2)
    certainty: Literal["confirmed", "tentative", "conflicting"]


class DraftItem(StrictModel):
    id: str
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=1500)
    source_ids: list[str]
    claim_ids: list[str] = Field(min_length=1)
    why: str = ""
    question: str = ""
    priority: int | None = None


class DraftSection(StrictModel):
    id: Literal["overview", "changes", "portfolio", "priorities", "actions", "confirm"]
    title: str
    items: list[DraftItem] = Field(max_length=20)


class AgentWork(StrictModel):
    """The same agent applies three skills and returns independently checkable work."""

    change_status: Literal["changed", "unchanged", "insufficient_information"]
    context_summary: str
    changes: list[ContextChange] = Field(default_factory=list)
    findings: list[Finding] = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    sections: list[DraftSection] = Field(min_length=6, max_length=6)
    client_agenda: list[str] = Field(min_length=1)


class ReviewRequest(BaseModel):
    brief: dict
    revision: int = Field(ge=1)
    expected_revision: int = Field(default=1, ge=1)
    decision: Literal["approve", "revise"]
    feedback: str = Field(default="", max_length=3000)


class CheckRequest(BaseModel):
    brief: dict
