"""Offline regressions at the real ADK -> B -> dashboard boundary."""

import asyncio
import importlib
import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from google.adk import Agent, Runner
from google.adk.models.base_llm import BaseLlm
from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types
from opentelemetry.trace import NoOpTracer
from pydantic import BaseModel, Field

from self_improving_ai.agents.briefing.model import create_model
from self_improving_ai.agents.briefing.runtime import run_adk
from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.store import DraftStore

REQUEST = {"client_id": "SYNTHETIC-1", "meeting_date": "2026-11-10",
           "meeting_time": "14:00", "focus": "Confirm home purchase plans", "mode": "agent"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("This regression suite must not contact external services")
    monkeypatch.setattr("socket.socket.connect", blocked)


@pytest.fixture
def api():
    # Part A builds a client directory at import; no cloud data is needed here.
    with patch("self_improving_ai.tools.portfolio.holdings._load_households", return_value=[]):
        return importlib.import_module("self_improving_ai.dashboard.app")


def synthetic_brief():
    return {"id": "synthetic-brief", **REQUEST, "client_name": "Synthetic Client",
            "sections": [{"id": key, "title": key, "items": [
                {"title": "Confirm plans", "text": "Plans remain tentative", "source_ids": ["NOTE-1"]}
            ]} for key in ("overview", "changes", "portfolio", "priorities", "actions", "confirm")],
            "tools_called": ["get_crm_notes"], "sources": [{"id": "NOTE-1", "text": "PRIVATE_EVIDENCE" * 5000}],
            "workflow": {"quality": {"verdict": "pass"}, "evidence": {"large": "PRIVATE_EVIDENCE" * 5000}}}


class SmallOutput(BaseModel):
    summary: str


@pytest.mark.parametrize("truncated", [False, True])
async def test_finish_reason_checked_before_adk_schema_validation(truncated):
    async def provider(self, llm_request, stream=False):
        yield LlmResponse.create(types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(
                text='{"summary":"' if truncated else '{"summary":"complete"}')]),
            finish_reason=types.FinishReason.MAX_TOKENS if truncated else types.FinishReason.STOP,
        )], usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, total_token_count=120)))

    agent = Agent(name="offline_writer", model=create_model("offline-provider"),
                  generate_content_config=types.GenerateContentConfig(max_output_tokens=20),
                  instruction="Return a summary", output_schema=SmallOutput, output_key="summary")
    trace = []
    with patch.object(Gemini, "generate_content_async", provider):
        if truncated:
            with pytest.raises(RuntimeError, match="MAX_TOKENS") as caught:
                await run_adk(agent, "Synthetic request", {}, trace)
            assert caught.value.model == "offline-provider"
            assert caught.value.output_limit == 20
            assert caught.value.usage["candidates_token_count"] == 20
            assert trace[-1]["finish_reason"] == "MAX_TOKENS"
        else:
            output, _ = await run_adk(agent, "Synthetic request", {}, trace)
            assert output == {"summary": "complete"}


@pytest.mark.parametrize("message,code", [
    ("400 INVALID_ARGUMENT: input token count exceeded the allowed limit", "input_context_limit"),
    ("Max number of llm calls limit of `25` exceeded", "llm_call_limit"),
    ("Unrelated threshold exceeded", "service_error"),
])
async def test_chat_distinguishes_input_tokens_from_step_budget(api, message, code):
    with patch.object(api, "_get_or_create_session", new=AsyncMock(return_value="synthetic")), \
         patch.object(api, "run_copilot", new=AsyncMock(side_effect=RuntimeError(message))):
        result = await api.chat(api.ChatRequest(message="Quick client summary"))
    assert result["error_code"] == code
    if code == "input_context_limit":
        assert "steps" not in result["response"]


class DelegatingModel(BaseLlm):
    turn: int = 0
    seen: list[str] = Field(default_factory=list)

    async def generate_content_async(self, llm_request, stream=False):
        self.turn += 1
        self.seen.append(llm_request.model_dump_json(exclude_none=True))
        # Repeat the same tool call to exercise request-local deduplication.
        if self.turn <= 2:
            part = types.Part(function_call=types.FunctionCall(
                name="meeting_briefing_agent", args={k: v for k, v in REQUEST.items() if k != "mode"}))
        else:
            part = types.Part(text="Your meeting brief is ready to review.")
        yield LlmResponse(content=types.Content(role="model", parts=[part]),
                          finish_reason=types.FinishReason.STOP)


