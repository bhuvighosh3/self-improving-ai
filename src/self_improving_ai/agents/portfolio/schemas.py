from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PortfolioRequest(BaseModel):
    request_text: str
    client_id: str = ""
    account_id: str = ""


class PortfolioResult(BaseModel):
    """Original team schema retained for existing importers."""
    answer_value: float = Field(description="The numeric answer")
    unit: str = Field(description="Unit of the answer (e.g., USD, percent, probability)")
    reasoning: str = Field(description="Explanation of method and inputs")


class PortfolioRun(BaseModel):
    """Structured envelope used by the independent A endpoints."""
    status: Literal["success", "error"]
    run_id: str
    mode: str
    result: dict[str, Any] = Field(default_factory=dict)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    response: str = ""
