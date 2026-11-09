"""One checked, persisted B workflow for Calendar, Meeting Prep and Copilot."""

import asyncio
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field

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


async def prepare_brief(request, *, as_of=None, store=None, offline_generator=None):
    from self_improving_ai.agents.briefing.runtime import generate_agent_brief
    from self_improving_ai.agents.briefing.service import generate_meeting_brief
    from self_improving_ai.tools.briefing.workspace_sources import (
        client_mail_snapshot,
        operational_scope,
    )

    scope = nullcontext()
    if as_of is not None:
        cutoff = min(as_of, request.meeting_date.isoformat())
        records = await asyncio.to_thread(client_mail_snapshot, request.client_id, cutoff)
        scope = operational_scope(request.client_id, cutoff, ai_mode=request.mode == "agent", records=records)
    with scope:
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
        await asyncio.to_thread((store if store is not None else DraftStore()).create, brief)
        return brief