async def test_real_adk_delegation_uses_shared_pipeline_and_only_returns_summary(api, tmp_path):
    from self_improving_ai.agents.orchestrator.runtime import run_copilot
    from self_improving_ai.tools.briefing.copilot import meeting_briefing_agent

    store = DraftStore(tmp_path / "drafts.db")
    model = DelegatingModel(model="offline-copilot")
    parent = Agent(name="request_orchestrator", model=model, instruction="Use the briefing tool",
                   tools=[meeting_briefing_agent])
    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name=parent.name, user_id="advisor-001")
    runner = Runner(app_name=parent.name, agent=parent, session_service=sessions)

    async def offline_copilot(**kwargs):
        return await run_copilot(**kwargs, max_loops=0)

    with patch.object(api, "_runner", runner), \
         patch.object(api, "_get_or_create_session", new=AsyncMock(return_value=session.id)), \
         patch.object(api, "run_copilot", side_effect=offline_copilot), \
         patch("self_improving_ai.agents.briefing.application.DraftStore", return_value=store), \
         patch("self_improving_ai.agents.briefing.runtime.generate_agent_brief",
               new=AsyncMock(return_value=synthetic_brief())) as generate, \
         patch("self_improving_ai.agents.orchestrator.runtime.get_tracer", return_value=NoOpTracer()):
        result = await api.chat(api.ChatRequest(message="Help me get ready for my client"))

    generate.assert_awaited_once()
    assert generate.call_args.args[0].mode == "agent"
    assert result["brief"] == store.get("synthetic-brief")["brief"]
    assert result["brief"]["sources"] == synthetic_brief()["sources"]
    assert result["intent"] == "meeting_briefing"
    assert "PRIVATE_EVIDENCE" not in "".join(model.seen)
    assert "synthetic-brief" in model.seen[-1]
    assert len(model.seen[-1]) < 12000


async def test_api_and_copilot_share_frozen_workspace_and_persistence(api, tmp_path):
    from self_improving_ai.agents.briefing.application import prepare_brief
    from self_improving_ai.tools.briefing.workspace_sources import current_scope

    store = DraftStore(tmp_path / "drafts.db")
    observed = []

    async def generate(request):
        assert request.meeting_type == "general_meeting"
        assert request.focus == REQUEST["focus"]
        observed.append(deepcopy(current_scope()))
        return synthetic_brief()

    records = [{"id": "EMAIL-1", "client_id": REQUEST["client_id"], "date": "2026-11-09", "body": "Tentative plans"}]
    with patch("self_improving_ai.tools.briefing.workspace_sources.client_mail_snapshot", return_value=records), \
         patch("self_improving_ai.agents.briefing.runtime.generate_agent_brief", side_effect=generate):
        result = await prepare_brief(MeetingBriefRequest(**REQUEST), as_of="2026-11-09", store=store)
    assert observed[0]["as_of"] == "2026-11-09"
    assert observed[0]["ai_mode"] is True
    assert observed[0]["mail"] == records
    assert current_scope() is None
    assert store.get(result["id"])["status"] == "draft"


def test_focus_only_requests_and_existing_calendar_types_are_compatible():
    from self_improving_ai.calendar_adapter import normalize_event

    request = MeetingBriefRequest(**{**REQUEST, "focus": "Equity compensation discussion"})
    assert request.meeting_type == "general_meeting"
    for meeting_type in ("quarterly_review", "annual_review", "goal_review"):
        assert MeetingBriefRequest(**REQUEST, meeting_type=meeting_type).meeting_type == meeting_type
    event = {"id": "SYNTHETIC-EVENT", "title": "Equity compensation discussion", "client_id": REQUEST["client_id"],
             "date": REQUEST["meeting_date"], "start_time": "14:00", "end_time": "14:30", "type": "custom_topic"}
    normalized = normalize_event(event, {REQUEST["client_id"]: "Synthetic Client"})
    assert normalized["meeting_type"] == "general_meeting"
    assert normalized["focus"] == event["title"]
    assert event["type"] == "custom_topic"


async def test_client_only_copilot_request_looks_up_next_calendar_meeting(api):
    client = {"client_id": REQUEST["client_id"], "profile": {"name": "Thompson Trust", "primary_contact": "Alex Thompson"}}
    event = {"id": "NEXT-THOMPSON", "client_id": client["client_id"], "title": "Bond duration follow-up",
             "date": "2026-11-14", "start_time": "10:00", "notes": "Rate impact on the bond portfolio", "type": "follow_up"}
    older = {**event, "id": "OLD-THOMPSON", "date": "2026-10-28"}
    brief = {**synthetic_brief(), "client_name": "Thompson Trust", "meeting_date": event["date"],
             "meeting_time": event["start_time"], "focus": event["notes"]}
    with patch.object(api, "_load_clients", return_value=[client]), \
         patch.object(api, "_meeting_workspace", return_value={
             "now": "2026-11-11T15:00:00-05:00", "mode": "agent", "events": [older, event]}), \
         patch.object(api, "create_meeting_brief", new=AsyncMock(return_value=brief)) as generate:
        result = await api.chat(api.ChatRequest(message="prepare a meeting prep for Thompson Trust"))
    assert "meeting_details" not in result
    assert result["brief"] == brief
    assert "calendar" in result["response"]
    generate.assert_awaited_once()
    request = generate.await_args.args[0]
    assert request.calendar_event_id == event["id"]
    assert request.meeting_date.isoformat() == event["date"]
    assert request.meeting_time.strftime("%H:%M") == event["start_time"]
    assert request.focus == event["notes"]
    assert request.mode == "agent"


