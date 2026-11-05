"""Conservative currency-amount check for model prose against executed tool data.

This is not a complete semantic fact checker. It detects unsupported dollar/USD
amounts; percentages, associations, unsupported formats and prose need evaluation.
"""
from __future__ import annotations

import math
import re

MONEY_FIELDS = {"market_value", "total_market_value", "cost_basis", "price", "close",
                "hypothetical_adjustment_usd", "initial_value", "target_amount",
                "annual_contribution", "annual_withdrawal", "ending_value_p10",
                "ending_value_median", "ending_value_p90", "median", "annual_income"}
NUMBER = r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
SCALE = r"\s*(?P<scale>billion|million|thousand|[KMB](?![A-Za-z]))?"
PREFIX = re.compile(r"(?:US\$|\$|\bUSD\s*)\s*[+-]?\s*" + NUMBER + SCALE, re.I)
SUFFIX = re.compile(r"(?<![\w.])" + NUMBER + SCALE + r"\s*USD\b", re.I)
SCALES = {"": 1, "k": 1000, "thousand": 1000, "m": 1000000, "million": 1000000,
          "b": 1000000000, "billion": 1000000000}


def currency_matches(text: str):
    def omit_math(match):
        body = match[1]
        mathematical = bool(re.search(r"\\[A-Za-z]+", body)) or (
            bool(re.fullmatch(r"[\d.\s()+*/^=\-]+", body)) and bool(re.search(r"[+*/^=]", body)))
        return " " * len(match[0]) if mathematical else match[0]
    text = re.sub(r"\$([^$\n]{1,160})\$", omit_math, text)
    for pattern in (PREFIX, SUFFIX):
        for match in pattern.finditer(text):
            yield match


def unsupported_currency_amounts(text: str, trace: list[dict]) -> list[float | str]:
    """Return unmatched currency amounts only when successful financial data exists."""
    allowed = []

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in MONEY_FIELDS and isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item):
                    allowed.append(abs(item))
                else:
                    collect(item)
            # Account subtotals are a valid explanatory aggregation of holdings.
            holdings = value.get("holdings")
            if isinstance(holdings, list) and holdings and all(
                isinstance(row, dict) and isinstance(row.get("market_value"), (int, float))
                for row in holdings
            ):
                allowed.append(abs(sum(row["market_value"] for row in holdings)))
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str):
            # Scenario notes can explicitly cite a monthly withdrawal/home price.
            for match in currency_matches(value):
                allowed.append(float(match["number"].replace(",", "")) * SCALES[(match["scale"] or "").lower()])

    for entry in trace:
        result = entry.get("result", {})
        if entry.get("kind") == "result" and result.get("status") == "success":
            collect(result)
    if not allowed:
        return []  # Clarification and error replies have no financial result to check.
    unsupported = []
    for match in currency_matches(text):
        raw = match["number"].replace(",", "")
        multiplier = SCALES[(match["scale"] or "").lower()]
        amount = float(raw) * multiplier
        if not math.isfinite(amount):
            return ["out_of_range_currency_amount"]
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        tolerance = .5 * 10 ** -decimals * multiplier + 1e-8
        if not any(abs(amount - value) <= tolerance for value in allowed):
            unsupported.append(amount)
    return sorted(set(unsupported))
