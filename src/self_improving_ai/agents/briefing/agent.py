"""Component B: one ADK agent applying three evidence-driven business skills."""

from __future__ import annotations

from google.adk import Agent

from self_improving_ai.agents.briefing.instructions import briefing_instructions
from self_improving_ai.agents.briefing.workflow_models import AgentWork
from self_improving_ai.tools.briefing.agent_tools import prepare_meeting_context, calculate_metrics
from self_improving_ai.config import settings


briefing_agent = Agent(
    name="meeting_briefing_agent",
    model=settings.agent_model,
    instruction=briefing_instructions,
    tools=[
        prepare_meeting_context,
        calculate_metrics,
    ],
    output_key="briefing_result",
    output_schema=AgentWork,
)
