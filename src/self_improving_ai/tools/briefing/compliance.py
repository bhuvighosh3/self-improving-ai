"""Rule-based compliance checks against client portfolio and profile data."""

from __future__ import annotations

from datetime import date, datetime, timezone

from self_improving_ai.client_store import load_households as _load_households

_HIGH_RISK_TICKERS = frozenset({"ARKK", "TSLA", "TQQQ", "SQQQ", "UVXY"})
_TAX_DEFERRED_TYPES = frozenset({"ira", "401k", "inherited_ira", "403b", "roth_ira"})


def _check_rmd(profile: dict, accounts: list[dict]) -> list[dict]:
    age = profile.get("age")
    if age is None or age < 73:
        return []
    tax_deferred = [a for a in accounts if a.get("type", "").lower() in _TAX_DEFERRED_TYPES]
    if not tax_deferred:
        return []
    acct_list = ", ".join(a["account_id"] for a in tax_deferred)
    return [{
        "code": "RMD_REQUIRED",
        "severity": "critical",
        "title": f"RMD required — client is {age}",
        "detail": (f"Client is {age} years old with {len(tax_deferred)} tax-deferred "
                   f"account(s): {acct_list}. Required Minimum Distributions must be "
                   "calculated and scheduled."),
        "rule": "Clients age 73+ with tax-deferred accounts must take annual RMDs per IRC 401(a)(9).",
    }]


def _check_concentration(accounts: list[dict], total_value: float) -> list[dict]:
    if total_value <= 0:
        return []
    by_ticker: dict[str, float] = {}
    for account in accounts:
        for holding in account.get("holdings", []):
            ticker = holding["ticker"]
            by_ticker[ticker] = by_ticker.get(ticker, 0) + holding["market_value"]
    flags = []
    for ticker, value in sorted(by_ticker.items(), key=lambda x: x[1], reverse=True):
        pct = value / total_value
        if pct > 0.25:
            flags.append({
                "code": "CONCENTRATION_LIMIT",
                "severity": "warning",
                "title": f"{ticker} exceeds 25% concentration ({pct:.0%})",
                "detail": (f"{ticker} represents {pct:.1%} (${value:,.0f}) of the "
                           f"${total_value:,.0f} portfolio."),
                "rule": "Single position concentration should not exceed 25% of total portfolio value.",
            })
    return flags


def _check_suitability(profile: dict, accounts: list[dict]) -> list[dict]:
    risk = profile.get("risk_tolerance", "").lower()
    if risk not in ("conservative",):
        return []
    flags = []
    for account in accounts:
        for holding in account.get("holdings", []):
            if holding["ticker"] in _HIGH_RISK_TICKERS:
                flags.append({
                    "code": "SUITABILITY_MISMATCH",
                    "severity": "warning",
                    "title": f"{holding['ticker']} may not suit {risk} risk tolerance",
                    "detail": (f"Client has {risk} risk tolerance but holds {holding['ticker']} "
                               f"(${holding['market_value']:,.0f}) in {account['account_id']}."),
                    "rule": "High-volatility or concentrated sector holdings may be unsuitable "
                            "for conservative investors.",
                })
    return flags


def _check_beneficiary(profile: dict) -> list[dict]:
    last_reviewed = profile.get("beneficiary_last_reviewed")
    if last_reviewed is None:
        return [{
            "code": "BENEFICIARY_UNKNOWN",
            "severity": "info",
            "title": "Beneficiary designation review date unknown",
            "detail": "No beneficiary review date is on file. Confirm designations are current.",
            "rule": "Beneficiary designations should be reviewed at least annually.",
        }]
    reviewed = date.fromisoformat(last_reviewed)
    if (date.today() - reviewed).days > 365:
        return [{
            "code": "BENEFICIARY_STALE",
            "severity": "warning",
            "title": "Beneficiary designations may be outdated",
            "detail": f"Last reviewed {last_reviewed}. Over 12 months since last review.",
            "rule": "Beneficiary designations should be reviewed at least annually.",
        }]
    return []


def _check_unrealized(accounts: list[dict]) -> list[dict]:
    flags = []
    for account in accounts:
        for holding in account.get("holdings", []):
            mv = holding["market_value"]
            cb = holding["cost_basis"]
            if cb <= 0:
                continue
            change = mv - cb
            pct = abs(change) / cb
            if abs(change) > 10_000 or pct > 0.30:
                is_gain = change > 0
                flags.append({
                    "code": "LARGE_UNREALIZED_GAIN" if is_gain else "LARGE_UNREALIZED_LOSS",
                    "severity": "info",
                    "title": (f"{holding['ticker']}: unrealized {'gain' if is_gain else 'loss'} "
                              f"${abs(change):,.0f}"),
                    "detail": (f"{holding['ticker']} in {account['account_id']}: market value "
                               f"${mv:,.0f}, cost basis ${cb:,.0f}, unrealized "
                               f"{'gain' if is_gain else 'loss'} ${abs(change):,.0f} "
                               f"({pct:.0%} of cost basis)."),
                    "rule": "Positions with large unrealized gains or losses should be flagged "
                            "for tax planning review.",
                })
    return flags


def check_compliance_flags(client_id: str) -> dict:
    """Run rule-based compliance checks against client data."""
    for household in _load_households():
        if household.get("client_id") == client_id:
            profile = household.get("profile", {})
            accounts = household.get("accounts", [])
            total = sum(
                h["market_value"]
                for a in accounts
                for h in a.get("holdings", [])
            )
            flags = []
            flags.extend(_check_rmd(profile, accounts))
            flags.extend(_check_concentration(accounts, total))
            flags.extend(_check_suitability(profile, accounts))
            flags.extend(_check_beneficiary(profile))
            flags.extend(_check_unrealized(accounts))
            return {
                "client_id": client_id,
                "flags": flags,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
    return {
        "client_id": client_id,
        "flags": [],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "error": f"Client {client_id} not found",
    }
