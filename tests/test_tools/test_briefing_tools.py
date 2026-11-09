"""Public Component B contracts, fixture boundaries and preparation integration."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from self_improving_ai.tools.briefing import BRIEFING_TOOLS
from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes
from self_improving_ai.tools.briefing.news import search_market_news
from self_improving_ai.tools.briefing.compliance import check_compliance_flags
from self_improving_ai.tools.briefing.context import prepare_context
from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief


@pytest.mark.parametrize("client_id", ["CLI-001", "CLI-002", "CLI-003", "CLI-004", "CLI-005"])
def test_four_public_tools_have_compatible_outputs_and_synthetic_provenance(client_id):
    profile = get_client_profile(client_id)
    notes = get_crm_notes(client_id, 1)
    news = search_market_news("bond duration", 3)
    flags = check_compliance_flags(client_id)
    assert profile["name"] and profile["risk_tolerance"]
    assert len(notes["notes"]) <= 1 and notes["client_id"] == client_id
    assert news["status"] == "ok"
    assert flags["client_id"] == client_id and flags["assessment_status"] == "not_cleared"
    for result in (profile, notes, flags):
        assert result["_provenance"]["read_only"] is True
        assert result["_provenance"]["as_of"] == "2026-10-27"
    assert news["_provenance"]["read_only"] is True


@pytest.mark.parametrize("invalid", [-1, 101, True, 1.5, "3", None])
def test_invalid_limits_are_structured_errors(invalid):
    assert get_crm_notes("CLI-001", invalid)["error_code"] == "INVALID_ARGUMENT"
    assert search_market_news("bonds", invalid)["error_code"] == "INVALID_ARGUMENT"


def test_zero_limit_and_unknown_client_do_not_masquerade_as_success():
    assert get_crm_notes("CLI-001", 0)["notes"] == []
    assert search_market_news("bonds", 0)["results"] == []
    for tool in (get_client_profile, get_crm_notes, check_compliance_flags):
        assert tool("CLI-999")["error_code"] == "CLIENT_NOT_FOUND"
        assert tool(None)["error_code"] == "INVALID_ARGUMENT"
    assert search_market_news("")["error_code"] == "INVALID_ARGUMENT"


def test_news_returns_ok_status_and_provenance():
    result = search_market_news("RMD", 1)
    assert result["status"] == "ok"
    assert result["_provenance"]["read_only"] is True
    unrelated = search_market_news("unmatched-query-xyz", 3)
    assert unrelated["status"] == "ok"
    assert unrelated["relevance_verified"] is False


def test_cutoff_precedes_limit_for_crm_notes():
    notes = get_crm_notes("CLI-001", 100)
    for note in notes["notes"]:
        assert note["date"] <= notes["_provenance"]["as_of"]


def test_compliance_flags_preserve_originals_and_never_claim_clearance():
    for client_id, expected in [("CLI-004", "PROFILE_STATE_MISSING"), ("CLI-005", "RECORDED_COMPLIANCE_FOLLOWUP")]:
        result = check_compliance_flags(client_id)
        flag = next(flag for flag in result["flags"] if flag["code"] == expected)
        assert flag["status"] == "needs_confirmation"
        evidence = prepare_context(client_id)
        sources = {source["id"] for source in evidence["sources"]}
        assert set(flag["source_ids"]) <= sources
        assert any(event["tool"] == "check_compliance_flags" for event in evidence["trace"])
    with patch("self_improving_ai.tools.briefing.compliance._load_households", return_value=[{"client_id":"CLI-002","accounts":[]}]), patch("self_improving_ai.tools.briefing.compliance.get_client_profile", return_value={"name":"Test", "state":"CA", "beneficiary_last_reviewed":"2026-10-01","_provenance":{"as_of":"2026-10-27"}}):
        empty = check_compliance_flags("CLI-002")
    assert empty["flags"] == [] and empty["assessment_status"] == "not_cleared"
    assert empty["coverage"] == "partial_synthetic_records"


def test_compliance_results_reach_the_actual_draft_with_resolvable_references():
    brief = generate_meeting_brief(MeetingBriefRequest(client_id="CLI-005", meeting_date="2026-11-11", meeting_time="14:00", focus="Withdrawal planning"))
    assert "check_compliance_flags" in brief["tools_called"]
    confirmations = next(section for section in brief["sections"] if section["id"] == "confirm")
    assert any("COMPLIANCE" in item["source_ids"] for item in confirmations["items"])
    assert brief["workflow"]["quality"]["verdict"] == "pass"
    sources = {source["id"] for source in brief["sources"]}
    assert all(set(item["source_ids"]) <= sources for item in confirmations["items"])


def test_catalog_ownership_matches_real_exported_functions_and_adk_contracts():
    from google.adk.tools import FunctionTool
    root = Path(__file__).resolve().parents[2] / "src/self_improving_ai/data"
    catalog = json.loads((root / "tool_catalog.json").read_text())
    entries = [tool for tool in catalog if tool["agent"] == "meeting_briefing_agent"]
    assert {entry["name"] for entry in entries} == set(BRIEFING_TOOLS)
    for entry in entries:
        assert entry["implementation_status"] == "implemented"
        assert entry["read_only"] is True
        declaration = FunctionTool(BRIEFING_TOOLS[entry["name"]])._get_declaration()
        assert declaration.name == entry["name"]
        schema = declaration.parameters_json_schema
        properties = schema["properties"] if schema else declaration.parameters.properties
        assert set(properties) == set(entry["parameters"])


def test_actual_adk_runner_executes_all_catalog_tools_without_network():
    import asyncio
    from google.adk import Agent
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types
    from self_improving_ai.agents.briefing.runtime import run_adk

    calls = [("get_client_profile", {"client_id": "CLI-005"}),
             ("get_crm_notes", {"client_id": "CLI-005", "limit": 2}),
             ("search_market_news", {"query": "RMD", "max_results": 2}),
             ("check_compliance_flags", {"client_id": "CLI-005"}),
             ("get_crm_context", {"client_id": "CLI-005"}),
             ("get_crm_records", {"client_id": "CLI-005"})]

    class LocalToolModel(BaseLlm):
        turn: int = 0

        async def generate_content_async(self, llm_request, stream=False):
            self.turn += 1
            if self.turn <= len(calls):
                name, arguments = calls[self.turn - 1]
                part = types.Part(function_call=types.FunctionCall(name=name, args=arguments))
            else:
                part = types.Part(text='{"checked":true}')
            yield LlmResponse(content=types.Content(role="model", parts=[part]))

    agent = Agent(name="briefing_tool_contract_test", model=LocalToolModel(model="offline-test"),
                  instruction="Exercise every read-only catalog tool contract.", tools=list(BRIEFING_TOOLS.values()))
    trace = []
    output, _ = asyncio.run(run_adk(agent, "Prepare the Patel meeting", {}, trace))
    assert output == {"checked": True}
    responses = {event["tool"]: event["result"] for event in trace if event.get("event") == "tool_response"}
    assert set(responses) == set(BRIEFING_TOOLS)
    assert all("error" not in result for result in responses.values())
    assert "RECORDED_COMPLIANCE_FOLLOWUP" in {flag["code"] for flag in responses["check_compliance_flags"]["flags"]}
