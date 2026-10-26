from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioRequest(BaseModel):
    request_text: str
    client_id: str = ""
    account_id: str = ""


class PortfolioResult(BaseModel):
    answer_value: float = Field(description="The numeric answer")
    unit: str = Field(description="Unit of the answer (e.g., USD, percent, probability)")
    reasoning: str = Field(description="Step-by-step reasoning")
