"""Independent Twelve Data tools. No LLM, fixture fallback, or trading access.

Authentication: TWELVE_DATA_API_KEY environment variable. Standard library only.
Provider contract: https://twelvedata.com/docs (reviewed 2026-10-30).
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
from datetime import date, datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE = "twelve_data"
BASE_URL = "https://api.twelvedata.com"
TIMEOUT_SECONDS = 10
MAX_RANGE_DAYS = 3650
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,19}\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


def _failure(symbol: str, code: str, message: str, *, retryable: bool = False,
             provider_code: int | None = None) -> dict:
    error = {"code": code, "message": message, "retryable": retryable}
    if provider_code is not None:
        error["provider_code"] = provider_code
    return {"status": "error", "source": SOURCE, "symbol": symbol, "error": error}


def _normalize_symbol(symbol: str) -> str | None:
    if not isinstance(symbol, str):
        return None
    normalized = symbol.strip().upper()
    return normalized if _SYMBOL.fullmatch(normalized) else None


def _parse_date(value: str) -> date:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("Expected YYYY-MM-DD")
    return date.fromisoformat(value)


def _price(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean price")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("Price must be positive and finite")
    return result


def _provider_failure(symbol: str, code: int, message: object = "") -> dict:
    # Classify provider text, but never expose it: a provider can echo credentials.
    text = str(message).lower()
    if code == 401:
        return _failure(symbol, "AUTHENTICATION_FAILED", "The provider rejected the API key.",
                        provider_code=code)
    if code == 403:
        return _failure(symbol, "ACCESS_DENIED", "The account cannot access this resource.",
                        provider_code=code)
    if code == 429:
        return _failure(symbol, "RATE_LIMITED", "The provider's API quota was reached.",
                        retryable=True, provider_code=code)
    if code >= 500:
        return _failure(symbol, "PROVIDER_UNAVAILABLE", "The provider is temporarily unavailable.",
                        retryable=True, provider_code=code)
    if "symbol" in text and any(s in text for s in ("invalid", "not found", "does not exist")):
        return _failure(symbol, "SYMBOL_NOT_FOUND", "The provider did not recognize the symbol.",
                        provider_code=code)
    if code == 404:
        return _failure(symbol, "NO_DATA", "No provider data was found for this request.",
                        provider_code=code)
    return _failure(symbol, "INVALID_REQUEST", "The provider rejected the request parameters.",
                    provider_code=code)


def _request(endpoint: str, symbol: str, params: dict, *, api_key: str | None = None) -> dict:
    key = (api_key if api_key is not None else os.environ.get("TWELVE_DATA_API_KEY", "")).strip()
    if not key:
        return _failure(symbol, "MISSING_API_KEY", "Set TWELVE_DATA_API_KEY before querying.")
    if any(ord(character) < 32 or ord(character) > 126 for character in key):
        return _failure(symbol, "INVALID_API_KEY", "The API key contains invalid characters.")
    request = Request(
        f"{BASE_URL}/{endpoint}?{urlencode({'symbol': symbol, **params})}",
        headers={"Authorization": f"apikey {key}", "Accept": "application/json",
                 "User-Agent": "component-a-market-data/0.1"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            return _failure(symbol, "INVALID_RESPONSE", "The provider response was too large.")
        payload = json.loads(raw)
    except HTTPError as exc:
        try:
            body = json.loads(exc.read(MAX_RESPONSE_BYTES))
            message = body.get("message", "") if isinstance(body, dict) else ""
        except HTTPException:
            return _failure(symbol, "NETWORK_ERROR", "Could not read the provider error response.",
                            retryable=True)
        except (ValueError, OSError):
            message = ""
        finally:
            exc.close()
        return _provider_failure(symbol, exc.code, message)
    except (TimeoutError, socket.timeout):
        return _failure(symbol, "TIMEOUT", "The market data request timed out.", retryable=True)
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return _failure(symbol, "TIMEOUT", "The market data request timed out.", retryable=True)
        return _failure(symbol, "NETWORK_ERROR", "Could not reach the market data provider.",
                        retryable=True)
    except (OSError, ConnectionError, HTTPException):
        return _failure(symbol, "NETWORK_ERROR", "Could not read the market data response.",
                        retryable=True)
    except (ValueError, UnicodeError):
        return _failure(symbol, "INVALID_RESPONSE", "The provider returned invalid JSON.")
    if not isinstance(payload, dict):
        return _failure(symbol, "INVALID_RESPONSE", "Expected one provider response object.")
    try:
        code = int(payload.get("code", 0))
    except (ValueError, TypeError, OverflowError):
        code = 0
    if payload.get("status") == "error" or code >= 400:
        return _provider_failure(symbol, code, payload.get("message", ""))
    return payload


def _check_identity(payload: dict, symbol: str) -> str:
    if not isinstance(payload, dict) or payload.get("symbol") != symbol:
        raise ValueError("Provider symbol mismatch")
    currency = payload.get("currency")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("Missing currency")
    return currency


def get_market_quote(symbol: str) -> dict:
    """Return the latest available provider quote, with explicit timing limitations.

    as_of is the exchange bar date, NOT the fetch time. last_quote_at_utc is a
    provider last-minute-bar timestamp when supplied. Neither the market-open
    flag nor a successful response establishes a real-time entitlement.
    """
    return _get_market_quote(symbol)


def probe_market_quote(api_key: str) -> dict:
    """Test a draft connection key without exposing it to any registered Agent tool."""
    return _get_market_quote("AAPL", api_key=api_key)


def _get_market_quote(symbol: str, *, api_key: str | None = None) -> dict:
    symbol = _normalize_symbol(symbol)
    if symbol is None:
        return _failure("", "INVALID_SYMBOL", "Use one stock or fund ticker, such as AAPL.")
    payload = _request("quote", symbol, {"interval": "1day", "prepost": "false"}, api_key=api_key)
    if payload.get("status") == "error":
        return payload
    if not payload or payload.get("close") in (None, ""):
        return _failure(symbol, "NO_DATA", "The provider returned no quote price.")
    try:
        currency = _check_identity(payload, symbol)
        value = _price(payload["close"])
        as_of = _parse_date(payload["datetime"]).isoformat()
        raw_timestamp = payload.get("last_quote_at")
        last_quote = None
        if raw_timestamp is not None:
            if isinstance(raw_timestamp, bool) or float(raw_timestamp) <= 0:
                raise ValueError("Invalid timestamp")
            last_quote = datetime.fromtimestamp(float(raw_timestamp), timezone.utc).isoformat()
        market_open = payload.get("is_market_open")
        if market_open is not None and not isinstance(market_open, bool):
            raise ValueError("Invalid market-open flag")
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        return _failure(symbol, "INVALID_RESPONSE", "The quote has invalid or missing fields.")
    return {
        "status": "success", "symbol": symbol, "price": value, "currency": currency,
        "as_of": as_of, "source": SOURCE, "price_type": "provider_quote_close",
        "bar_date": as_of, "last_quote_at_utc": last_quote,
        "is_market_open": market_open, "timeliness": "unverified",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "warnings": ["Latest available provider quote; real-time or delayed status is unverified.",
                     "as_of is the exchange bar date, not the last trade time or fetch time."],
    }


def get_external_price_history(symbol: str, start_date: str, end_date: str) -> dict:
    """Return daily split-adjusted closes, ascending, within inclusive date bounds.

    At most 3650 calendar days per request. Missing dates are not filled. Split
    adjustment excludes dividend reinvestment and does not define total return.
    """
    symbol = _normalize_symbol(symbol)
    if symbol is None:
        return _failure("", "INVALID_SYMBOL", "Use one stock or fund ticker, such as AAPL.")
    try:
        start, end = _parse_date(start_date), _parse_date(end_date)
    except (ValueError, TypeError):
        return _failure(symbol, "INVALID_DATE", "Dates must be valid YYYY-MM-DD values.")
    if start > end:
        return _failure(symbol, "INVALID_DATE_RANGE", "start_date must not follow end_date.")
    if (end - start).days > MAX_RANGE_DAYS:
        return _failure(symbol, "DATE_RANGE_TOO_LARGE", "Query at most 3650 calendar days at once.")
    # A date-only provider end_date is a midnight cutoff and can omit that
    # day's close. Send full exchange-local day bounds; still filter rows below.
    # https://support.twelvedata.com/en/articles/5214728-getting-historical-data
    payload = _request("time_series", symbol, {
        "interval": "1day", "start_date": f"{start_date}T00:00:00",
        "end_date": f"{end_date}T23:59:59",
        "order": "asc", "outputsize": 5000, "adjust": "splits", "prepost": "false",
    })
    if payload.get("status") == "error":
        return payload
    rows = payload.get("values")
    if rows == [] or rows is None:
        return _failure(symbol, "NO_DATA", "No daily prices were returned for this range.")
    try:
        if not isinstance(rows, list):
            raise ValueError("Invalid values")
        currency = _check_identity(payload["meta"], symbol)
        prices = {}
        for row in rows:
            day = _parse_date(row["datetime"])
            value = _price(row["close"])
            if start <= day <= end:
                key = day.isoformat()
                if key in prices and prices[key] != value:
                    raise ValueError("Conflicting prices for the same date")
                prices[key] = value
    except (KeyError, ValueError, TypeError, OverflowError):
        return _failure(symbol, "INVALID_RESPONSE", "Daily prices have invalid or missing fields.")
    if not prices:
        return _failure(symbol, "NO_DATA", "No daily prices fall within the requested range.")
    if len(rows) >= 5000:
        return _failure(symbol, "INCOMPLETE_DATA", "Provider row limit reached; use a shorter range.")
    ordered = [{"date": day, "close": prices[day]} for day in sorted(prices)]
    return {
        "status": "success", "symbol": symbol, "currency": currency, "source": SOURCE,
        "start_date": start_date, "end_date": end_date, "interval": "1day",
        "price_type": "split_adjusted_close", "adjustment": "splits",
        "prices": ordered, "data_start": ordered[0]["date"], "data_end": ordered[-1]["date"],
        "count": len(ordered), "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "warnings": ["Not dividend-adjusted total-return data.",
                     "Missing dates are not filled; full trading-calendar coverage is unverified.",
                     "A current-day daily bar may be incomplete until the exchange session ends."],
    }
