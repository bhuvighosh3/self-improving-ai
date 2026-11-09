"""Read-only, cutoff-aware adapters over the Firestore CRM and optional sources."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from self_improving_ai.tools.briefing.crm import get_client_profile, get_crm_notes
from self_improving_ai.tools.portfolio.holdings import get_holdings
from self_improving_ai.tools.briefing.compliance import check_compliance_flags


def load_context(client_id: str) -> dict:
    from self_improving_ai.tools.briefing.crm_records import get_crm_context
    result = get_crm_context(client_id)
    if result.get("status") == "error":
        raise LookupError("Client not found")
    from self_improving_ai.tools.briefing.workspace_sources import current_scope
    scope = current_scope()
    if scope and scope["client_id"] != client_id:
        raise ValueError("Client is locked to the operational snapshot")
    if scope and scope["as_of"] < result["data_as_of"]:
        raise ValueError("Meeting precedes the available historical snapshot")
    return {"as_of": scope["as_of"] if scope else result["data_as_of"],
            "holdings_as_of": result["holdings_as_of"],
            "previous_meeting": result.get("previous_meeting"),
            "tasks": result.get("tasks", []),
            "context_revision": scope["revision"] if scope else "firestore-v1"}


def _records(client_id: str, kind: str) -> dict:
    context = load_context(client_id)
    from self_improving_ai.tools.briefing.crm_records import get_crm_records
    crm_result = get_crm_records(client_id, kind=kind)
    records = crm_result.get("records", [])
    if kind == "email":
        from self_improving_ai.tools.briefing.workspace_sources import email_originals
        records.extend(email_originals(client_id))
    items = [r for r in records if r.get("client_id") == client_id and r.get("kind") == kind
             and r.get("event_at", "")[:10] <= context["as_of"]
             and r.get("recorded_at", "")[:10] <= context["as_of"]]
    return {"status": "ok" if items else "no_results", "client_id": client_id,
            "as_of": context["as_of"], "items": items,
            "scope": "Available records only; not complete client history"}


def list_previous_meetings(client_id: str) -> dict:
    """Read available original minutes. A previous meeting date is not full minutes."""
    return _records(client_id, "minutes")


def list_client_tasks(client_id: str) -> dict:
    """Read every task status, excluding records not yet visible at fixture cutoff."""
    context = load_context(client_id)
    items = [t for t in context.get("tasks", [])
             if t.get("recorded_at", t["note_date"])[:10] <= context["as_of"]]
    return {"status": "ok", "items": items, "as_of": context["as_of"]}


def search_sources(client_id: str, query: str = "") -> dict:
    """Locate updates after the previous meeting; snippets are not original evidence."""
    context = load_context(client_id)
    records = []
    for kind in ("email", "investment_update", "service_update", "review_confirmation"):
        records.extend(_records(client_id, kind)["items"])
    records = [r for r in records if r["event_at"][:10] > context.get("previous_meeting", "")
               and query.lower() in (r["title"] + r["text"]).lower()]
    return {"status": "ok" if records else "no_results", "as_of": context["as_of"],
            "searched_from": context.get("previous_meeting"), "query": query,
            "hits": [{"id": r["id"], "title": r["title"], "snippet": r["text"][:100]}
                     for r in records], "complete_history": False}


def read_source(client_id: str, source_id: str) -> dict:
    """Read original content after checking client and cutoff again."""
    for kind in ("minutes", "email", "investment_update", "service_update", "review_confirmation"):
        for record in _records(client_id, kind)["items"]:
            if record["id"] == source_id:
                return {"status": "ok", "record": record}
    return {"status": "denied", "error": "Source is unavailable for this client and cutoff"}


def prepare_context(client_id: str, meeting_type: str = "general_meeting", focus: str = "") -> dict:
    """Collect raw evidence and actual tool results, without inventing missing coverage."""
    from self_improving_ai.agents.briefing.skills import ROUTINES

    if meeting_type not in ROUTINES:
        raise ValueError("Unsupported meeting type")
    context = load_context(client_id)
    sources, trace = [], []
    confirmed_coverage = False

    def call(name, arguments, fn):
        started = datetime.now(timezone.utc).isoformat()
        result = fn(**arguments)
        trace.append({"tool": name, "arguments": arguments, "result": result,
                      "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat()})
        return result

    profile = call("get_client_profile", {"client_id": client_id}, get_client_profile)
    if "error" in profile:
        raise LookupError("Client not found")
    holdings = call("get_holdings", {"client_id": client_id}, get_holdings)
    notes = call("get_crm_notes", {"client_id": client_id, "limit": 100}, get_crm_notes)
    notes["notes"] = [n for n in notes["notes"] if n["date"] <= context["as_of"]]
    compliance = call("check_compliance_flags", {"client_id": client_id}, check_compliance_flags)
    if "error" in compliance:
        raise ValueError("Compliance fixture checks are unavailable")
    minutes = call("list_previous_meetings", {"client_id": client_id}, list_previous_meetings)
    tasks = call("list_client_tasks", {"client_id": client_id}, list_client_tasks)
    updates = call("search_sources", {"client_id": client_id}, search_sources)

    def source(sid, title, content, kind, when=None):
        sources.append({"id": sid, "client_id": client_id, "title": title, "kind": kind,
                        "date": when, "version": "fixture-v1", "author": "Synthetic CRM",
                        "content": content, "read_state": "full"})
        if kind == "holdings":
            sources[-1]["currency"] = "USD"

    source("PROFILE", "Client profile", json.dumps(profile), "profile")
    source("HOLDINGS", "Managed-account snapshot", json.dumps(holdings), "holdings",
           context["holdings_as_of"])
    source("TASKS", "Tasks in all states", json.dumps(tasks["items"]), "tasks", context["as_of"])
    source("COMPLIANCE", "Recorded compliance follow-ups and coverage", json.dumps(compliance),
           "compliance_check", context["as_of"])
    sources[-1].update(author="Read-only fixture checks", version="briefing-tools-v1")
    for i, note in enumerate(notes["notes"]):
        source(f"NOTE-{i}", f"CRM note by {note['author']}", note["text"], "crm_note", note["date"])
    for record in minutes["items"]:
        source(record["id"], record["title"], record["text"], "minutes", record["event_at"][:10])
        sources[-1].update(recorded_at=record["recorded_at"], version=record["version"])
    for hit in updates["hits"]:
        result = call("read_source", {"client_id": client_id, "source_id": hit["id"]}, read_source)
        if result["status"] == "ok":
            r = result["record"]
            source(r["id"], r["title"], r["text"], r["kind"], r["event_at"][:10])
            sources[-1]["origin"] = r.get("origin", "fixture")
            sources[-1].update(recorded_at=r["recorded_at"], version=r["version"])
            confirmed_coverage |= (r["kind"] == "review_confirmation"
                                   and r.get("covers_from") == context.get("previous_meeting")
                                   and r.get("covers_through") == context["as_of"]
                                   and set(r.get("domains", [])) == {"client", "investment", "service"})
    if focus:
        from self_improving_ai.tools.briefing.news import search_market_news

        news = call("search_market_news", {"query": focus, "max_results": 100}, search_market_news)
        for article in news["results"]:
            if article["date"] <= context["as_of"] and any(
                token in (article["headline"] + " " + article["text"]).lower()
                for token in focus.lower().split() if len(token) > 3
            ):
                source(article["id"], article["headline"], article["text"], "news", article["date"])
                sources[-1].update(provenance=news.get("_provenance", {}), author=news.get("_provenance", {}).get("source", "Synthetic news"))
    return {"client_id": client_id, "as_of": context["as_of"],
            "previous_meeting": context.get("previous_meeting"), "meeting_type": meeting_type,
            "routine_items": ROUTINES[meeting_type], "template_version": "proposal-v1",
            "sources": sources, "trace": trace,
            "coverage": {"profile": "checked", "accounts": "checked", "tasks": "checked",
                         "prior_meeting": "checked" if minutes["items"] else "no_results",
                         "communications": updates["status"],
                         "investment_service_history": "checked" if confirmed_coverage else "incomplete"}}
