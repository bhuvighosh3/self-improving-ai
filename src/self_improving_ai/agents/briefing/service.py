"""Evidence-backed meeting preparation using the repository's synthetic fixtures."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes
from self_improving_ai.tools.briefing.news import search_market_news
from self_improving_ai.tools.portfolio.holdings import get_holdings

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
STOP_WORDS = {"the", "and", "for", "with", "this", "that", "meeting", "review", "prepare", "discuss", "client"}


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2} - STOP_WORDS


def _item(item_id: str, title: str, text: str, refs: list[str], **extra) -> dict:
    return {"id": item_id, "title": title, "text": text, "source_ids": refs, **extra}


def generate_meeting_brief(request: MeetingBriefRequest) -> dict:
    """Read real mock tools, calculate facts, and retain the evidence for each item.

    This is a deterministic demo workflow. It makes no LLM or external market calls.
    """
    profile = get_client_profile(request.client_id)
    if "error" in profile:
        raise LookupError("Client not found. Select a client from the list.")

    context = json.loads((DATA_DIR / "clients/meeting_context.json").read_text())
    data_as_of = date.fromisoformat(context["data_as_of"])
    if request.meeting_date < data_as_of:
        raise ValueError(f"This demo supports meetings on or after {data_as_of}. Historical snapshots are not available.")
    if not request.focus.strip():
        raise ValueError("Enter a meeting focus.")

    client_context = context["households"].get(request.client_id, {})
    notes = get_crm_notes(request.client_id)["notes"]
    notes = [note for note in notes if note["date"] <= data_as_of.isoformat()]
    holdings_result = get_holdings(request.client_id)
    accounts = holdings_result["accounts"]
    positions = [dict(h, account_id=a["account_id"], account_type=a["type"])
                 for a in accounts for h in a.get("holdings", [])]
    total = holdings_result["total_market_value"]
    sources = [
        {"id": "PROFILE", "kind": "Client profile", "title": profile["name"],
         "date": None, "author": "Synthetic CRM", "content": json.dumps(profile, indent=2)},
        {"id": "HOLDINGS", "kind": "Holdings snapshot", "title": "Household holdings and cost basis",
         "date": context["holdings_as_of"], "author": "Synthetic account ledger",
         "content": json.dumps(accounts, indent=2)},
    ]
    note_pairs = []
    for index, note in enumerate(notes, 1):
        ref = f"CRM-{index}"
        sources.append({"id": ref, "kind": "CRM note", "title": f"Note by {note['author']}",
                        "date": note["date"], "author": note["author"], "content": note["text"]})
        note_pairs.append((ref, note))

    focus_words = _words(request.focus)
    tickers = {position["ticker"].lower() for position in positions}
    requested_tickers = tickers & focus_words
    context_sectors = set()
    if tickers & {"bnd", "mub", "vtip"}:
        context_sectors |= {"macro", "fixed_income"}
    goals = " ".join(profile.get("goals", []))
    security_universe = set(json.loads((DATA_DIR / "prices/price_history.json").read_text()))
    security_universe = {ticker.lower() for ticker in security_universe}
    if "home" in goals:
        context_sectors.add("real_estate")
    if "growth" in goals:
        context_sectors |= {"tech", "equities"}
    if "income" in goals:
        context_sectors |= {"fixed_income", "equities"}

    ranked_news = []
    for article in search_market_news(request.focus, max_results=100)["results"]:
        if article["date"] > data_as_of.isoformat() or article["sector"] in {"lifestyle", "health", "entertainment"}:
            continue
        terms = _words(article["headline"] + " " + article["text"])
        direct_tickers = requested_tickers & terms
        held_tickers = tickers & terms
        overlap = focus_words & terms
        sector_match = article["sector"] in context_sectors
        if security_universe & terms and not held_tickers and not sector_match:
            # A generic word such as "tax" should not select an unrelated security.
            continue
        score = len(direct_tickers) * 50 + len(overlap) * 5 + len(held_tickers) * 3 + int(sector_match) * 2
        if score <= 0:
            continue
        if direct_tickers:
            reason = "Directly relates to the requested position: " + ", ".join(sorted(t.upper() for t in direct_tickers)) + "."
        elif overlap:
            reason = "Matches the meeting focus: " + ", ".join(sorted(overlap)) + "."
        elif held_tickers:
            reason = "Mentions a household holding: " + ", ".join(sorted(t.upper() for t in held_tickers)) + "."
        else:
            reason = "Provides context for the household's holdings or stated goals."
        ranked_news.append((score, article["date"], dict(article, relevance=reason)))
    selected_news = [record[2] for record in sorted(ranked_news, key=lambda record: (record[0], record[1]), reverse=True)[:3]]
    for article in selected_news:
        sources.append({"id": article["id"], "kind": "Market news", "title": article["headline"],
                        "date": article["date"], "author": "Synthetic news feed", "content": article["text"]})

    overview = [_item("overview", profile["primary_contact"],
        f"Goals: {', '.join(goal.replace('_', ' ') for goal in profile.get('goals', []))}. "
        f"Risk tolerance: {profile.get('risk_tolerance', 'not recorded')}. "
        f"Recorded investment horizon: {profile.get('investment_horizon', 'not recorded')}.", ["PROFILE"])]
    changes = [_item(ref, f"{note['date']} · {note['author']}", note["text"], [ref]) for ref, note in note_pairs[:3]]
    if not changes:
        changes = [_item("no-notes", "No recent notes", "Ask the client what has changed since the last review.", ["PROFILE"])]

    by_ticker = {}
    for position in positions:
        by_ticker[position["ticker"]] = by_ticker.get(position["ticker"], 0) + position["market_value"]
    highlights = [_item("household", "Household snapshot",
        f"${total:,.0f} across {len(accounts)} {'account' if len(accounts) == 1 else 'accounts'} and {len(positions)} account positions. "
        "Values are a dated snapshot, not live prices.", ["HOLDINGS"])]
    focused_positions = [p for p in positions if p["ticker"].lower() in requested_tickers]
    if not focused_positions:
        focused_positions = sorted(positions, key=lambda p: abs(p["market_value"] - p["cost_basis"]), reverse=True)[:1]
    for index, position in enumerate(focused_positions):
        change = position["market_value"] - position["cost_basis"]
        highlights.append(_item(f"position-{index}", f"{position['ticker']} · {position['account_id']}",
            f"Market value ${position['market_value']:,.0f}; cost basis ${position['cost_basis']:,.0f}; "
            f"unrealized {'gain' if change >= 0 else 'loss'} ${abs(change):,.0f}. "
            f"Account type: {position['account_type'].replace('_', ' ')}. This is not a tax savings estimate.", ["HOLDINGS"]))
    if by_ticker and total:
        ticker, value = max(by_ticker.items(), key=lambda pair: pair[1])
        highlights.append(_item("concentration", "Largest household position",
            f"{ticker}: ${value:,.0f}, or {value / total:.1%} of the recorded household portfolio (aggregated across accounts).", ["HOLDINGS"]))

    ranked_notes = sorted(note_pairs, key=lambda pair: (len(_words(pair[1]["text"]) & focus_words), pair[1]["date"]), reverse=True)
    priorities = []
    for index, (ref, note) in enumerate(ranked_notes[:3]):
        text = note["text"]
        lower = text.lower()
        if "harvest" in lower:
            title = "Review the loss position and tax context"
            question = "What recent or planned transactions and realized gains should the advisor consider before assessing harvesting?"
        elif "retire" in lower or "monte carlo" in lower:
            title = "Reconcile the retirement timeline"
            question = "Is the target retirement date unchanged, and which spending and contribution assumptions need updating?"
        elif "duration" in lower or "rates" in lower:
            title = "Discuss bond sensitivity and liquidity"
            question = "How soon might the client need these funds, and does the advisor need an updated duration calculation?"
        elif "home" in lower or "down payment" in lower:
            title = "Confirm the home purchase funding need"
            question = "What is the required down payment, purchase date, and available cash outside these accounts?"
        elif "withdraw" in lower or "spend" in lower:
            title = "Review the withdrawal requirement"
            question = "Is the recorded spending need current, and what other income or cash reserves are available?"
        elif "rmd" in lower or "compliance" in lower:
            title = "Verify the distribution requirements"
            question = "What account, beneficiary and age information must the advisor verify before confirming the schedule?"
        elif "college" in lower:
            title = "Plan the upcoming education funding"
            question = "When are payments due, and which account will fund them?"
        else:
            title = "Follow up on the previous discussion"
            question = "What has changed, and what decision or follow-up does the client need from this meeting?"
        priorities.append(_item(f"priority-{index}", title, text, [ref],
            why="Matches the meeting focus and a recorded client request." if _words(text) & focus_words else "Keeps an outstanding client concern on the agenda.",
            question=question, priority=index + 1))
    if not priorities:
        priorities = [_item("priority-focus", "Confirm the requested meeting scope", request.focus,
                            ["PROFILE"], why="No supporting CRM note is available for this focus.",
                            question="What outcome does the client want from today's meeting?", priority=1)]
    if not any(_words(note["text"]) & focus_words for _, note in note_pairs):
        priorities.insert(0, _item("priority-focus", "Confirm the requested meeting focus", request.focus, [],
                                  why="Provided by the advisor; no matching CRM note was found.",
                                  question="Which details should be confirmed directly with the client?", priority=1))
        priorities = priorities[:3]
        for index, item in enumerate(priorities, 1):
            item["priority"] = index
    if len(priorities) < 3 and by_ticker and total:
        ticker, value = max(by_ticker.items(), key=lambda pair: pair[1])
        priorities.append(_item("priority-allocation", "Confirm allocation against the client's goals",
            f"The largest recorded household position is {ticker} at {value / total:.1%} of the portfolio.",
            ["HOLDINGS", "PROFILE"], why="Connects the portfolio snapshot with the client's recorded goals and risk tolerance.",
            question="Does the current allocation still reflect the client's timeframe, liquidity needs and comfort with risk?",
            priority=len(priorities) + 1))

    actions = []
    for task in client_context.get("tasks", []):
        if task["status"] != "open":
            continue
        sources.append({"id": task["id"], "kind": "CRM task", "title": task["title"],
                        "date": task["note_date"], "author": task["owner"], "content": json.dumps(task, indent=2)})
        actions.append(_item(task["id"], task["title"],
                             f"Owner: {task['owner']}. Due: {task['due_date']}. Status: open.", [task["id"]]))

    confirmations = [_item("freshness", "Refresh account information",
        f"Holdings are dated {context['holdings_as_of']}. Confirm balances and transactions before making decisions.", ["HOLDINGS"])]
    if "early_retirement" in profile.get("goals", []):
        retirement_refs = [ref for ref, note in note_pairs if "retirement" in note["text"].lower()]
        confirmations.append(_item("horizon", "Confirm the planning horizon",
            f"The profile records {profile['investment_horizon']}, while CRM includes a separate early retirement target. "
            "Confirm which horizon applies to this discussion.", ["PROFILE"] + retirement_refs))
    if not profile.get("state"):
        confirmations.append(_item("state", "State of residence is missing",
            "Confirm the state of residence before requesting a state-specific tax calculation.", ["PROFILE"]))
    if "tax" in request.focus.lower() or "harvest" in request.focus.lower():
        confirmations.append(_item("tax", "Tax eligibility has not been assessed",
            "Transaction history, tax lots and the full tax situation are not supplied. The unrealized loss alone does not establish an eligible deduction or tax savings.", ["HOLDINGS"]))
    if any("rmd" in note["text"].lower() for _, note in note_pairs):
        confirmations.append(_item("distribution", "Distribution schedule requires verification",
            "Age and complete beneficiary/account details are not supplied. Synthetic news does not establish which rules apply to this client.",
            [ref for ref, note in note_pairs if "rmd" in note["text"].lower()]))
    confirmations.append(_item("performance", "Performance is not calculated",
        "Dated market values and cost basis are available; a portfolio return series adjusted for cash flows is not supplied.", ["HOLDINGS"]))

    sections = [
        {"id": "overview", "title": "Client Overview", "items": overview},
        {"id": "changes", "title": "Recent Changes & Requests", "items": changes},
        {"id": "portfolio", "title": "Portfolio Highlights", "items": highlights},
        {"id": "priorities", "title": "Discussion Priorities", "items": priorities},
        {"id": "actions", "title": "Open Action Items", "items": actions},
        {"id": "confirm", "title": "Items to Confirm", "items": confirmations},
    ]
    source_ids = {source["id"] for source in sources}
    if any(ref not in source_ids for section in sections for item in section["items"] for ref in item["source_ids"]):
        raise ValueError("The brief contains an unresolved evidence reference.")
    return {
        "id": str(uuid4()), "client_id": request.client_id, "client_name": profile["name"],
        "contact": profile["primary_contact"], "meeting_date": request.meeting_date.isoformat(),
        "meeting_time": request.meeting_time.strftime("%H:%M"), "timezone": "America/New_York",
        "focus": request.focus.strip(), "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_as_of": data_as_of.isoformat(), "previous_meeting": client_context.get("previous_meeting"),
        "mode": "simulation", "sections": sections, "news": selected_news, "sources": sources,
        "tools_called": ["get_client_profile", "get_crm_notes", "get_holdings", "search_market_news"],
    }
