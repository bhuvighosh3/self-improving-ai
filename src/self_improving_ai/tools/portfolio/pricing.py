"""Mock pricing tools — includes a stale-price trap."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _load_prices() -> dict:
    path = _DATA_DIR / "prices" / "price_history.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def get_price_history(
    ticker: str,
    period: str = "1Y",
) -> dict:
    """Return recent price history for a ticker.

    Args:
        ticker: Stock or fund ticker symbol (e.g. "AAPL", "VTSAX").
        period: Lookback period — one of "1M", "3M", "6M", "1Y", "5Y".

    Returns:
        Dictionary with ticker, period, and a list of {date, close} entries.
    """
    prices = _load_prices()
    series = prices.get(ticker, [])
    return {"ticker": ticker, "period": period, "prices": series}


def get_stale_price(ticker: str) -> dict:
    """Return the last known price for a ticker.

    Args:
        ticker: Stock or fund ticker symbol.

    Returns:
        Dictionary with ticker, price, and as_of date.
    """
    # Trap: silently returns data that is 6 months old
    return {
        "ticker": ticker,
        "price": 142.50,
        "as_of": "2025-04-15",
        "warning": None,
    }
