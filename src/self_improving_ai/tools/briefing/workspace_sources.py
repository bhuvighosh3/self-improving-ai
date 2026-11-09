"""Frozen, client-scoped operational Inbox evidence for the shared B pipeline."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

_scope = ContextVar("briefing_workspace_scope", default=None)
NY = ZoneInfo("America/New_York")


def current_scope():
    return _scope.get()


def scoped_crm_read(key, read):
    """Freeze repeated CRM reads within one authorized preparation, never globally."""
    scope = current_scope()
    if scope is None:
        return read()
    cache = scope.setdefault("crm_reads", {})
    if key not in cache:
        cache[key] = deepcopy(read())
    return deepcopy(cache[key])


def content_version(record):
    fields = ("id", "client_id", "subject", "from_name", "from_addr", "to_name", "to_addr", "body", "date", "time")
    return hashlib.sha256(json.dumps({key:record.get(key) for key in fields}, sort_keys=True).encode()).hexdigest()[:20]


def client_mail_snapshot(client_id, as_of):
    from self_improving_ai.workspace_store import workspace_snapshot
    records = workspace_snapshot("email")
    return [record for record in records if record.get("client_id") == client_id
            and record.get("folder") in {"inbox", "sent", "archive"}
            and record["date"] <= as_of
            and record.get("created_at", record["date"])[:10] <= as_of]


@contextmanager
def operational_scope(client_id, as_of, ai_mode=False, records=None):
    records = client_mail_snapshot(client_id, as_of) if records is None else records
    revision = hashlib.sha256(json.dumps(sorted((record["id"], content_version(record)) for record in records)).encode()).hexdigest()[:20]
    token = _scope.set({"client_id":client_id,"as_of":as_of,"mail":records,"revision":revision,"ai_mode":ai_mode})
    try:
        yield _scope.get()
    finally:
        _scope.reset(token)


def email_originals(client_id):
    scope = current_scope()
    if not scope:
        return []
    if client_id != scope["client_id"]:
        raise ValueError("Client is locked to the current workspace snapshot")
    originals = []
    for record in scope["mail"]:
        when = datetime.fromisoformat(record["date"] + "T" + record.get("time", "00:00")).replace(tzinfo=NY).isoformat()
        headers = f"From: {record.get('from_name', '')} <{record.get('from_addr', '')}>\nTo: {record.get('to_name', '')} <{record.get('to_addr', '')}>"
        originals.append({"id":record["id"],"client_id":client_id,"kind":"email",
            "title":record["subject"],"text":headers + "\n\n" + record["body"],
            "event_at":when,"recorded_at":record.get("created_at",when),
            "version":content_version(record),"origin":"workspace_inbox"})
    return originals
