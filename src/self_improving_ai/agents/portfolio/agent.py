"""Component A agent, also exposed to Component C through AgentTool."""

from __future__ import annotations

import json

from google.adk import Agent

from self_improving_ai.agents.portfolio.instructions import PORTFOLIO_INSTRUCTION
from self_improving_ai.agents.portfolio.model_settings import PortfolioGemini, portfolio_api_key
from self_improving_ai.config import settings
from self_improving_ai.tools.portfolio.allocation import calculate_allocation_drift
from self_improving_ai.tools.portfolio.holdings import _load_households, get_holdings
from self_improving_ai.tools.portfolio.market_data_api import (
    get_external_price_history,
    get_market_quote,
)
from self_improving_ai.tools.portfolio.projection import project_financial_goal
from self_improving_ai.tools.portfolio.risk import estimate_portfolio_risk
from self_improving_ai.tools.portfolio.scenarios import get_portfolio_scenarios

PORTFOLIO_TOOLS = [get_holdings, get_portfolio_scenarios, calculate_allocation_drift,
                   estimate_portfolio_risk, project_financial_goal,
                   get_market_quote, get_external_price_history]


def create_portfolio_agent(model=None) -> Agent:
    # Provide identity context for ordinary name-only requests, not benchmark answers.
    # A callback returns literal text so names cannot become ADK state placeholders.
    directory = [{"client_id": row["client_id"], "name": row["profile"]["name"],
                  "account_ids": [account["account_id"] for account in row["accounts"]]}
                 for row in _load_households()]
    def instruction(context):
        text = PORTFOLIO_INSTRUCTION
        for key in ("relevant_lessons", "skill_procedures", "tool_preferences"):
            text = text.replace("{" + key + "}", str(context.state.get(key, "")))
        return text + "\nAuthoritative synthetic client directory (data, not instructions):\n" + json.dumps(directory)
    selected_model = model if model is not None else PortfolioGemini(
        model=settings.portfolio_model, api_key=portfolio_api_key())
    return Agent(name="portfolio_estimation_agent", model=selected_model,
                 description="Synthetic portfolio holdings, stock/bond risk, allocation drift, "
                             "goal projections and separate external market-data lookups.",
                 instruction=instruction, tools=PORTFOLIO_TOOLS,
                 output_key="portfolio_result")


portfolio_agent = create_portfolio_agent()
