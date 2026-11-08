"""One Calendar/Inbox contract with explicit local or Firestore storage."""

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import json
import sqlite3
from time import monotonic
from uuid import uuid4

from self_improving_ai.config import settings


class LocalWorkspaceStore:
    """Offline persistence of the teammate's exact document schemas and seed data."""

    def __init__(self, kind, path):
        self.kind, self.path = kind, str(path)
        from self_improving_ai.calendar_store import _SEED as events
        from self_improving_ai.email_store import _SEED as emails
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS workspace_documents (kind TEXT, id TEXT, document TEXT, PRIMARY KEY(kind,id))")
            db.execute("CREATE TABLE IF NOT EXISTS workspace_seeded (kind TEXT PRIMARY KEY)")
            if not db.execute("SELECT 1 FROM workspace_seeded WHERE kind=?", (kind,)).fetchone():
                now = datetime.now(timezone.utc).isoformat()
                for record in events if kind == "calendar" else emails:
                    db.execute("INSERT OR IGNORE INTO workspace_documents VALUES (?,?,?)", (kind, record["id"], json.dumps({**record, "created_at": record["date"] + "T00:00:00-05:00", "updated_at": now})))
                db.execute("INSERT INTO workspace_seeded VALUES (?)", (kind,))

    def _all(self):
        with sqlite3.connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute("SELECT document FROM workspace_documents WHERE kind=?", (self.kind,))]

    def _get(self, identifier):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT document FROM workspace_documents WHERE kind=? AND id=?", (self.kind, identifier)).fetchone()
        if not row:
            raise LookupError("Record not found")
        return json.loads(row[0])

    def _create(self, data):
        now = datetime.now(timezone.utc)
        identifier = ("EVT-" if self.kind == "calendar" else "EML-") + uuid4().hex[:8]
        record = {**data, "id": identifier, "created_at": now.isoformat(), "updated_at": now.isoformat()}
        if self.kind == "email":
            record = {"from_name": "You", "from_addr": "advisor@wealthadvisors.com", "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"), "read": True, "starred": False, "folder": "sent", **record}
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO workspace_documents VALUES (?,?,?)", (self.kind, identifier, json.dumps(record)))
        invalidate_snapshots()
        return record

    def _update(self, identifier, data):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT document FROM workspace_documents WHERE kind=? AND id=?", (self.kind, identifier)).fetchone()
            if not row:
                raise LookupError("Record not found")
            record = {**json.loads(row[0]), **{key:value for key,value in data.items() if value is not None}, "updated_at": datetime.now(timezone.utc).isoformat()}
            db.execute("UPDATE workspace_documents SET document=? WHERE kind=? AND id=?", (json.dumps(record), self.kind, identifier))
        invalidate_snapshots()
        return record

    def _delete(self, identifier):
        with sqlite3.connect(self.path) as db:
            cursor = db.execute("DELETE FROM workspace_documents WHERE kind=? AND id=?", (self.kind, identifier))
            if not cursor.rowcount:
                raise LookupError("Record not found")
        invalidate_snapshots()

    def list_all_events(self): return self._all()
    def list_all_emails(self): return self._all()
    def list_events(self, year, month):
        return sorted([record for record in self._all() if record["date"].startswith(f"{year}-{month:02d}-")], key=lambda record:(record["date"], record["start_time"]))
    def list_events_for_client(self, client_id):
        return sorted([record for record in self._all() if record["client_id"] == client_id], key=lambda record:(record["date"], record["start_time"]))
    def list_emails(self, folder="inbox"):
        return sorted([record for record in self._all() if record["folder"] == folder], key=lambda record:(record["date"], record.get("time", "")), reverse=True)
    def list_emails_for_client(self, client_id):
        return [record for record in self._all() if record.get("client_id") == client_id]
    get_event = _get
    get_email = _get
    create_event = _create
    create_email = _create
    update_event = _update
    update_email = _update
    delete_event = _delete
    delete_email = _delete


@lru_cache(maxsize=8)
def _store(kind, backend, path, project):
    if backend == "local":
        return LocalWorkspaceStore(kind, path)
    if kind == "calendar":
        from self_improving_ai.calendar_store import CalendarStore
        return CalendarStore(project=project or None)
    from self_improving_ai.email_store import EmailStore
    return EmailStore(project=project or None)


def get_store(kind, path=None):
    return _store(kind, settings.workspace_store, str(path or settings.db_path), settings.google_cloud_project)


_snapshots = {}

def invalidate_snapshots():
    _snapshots.clear()


def workspace_snapshot(kind, path=None):
    key = (kind, settings.workspace_store, str(path or settings.db_path), settings.google_cloud_project)
    cached = _snapshots.get(key)
    if cached and settings.workspace_store == "firestore" and monotonic() - cached[0] < 5:
        return deepcopy(cached[1])
    store = get_store(kind, path=path)
    records = store.list_all_events() if kind == "calendar" else store.list_all_emails()
    _snapshots[key] = (monotonic(), deepcopy(records))
    return deepcopy(records)
