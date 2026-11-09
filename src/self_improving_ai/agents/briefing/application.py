"""One checked, persisted B workflow for Calendar, Meeting Prep and Copilot."""

import asyncio
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from weakref import WeakKeyDictionary

from google.genai.errors import APIError

from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.config import settings


class BriefingPreparationError(RuntimeError):
    """The delegated B workflow already handled its own model fallback."""


@dataclass
class BriefingRequestScope:
    as_of: str | None
    tasks: dict = field(default_factory=dict)
    briefs: dict = field(default_factory=dict)


_request_scope = ContextVar("briefing_request_scope", default=None)


def current_request_scope():
    return _request_scope.get()


@contextmanager
def briefing_request_scope(as_of=None):
    """Deduplicate within one HTTP request, never across later advisor requests."""
    scope = BriefingRequestScope(as_of=as_of)
    token = _request_scope.set(scope)
    try:
        yield scope
    finally:
        _request_scope.reset(token)


_workflow_locks = WeakKeyDictionary()


async def prepare_brief(request, *, as_of=None, store=None, offline_generator=None):
    # Serialize requests for the same meeting in this process, including double clicks.
    loop_locks = _workflow_locks.setdefault(asyncio.get_running_loop(), {})
    key = (str(settings.db_path), request.client_id, str(request.meeting_date), str(request.meeting_time))
    entry = loop_locks.setdefault(key, {"lock": asyncio.Lock(), "users": 0})
    entry["users"] += 1
    try:
        async with entry["lock"]:
            return await _prepare_brief(request, as_of=as_of, store=store, offline_generator=offline_generator)
    finally:
        entry["users"] -= 1
        if entry["users"] == 0:
            loop_locks.pop(key, None)


async def _prepare_brief(request, *, as_of=None, store=None, offline_generator=None):
    from self_improving_ai.agents.briefing.runtime import generate_agent_brief
    from self_improving_ai.agents.briefing.service import generate_meeting_brief
    from self_improving_ai.tools.briefing.workspace_sources import (
        client_mail_snapshot,
        operational_scope,
    )

    store = store if store is not None else DraftStore()
    scope = nullcontext()
    appointment = None
    if as_of is not None:
        cutoff = min(as_of, request.meeting_date.isoformat())
        records = await asyncio.to_thread(client_mail_snapshot, request.client_id, cutoff)
        scope = operational_scope(request.client_id, cutoff, ai_mode=request.mode == "agent", records=records)
    with scope:
        if as_of is not None:
            from self_improving_ai.calendar_adapter import normalize_event
            from self_improving_ai.tools.briefing.workspace_sources import current_scope
            from self_improving_ai.workspace_store import (
                get_store,
                invalidate_snapshots,
                workspace_snapshot,
            )

            events = await asyncio.to_thread(workspace_snapshot, "calendar")
            matches = [event for event in events if event.get("client_id") == request.client_id
                       and event["date"] == request.meeting_date.isoformat()
                       and event["start_time"][:5] == request.meeting_time.strftime("%H:%M")
                       and (not request.calendar_event_id or event["id"] == request.calendar_event_id)]
            if not matches and not request.calendar_event_id:
                from self_improving_ai.tools.briefing.crm import get_client_profile
                start = datetime.combine(request.meeting_date, request.meeting_time)
                end = min(start + timedelta(minutes=45), start.replace(hour=23, minute=59))
                record = {"title": request.focus.strip()[:200], "client_id": request.client_id,
                    "date": request.meeting_date.isoformat(), "start_time": start.strftime("%H:%M"),
                    "end_time": end.strftime("%H:%M"), "type": "general_meeting",
                    "notes": request.focus.strip(), "location": ""}
                profile = await asyncio.to_thread(get_client_profile, request.client_id)
                if "error" in profile or end <= start or not record["title"]:
                    raise ValueError("Provide a known client, meeting focus, and valid meeting time.")
                matches = [await asyncio.to_thread(get_store("calendar").create_event, record)]
                invalidate_snapshots()
            if len(matches) != 1:
                raise ValueError("The calendar appointment changed or is ambiguous. Reopen the current meeting before preparing it.")
            appointment = normalize_event(matches[0], {}, current_scope()["revision"])
            request = request.model_copy(update={"calendar_event_id": appointment["id"]})
            retained = await asyncio.to_thread(store.current_calendar_brief, appointment, request.mode)
            if retained and retained["focus"] == request.focus.strip() and retained["data_as_of"] == cutoff:
                return retained
        if appointment:
            await asyncio.to_thread(store.begin_calendar_preparation, appointment, request)
        try:
            if request.mode == "agent":
                try:
                    brief = await asyncio.wait_for(generate_agent_brief(request), timeout=180)
                except APIError as primary:
                    fallback = settings.agent_model_fallback
                    if primary.code not in (503, 504) or not fallback or fallback == settings.agent_model:
                        raise
                    brief = await asyncio.wait_for(generate_agent_brief(request, model=fallback), timeout=180)
                    brief["workflow"]["model_fallback_from"] = settings.agent_model
            else:
                brief = await asyncio.to_thread(offline_generator or generate_meeting_brief, request)
            if appointment:
                # An edit during generation must never publish the previous appointment.
                current = await asyncio.to_thread(get_store("calendar").get_event, appointment["id"])
                latest_mail = await asyncio.to_thread(client_mail_snapshot, request.client_id, cutoff)
                with operational_scope(request.client_id, cutoff, records=latest_mail) as latest:
                    current = normalize_event(current, {}, latest["revision"])
                if current["version"] != appointment["version"]:
                    raise ValueError("The meeting changed during preparation. Its updated brief will be prepared instead.")
                brief["calendar_event"] = {**appointment, "client_name": brief["client_name"]}
            await asyncio.to_thread(store.create, brief)
            return brief
        except BaseException as exc:
            if appointment:
                await asyncio.to_thread(store.fail_calendar_preparation, appointment, request.mode, getattr(exc, "briefing_run_id", None))
            raise
