from __future__ import annotations

from datetime import date, datetime, time
import datetime as dt

from pydantic import BaseModel, Field
from typing import Literal


class BriefingRequest(BaseModel):
    request_text: str
    client_id: str = ""
    meeting_date: str = ""


class BriefingResult(BaseModel):
    briefing_text: str = Field(description="The one-page client meeting briefing")
    sources_used: list[str] = Field(default_factory=list)
    compliance_flags: list[str] = Field(default_factory=list)


class MeetingBriefRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=60)
    meeting_date: date
    meeting_time: time
    focus: str = Field(min_length=3, max_length=500)
    meeting_type: Literal["quarterly_review", "annual_review", "goal_review"] = "quarterly_review"
    mode: Literal["simulation", "agent"] = "simulation"


class BriefItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=1500)
    source_ids: list[str] = Field(max_length=20)
    why: str = Field(default="", max_length=500)
    question: str = Field(default="", max_length=500)


class BriefSection(BaseModel):
    title: str = Field(max_length=100)
    items: list[BriefItem] = Field(max_length=20)


class BriefSource(BaseModel):
    id: str = Field(max_length=60)
    title: str = Field(max_length=200)
    date: dt.date | None = None


class BriefNews(BaseModel):
    id: str = Field(max_length=60)
    headline: str = Field(max_length=250)
    relevance: str = Field(max_length=500)


class BriefDocument(BaseModel):
    client_id: str = Field(max_length=60)
    client_name: str = Field(max_length=200)
    contact: str = Field(max_length=200)
    meeting_date: date
    meeting_time: time
    focus: str = Field(max_length=500)
    data_as_of: date
    sections: list[BriefSection] = Field(min_length=6, max_length=6)
    sources: list[BriefSource] = Field(max_length=60)
    news: list[BriefNews] = Field(max_length=3)


class BriefExportRequest(BaseModel):
    brief: BriefDocument
    reviewed_at: datetime | None = None
    revision: int = Field(default=1, ge=1, le=100000)
    edited: bool = False
