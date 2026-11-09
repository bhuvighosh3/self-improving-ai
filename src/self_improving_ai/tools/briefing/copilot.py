"""Bounded Copilot handoff to the same B workflow used by Meeting Prep."""

import asyncio
from typing import Literal

from google.adk.tools import ToolContext
from pydantic import ValidationError

from self_improving_ai.agents.briefing.application import (
    BriefingPreparationError,
    current_request_scope,
    prepare_brief,
)
from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest


async def meeting_briefing_agent(
    client_id: str,
    meeting_date: str,
    meeting_time: str,
    focus: str,
    tool_context: ToolContext,
    meeting_type: Literal["quarterly_review", "annual_review", "goal_review"] = "quarterly_review",
    calendar_event_id: str = "",
) -> dict:
    """Prepare and save a checked meeting draft for confirmed client/date/time/focus.

    Times are America/New_York. Resolve details from the advisor or calendar first;
    ask for missing details instead of inventing them. Returns a short summary and
    saved draft ID. The full draft opens in Meeting Prep for advisor review.
    """
    try:
        request = MeetingBriefRequest(
            client_id=client_id, meeting_date=meeting_date, meeting_time=meeting_time,
            focus=focus, meeting_type=meeting_type, calendar_event_id=calendar_event_id or None,
            mode="agent",
        )
    except ValidationError as exc:
        return {"status": "needs_confirmation", "required_fields": sorted({str(e["loc"][0]) for e in exc.errors()}),
                "message": "Confirm the client, meeting date, New York time and focus before preparing."}

    scope = current_request_scope()
    try:
        if scope is None:
            brief = await prepare_brief(request)
        else:
            key = request.model_dump_json()
            if key not in scope.tasks:
                scope.tasks[key] = asyncio.create_task(prepare_brief(request, as_of=scope.as_of))
            brief = await scope.tasks[key]
            scope.briefs[brief["id"]] = brief
    except Exception as exc:
        raise BriefingPreparationError("Meeting preparation could not complete") from exc

    sections = {section["id"]: section for section in brief["sections"]}
    overview = sections.get("overview", {}).get("items", [])
    return {
        "status": "ready", "brief_id": brief["id"], "client_id": brief["client_id"],
        "client_name": brief["client_name"][:200], "meeting_date": brief["meeting_date"],
        "meeting_time": brief["meeting_time"], "focus": brief["focus"][:160],
        "summary": overview[0]["text"][:350] if overview else "The meeting draft is ready to review.",
        "priorities": [item["title"][:100] for item in sections.get("priorities", {}).get("items", [])[:3]],
        "review_status": "draft", "next_action": "Open Meeting Brief for sources, editing and advisor review.",
    }
