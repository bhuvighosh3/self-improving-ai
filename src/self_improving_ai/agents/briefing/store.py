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
