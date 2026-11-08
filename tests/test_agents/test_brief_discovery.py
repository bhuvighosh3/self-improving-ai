"""Real offline ADK investigation, boundaries, budget and checkpoint/resume."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from self_improving_ai.agents.briefing import discovery
from self_improving_ai.tools.briefing.context import load_context

TASK = {"client_id": "CLI-004", "meeting_date": "2026-11-11", "meeting_time": "09:00",
        "meeting_type": "goal_review", "focus": "Home purchase funding", "discovery_strategy": "agent"}
BASELINE = [("get_client_profile", {}), ("get_crm_notes", {"limit": 100}),
            ("get_holdings", {}), ("check_compliance_flags", {}),
            ("list_previous_meetings", {}), ("list_client_tasks", {}), ("search_sources", {"query": ""})]


class InvestigatorModel(BaseLlm):
    turn: int = 0

    async def generate_content_async(self, llm_request, stream=False):
        self.turn += 1
        if self.turn == 1:
            parts = [types.Part(function_call=types.FunctionCall(name=name, args={"client_id": "CLI-004", **arguments}))
                     for name, arguments in BASELINE]
        elif self.turn == 2:
            parts = [types.Part(function_call=types.FunctionCall(name="read_source", args={"client_id": "CLI-004", "source_id": "EMAIL-004"})),
                     types.Part(function_call=types.FunctionCall(name="search_market_news", args={"query": "housing", "max_results": 2}))]
        else:
            parts = [types.Part(text='{"summary":"Read the original tentative update and retained the funding gap as unknown."}')]
        yield LlmResponse(content=types.Content(role="model", parts=parts))


def initial_state():
    return {"meeting_discovery": discovery.initial_discovery(TASK, load_context("CLI-004")), "meeting_calculations": []}


def test_actual_adk_investigator_selects_tools_and_registers_only_read_originals():
    state, trace, saved = initial_state(), [], []
    with patch.object(discovery, "create_model", return_value=InvestigatorModel(model="offline-discovery")):
        evidence = asyncio.run(discovery.investigate(TASK, state, trace, lambda status: saved.append(deepcopy(state))))
    assert state["meeting_discovery"]["complete"] is True
    assert state["meeting_discovery"]["model_turns"] == 3
    assert len(state["meeting_discovery"]["executions"]) == 9
    assert all(entry["origin"] == "model_selected" for entry in state["meeting_discovery"]["executions"])
    assert {"PROFILE", "HOLDINGS", "MINUTES-004", "EMAIL-004", "COMPLIANCE"} <= {source["id"] for source in evidence["sources"]}
    assert "may buy" in next(source["content"] for source in evidence["sources"] if source["id"] == "EMAIL-004")
    assert saved and any(snapshot["meeting_discovery"]["executions"] for snapshot in saved)
    assert any(event.get("event") == "tool_response" and event["tool"] == "read_source" for event in trace)


def test_cross_client_and_unavailable_originals_never_enter_the_registry():
    state = initial_state()
    assert discovery.get_client_profile("CLI-002", SimpleNamespace(state=state))["status"] == "denied"
    assert not state["meeting_discovery"]["executions"]
    denied = discovery.read_source("CLI-004", "CONFIRM-002", SimpleNamespace(state=state))
    assert denied["status"] == "denied"
    discovery.coverage_gate(state)
    evidence = discovery.assemble_evidence(state["meeting_discovery"])
    assert "CONFIRM-002" not in {source["id"] for source in evidence["sources"]}


def test_completed_reads_are_cached_and_request_loops_are_bounded():
    state = initial_state()
    with patch.object(discovery.crm, "get_client_profile", wraps=discovery.crm.get_client_profile) as read:
        first = discovery.get_client_profile("CLI-004", SimpleNamespace(state=state))
        second = discovery.get_client_profile("CLI-004", SimpleNamespace(state=state))
        assert first == second and read.call_count == 1
        for _ in range(discovery.MAX_REQUESTS - 2):
            discovery.get_client_profile("CLI-004", SimpleNamespace(state=state))
        with pytest.raises(discovery.DiscoveryBudgetExceeded):
            discovery.get_client_profile("CLI-004", SimpleNamespace(state=state))


def test_backend_required_reads_have_distinct_origin_and_do_not_invent_complete_history():
    state = initial_state()
    discovery.get_client_profile("CLI-004", SimpleNamespace(state=state))
    discovery.coverage_gate(state)
    evidence = discovery.assemble_evidence(state["meeting_discovery"])
    assert any(entry["origin"] == "backend_required" for entry in state["meeting_discovery"]["executions"])
    assert evidence["coverage"]["investment_service_history"] == "incomplete"
    assert evidence["coverage"]["communications"] == "ok"


def test_exhausted_source_budget_keeps_unread_hit_as_incomplete_coverage():
    state = initial_state()
    for name, arguments in BASELINE:
        discovery.execute_tool(name, {"client_id": "CLI-004", **arguments}, state)
    for limit in (1, 2, 3):
        discovery.execute_tool("get_crm_notes", {"client_id": "CLI-004", "limit": limit}, state)
    discovery.coverage_gate(state)
    evidence = discovery.assemble_evidence(state["meeting_discovery"])
    assert evidence["coverage"]["communications"] == "incomplete"
    assert "EMAIL-004" not in {source["id"] for source in evidence["sources"]}
    with pytest.raises(discovery.DiscoveryBudgetExceeded):
        discovery.execute_tool("read_source", {"client_id": "CLI-004", "source_id": "EMAIL-004"}, state)


def test_checkpointed_read_survives_provider_failure_and_retry_uses_cache():
    from google.genai.errors import ServerError
    from self_improving_ai.agents.briefing.runtime import generate_agent_brief
    from self_improving_ai.agents.briefing.runs import BriefRunStore
    from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest

    async def fail_after_read(agent, message, state, trace, **kwargs):
        discovery.get_client_profile("CLI-004", SimpleNamespace(state=state))
        raise ServerError(503, {"error": {"message": "busy"}})
    request = MeetingBriefRequest(client_id="CLI-004", meeting_date="2026-11-11", meeting_time="09:00", focus="Home purchase funding", meeting_type="goal_review", mode="agent")
    with TemporaryDirectory() as directory:
        store = BriefRunStore(Path(directory) / "runs.db")
        with patch("self_improving_ai.config.settings.briefing_discovery", "agent"), patch("self_improving_ai.agents.briefing.runtime.BriefRunStore", return_value=store), patch("self_improving_ai.agents.briefing.runtime.run_adk", side_effect=fail_after_read):
            with pytest.raises(ServerError) as error:
                asyncio.run(generate_agent_brief(request))
            retained = store.get(error.value.briefing_run_id)
            assert retained["snapshot"]["phase"] == "discover"
            assert retained["status"] == "interrupted"
            assert len(retained["snapshot"]["state"]["meeting_discovery"]["executions"]) == 1
            with patch.object(discovery.crm, "get_client_profile", side_effect=AssertionError("Repeated I/O")):
                with pytest.raises(ServerError) as retry:
                    asyncio.run(generate_agent_brief(request))
            assert retry.value.briefing_run_id == error.value.briefing_run_id


def test_enabled_runtime_investigates_then_writes_reviews_and_retains_one_brief():
    from self_improving_ai.agents.briefing import runtime
    from self_improving_ai.agents.briefing.runs import BriefRunStore
    from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest

    sections = {}
    for name in ("overview", "changes", "portfolio", "priorities", "actions", "confirm"):
        sections[name] = [{"title": "Recorded risk tolerance", "text": "The profile records moderate risk tolerance.",
            "kind": "fact", "source_ids": ["PROFILE"], "calculation_ids": [], "rationale": "Profile record",
            "uncertainty": "Dated fixture", "why": "Confirm current preferences.", "question": "Is the recorded risk tolerance still current?"}]
    content = {"change_status": "insufficient_information", "context_summary": "Partial fixture coverage",
        "changes": [], "findings": [{"claim": "Confirm current preferences", "origin": "routine",
            "source_ids": ["PROFILE"], "rationale": "Routine review", "uncertainty": "Dated fixture",
            "priority": "routine", "question": "Are preferences current?"}],
        "sections": sections, "client_agenda": ["Confirm current preferences"]}
    actual_run = runtime.run_adk
    writers = []
    async def route(agent, message, state, trace, **kwargs):
        if agent.name == "meeting_context_investigator":
            return await actual_run(agent, message, state, trace, **kwargs)
        writers.append(agent.name)
        assert agent.tools == []
        return content, state
    with TemporaryDirectory() as directory:
        store = BriefRunStore(Path(directory) / "runs.db")
        with patch("self_improving_ai.config.settings.briefing_discovery", "agent"), patch.object(runtime, "BriefRunStore", return_value=store), patch.object(runtime, "prepare_context", side_effect=AssertionError("Fixed collection must not run")), patch.object(runtime, "run_adk", side_effect=route), patch.object(runtime, "semantic_check", new=AsyncMock(return_value={"verdict": "pass", "findings": []})), patch.object(discovery, "create_model", return_value=InvestigatorModel(model="offline-discovery")):
            result = asyncio.run(runtime.generate_agent_brief(MeetingBriefRequest(client_id="CLI-004", meeting_date="2026-11-11", meeting_time="09:00", meeting_type="goal_review", focus="Home purchase funding", mode="agent")))
        assert writers == ["meeting_briefing_agent"]
        assert result["workflow"]["discovery"]["complete"] is True
        assert result["workflow"]["quality"]["verdict"] == "pass"
        assert len(result["sections"]) == 6
        assert store.get(result["workflow"]["run_id"])["status"] == "complete"
        assert any(event.get("origin") == "model_selected" for event in result["workflow"]["trace"])
