"""Review completed follow-up preparations without rewriting historical briefs.

This bounded comparison observes agenda coverage, not what was said in a meeting.
A calendar end time is not a transcript or proof of a completed client action.
"""

import hashlib
import json
from datetime import datetime, timedelta
from itertools import pairwise
from threading import RLock

from self_improving_ai.agents.briefing.learning import LearningStore
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.orchestrator.memory import tokens
from self_improving_ai.workspace_store import workspace_snapshot

_lock = RLock()
_GENERAL = {"prepare", "review", "follow", "up", "discuss", "confirm", "update", "plan", "planning", "meeting", "client", "current", "questions"}


def _words(text):
    return {word for word in tokens(text) if len(word) >= 3 and word not in _GENERAL}


def _items(brief, section):
    return next((s["items"] for s in brief["sections"] if s["id"] == section), [])


def _gap(previous, later):
    agenda = _words(" ".join(i["title"] + " " + i["text"] for i in _items(previous, "priorities")))
    follow_up = _words(later["focus"] + " " + " ".join(
        i["title"] + " " + i["text"] for i in _items(later, "priorities")))
    sources = {s["id"] for s in previous["workflow"]["evidence"]["sources"]}
    for action in _items(previous, "actions"):
        topic = _words(action["title"])
        if not topic or topic & agenda or len(topic & follow_up) < min(2, len(topic)):
            continue
        if action["source_ids"] and set(action["source_ids"]) <= sources:
            return action
    return None


def review_completed_meetings(now, path=None, current_events=None):
    """At most 100 retained drafts, latest per event, same-client adjacent pairs."""
    if len(now) == 10:
        now += "T00:00:00-05:00"
    current = {event["id"]: event for event in (current_events if current_events is not None
                                               else workspace_snapshot("calendar", path=path))}
    drafts, learning = DraftStore(path), LearningStore(path)
    completed = {}
    for summary in drafts.summaries()[:100]:
        brief = drafts.get(summary["id"])["brief"]
        event = brief.get("calendar_event") or {}
        record = current.get(event.get("id"))
        workflow = brief.get("workflow", {})
        if not record or "evidence" not in workflow or workflow.get("quality", {}).get("verdict") != "pass":
            continue
        fields = ("client_id", "title", "date", "start_time", "end_time", "notes")
        if any(event.get(field) != record.get(field) for field in fields):
            continue
        end = record["date"] + "T" + record["end_time"][:5]
        if end >= now[:16] or record["date"] < (datetime.fromisoformat(now[:10]) - timedelta(days=180)).date().isoformat():
            continue
        if event["id"] not in completed:
            completed[event["id"]] = brief
    grouped = {}
    for brief in completed.values():
        grouped.setdefault(brief["client_id"], []).append(brief)
    outcomes = []
    for client_id, meetings in grouped.items():
        meetings.sort(key=lambda b: b["meeting_date"] + b["meeting_time"])
        for previous, later in pairwise(meetings):
            prior_record, later_record = drafts.get(previous["id"]), drafts.get(later["id"])
            key = "retrospective-" + hashlib.sha256(
                (prior_record["digest"] + later_record["digest"]).encode()).hexdigest()[:24]
            with _lock:
                with learning.db() as db:
                    row = db.execute("SELECT payload FROM meeting_learning_actions WHERE id=?", (key,)).fetchone()
                saved = json.loads(row[0]) if row else {}
                if saved.get("status") == "complete":
                    continue
                action = _gap(previous, later)
                if not action:
                    learning.action(key, client_id, "retrospective_review", {"status": "complete", "result": "no_supported_gap"})
                    continue
                event_id = saved.get("feedback_id")
                available = later["calendar_event"]["date"] + "T" + later["calendar_event"]["end_time"][:5]
                reason = f"A later preparation revisited '{action['title']}' without it appearing in the earlier discussion priorities."
                payload = {"summary": reason, "previous_brief_id": previous["id"], "later_brief_id": later["id"],
                    "later_meeting_date": later["meeting_date"], "available_after": available,
                    "lesson_key": "actions_first", "source_ids": action["source_ids"],
                    "observation": "preparation_comparison_after_scheduled_end",
                    "limitation": "This compares retained preparations; no meeting transcript or action-completion evidence was supplied."}
                if not event_id:
                    with learning.db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        event_id = learning.record(previous, "retrospective", prior_record["revision"], payload, db=db)
                        db.execute("INSERT OR REPLACE INTO meeting_learning_actions VALUES (?,?,?,?)",
                                   (key, client_id, "retrospective_review", json.dumps({"status": "pending", "feedback_id": event_id})))
                memory = learning.memory(client_id).load()
                if "actions_first" not in memory.preferences:
                    learning.remember(later, ["actions_first"], event_id, "Follow-up review: surface outstanding actions",
                                      available_after=available, adoption_type="observed_agenda_gap_not_statistical_policy_improvement")
                with learning.db() as db:
                    db.execute("UPDATE meeting_learning_actions SET payload=? WHERE id=?",
                               (json.dumps({"status": "complete", "feedback_id": event_id, "previous_brief_id": previous["id"], "later_brief_id": later["id"]}), key))
                outcomes.append(payload)
    return outcomes
