"""Resolve meeting requests from user details and the existing calendar."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from self_improving_ai.calendar_adapter import TYPE_MAP


def short_preparation_target(message: str) -> str:
    match = re.fullmatch(r"\s*(?:please\s+)?(?:prepare|prep)\s+(?:for\s+)?(.+?)\s*[.!?]?\s*", message, re.IGNORECASE)
    return match.group(1).strip().casefold().rstrip(".!?").strip() if match else ""


def is_meeting_request(message: str, clients: list[dict] | None = None) -> bool:
    """Route explicit preparation requests to the shared, reviewable B workflow.

    This is a UI handoff, not a replacement for C's general intent planner.
    Discussion of previous meetings alone does not start a new brief.
    """
    text = message.lower()
    preparation = r"\b(?:prepare|prep|brief|briefing|agenda|ready)\b"
    meeting = r"\b(?:meeting|meetings|appointment|review)\b"
    target = short_preparation_target(message)
    for client in clients or []:
        profile = client["profile"]
        surname = profile["primary_contact"].split()[-1]
        aliases = (client["client_id"], profile["name"], profile["primary_contact"], surname, surname + "s")
        if target and target in {alias.casefold() for alias in aliases}:
            return True
    return bool(
        re.search(preparation, text) and re.search(meeting, text)
        or re.search(r"\bget me ready\b", text)
        or re.search(r"\bprep(?:are)? me for\b", text)
    )


def collect_meeting_details(message: str, clients: list[dict], selected_client_id: str | None = None,
                            today: date | None = None) -> dict:
    """Leave missing or ambiguous fields empty rather than silently guessing."""
    text = message.lower()
    today = today or datetime.now(ZoneInfo("America/New_York")).date()
    matches = []
    for client in clients:
        profile = client["profile"]
        surname = profile["primary_contact"].split()[-1]
        aliases = [client["client_id"], profile["name"], profile["primary_contact"], surname, surname + "s"]
        if any(re.search(r"\b" + re.escape(alias.lower()) + r"\b", text) for alias in aliases):
            matches.append(client["client_id"])
    known_ids = {client["client_id"] for client in clients}
    selected = selected_client_id if selected_client_id in known_ids else ""
    client_id = matches[0] if len(matches) == 1 else ""
    if not matches:
        client_id = selected
    elif selected and selected != client_id:
        client_id = ""

    meeting_date = ""
    explicit_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if explicit_date:
        try:
            meeting_date = date.fromisoformat(explicit_date.group(1)).isoformat()
        except ValueError:
            pass
    elif "tomorrow" in text:
        meeting_date = (today + timedelta(days=1)).isoformat()
    elif re.search(r"\btoday\b", text):
        meeting_date = today.isoformat()

    meeting_time = ""
    clock = re.search(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(a\.?m\.?|p\.?m\.?)\b", text)
    if clock:
        hour = int(clock.group(1)) % 12 + (12 if clock.group(3).startswith("p") else 0)
        meeting_time = f"{hour:02d}:{int(clock.group(2) or 0):02d}"
    else:
        clock = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
        if clock:
            meeting_time = f"{int(clock.group(1)):02d}:{clock.group(2)}"

    focus_match = re.search(r"(?:focus(?:ing)?\s+on|focus\s*:)\s*(.+)$", message, re.IGNORECASE)
    if not focus_match:
        focus_match = re.search(r"\s(?:—|–|-)\s+(.+)$", message)
    focus = focus_match.group(1).strip()[:500] if focus_match else ""
    return {"client_id": client_id, "meeting_date": meeting_date,
            "meeting_time": meeting_time, "focus": focus}


def resolve_calendar_meeting(details: dict, events: list[dict], now: datetime) -> dict:
    """Use a client's next matching appointment; never invent missing schedule data."""
    candidates = []
    if not details["client_id"]:
        return {"details": details, "reason": "client_required"}
    for event in events:
        if event.get("client_id") != details["client_id"]:
            continue
        if details["meeting_date"] and event["date"] != details["meeting_date"]:
            continue
        if details["meeting_time"] and event["start_time"][:5] != details["meeting_time"]:
            continue
        start = datetime.fromisoformat(event["date"] + "T" + event["start_time"]).replace(tzinfo=ZoneInfo("America/New_York"))
        if not details["meeting_date"] and start < now:
            continue
        candidates.append((start, event))
    candidates.sort(key=lambda item: (item[0], item[1]["id"]))
    if candidates:
        first_time = candidates[0][0]
        matching = [event for start, event in candidates if start == first_time]
        # A specified day with several appointments needs a choice; an
        # unspecified date means the next appointment for this client.
        if len(matching) > 1 or (details["meeting_date"] and not details["meeting_time"] and len(candidates) > 1):
            return {"details": details, "reason": "multiple_meetings", "choices": [event for _, event in candidates[:5]]}
        event = matching[0]
        resolved = {**details, "calendar_event_id": event["id"],
                    "meeting_date": event["date"], "meeting_time": event["start_time"][:5],
                    "focus": details["focus"] or (event.get("notes") or "").strip() or event["title"],
                    "meeting_type": event.get("meeting_type") or TYPE_MAP.get(event.get("type"), "general_meeting")}
        return {"details": resolved, "event": event, "reason": "resolved"}
    if all(details.values()):
        return {"details": details, "reason": "resolved"}
    return {"details": details, "reason": "meeting_not_found"}
