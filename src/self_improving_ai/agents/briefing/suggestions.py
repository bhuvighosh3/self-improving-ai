"""Explainable follow-up suggestions from feedback and observed scheduling choices."""

import hashlib
from datetime import datetime, timedelta
from itertools import pairwise
from statistics import median

from self_improving_ai.agents.briefing.learning import LearningStore
from self_improving_ai.agents.briefing.store import DraftStore


def suggestions(now, events, path=None):
    store = LearningStore(path)
    actions = store.actions()
    dismissed = {a["id"] for a in actions if a["kind"] in {"dismissed", "accepted"}}
    result = []
    for summary in DraftStore(path).summaries():
        if summary.get("meeting_date", "9999") > now[:10]:
            continue
        brief = DraftStore(path).get(summary["id"])["brief"]
        if len(now) > 10 and brief["meeting_date"] + "T" + brief["meeting_time"][:5] >= now[:16]:
            continue
        feedback = next((e for e in store.events(brief_id=brief["id"]) if e["kind"] == "feedback"), None)
        if any(item["client_id"] == brief["client_id"] for item in result):
            continue
        event_id = (brief.get("calendar_event") or {}).get("id") or brief["id"]
        identifier = "followup-" + hashlib.sha256((brief["client_id"] + event_id).encode()).hexdigest()[:20]
        if identifier in dismissed or any(e.get("learning_suggestion_id") == identifier for e in events):
            continue
        # Only the latest feedback-bearing preparation for an appointment can suggest a follow-up.
        if any(s["client_id"] == brief["client_id"] and s.get("calendar_event", {})
               and s["calendar_event"].get("id") == event_id and s["id"] != brief["id"]
               and s.get("generated_at", "") > brief["generated_at"] for s in DraftStore(path).summaries()):
            continue
        history = [a["payload"] for a in actions if a["client_id"] == brief["client_id"]
                   and a["kind"] == "meeting_added" and a["payload"].get("date", "") <= now[:10]]
        dates = sorted({r["date"] for r in history})
        intervals = [(datetime.fromisoformat(b) - datetime.fromisoformat(a)).days for a, b in pairwise(dates)]
        intervals = [d for d in intervals if 1 <= d <= 60]
        learned_cadence = len(intervals) >= 2
        pending = next((s for s in brief["sections"] if s["id"] == "actions"), {"items": []})["items"]
        requested = feedback and feedback["payload"].get("follow_up")
        if not requested and not (learned_cadence and pending):
            continue
        days = round(median(intervals)) if learned_cadence else 7
        target = max(datetime.fromisoformat(brief["meeting_date"]) + timedelta(days=days),
                     datetime.fromisoformat(now[:10]) + timedelta(days=1))
        if any(e.get("client_id") == brief["client_id"] and e.get("date", "") > brief["meeting_date"]
               and now[:10] <= e.get("date", "") <= (target + timedelta(days=1)).date().isoformat() for e in events):
            continue  # A nearby next appointment already covers this client.
        time = sorted([r.get("start_time", "09:00") for r in history])
        start = time[len(time) // 2] if len(time) >= 3 else "09:00"
        hour, minute = map(int, start.split(":"))
        if hour >= 23:
            hour, minute = 9, 0
        target = target.replace(hour=hour, minute=minute)
        for _ in range(40):
            end = target + timedelta(minutes=45)
            overlaps = any(e.get("date") == target.date().isoformat()
                           and e.get("start_time", "") < end.strftime("%H:%M")
                           and e.get("end_time", "") > target.strftime("%H:%M") for e in events)
            if target.weekday() < 5 and not overlaps:
                break
            target += timedelta(days=1)
        else:
            continue
        topic = pending[0]["title"] if pending else brief["focus"]
        reason = ("You marked the previous meeting as needing a follow-up." if requested
                  else "The previous preparation lists open actions, and your recorded scheduling pattern suggests a follow-up.")
        reason += (f" Your recorded additions usually leave about {days} days between meetings."
                   if learned_cadence else " The proposed time is a starting suggestion; no scheduling pattern has been learned yet.")
        result.append({"id": identifier, "client_id": brief["client_id"], "client_name": brief["client_name"],
            "source_brief_id": brief["id"], "source_meeting_date": brief["meeting_date"],
            "reason": reason, "behavior_examples": len(history), "learned_cadence": learned_cadence,
            "event": {"title": ("Follow-up: " + brief["client_name"])[:200],
                      "client_id": brief["client_id"], "date": target.date().isoformat(),
                      "start_time": target.strftime("%H:%M"), "end_time": end.strftime("%H:%M"),
                      "notes": ("Follow up on: " + topic)[:1000], "location": ""}})
    return result[:5]
