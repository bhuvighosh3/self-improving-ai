"""Component B: Client Meeting Briefing Agent (stub)."""

from __future__ import annotations

from google.adk import Agent

from self_improving_ai.agents.briefing.instructions import BRIEFING_INSTRUCTION
from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes
from self_improving_ai.tools.briefing.news import search_market_news
from self_improving_ai.tools.portfolio.holdings import get_holdings
from self_improving_ai.config import settings


briefing_agent = Agent(
    name="meeting_briefing_agent",
    model=settings.agent_model,
    instruction=BRIEFING_INSTRUCTION,
    tools=[
        get_client_profile,
        get_crm_notes,
        search_market_news,
        get_holdings,
    ],
    output_key="briefing_result",
)
