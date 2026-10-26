"""Mock market news search — includes distractor articles."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def search_market_news(query: str, max_results: int = 10) -> dict:
    """Search recent market news articles.

    Args:
        query: Search query (e.g. "tech sector outlook", "municipal bonds").
        max_results: Maximum number of articles to return.

    Returns:
        Dictionary with a list of articles. Note: results include distractor
        articles not relevant to the query — the agent must filter.
    """
    path = _DATA_DIR / "news" / "market_news.json"
    if path.exists():
        articles = json.loads(path.read_text())
    else:
        articles = []

    query_lower = query.lower()
    relevant = [a for a in articles if query_lower in a.get("text", "").lower()]
    distractors = [a for a in articles if query_lower not in a.get("text", "").lower()]

    # Mix relevant results with distractors
    results = relevant[:max_results]
    remaining = max_results - len(results)
    if remaining > 0:
        results.extend(distractors[:remaining])

    return {"query": query, "results": results[:max_results]}
