"""Local checkpoints for interrupted B generation; never an approval record."""

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from uuid import uuid4

from self_improving_ai.config import settings
from self_improving_ai.agents.briefing.contract import CONTRACT_VERSION


class BriefRunStore:
    def __init__(self, path=None):
        self.path = str(path or settings.db_path)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS meeting_runs "
                       "(id TEXT PRIMARY KEY, fingerprint TEXT, status TEXT, snapshot TEXT, updated_at TEXT)")

    def begin(self, request: dict, model: str, as_of: str) -> tuple[str, dict | None]:
        fingerprint = hashlib.sha256(json.dumps([request, model, as_of, CONTRACT_VERSION], sort_keys=True).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            # Only an interrupted run can resume; completed/blocked runs never
            # masquerade as a newly generated or independently approved draft.
            row = db.execute("SELECT id, snapshot FROM meeting_runs WHERE fingerprint=? "
                             "AND status='interrupted' ORDER BY updated_at DESC LIMIT 1",
                             (fingerprint,)).fetchone()
            if row:
                db.execute("UPDATE meeting_runs SET status='running' WHERE id=?", (row[0],))
                return row[0], json.loads(row[1])
            run_id = str(uuid4())
            db.execute("INSERT INTO meeting_runs VALUES (?, ?, 'running', '{}', ?)",
                       (run_id, fingerprint, datetime.now(timezone.utc).isoformat()))
            return run_id, None

    def save(self, run_id: str, snapshot: dict, status: str):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE meeting_runs SET snapshot=?, status=?, updated_at=? WHERE id=?",
                       (json.dumps(snapshot), status, datetime.now(timezone.utc).isoformat(), run_id))

    def get(self, run_id: str) -> dict:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT status, snapshot, updated_at FROM meeting_runs WHERE id=?",
                             (run_id,)).fetchone()
        if row is None:
            raise LookupError("Briefing run not found")
        return {"run_id": run_id, "status": row[0], "snapshot": json.loads(row[1]),
                "updated_at": row[2], "approved": False}
