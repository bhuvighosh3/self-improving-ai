"""Market news search via Twelve Data API."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

from self_improving_ai.tools.briefing.contracts import tool_error, valid_limit
from self_improving_ai.tools.briefing.workspace_sources import current_scope


_fixture_only = ContextVar("briefing_fixture_news", default=False)


@contextmanager
def fixture_news():
    token = _fixture_only.set(True)
    try:
        yield
    finally:
        _fixture_only.reset(token)


def search_market_news(query: str, max_results: int = 10) -> dict:
    """Search recent market news articles via the Twelve Data API.

    Args:
        query: Search query (e.g. "tech sector outlook", "municipal bonds").
        max_results: Maximum number of articles to return.

    Returns:
        Dictionary with a list of articles. Note: results include distractor
        articles not relevant to the query — the agent must filter.
    """
    if not isinstance(query, str) or not query.strip() or len(query) > 2000 or not valid_limit(max_results):
        return tool_error("INVALID_ARGUMENT", "Provide a nonempty query and an integer max_results from 0 to 100")
    scope = current_scope()
    cutoff = scope["as_of"] if scope else None
    if os.environ.get("TWELVE_DATA_API_KEY"):
        from self_improving_ai.tools.briefing.news_api import fetch_market_news
        result = fetch_market_news(query, max_results)
        if result.get("status") != "error":
            articles = [a for a in result["results"]
                        if a.get("date") and a["date"] <= (cutoff or date.today().isoformat())]
            terms = set(re.findall(r"[a-z0-9]+", query.lower()))
            matched = [a["id"] for a in articles
                       if terms & set(re.findall(r"[a-z0-9]+", (a["headline"] + " " + a["text"]).lower()))]
            return {**result, "status": "ok", "results": articles, "matched_ids": matched,
                    "includes_distractors": len(matched) < len(articles), "relevance_verified": False,
                    "_provenance": {"source": "twelve_data", "as_of": cutoff or date.today().isoformat(),
                                    "synthetic": False, "read_only": True, "version": "news-api-v1"}}
    return {"status": "ok", "query": query, "results": [], "matched_ids": [],
            "includes_distractors": False, "relevance_verified": False,
            "_provenance": {"source": "none", "as_of": cutoff or date.today().isoformat(),
                            "synthetic": False, "read_only": True, "version": "news-api-v1"}}
