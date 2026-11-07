"""Calendar CRUD endpoints backed by Cloud Firestore."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from self_improving_ai.calendar_store import CalendarStore

router = APIRouter(prefix="/api/calendar", tags=["calendar"])
_store = CalendarStore()

_EVENT_TYPES = Literal[
    "quarterly_review", "follow_up", "portfolio_review", "annual_review", "goal_review"
]


class CalendarEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=30)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    type: _EVENT_TYPES
    notes: str = Field(default="", max_length=1000)
    location: str = Field(default="", max_length=200)


class CalendarEventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    client_id: str | None = Field(default=None, min_length=1, max_length=30)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    type: _EVENT_TYPES | None = None
    notes: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=200)


@router.get("/events")
async def list_events(year: int = 2026, month: int = 11):
    return await run_in_threadpool(_store.list_events, year, month)


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    try:
        return await run_in_threadpool(_store.get_event, event_id)
    except LookupError:
        raise HTTPException(404, "Event not found")


@router.post("/events", status_code=201)
async def create_event(body: CalendarEventCreate):
    return await run_in_threadpool(_store.create_event, body.model_dump())


@router.put("/events/{event_id}")
async def update_event(event_id: str, body: CalendarEventUpdate):
    try:
        return await run_in_threadpool(
            _store.update_event, event_id, body.model_dump(exclude_none=True)
        )
    except LookupError:
        raise HTTPException(404, "Event not found")


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: str):
    try:
        await run_in_threadpool(_store.delete_event, event_id)
    except LookupError:
        raise HTTPException(404, "Event not found")
