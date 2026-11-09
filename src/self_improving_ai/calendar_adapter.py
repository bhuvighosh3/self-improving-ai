"""Normalize the teammate's canonical calendar documents for Part B preparation."""

from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
TYPE_MAP = {"quarterly_review":"quarterly_review", "annual_review":"annual_review", "goal_review":"goal_review",
            "follow_up":"goal_review", "portfolio_review":"quarterly_review"}


def normalize_event(record, client_names, mail_revision=""):
    start = datetime.fromisoformat(record["date"] + "T" + record["start_time"]).replace(tzinfo=NY)
    end = datetime.fromisoformat(record["date"] + "T" + record["end_time"]).replace(tzinfo=NY)
    if end <= start:
        raise ValueError("Meeting end time must follow its start time")
    fields = ("id", "title", "client_id", "date", "start_time", "end_time", "type", "notes", "location")
    version = "v-" + hashlib.sha256(json.dumps([{key:record.get(key) for key in fields}, mail_revision], sort_keys=True).encode()).hexdigest()[:20]
    client = record.get("client_id", "")
    return {**record, "version":version, "starts_at":start.isoformat(),
        "duration_minutes":int((end-start).total_seconds()/60), "category":"client" if client else "internal",
        "prep_required":bool(client), "client_name":client_names.get(client, client),
        "meeting_type":TYPE_MAP.get(record["type"],"general_meeting"),
        "focus":record.get("notes") or record["title"],"participants":[client_names.get(client,client),"Advisor"]}
