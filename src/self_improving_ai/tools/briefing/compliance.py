"""Rule-based compliance checks against client portfolio and profile data."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_HIGH_RISK_TICKERS = frozenset({"ARKK", "TSLA", "TQQQ", "SQQQ", "UVXY"})
_TAX_DEFERRED_TYPES = frozenset({"ira", "401k", "inherited_ira", "403b"})


def _load_households() -> list[dict]:
    path = _DATA_DIR / "clients" / "households.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


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
        "title": f"Verify distribution requirements — client is {age}",
        "detail": (f"Client is {age} with recorded tax-deferred accounts: {acct_list}. "
                   "Confirm the applicable account, beneficiary and distribution requirements."),
        "rule": "Illustrative age-based review trigger; this is not a determination of legal eligibility or due amounts.",
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


def _check_beneficiary(profile: dict, as_of: date | None = None) -> list[dict]:
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
    if ((as_of or date.today()) - reviewed).days > 365:
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



from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes
def check_compliance_flags(client_id: str) -> dict:
    """Return sourced items for advisor confirmation from profile and CRM fixtures.

    Args:
        client_id: The client household identifier.

    Returns:
        Active confirmation flags, source locators and explicit partial coverage.
        An empty flags list is not compliance clearance. No legal rules are inferred
        from synthetic news, and no CRM/account records are modified.
    """
    profile = get_client_profile(client_id)
    if "error" in profile:
        return profile
    notes = get_crm_notes(client_id, limit=100)
    if "error" in notes:
        return notes
    household = next(record for record in _load_households() if record.get("client_id") == client_id)
    accounts = household.get("accounts", [])
    total = sum(holding["market_value"] for account in accounts for holding in account.get("holdings", []))
    from self_improving_ai.tools.briefing.workspace_sources import current_scope
    scope = current_scope()
    cutoff = scope["as_of"] if scope else profile["_provenance"]["as_of"]
    policy = (_check_rmd(profile,accounts) + _check_concentration(accounts,total)
        + _check_suitability(profile,accounts) + _check_beneficiary(profile,date.fromisoformat(cutoff))
        + _check_unrealized(accounts))
    flags = [{**flag, "id":f"{client_id}-POLICY-{index}", "status":"needs_confirmation",
        "description":flag["detail"], "source_ids":["PROFILE","HOLDINGS"],
        "policy_scope":"Illustrative team review rules, not regulatory clearance",
        "next_action":"Verify source records and applicable requirements with the advisor."}
        for index,flag in enumerate(policy)]
    if not profile.get("state"):
        flags.append({"id": f"{client_id}-PROFILE-STATE", "code": "PROFILE_STATE_MISSING",
            "status": "needs_confirmation", "severity": "attention",
            "title": "Confirm the state of residence",
            "description": "The provided profile has no state of residence. Confirm it before any state-specific assessment.",
            "source_ids": ["PROFILE"], "locators": [{"source_id": "PROFILE", "field": "state"}],
            "next_action": "Ask the client to confirm their state of residence."})
    for index, note in enumerate(notes["notes"]):
        if "compliance flag:" not in note["text"].lower():
            continue
        flags.append({"id": f"{client_id}-CRM-{index}", "code": "RECORDED_COMPLIANCE_FOLLOWUP",
            "status": "needs_confirmation", "severity": "attention",
            "title": "Verify a recorded compliance follow-up", "description": note["text"],
            "source_ids": [f"NOTE-{index}"],
            "locators": [{"source_id": f"NOTE-{index}", "date": note["date"], "author": note["author"]}],
            "next_action": "Review original account and beneficiary records with the advisor before confirming any distribution schedule."})
    return {"status": "ok", "client_id": client_id, "flags": flags,
        "assessment_status": "not_cleared", "coverage": "partial_synthetic_records",
        "scope": "Team policy review checks, profile completeness and explicitly recorded CRM follow-ups",
        "limitations": ["An empty flags list does not establish compliance.",
            "Account documentation and applicable regulations have not been independently checked.",
            "Flags identify confirmation work, not established violations."],
        "_provenance": profile["_provenance"]}
