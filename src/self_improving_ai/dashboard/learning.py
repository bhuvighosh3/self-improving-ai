"""Feedback and editing endpoints for the existing Meeting Prep workflow."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from google.genai.errors import APIError
from pydantic import BaseModel, ConfigDict, Field

from self_improving_ai.agents.briefing.learning import LABELS, LearningStore, metadata
from self_improving_ai.agents.briefing.review import check_draft
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.briefing.suggestions import suggestions
from self_improving_ai.agents.briefing.workflow_models import DraftSection
from self_improving_ai.workspace_store import workspace_snapshot

router = APIRouter(prefix="/api/meeting-learning", tags=["meeting learning"])


def learning_clock():
    from self_improving_ai.dashboard.app import app
    monitor = getattr(app.state, "preparations", None)
    if monitor is not None:
        with monitor.db() as db:
            return json.loads(db.execute("SELECT state FROM calendar_simulation WHERE id=1").fetchone()[0])["now"]
    return datetime.now(ZoneInfo("America/New_York")).isoformat()


@router.get("/suggestions")
async def meeting_suggestions():
    try:
        records = await asyncio.to_thread(workspace_snapshot, "calendar")
        return await asyncio.to_thread(suggestions, learning_clock(), records)
    except Exception as exc:
        raise HTTPException(503, "Meeting suggestions are unavailable. Your calendar is unchanged.") from exc


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str):
    records = await asyncio.to_thread(workspace_snapshot, "calendar")
    choices = await asyncio.to_thread(suggestions, learning_clock(), records)
    suggestion = next((s for s in choices if s["id"] == suggestion_id), None)
    if not suggestion:
        raise HTTPException(409, "This suggestion changed. Refresh the calendar.")
    await asyncio.to_thread(LearningStore().action, suggestion_id, suggestion["client_id"],
                            "dismissed", {"source_brief_id": suggestion["source_brief_id"]})
    return {"status": "dismissed"}


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[DraftSection] = Field(min_length=6, max_length=6)
    expected_revision: int = Field(ge=1)
    remember: bool = True


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    rating: Literal["helpful", "needs_work"]
    reason: Literal["concise", "actions_first", "more_context", "incorrect", "other"] | None = None
    note: str = Field(default="", max_length=1000)
    follow_up: bool | None = None


def state(brief_id):
    record = DraftStore().get(brief_id)
    brief = record["brief"]
    learning = LearningStore()
    events = learning.events(brief_id=brief_id)
    memory = learning.memory(brief["client_id"]).load()
    with DraftStore().connect() as db:
        reviewed = db.execute("SELECT created_at FROM meeting_reviews WHERE id=? AND revision=? "
                              "AND decision='approve' ORDER BY rowid DESC LIMIT 1", (brief_id, record["revision"])).fetchone()
    return {**record, "reviewed_at": reviewed[0] if reviewed and record["status"] == "approve" else None,
            "metadata": brief.get("learning", metadata(brief)), "history": events,
            "feedback": next((e["payload"] for e in events if e["kind"] == "feedback"), None),
            "preferences": [{"key": key, "label": LABELS[key], **value}
                            for key, value in memory.preferences.items() if key in LABELS],
            "memory_version": memory.version}


@router.get("/briefs/{brief_id}")
async def brief_learning(brief_id: str):
    try:
        return await asyncio.to_thread(state, brief_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


def checked_sections(submitted, original):
    """Allow text edits only; the server owns identity, evidence and graph links."""
    if [s["id"] for s in submitted] != [s["id"] for s in original["sections"]]:
        raise ValueError("Keep the six original sections in order.")
    sections = deepcopy(original["sections"])
    for source, retained in zip(submitted, sections, strict=True):
        if [i["id"] for i in source["items"]] != [i["id"] for i in retained["items"]]:
            raise ValueError("Edit the existing items without changing their IDs.")
        for incoming, item in zip(source["items"], retained["items"], strict=True):
            if incoming["source_ids"] != item["source_ids"] or incoming["claim_ids"] != item["claim_ids"]:
                raise ValueError("Original evidence references cannot be changed.")
            for field in ("title", "text", "why", "question"):
                if field in item or incoming.get(field):
                    item[field] = incoming.get(field, "")
            if not item["title"].strip() or not item["text"].strip():
                raise ValueError("Each item needs a title and details.")
    return sections


@router.post("/briefs/{brief_id}/edits")
async def save_edits(brief_id: str, body: EditRequest):
    try:
        from self_improving_ai.dashboard.app import _require_current_calendar
        original = await asyncio.to_thread(DraftStore().get, brief_id)
        await asyncio.to_thread(_require_current_calendar, original["brief"])
        if original["revision"] != body.expected_revision:
            raise ValueError("This brief changed elsewhere. Reopen it before saving.")
        sections = checked_sections([s.model_dump() for s in body.sections], original["brief"])
        if "evidence" not in original["brief"].get("workflow", {}):
            raise ValueError("This older brief has no retained evidence. Prepare it again before editing.")
        try:
            quality = await asyncio.wait_for(check_draft({**original["brief"], "sections": sections}, original["brief"]), 90)
        except (RuntimeError, TimeoutError, ValueError, APIError):
            quality = {"verdict": "unavailable", "findings": [],
                       "semantic_support": "not_checked", "message": "Changes saved; automatic review was unavailable. Save again to retry. Nothing was learned from these edits."}
        await asyncio.to_thread(LearningStore().save_edits, original, sections,
                                body.expected_revision, quality, body.remember)
        return await asyncio.to_thread(state, brief_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/briefs/{brief_id}/feedback")
async def save_feedback(brief_id: str, body: FeedbackRequest):
    try:
        record = await asyncio.to_thread(DraftStore().get, brief_id)
        if body.revision != record["revision"]:
            raise ValueError("The brief changed. Reopen it before giving feedback.")
        brief = record["brief"]
        store = LearningStore()
        previous = next((e for e in store.events(brief_id=brief_id) if e["kind"] == "feedback"), None)
        reason = LABELS.get(body.reason, "Check accuracy" if body.reason == "incorrect" else "Needs improvement")
        payload = {**body.model_dump(), "summary": "Helpful" if body.rating == "helpful" else reason}
        # A one-click rating does not erase an earlier scheduling request.
        if body.follow_up is None:
            payload["follow_up"] = bool(previous and previous["payload"].get("follow_up"))
        if previous and all(previous["payload"].get(k) == v for k, v in payload.items()):
            return await asyncio.to_thread(state, brief_id)
        event_id = await asyncio.to_thread(store.record, brief, "feedback", record["revision"], payload)
        if body.rating == "needs_work" and body.reason in LABELS:
            await asyncio.to_thread(store.remember, brief, [body.reason], event_id, "Advisor feedback: " + reason)
        return await asyncio.to_thread(state, brief_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/briefs/{brief_id}/preferences/{key}")
async def forget_preference(brief_id: str, key: str):
    try:
        record = await asyncio.to_thread(DraftStore().get, brief_id)
        if key not in LABELS:
            raise ValueError("Unknown preference")
        await asyncio.to_thread(LearningStore().forget, record["brief"]["client_id"], key)
        return await asyncio.to_thread(state, brief_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
