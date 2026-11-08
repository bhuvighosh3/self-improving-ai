"""Plan-execute-check runtime loop for the orchestrator.

Runs the orchestrator agent, checks completeness with a lightweight model,
and retries if the response is incomplete — up to max_loops iterations.
"""

from __future__ import annotations

import logging

from google.adk.agents.run_config import RunConfig
from google.genai import types

from self_improving_ai.agents.orchestrator.checker import CompletionVerdict, check_completion

log = logging.getLogger(__name__)

_FRIENDLY_ACTIONS = {
    "get_holdings": "Looking up portfolio holdings",
    "get_client_profile": "Pulling up client profile",
    "get_crm_notes": "Reviewing recent notes",
    "search_market_news": "Scanning market news",
    "check_compliance_flags": "Checking compliance",
    "calculate_fee_drag": "Analyzing fee impact",
    "search_tool_catalog": "Searching available tools",
    "calculate_allocation_drift": "Checking allocation drift",
    "estimate_portfolio_risk": "Estimating portfolio risk",
    "project_financial_goal": "Running goal projection",
    "get_market_quote": "Getting market quote",
    "get_external_price_history": "Fetching price history",
    "get_portfolio_scenarios": "Running scenario analysis",
    "prepare_meeting_context": "Gathering meeting context",
    "calculate_metrics": "Calculating key metrics",
    # Direct workspace tools
    "get_upcoming_events": "Checking calendar",
    "get_recent_emails": "Checking emails",
    "get_client_info": "Looking up client",
    "get_crm_summary": "Checking CRM notes",
    "get_client_holdings": "Looking up holdings",
}

_FRIENDLY_AGENTS = {
    "request_orchestrator": "Copilot",
    "portfolio_estimation_agent": "Portfolio Analysis",
    "meeting_briefing_agent": "Meeting Prep",
}

# Stopping criteria thresholds
_CONFIDENCE_THRESHOLD = 0.5
_DEFAULT_MAX_LOOPS = 2
_DEFAULT_MAX_LLM_CALLS = 25


async def _run_once(runner, session_id: str, user_id: str, content: types.Content,
                    max_llm_calls: int) -> tuple[list[dict], list[str]]:
    """Run the orchestrator once, collecting steps and response parts."""
    steps: list[dict] = []
    response_parts: list[str] = []

    async for event in runner.run_async(
        session_id=session_id,
        user_id=user_id,
        new_message=content,
        run_config=RunConfig(max_llm_calls=max_llm_calls),
    ):
        author = event.author or "unknown"
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    friendly = _FRIENDLY_ACTIONS.get(fc.name, fc.name.replace("_", " ").title())
                    steps.append({
                        "agent": _FRIENDLY_AGENTS.get(author, author),
                        "action": fc.name,
                        "detail": friendly,
                        "tools_called": [fc.name],
                    })
                elif hasattr(part, "text") and part.text:
                    response_parts.append(part.text)

    return steps, response_parts


async def run_copilot(
    runner,
    message: str,
    session_id: str,
    user_id: str,
    *,
    max_loops: int = _DEFAULT_MAX_LOOPS,
    max_llm_calls: int = _DEFAULT_MAX_LLM_CALLS,
) -> dict:
    """Plan-execute-check loop for the orchestrator.

    Args:
        runner: ADK Runner with the orchestrator agent.
        message: The advisor's request text.
        session_id: ADK session ID.
        user_id: ADK user ID.
        max_loops: Maximum number of check-retry cycles (default 2).
        max_llm_calls: Max LLM calls per orchestrator run (default 12).

    Returns:
        Dictionary with steps, response_parts, and loops_used.
    """
    all_steps: list[dict] = []
    response_parts: list[str] = []
    original_message = message
    verdict = CompletionVerdict(complete=False, confidence=0.0)

    for loop_num in range(max_loops + 1):
        content = types.Content(
            role="user",
            parts=[types.Part(text=message)],
        )

        steps, parts = await _run_once(runner, session_id, user_id, content, max_llm_calls)
        all_steps.extend(steps)
        response_parts = parts

        # Stopping criterion 1: hard loop limit
        if loop_num == max_loops:
            log.info("Copilot loop hit max_loops=%d, returning best-effort", max_loops)
            break

        # Stopping criterion 2: lightweight completion check
        verdict = await check_completion(original_message, all_steps, response_parts)

        # Stopping criterion 3: complete with sufficient confidence
        if verdict.complete and verdict.confidence >= _CONFIDENCE_THRESHOLD:
            log.info("Copilot loop complete on iteration %d (confidence=%.2f): %s",
                     loop_num + 1, verdict.confidence, verdict.stop_reason)
            break

        # Stopping criterion 4: nothing missing identified (checker unsure but can't help)
        if not verdict.missing:
            log.info("Copilot loop: checker found no specific gaps, stopping")
            break

        # Retry: feed the gap back as a follow-up message
        log.info("Copilot loop iteration %d incomplete: %s", loop_num + 1, verdict.missing)
        message = (
            f"Your previous answer was incomplete. "
            f"Missing: {verdict.missing}. "
            f"Please address this to fully answer the original request."
        )

    return {
        "steps": all_steps,
        "response_parts": response_parts,
        "loops_used": loop_num + 1,
        "verdict": {
            "complete": verdict.complete,
            "confidence": verdict.confidence,
            "missing": verdict.missing,
            "stop_reason": verdict.stop_reason,
        },
    }
