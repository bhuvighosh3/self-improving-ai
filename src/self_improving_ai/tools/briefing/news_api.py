"""Twelve Data news endpoint. Stdlib HTTP only, structured errors, mock fallback."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = "twelve_data"
BASE_URL = "https://api.twelvedata.com"
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 8 * 1024 * 1024

_SECTOR_KEYWORDS: dict[str, set[str]] = {
    "macro": {"fed", "federal reserve", "interest rate", "inflation", "gdp",
              "employment", "jobs", "recession", "monetary policy", "fomc"},
    "tech": {"technology", "ai", "artificial intelligence", "cloud",
             "semiconductor", "software", "saas", "cyber", "nasdaq"},
    "fixed_income": {"bond", "treasury", "yield", "fixed income", "municipal",
                     "credit", "duration", "coupon"},
    "equities": {"stock", "equity", "s&p", "dow", "dividend", "earnings", "ipo"},
    "real_estate": {"real estate", "housing", "mortgage", "reit", "property"},
    "international": {"international", "emerging market", "europe", "asia",
                      "trade", "tariff", "forex"},
    "tax": {"tax", "irs", "capital gains", "rmd", "estate", "deduction"},
    "regulatory": {"sec", "regulation", "compliance", "fiduciary", "dodd-frank"},
}


def _failure(code: str, message: str, *, retryable: bool = False) -> dict:
    return {"status": "error", "source": SOURCE, "error": {"code": code, "message": message, "retryable": retryable}}


def _classify_sector(text: str) -> str:
    lower = text.lower()
    for sector, keywords in _SECTOR_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return sector
    return "general"


def _article_id(url: str) -> str:
    return "TD-" + hashlib.sha256(url.encode()).hexdigest()[:8]


def fetch_market_news(query: str, max_results: int = 10, *, api_key: str | None = None) -> dict:
    """Fetch news from Twelve Data, returning the same shape as the mock."""
    key = (api_key if api_key is not None else os.environ.get("TWELVE_DATA_API_KEY", "")).strip()
    if not key:
        return _failure("MISSING_API_KEY", "Set TWELVE_DATA_API_KEY before querying.")
    if any(ord(c) < 32 or ord(c) > 126 for c in key):
        return _failure("INVALID_API_KEY", "The API key contains invalid characters.")

    query = query.strip()
    if not query:
        return _failure("INVALID_QUERY", "Query must not be empty.")

    params = urlencode({"q": query, "items": min(max_results, 50)})
    request = Request(
        f"{BASE_URL}/news?{params}",
        headers={
            "Authorization": f"apikey {key}",
            "Accept": "application/json",
            "User-Agent": "self-improving-ai/0.1",
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return _failure("INVALID_RESPONSE", "The provider response was too large.")
        payload = json.loads(raw)
    except HTTPError as exc:
        code = exc.code
        if code == 401:
            return _failure("AUTHENTICATION_FAILED", "The provider rejected the API key.")
        if code == 403:
            return _failure("ACCESS_DENIED", "The account cannot access this resource.")
        if code == 429:
            return _failure("RATE_LIMITED", "The provider's API quota was reached.", retryable=True)
        if code >= 500:
            return _failure("PROVIDER_UNAVAILABLE", "The provider is temporarily unavailable.", retryable=True)
        return _failure("INVALID_REQUEST", "The provider rejected the request parameters.")
    except (URLError, socket.timeout, OSError):
        return _failure("NETWORK_ERROR", "Could not reach the news provider.", retryable=True)
    except (json.JSONDecodeError, ValueError):
        return _failure("INVALID_RESPONSE", "The provider returned unparseable data.")

    if not isinstance(payload, dict):
        return _failure("INVALID_RESPONSE", "Unexpected response format.")

    if payload.get("status") == "error":
        return _failure("PROVIDER_ERROR", payload.get("message", "Unknown provider error."))

    raw_articles = payload.get("data") or payload.get("articles") or []
    if not isinstance(raw_articles, list):
        return _failure("INVALID_RESPONSE", "News data is not a list.")

    results = []
    for article in raw_articles[:max_results]:
        if not isinstance(article, dict):
            continue
        title = article.get("title") or article.get("headline") or ""
        snippet = article.get("snippet") or article.get("description") or article.get("content") or ""
        url = article.get("url") or ""
        dt = article.get("datetime") or article.get("published_at") or ""
        article_date = dt[:10] if len(dt) >= 10 else ""
        combined = title + " " + snippet
        results.append({
            "id": _article_id(url) if url else f"TD-{len(results)}",
            "date": article_date,
            "headline": title,
            "text": snippet,
            "sector": _classify_sector(combined),
        })

    return {"query": query, "results": results, "source": SOURCE}
