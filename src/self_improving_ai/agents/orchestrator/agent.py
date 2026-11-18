"""Component C: Advisor Request Orchestrator."""

from __future__ import annotations

import logging

from google.adk import Agent
from google.adk.tools.agent_tool import AgentTool

from self_improving_ai.agents.briefing.agent import briefing_agent
from self_improving_ai.tools.briefing.capped_agent_tool import CappedBriefingAgentTool
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


# Hand fixes from the golden-set baseline (docs/evaluation): the model did not know today's
# date, and had no way to map a client name to its ID. Switchable so the golden set can
# measure their effect.
CONTEXT_FIXES = True
_client_directory_cache: tuple[float, str] | None = None


def set_context_fixes(enabled: bool) -> None:
    global CONTEXT_FIXES
    CONTEXT_FIXES = enabled


def today_line() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    return (f"## Today\nToday is {now:%A, %B %-d, %Y} (New York). Meetings before today have already "
            "happened; \"next\" or \"upcoming\" means today or later.")


def client_directory() -> str:
    """Household name -> client ID, read from the client store (cached for 5 minutes)."""
    global _client_directory_cache
    from time import monotonic

    if _client_directory_cache and monotonic() - _client_directory_cache[0] < 300:
        return _client_directory_cache[1]
    from self_improving_ai.client_store import load_households

    rows = []
    for c in load_households():
        p = c.get("profile", {})
        rows.append(f"- {c['client_id']}: {p.get('name', '')} (primary contact {p.get('primary_contact', 'unknown')})")
    text = ("## Client directory (every household; match names here, never guess an ID)\n" + "\n".join(rows)
            + "\nIf a name matches no household here, say so and do not search further.")
    _client_directory_cache = (monotonic(), text)
    return text


def inject_learned_memory(callback_context):
    """Before each turn, load the lessons relevant to the advisor's new message.

    Fills the {intent_corrections}, {tool_notes} and {plan_templates} placeholders in the
    instruction from the active version of the orchestrator's learned memory, plus the
    {current_date} and {client_directory} context when CONTEXT_FIXES is on.
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
    callback_context.state["current_date"] = today_line() if CONTEXT_FIXES else ""
    directory = ""
    if CONTEXT_FIXES:
        try:
            directory = client_directory()
        except Exception:
            log.exception("Could not load the client directory")
    callback_context.state["client_directory"] = directory


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
        CappedBriefingAgentTool(agent=briefing_agent),
        # Discovery
        search_tool_catalog,
    ],
    before_agent_callback=inject_learned_memory,
    output_key="orchestrator_result",
)
