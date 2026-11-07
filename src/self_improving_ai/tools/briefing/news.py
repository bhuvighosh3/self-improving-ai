"""Market news search — live Twelve Data API with local fixture fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _mock_search(query: str, max_results: int) -> dict:
    path = _DATA_DIR / "news" / "market_news.json"
    if path.exists():
        articles = json.loads(path.read_text(encoding="utf-8"))
    else:
        articles = []

    query_lower = query.lower()
    relevant = [a for a in articles if query_lower in a.get("text", "").lower()]
    distractors = [a for a in articles if query_lower not in a.get("text", "").lower()]

    results = relevant[:max_results]
    remaining = max_results - len(results)
    if remaining > 0:
        results.extend(distractors[:remaining])

    return {"query": query, "results": results[:max_results]}


def search_market_news(query: str, max_results: int = 10) -> dict:
    """Search market news via Twelve Data when available, otherwise local fixtures."""
    api_key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if api_key:
        from self_improving_ai.tools.briefing.news_api import fetch_market_news

        result = fetch_market_news(query, max_results, api_key=api_key)
        if result.get("status") != "error":
            return result

    return _mock_search(query, max_results)
