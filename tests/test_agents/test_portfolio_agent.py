"""Real ADK tool dispatch with a scripted model transport; never a Gemini quality claim."""
import asyncio
import json

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field

from self_improving_ai.agents.portfolio.service import execute_task, run_portfolio_agent


class ScriptedModel(BaseLlm):
    model: str = "scripted-offline-test"
    tool_name: str = "calculate_allocation_drift"
    arguments: dict = Field(default_factory=lambda: {"client_id": "CLI-001"})

    async def generate_content_async(self, llm_request, stream=False):
        results = [part.function_response for content in llm_request.contents
                   for part in content.parts or [] if part.function_response]
        if results:
            content = types.Content(role="model", parts=[types.Part(text=json.dumps(results[-1].response))])
        else:
            content = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
                name=self.tool_name, args=self.arguments))])
        yield LlmResponse(content=content)


class EmptyModel(BaseLlm):
    model: str = "empty-transport-test"
    text: str = ""

    async def generate_content_async(self, llm_request, stream=False):
        yield LlmResponse(content=types.Content(role="model",parts=[types.Part(text=self.text)]))


class DirectoryCheckingModel(ScriptedModel):
    async def generate_content_async(self, llm_request, stream=False):
        instruction=llm_request.config.system_instruction
        assert '"client_id": "CLI-002", "name": "Thompson Trust"' in instruction
        assert '"client_id": "CLI-003", "name": "Chen Household"' in instruction
        assert "ACC-003A" in instruction
        assert "test-validated-lesson" in instruction
        assert "{relevant_lessons}" not in instruction
        async for event in super().generate_content_async(llm_request,stream):
            yield event


@pytest.mark.asyncio
async def test_real_adk_receives_name_id_account_mapping_and_validated_lessons():
    result=await run_portfolio_agent("Show Chen holdings",model=DirectoryCheckingModel(
        tool_name="get_holdings",arguments={"client_id":"CLI-003"}),lessons="test-validated-lesson")
    assert result["status"]=="success",result.get("result")
    assert json.loads(result["response"])["client_name"]=="Chen Household"


@pytest.mark.asyncio
@pytest.mark.parametrize("text",["","<output>","<response> </response>"])
async def test_empty_response_is_not_reported_as_success(text):
    run = await run_portfolio_agent("Calculate", model=EmptyModel(text=text))
    assert run["status"] == "error"
    assert run["result"]["error"]["code"] == "EMPTY_MODEL_RESPONSE"
    assert run["result"]["error"]["retryable"]
    assert run["response"]==""


@pytest.mark.asyncio
async def test_setup_failure_is_structured_and_does_not_expose_details(monkeypatch):
    from self_improving_ai.agents.portfolio import agent
    def broken_factory(*args):
        raise ValueError("private-key-or-request-details")
    monkeypatch.setattr(agent,"create_portfolio_agent",broken_factory)
    run=await run_portfolio_agent("Calculate",model=ScriptedModel())
    assert run["status"] == "error"
    assert "private-key" not in json.dumps(run)


@pytest.mark.asyncio
async def test_adk_dispatches_requested_scenario_parameters():
    run=await run_portfolio_agent("Compare with 60/40",model=ScriptedModel(arguments={
        "client_id":"CLI-002","target_stock_weight":.6}))
    assert run["status"] == "success"
    assert json.loads(run["response"])["asset_classes"]["stock"]["hypothetical_adjustment_usd"] == 54820


@pytest.mark.asyncio
async def test_adk_executes_actual_allocation_and_returns_trace():
    result = await run_portfolio_agent("Garcia allocation", model=ScriptedModel())
    assert result["status"] == "success", result
    assert result["mode"] == "adk_scripted_transport_test"
    tool_result = next(x["result"] for x in result["trace"] if x["kind"] == "result")
    assert tool_result["total_market_value"] == 146750
    assert tool_result["asset_classes"]["stock"]["hypothetical_adjustment_usd"] == -29150


@pytest.mark.asyncio
async def test_adk_propagates_unknown_account_error():
    result = await run_portfolio_agent("Invalid account", model=ScriptedModel(
        tool_name="get_holdings", arguments={"client_id": "CLI-001", "account_id": "bad"}))
    assert "ACCOUNT_NOT_FOUND" in result["response"]


def test_missing_configuration_makes_no_model_call(monkeypatch):
    for key in ("SIA_PORTFOLIO_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(key, raising=False)
    result = asyncio.run(run_portfolio_agent("Garcia"))
    assert result["result"]["error"]["code"] == "MISSING_MODEL_CONFIGURATION"


def test_explicit_tool_mode_is_not_labeled_as_agent():
    result = execute_task("allocation", {"client_id": "CLI-001"})
    assert result["mode"] == "explicit_tool_execution"
    assert result["model_tokens"] == 0
    assert execute_task("missing", {})["status"] == "error"


@pytest.mark.asyncio
async def test_orchestrator_can_delegate_to_a_via_agent_tool():
    from google.adk import Agent, Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.agent_tool import AgentTool

    from self_improving_ai.agents.portfolio.agent import create_portfolio_agent

    child = create_portfolio_agent(ScriptedModel())
    parent = Agent(name="test_orchestrator", model=ScriptedModel(
        tool_name="portfolio_estimation_agent", arguments={"request":"Garcia CLI-001 allocation"}),
        tools=[AgentTool(agent=child)])
    sessions = InMemorySessionService()
    session = await sessions.create_session(app_name="delegation_test", user_id="test",
        state={"relevant_lessons":"", "skill_procedures":"", "tool_preferences":""})
    runner = Runner(agent=parent, app_name="delegation_test", session_service=sessions)
    responses = []
    async for event in runner.run_async(user_id="test", session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text="Review Garcia allocation")])):
        responses.extend(response.response for response in event.get_function_responses())
    assert "29150" in json.dumps(responses)
