"""Calendar CRUD endpoints backed by Cloud Firestore."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from self_improving_ai.workspace_store import get_store, invalidate_snapshots


class StoreProxy:
    """Resolve credentials only when the shared store is actually used."""
    def __getattr__(self, name):
        def call(*args, **kwargs):
            try:
                return getattr(get_store("calendar"), name)(*args, **kwargs)
            except LookupError:
                raise
            except Exception as exc:
                raise HTTPException(503, "Workspace storage unavailable. Check the selected storage configuration.") from exc
        return call

router = APIRouter(prefix="/api/calendar", tags=["calendar"])
_store = StoreProxy()

_EVENT_TYPES = Literal[
    "general_meeting", "quarterly_review", "follow_up", "portfolio_review", "annual_review", "goal_review"
]


class CalendarEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=30)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    type: _EVENT_TYPES = "general_meeting"
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


def validate_event(record):
    from self_improving_ai.tools.briefing.crm import get_client_profile
    try:
        start = datetime.fromisoformat(record["date"] + "T" + record["start_time"])
        end = datetime.fromisoformat(record["date"] + "T" + record["end_time"])
        if end <= start:
            raise ValueError("End time must be after start time")
        if not record["title"].strip():
            raise ValueError("Provide a meeting title")
        if "error" in get_client_profile(record["client_id"]):
            raise ValueError("Select a known client")
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, "Provide a valid date, an end time after start time, and a known client.") from exc


@router.get("/events")
async def list_events(year: int = Query(2026, ge=1900, le=9998), month: int = Query(11, ge=1, le=12)):
    return await run_in_threadpool(_store.list_events, year, month)


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    try:
        return await run_in_threadpool(_store.get_event, event_id)
    except LookupError:
        raise HTTPException(404, "Event not found")


@router.post("/events", status_code=201)
async def create_event(body: CalendarEventCreate):
    await run_in_threadpool(validate_event, body.model_dump())
    result = await run_in_threadpool(_store.create_event, body.model_dump())
    invalidate_snapshots()
    return result


@router.put("/events/{event_id}")
async def update_event(event_id: str, body: CalendarEventUpdate, request: Request):
    try:
        current = await run_in_threadpool(_store.get_event, event_id)
        await run_in_threadpool(validate_event, {**current, **body.model_dump(exclude_none=True)})
        result = await run_in_threadpool(_store.update_event, event_id, body.model_dump(exclude_none=True))
        invalidate_snapshots()
        monitor = getattr(request.app.state, "preparations", None)
        if monitor is not None:
            await monitor.meeting_changed(event_id)
        return result
    except LookupError:
        raise HTTPException(404, "Event not found")


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: str):
    try:
        await run_in_threadpool(_store.delete_event, event_id)
        invalidate_snapshots()
    except LookupError:
        raise HTTPException(404, "Event not found")
