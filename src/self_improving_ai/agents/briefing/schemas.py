from __future__ import annotations

from pydantic import BaseModel, Field


class BriefingRequest(BaseModel):
    request_text: str
    client_id: str = ""
    meeting_date: str = ""


class BriefingResult(BaseModel):
    briefing_text: str = Field(description="The one-page client meeting briefing")
    sources_used: list[str] = Field(default_factory=list)
    compliance_flags: list[str] = Field(default_factory=list)
