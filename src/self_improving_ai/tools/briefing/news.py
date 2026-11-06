"""Mock market news search — includes distractor articles."""

from __future__ import annotations

import json
from pathlib import Path
import re

from self_improving_ai.tools.briefing.contracts import provenance, tool_error, valid_limit

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


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
    try:
        metadata = provenance("news/market_news.json", _DATA_DIR)
        articles = json.loads((_DATA_DIR / "news/market_news.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return tool_error("DATA_UNAVAILABLE", "News fixture data is unavailable")
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
