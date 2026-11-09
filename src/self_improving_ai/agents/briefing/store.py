"""Versioned local-demo drafts and review audit. Not an authentication service."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from self_improving_ai.config import settings


class DraftStore:
    def __init__(self, path=None):
        self.path = str(path or settings.db_path)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS meeting_drafts "
                       "(id TEXT PRIMARY KEY, brief TEXT, revision INTEGER, status TEXT, digest TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS meeting_reviews "
                       "(id TEXT, revision INTEGER, decision TEXT, feedback TEXT, digest TEXT, created_at TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def digest(brief):
        # Check reports/trace are server metadata, not a change to reviewed content.
        document = {key: value for key, value in brief.items() if key != "workflow"}
        return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()

    def create(self, brief):
        with self.connect() as db:
            db.execute("INSERT INTO meeting_drafts VALUES (?, ?, 1, 'draft', ?)",
                       (brief["id"], json.dumps(brief), self.digest(brief)))
            self._link_calendar(db, brief)

    @staticmethod
    def _link_calendar(db, brief):
        event = brief.get("calendar_event")
        if not event or not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_preparations'").fetchone():
            return
        from uuid import uuid4

        from self_improving_ai.agents.briefing.contract import CONTRACT_VERSION

        request = {key: brief[key] for key in ("client_id", "meeting_date", "meeting_time", "focus", "mode")}
        request.update(calendar_event_id=event["id"], meeting_type=brief.get("meeting_type", "general_meeting"))
        pipeline = CONTRACT_VERSION + ":" + settings.briefing_discovery if brief["mode"] == "agent" else "offline-v1"
        db.execute("INSERT INTO calendar_preparations "
                   "(id,event_id,version,mode,status,request,brief_id,requested,pipeline_version) "
                   "VALUES (?, ?, ?, ?, 'ready', ?, ?, 1, ?) "
                   "ON CONFLICT(event_id,version,mode) DO UPDATE SET "
                   "status='ready',request=excluded.request,brief_id=excluded.brief_id,error=NULL,"
                   "requested=1,pipeline_version=excluded.pipeline_version",
                   (str(uuid4()), event["id"], event["version"], brief["mode"], json.dumps(request), brief["id"], pipeline))

    def link_calendar(self, brief):
        """Index an existing snapshot without changing its content or approval digest."""
        with self.connect() as db:
            self._link_calendar(db, brief)

    def current_calendar_brief(self, event, mode):
        """Reuse the current saved result instead of generating a second brief."""
        from self_improving_ai.agents.briefing.contract import CONTRACT_VERSION
        pipeline = CONTRACT_VERSION + ":" + settings.briefing_discovery if mode == "agent" else "offline-v1"
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_preparations'").fetchone():
                return None
            row = db.execute("SELECT brief_id FROM calendar_preparations WHERE event_id=? AND version=? "
                "AND mode=? AND status='ready' AND pipeline_version=?", (event["id"], event["version"], mode, pipeline)).fetchone()
        return self.get(row[0])["brief"] if row else None

    def begin_calendar_preparation(self, event, request):
        """Make synchronous Copilot work visible to edits and the shared monitor."""
        from uuid import uuid4

        from self_improving_ai.agents.briefing.contract import CONTRACT_VERSION
        pipeline = CONTRACT_VERSION + ":" + settings.briefing_discovery if request.mode == "agent" else "offline-v1"
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_preparations'").fetchone():
                return
            db.execute("INSERT INTO calendar_preparations "
                "(id,event_id,version,mode,status,request,requested,pipeline_version) VALUES (?,?,?,?, 'preparing',?,1,?) "
                "ON CONFLICT(event_id,version,mode) DO UPDATE SET status='preparing',brief_id=NULL,error=NULL,requested=1,"
                "request=excluded.request,pipeline_version=excluded.pipeline_version",
                (str(uuid4()), event["id"], event["version"], request.mode, request.model_dump_json(), pipeline))

    def fail_calendar_preparation(self, event, mode, run_id=None):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_preparations'").fetchone():
                return
            db.execute("UPDATE calendar_preparations SET status='failed',error=?,run_id=? "
                "WHERE event_id=? AND version=? AND mode=? AND status='preparing'",
                ("Preparation interrupted. Retry to continue.", run_id, event["id"], event["version"], mode))

    def summaries(self):
        """Return small saved-brief records, keeping evidence and traces server-side."""
        with self.connect() as db:
            rows = db.execute("SELECT brief, status FROM meeting_drafts ORDER BY rowid DESC").fetchall()
        keys = ("id", "client_id", "client_name", "meeting_date", "meeting_time", "focus", "mode",
                "generated_at", "data_as_of", "meeting_type", "calendar_event")
        return [{**{key: brief.get(key) for key in keys}, "review_status": status}
                for serialized, status in rows for brief in [json.loads(serialized)]]

    def get(self, brief_id):
        with self.connect() as db:
            row = db.execute("SELECT brief, revision, status, digest FROM meeting_drafts WHERE id=?",
                             (brief_id,)).fetchone()
        if row is None:
            raise LookupError("Draft not found; generate it again on this server")
        return {"brief": json.loads(row[0]), "revision": row[1], "status": row[2], "digest": row[3]}

    def review(self, brief, revision, expected_revision, decision, feedback):
        digest = self.digest(brief)
        if revision < expected_revision:
            raise ValueError("Cannot review an obsolete revision")
        created = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            current = db.execute("SELECT revision, digest FROM meeting_drafts WHERE id=?",
                                 (brief["id"],)).fetchone()
            if current is None:
                raise LookupError("Draft not found")
            if current[1] != digest and revision <= current[0]:
                raise ValueError("Changed content requires a newer revision")
            cursor = db.execute("UPDATE meeting_drafts SET brief=?, revision=?, status=?, digest=? "
                                "WHERE id=? AND revision=?",
                                (json.dumps(brief), revision, decision, digest, brief["id"], expected_revision))
            if cursor.rowcount != 1:
                raise ValueError("Draft changed on the server; reload before reviewing")
            db.execute("INSERT INTO meeting_reviews VALUES (?, ?, ?, ?, ?, ?)",
                       (brief["id"], revision, decision, feedback, digest, created))
        return {"revision": revision, "status": decision, "digest": digest, "reviewed_at": created,
                "identity_scope": "local_demo_no_authenticated_advisor"}
