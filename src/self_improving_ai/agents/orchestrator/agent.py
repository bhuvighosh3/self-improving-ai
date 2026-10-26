"""Component C: Advisor Request Orchestrator."""

from __future__ import annotations

from google.adk import Agent
from google.adk.tools.agent_tool import AgentTool

from self_improving_ai.agents.orchestrator.instructions import ORCHESTRATOR_INSTRUCTION
from self_improving_ai.agents.portfolio.agent import portfolio_agent
from self_improving_ai.agents.briefing.agent import briefing_agent
from self_improving_ai.tools.orchestrator.catalog import search_tool_catalog
from self_improving_ai.config import settings


orchestrator = Agent(
    name="request_orchestrator",
    model=settings.agent_model,
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[
        AgentTool(agent=portfolio_agent),
        AgentTool(agent=briefing_agent),
        search_tool_catalog,
    ],
    output_key="orchestrator_result",
)
