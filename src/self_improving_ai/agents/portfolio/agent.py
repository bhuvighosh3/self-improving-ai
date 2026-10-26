"""Component A: Portfolio Estimation Agent (stub)."""

from __future__ import annotations

from google.adk import Agent

from self_improving_ai.agents.portfolio.instructions import PORTFOLIO_INSTRUCTION
from self_improving_ai.tools.portfolio.holdings import get_holdings
from self_improving_ai.tools.portfolio.pricing import get_price_history
from self_improving_ai.config import settings


portfolio_agent = Agent(
    name="portfolio_estimation_agent",
    model=settings.agent_model,
    instruction=PORTFOLIO_INSTRUCTION,
    tools=[
        get_holdings,
        get_price_history,
    ],
    output_key="portfolio_result",
)
