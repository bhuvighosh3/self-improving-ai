"""Mock market news search — includes distractor articles."""

from __future__ import annotations

import json
from pathlib import Path
import re
import os
from datetime import date
from contextlib import contextmanager
from contextvars import ContextVar
from self_improving_ai.config import settings
from self_improving_ai.tools.briefing.workspace_sources import current_scope

from self_improving_ai.tools.briefing.contracts import provenance, tool_error, valid_limit

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


_fixture_only = ContextVar("briefing_fixture_news", default=False)


@contextmanager
def fixture_news():
    token = _fixture_only.set(True)
    try:
        yield
    finally:
        _fixture_only.reset(token)


def search_market_news(query: str, max_results: int = 10) -> dict:
    """Search recent market news articles.

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
    live_error = None
    if max_results > 0 and not _fixture_only.get() and settings.briefing_news_source != "fixture" and (scope is None or scope.get("ai_mode")) and os.environ.get("TWELVE_DATA_API_KEY"):
        from self_improving_ai.tools.briefing.news_api import fetch_market_news
        result = fetch_market_news(query,max_results)
        if result.get("status") != "error":
            articles = [article for article in result["results"] if article.get("date") and article["date"] <= (cutoff or date.today().isoformat())]
            terms = set(re.findall(r"[a-z0-9]+",query.lower()))
            matched = [article["id"] for article in articles if terms & set(re.findall(r"[a-z0-9]+",(article["headline"]+" "+article["text"]).lower()))]
            return {**result,"status":"ok","results":articles,"matched_ids":matched,
                "includes_distractors":len(matched)<len(articles),"relevance_verified":False,
                "_provenance":{"source":"twelve_data","as_of":cutoff or date.today().isoformat(),"synthetic":False,"read_only":True,"version":"news-api-v1"}}
        live_error = result.get("error",{}).get("code","PROVIDER_ERROR")
    try:
        metadata = provenance("news/market_news.json", _DATA_DIR)
        articles = json.loads((_DATA_DIR / "news/market_news.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return tool_error("DATA_UNAVAILABLE", "News fixture data is unavailable")
    if cutoff:
        metadata["as_of"] = cutoff
    if live_error:
        metadata["fallback_reason"] = live_error
    articles = [article for article in articles if article["date"] <= metadata["as_of"]
                and article.get("recorded_at", article["date"])[:10] <= metadata["as_of"]]
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    def score(article):
        words = set(re.findall(r"[a-z0-9]+", (article["headline"] + " " + article["text"]).lower()))
        return len(terms & words)
    relevant = sorted((article for article in articles if score(article)),
                      key=lambda article: (score(article), article["date"]), reverse=True)
    distractors = [article for article in articles if not score(article)]
    # Preserve the research testbed's distractors; consumers must still judge relevance.
    results = (relevant + distractors)[:max_results]
    return {"status": "ok", "query": query, "results": results,
            "matched_ids": [article["id"] for article in relevant[:max_results]],
            "includes_distractors": any(not score(article) for article in results),
            "relevance_verified": False, "_provenance": metadata}
