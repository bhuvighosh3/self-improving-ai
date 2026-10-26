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