async def test_prepare_for_named_client_does_not_fall_through_to_general_copilot(api):
    client = {"client_id": "CLI-005", "profile": {"name": "Patel Retirement Account", "primary_contact": "Priya Patel"}}
    event = {"id": "PATEL-MEETING", "client_id": client["client_id"], "title": "Withdrawal planning",
             "date": "2026-11-22", "start_time": "09:00", "notes": "Sustainable withdrawals and inherited IRA", "type": "follow_up"}
    brief = {**synthetic_brief(), "client_id": client["client_id"], "client_name": client["profile"]["name"]}
    with patch.object(api, "_load_clients", return_value=[client]), \
         patch.object(api, "_meeting_workspace", return_value={
             "now": "2026-11-11T15:00:00-05:00", "mode": "agent", "events": [event]}), \
         patch.object(api, "create_meeting_brief", new=AsyncMock(return_value=brief)) as generate, \
         patch.object(api, "_get_or_create_session", new=AsyncMock(return_value="offline")), \
         patch.object(api, "run_copilot", new=AsyncMock(side_effect=RuntimeError("Unexpected general route"))) as copilot:
        result = await api.chat(api.ChatRequest(message="prepare for Patel Retirement Account"))
    assert result.get("brief", {}).get("id") == brief["id"]
    assert generate.await_args.args[0].calendar_event_id == event["id"]
    copilot.assert_not_awaited()


def test_calendar_resolution_respects_explicit_details_and_asks_on_ambiguity():
    from self_improving_ai.dashboard.meeting_requests import resolve_calendar_meeting

    now = datetime.fromisoformat("2026-11-11T15:00:00-05:00")
    details = {"client_id": REQUEST["client_id"], "meeting_date": "", "meeting_time": "", "focus": ""}
    event = {"id": "FIRST", "client_id": details["client_id"], "date": "2026-11-12", "start_time": "10:00",
             "title": "Client follow-up", "notes": "", "type": "follow_up"}
    later = {**event, "id": "LATER", "start_time": "14:00"}
    other_client = {**event, "id": "OTHER", "client_id": "ANOTHER-CLIENT"}
    selected = resolve_calendar_meeting(details, [later, other_client, event], now)
    assert selected["details"]["calendar_event_id"] == event["id"]
    assert selected["details"]["focus"] == event["title"]
    selected = resolve_calendar_meeting({**details, "meeting_time": "14:00", "focus": "Specific advisor question"}, [event, later], now)
    assert selected["details"]["calendar_event_id"] == later["id"]
    assert selected["details"]["focus"] == "Specific advisor question"
    ambiguous = resolve_calendar_meeting({**details, "meeting_date": event["date"]}, [event, later], now)
    assert ambiguous["reason"] == "multiple_meetings"
    simultaneous = resolve_calendar_meeting(details, [event, {**event, "id": "DUPLICATE"}], now)
    assert simultaneous["reason"] == "multiple_meetings"
    assert resolve_calendar_meeting(details, [other_client], now)["reason"] == "meeting_not_found"
    assert resolve_calendar_meeting({**details, "client_id": ""}, [event], now)["reason"] == "client_required"


async def test_calendar_failure_does_not_look_like_missing_meeting_details(api):
    from fastapi import HTTPException

    with patch.object(api, "_load_clients", return_value=[]), \
         patch.object(api, "_meeting_workspace", side_effect=RuntimeError("Private provider details")), \
         patch.object(api, "create_meeting_brief", new=AsyncMock()) as generate, \
         pytest.raises(HTTPException) as caught:
        await api.chat(api.ChatRequest(message="Prepare my meeting"))
    assert caught.value.status_code == 503
    assert "Private" not in caught.value.detail
    generate.assert_not_awaited()


