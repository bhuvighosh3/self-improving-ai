from __future__ import annotations

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step_number: int
    tool_name: str
    description: str
    arguments: dict = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)


class AdvisorRequest(BaseModel):
    request_text: str
    advisor_id: str = ""
    client_id: str = ""


class OrchestratorResult(BaseModel):
    intent: str = Field(description="The classified intent of the advisor request")
    plan: list[PlanStep] = Field(default_factory=list, description="Ordered execution plan")
    final_answer: str = Field(description="The synthesized answer to the advisor")
    agents_called: list[str] = Field(default_factory=list)


# Structured plan used by the planner, the scorer and the learning loop.
# Arguments are name/value string pairs because Gemini structured output does not support
# free-form dictionaries; use PlannedStep.arg_dict() to read them.


class StepArg(BaseModel):
    name: str
    value: str


class PlannedStep(BaseModel):
    id: int = Field(description="Step number, starting at 1")
    tool: str = Field(description="Exact tool or agent name from the catalog")
    args: list[StepArg] = Field(default_factory=list)
    depends_on: list[int] = Field(
        default_factory=list, description="Ids of earlier steps whose output this step needs"
    )
    purpose: str = ""

    def arg_dict(self) -> dict[str, str]:
        return {a.name: a.value for a in self.args}


class OrchestratorPlan(BaseModel):
    intent: str = Field(description="One intent label from the taxonomy")
    interpretation: str = Field(
        default="", description="One sentence restating what the advisor is asking for"
    )
    client_ids: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""
    steps: list[PlannedStep] = Field(default_factory=list)
    disclosures: list[str] = Field(
        default_factory=list,
        description="Limitations the advisor must know (missing tools, coverage gaps, refusals)",
    )
