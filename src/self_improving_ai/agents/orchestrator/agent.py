"""Component C: Advisor Request Orchestrator."""

from __future__ import annotations

import logging

from google.adk import Agent
from google.adk.tools.agent_tool import AgentTool

from self_improving_ai.tools.briefing.copilot import meeting_briefing_agent
from self_improving_ai.agents.orchestrator.instructions import ORCHESTRATOR_INSTRUCTION
from self_improving_ai.agents.orchestrator.memory import orchestrator_state_for
from self_improving_ai.agents.portfolio.agent import portfolio_agent
from self_improving_ai.config import settings
from self_improving_ai.tools.orchestrator.catalog import search_tool_catalog
from self_improving_ai.tools.orchestrator.workspace import (
    get_client_holdings,
    get_client_info,
    get_crm_summary,
    get_recent_emails,
    get_upcoming_events,
)

log = logging.getLogger(__name__)
_MEMORY_KEYS = ("intent_corrections", "tool_notes", "plan_templates")


def inject_learned_memory(callback_context):
    """Before each turn, load the lessons relevant to the advisor's new message.

    Fills the {intent_corrections}, {tool_notes} and {plan_templates} placeholders in the
    instruction from the active version of the orchestrator's learned memory.
    """
    text = ""
    content = getattr(callback_context, "user_content", None)
    if content and content.parts:
        text = " ".join(p.text for p in content.parts if getattr(p, "text", None))
    try:
        blocks = orchestrator_state_for(text)
    except Exception:  # memory is an enhancement; never block a request on it
        log.exception("Could not load orchestrator memory")
        blocks = {}
    for key in _MEMORY_KEYS:
        callback_context.state[key] = blocks.get(key, "")


orchestrator = Agent(
    name="request_orchestrator",
    model=settings.agent_model,
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[
        # Direct lookup tools (fast, no sub-agent overhead)
        get_upcoming_events,
        get_recent_emails,
        get_client_info,
        get_crm_summary,
        get_client_holdings,
        # Sub-agents for complex tasks
        AgentTool(agent=portfolio_agent),
        meeting_briefing_agent,
        # Discovery
        search_tool_catalog,
    ],
    before_agent_callback=inject_learned_memory,
    output_key="orchestrator_result",
)