@pytest.mark.parametrize("truncated", [False, True])
async def test_delegated_provider_failure_is_not_retried_by_parent(api, truncated):
    from google.genai.errors import ServerError

    from self_improving_ai.agents.briefing.application import BriefingPreparationError
    from self_improving_ai.agents.model_errors import ModelOutputLimitError
    cause = (ModelOutputLimitError(model="offline-provider", output_limit=20) if truncated
             else ServerError(503, {"error": {"message": "Busy"}}))
    failure = BriefingPreparationError("Meeting preparation failed")
    failure.__cause__ = cause
    with patch.object(api, "_get_or_create_session", new=AsyncMock(return_value="synthetic")), \
         patch.object(api, "run_copilot", new=AsyncMock(side_effect=failure)) as run, \
         patch.object(api, "_get_fallback_runner") as fallback:
        result = await api.chat(api.ChatRequest(message="Help with my client"))
    assert result["error_code"] == ("output_token_limit" if truncated else "service_busy")
    assert run.await_count == 1
    fallback.assert_not_called()


def test_both_copilot_models_register_the_bounded_adapter(api):
    from self_improving_ai.tools.briefing.copilot import meeting_briefing_agent
    assert meeting_briefing_agent in api.orchestrator.tools
    with patch.object(api, "_fallback_runner", None):
        assert meeting_briefing_agent in api._get_fallback_runner().agent.tools


async def test_parallel_duplicate_calls_share_work_but_later_requests_do_not():
    from self_improving_ai.agents.briefing.application import (
        briefing_request_scope,
        current_request_scope,
    )
    from self_improving_ai.tools.briefing.copilot import meeting_briefing_agent

    args = {k: v for k, v in REQUEST.items() if k != "mode"}
    with patch("self_improving_ai.tools.briefing.copilot.prepare_brief",
               new=AsyncMock(return_value=synthetic_brief())) as prepare:
        with briefing_request_scope("2026-11-09") as scope:
            results = await asyncio.gather(*[
                meeting_briefing_agent(**args, tool_context=None) for _ in range(2)])
            assert len(scope.briefs) == 1
            assert results[0] == results[1]
            assert len(json.dumps(results[0])) < 2200
            prepare.assert_awaited_once()
            assert prepare.call_args.kwargs == {"as_of": "2026-11-09"}
        assert current_request_scope() is None
        with briefing_request_scope():
            await meeting_briefing_agent(**args, tool_context=None)
        assert prepare.await_count == 2


async def test_invalid_details_do_not_call_the_provider():
    from self_improving_ai.tools.briefing.copilot import meeting_briefing_agent
    with patch("self_improving_ai.tools.briefing.copilot.prepare_brief", new=AsyncMock()) as prepare:
        result = await meeting_briefing_agent(client_id="", meeting_date="", meeting_time="",
                                              focus="", tool_context=None)
    assert result["status"] == "needs_confirmation"
    assert set(result["required_fields"]) == {"client_id", "meeting_date", "meeting_time", "focus"}
    prepare.assert_not_awaited()


async def test_truncated_brief_is_rejected_without_saving_or_offline_fallback(api, tmp_path):
    from fastapi import HTTPException

    from self_improving_ai.agents.model_errors import ModelOutputLimitError

    store = DraftStore(tmp_path / "drafts.db")
    error = ModelOutputLimitError(model="offline-provider", output_limit=20)
    error.briefing_run_id = "synthetic-interrupted-run"
    error.briefing_run_resumable = True
    with patch.object(api, "DraftStore", return_value=store), \
         patch("self_improving_ai.agents.briefing.runtime.generate_agent_brief",
               new=AsyncMock(side_effect=error)) as generate, \
         patch.object(api, "generate_meeting_brief") as offline, \
         pytest.raises(HTTPException) as caught:
        await api.create_meeting_brief(MeetingBriefRequest(**REQUEST))
    assert caught.value.status_code == 502
    assert "could not finish" in caught.value.detail
    assert "narrower" not in caught.value.detail
    assert caught.value.headers["X-Briefing-Run-ID"] == error.briefing_run_id
    assert "Progress is saved" in caught.value.detail
    generate.assert_awaited_once()
    offline.assert_not_called()
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM meeting_drafts").fetchone()[0] == 0


async def test_parent_max_tokens_response_is_not_returned_as_a_complete_answer(api):
    from google.adk.events import Event

    from self_improving_ai.agents.model_errors import ModelOutputLimitError
    from self_improving_ai.agents.orchestrator.runtime import run_copilot

    async def events(**kwargs):
        yield Event(author="request_orchestrator", finish_reason=types.FinishReason.MAX_TOKENS,
                    content=types.Content(role="model", parts=[types.Part(text="Incomplete answer")]))

    with patch.object(api._runner, "run_async", side_effect=events), \
         patch("self_improving_ai.agents.orchestrator.runtime.get_tracer", return_value=NoOpTracer()), \
         pytest.raises(ModelOutputLimitError):
        await run_copilot(api._runner, "Synthetic request", "synthetic-session", "advisor", max_loops=0)
