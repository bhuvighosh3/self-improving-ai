"""Structured tool execution and a separate real ADK runner. No simulated LLM answers."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from self_improving_ai.agents.portfolio.answer_validation import unsupported_currency_amounts
from self_improving_ai.agents.portfolio.model_errors import classify_model_error, model_failure
from self_improving_ai.agents.portfolio.model_settings import portfolio_api_key
from self_improving_ai.agents.portfolio.provenance import run_metadata
from self_improving_ai.tools.portfolio.allocation import calculate_allocation_drift
from self_improving_ai.tools.portfolio.holdings import get_holdings
from self_improving_ai.tools.portfolio.market_data_api import (
    get_external_price_history,
    get_market_quote,
)
from self_improving_ai.tools.portfolio.projection import project_financial_goal
from self_improving_ai.tools.portfolio.risk import estimate_portfolio_risk
from self_improving_ai.tools.portfolio.scenarios import failure, get_portfolio_scenarios

TASKS = {"holdings": get_holdings, "scenarios": get_portfolio_scenarios,
         "allocation": calculate_allocation_drift, "risk": estimate_portfolio_risk,
         "projection": project_financial_goal, "quote": get_market_quote,
         "history": get_external_price_history}


def save_run(run: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return path


def execute_task(task: str, arguments: dict) -> dict:
    """Explicit tool mode: no natural-language inference and no model request."""
    run_id, started = uuid4().hex, time.perf_counter()
    function = TASKS.get(task)
    if function is None:
        result = failure("UNKNOWN_TASK", "Select a supported portfolio task.")
        trace = []
    else:
        try:
            result = function(**arguments)
        except TypeError:
            result = failure("INVALID_ARGUMENTS", "Arguments do not match the selected tool.")
        trace = [{"tool": function.__name__, "arguments": arguments, "result": result}]
    return {"run_id": run_id, "mode": "explicit_tool_execution", "status": result["status"],
            "result": result, "trace": trace, "elapsed_seconds": time.perf_counter() - started,
            "model": None, "model_tokens": 0, "metadata": run_metadata()}


async def run_portfolio_agent(message: str, *, model=None, lessons: str = "") -> dict:
    """Run real ADK. An injected BaseLlm is for explicitly labeled transport tests only."""
    started = time.perf_counter()
    run = {"run_id": uuid4().hex,
           "mode": "adk_scripted_transport_test" if model is not None else "adk_gemini",
           "status": "error", "request": message, "model": None, "trace": [],
           "response": "", "model_tokens": 0, "metadata": run_metadata(lessons),
           "model_responses": 0, "elapsed_seconds": 0.,
           "task_outcome": "not_scored"}
    if model is None and not portfolio_api_key():
        run["result"] = model_failure("MISSING_MODEL_CONFIGURATION", "Configure Gemini in Connections before running the Agent.")
        run["elapsed_seconds"] = time.perf_counter() - started
        return run
    try:
        from google.adk import Runner
        from google.adk.agents.run_config import RunConfig
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        from self_improving_ai.agents.portfolio.agent import create_portfolio_agent

        agent = create_portfolio_agent(model)
        run["model"] = agent.model.model if model is None else type(model).__name__
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="component_a", user_id="local_advisor",
            state={"relevant_lessons": lessons, "skill_procedures": "", "tool_preferences": ""})
        runner = Runner(agent=agent, app_name="component_a", session_service=sessions)
        async with asyncio.timeout(120):
            async for event in runner.run_async(user_id="local_advisor", session_id=session.id,
                    new_message=types.Content(role="user", parts=[types.Part(text=message)]),
                    run_config=RunConfig(max_llm_calls=12)):
                if event.error_code:
                    run["result"] = model_failure("MODEL_RESPONSE_ERROR", "The model returned an error response.")
                    break
                for call in event.get_function_calls():
                    run["trace"].append({"kind": "call", "id": call.id,
                                         "tool": call.name, "arguments": call.args})
                for response in event.get_function_responses():
                    run["trace"].append({"kind": "result", "id": response.id,
                                         "tool": response.name, "result": response.response})
                if event.usage_metadata:
                    run["model_tokens"] += event.usage_metadata.total_token_count or 0
                    run["model_responses"] += 1
                if event.is_final_response() and event.content:
                    run["response"] = "".join(part.text or "" for part in event.content.parts or []
                                               if not part.thought)
        if "result" not in run:
            # A provider can finish with a bare template tag (observed live).
            visible = re.sub(r"<[^>]*>", "", run["response"]).strip(" \n\r\t`")
            if visible:
                unsupported = unsupported_currency_amounts(run["response"], run["trace"])
                if unsupported:
                    run["response_validation"] = {"status": "rejected", "unsupported_currency_amounts": unsupported,
                        "scope": "Dollar/USD amounts only; not complete semantic validation."}
                    run["response"] = ""
                    run["result"] = model_failure("MODEL_ANSWER_MISMATCH",
                        "The model added a dollar amount that the calculation did not support. Try again. Tool results remain in Execution evidence.", retryable=True)
                else:
                    run["status"] = "success"
            else:
                run["response"] = ""
                run["result"] = model_failure("EMPTY_MODEL_RESPONSE",
                    "Gemini did not produce a usable final answer. Try again or choose another model.",retryable=True)
    except Exception as exc:
        # SDK exceptions may contain request details or credentials.
        run["status"] = "error"
        run["result"] = classify_model_error(exc)
    run["elapsed_seconds"] = time.perf_counter() - started
    return run
