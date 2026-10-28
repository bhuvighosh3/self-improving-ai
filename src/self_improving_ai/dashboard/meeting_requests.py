"""Extract conservative meeting suggestions for advisor confirmation."""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


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
