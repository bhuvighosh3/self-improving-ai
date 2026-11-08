"""Validate portfolio fixture references, units, scenario parameters, and Advisor cases."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _number(value):
    return (isinstance(value, (float, int)) and not isinstance(value, bool)
            and math.isfinite(value))


def validate_project(root: Path = ROOT) -> dict:
    errors = []
    warnings = []
    portfolio = root / "src/self_improving_ai/data/portfolio"

    def read(path):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"),
                              object_pairs_hook=_no_duplicate_keys,
                              parse_constant=_reject_constant)
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
            return None

    try:
        from self_improving_ai.client_store import load_households
        households = load_households()
    except Exception:
        households = None
        errors.append("Could not load client data from Firestore")
    asset_doc = read(portfolio / "asset_class_map.json")
    target_doc = read(portfolio / "target_allocations.json")
    goal_doc = read(portfolio / "financial_goals.json")
    case_doc = read(portfolio / "portfolio_advisor_cases.json")

    def report(clients=0, tickers=0, cases=0):
        return {"status": "error" if errors else "success",
                "client_count": clients, "ticker_count": tickers, "case_count": cases,
                "errors": errors, "warnings": warnings}

    if errors:
        return report()
    if not isinstance(households, list) or not all(
        isinstance(doc, dict) for doc in (asset_doc, target_doc, goal_doc, case_doc)
    ):
        errors.append("Expected a households array and four portfolio JSON objects.")
        return report()
    clients, tickers = set(), set()
    try:
        for household in households:
            cid = household["client_id"]
            if not isinstance(cid, str) or cid in clients:
                raise ValueError("Invalid or duplicated client_id")
            clients.add(cid)
            for account in household["accounts"]:
                for holding in account["holdings"]:
                    ticker = holding["ticker"]
                    if not isinstance(ticker, str):
                        raise ValueError("Invalid holding ticker")
                    tickers.add(ticker)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"households.json structure: {exc}")
        return report()
    assets = asset_doc.get("assets")
    if not isinstance(assets, dict):
        errors.append("asset_class_map.json: assets must be an object.")
        return report(len(clients), len(tickers))
    if set(assets) != tickers:
        errors.append(f"Asset coverage mismatch; missing={sorted(tickers-set(assets))}, "
                      f"extra={sorted(set(assets)-tickers)}")
    for ticker, entry in assets.items():
        if (not isinstance(entry, dict) or entry.get("asset_class") not in {"stock", "bond"}
                or entry.get("instrument_type") not in {"common_stock", "ETF", "mutual_fund"}):
            errors.append(f"{ticker}: invalid asset class or instrument type.")

    for label, doc in (("target_allocations", target_doc), ("financial_goals", goal_doc)):
        if doc.get("data_kind") != "synthetic_scenario":
            errors.append(f"{label}: data_kind must explicitly label the synthetic scenario.")
        if doc.get("review_status") == "draft_pending_owner_confirmation":
            warnings.append(f"{label}: demo parameters still require owner confirmation.")

    if target_doc.get("weight_unit") != "decimal":
        errors.append("Target weights must use decimal units.")
    if target_doc.get("scope") != "client_all_accounts":
        errors.append("Target scope must be client_all_accounts.")
    if (goal_doc.get("currency") != "USD" or goal_doc.get("amount_unit") != "USD"
            or goal_doc.get("horizon_unit") != "years"
            or goal_doc.get("cash_flow_unit") != "USD_per_year"
            or goal_doc.get("contribution_timing") != "end_of_year"
            or goal_doc.get("withdrawal_timing") != "end_of_year"
            or goal_doc.get("inflation_basis") != "nominal"
            or goal_doc.get("starting_value_basis") != "sum_of_fixture_market_value"):
        errors.append("Goal units, timing, inflation basis, or starting-value basis are invalid.")

    def client_records(doc, key):
        records = doc.get(key)
        if not isinstance(records, list):
            errors.append(f"{key}: expected an array.")
            return []
        found = []
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("client_id"), str):
                errors.append(f"{key}: invalid record or client_id.")
                continue
            found.append(record["client_id"])
        if len(set(found)) != len(found):
            errors.append(f"{key}: duplicate client_id.")
        if set(found) != clients:
            errors.append(f"{key}: client_id coverage does not match households.json.")
        return [record for record in records if isinstance(record, dict)]

    for record in client_records(target_doc, "allocations"):
        weights = record.get("weights")
        if (not isinstance(weights, dict) or set(weights) != {"stock", "bond"}
                or not all(_number(v) and 0 <= v <= 1 for v in weights.values())
                or not math.isclose(sum(weights.values()), 1, rel_tol=0, abs_tol=1e-9)):
            errors.append(f"{record.get('client_id')}: weights must be stock/bond decimals summing to 1.")
        if not record.get("assumption"):
            errors.append(f"{record.get('client_id')}: target assumption is missing.")

    for record in client_records(goal_doc, "goals"):
        cid = record.get("client_id")
        amount, years = record.get("target_amount"), record.get("years")
        if not _number(amount) or amount <= 0:
            errors.append(f"{cid}: target_amount must be positive.")
        if not isinstance(years, int) or isinstance(years, bool) or not 1 <= years <= 120:
            errors.append(f"{cid}: years must be a positive integer, at most 120.")
        for key in ("annual_contribution", "annual_withdrawal"):
            if not _number(record.get(key)) or record[key] < 0:
                errors.append(f"{cid}: {key} must be a nonnegative finite USD/year amount.")
        if not record.get("goal_type") or not record.get("assumption"):
            errors.append(f"{cid}: goal_type and assumption are required.")
        if _number(record.get("annual_withdrawal")) and record["annual_withdrawal"] > 0:
            warnings.append(f"{cid}: projection must account for annual withdrawals.")

    cases = case_doc.get("cases")
    if not isinstance(cases, list):
        errors.append("Advisor cases must be an array.")
        return report(len(clients), len(tickers))
    if not 12 <= len(cases) <= 15:
        errors.append("Expected 12 to 15 Advisor cases.")
    ids = []
    for case in cases:
        if not isinstance(case, dict):
            errors.append("Advisor case must be an object.")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append("Every case requires a case_id.")
            continue
        ids.append(case_id)
        for key in ("question", "category", "execution_status"):
            if not isinstance(case.get(key), str) or not case[key]:
                errors.append(f"{case_id}: missing {key}.")
        for key in ("symbols", "expected_tools", "required_data", "expected_information"):
            if not isinstance(case.get(key), list) or not all(
                isinstance(value, str) and value for value in case.get(key, [])
            ):
                errors.append(f"{case_id}: {key} must be an array of nonempty strings.")
        if not case.get("expected_information"):
            errors.append(f"{case_id}: expected_information cannot be empty.")
        cid = case.get("client_id")
        if cid is not None and cid not in clients and case.get("category") != "invalid_client":
            errors.append(f"{case_id}: unrecognized client_id.")
        if not isinstance(case.get("requires_live_api"), bool):
            errors.append(f"{case_id}: requires_live_api must be boolean.")
    if len(ids) != len(set(ids)):
        errors.append("Advisor case_id values must be unique.")
    demos = case_doc.get("demo_case_ids")
    if (not isinstance(demos, list) or not 2 <= len(demos) <= 3
            or any(not isinstance(value, str) or value not in ids for value in demos)
            or len(set(demos)) != len(demos)):
        errors.append("Select 2 or 3 different existing demo case IDs.")
    elif not any(isinstance(case, dict) and case.get("case_id") in demos
                 and case.get("requires_live_api") for case in cases):
        errors.append("At least one demo must query the external API.")
    warnings.append("Draft market return/volatility assumptions still require owner confirmation.")
    return report(len(clients), len(tickers), len(cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = validate_project(args.project_root)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
