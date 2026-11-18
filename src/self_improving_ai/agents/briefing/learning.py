"""Client-scoped correction memory using C's version, audit and rollback store.

Only bounded presentation preferences become instructions. Edited facts and free
text remain feedback records, never reusable facts or executable instructions.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from self_improving_ai.agents.orchestrator.memory import MemoryStore
from self_improving_ai.config import settings

PREFERENCES = {
    "concise": "Use concise summaries; keep source references and uncertainty intact.",
    "actions_first": "Prioritize outstanding actions and concrete follow-up questions.",
    "more_context": "Include relevant recent client context and explain why it matters.",
}
LABELS = {"concise": "Shorter summaries", "actions_first": "Highlight open actions",
          "more_context": "More client context"}
_profile = ContextVar("meeting_learning_profile", default=None)
_write_lock = RLock()


@dataclass
class MeetingMemory:
    version: int = 0
    preferences: dict = dataclass_field(default_factory=dict)

    def to_dict(self):
        return {"version": self.version, "preferences": self.preferences}


class MeetingMemoryStore(MemoryStore):
    """Reuse C's adoption/audit/rollback implementation with B's payload codec."""

    def load(self, version=None):
        version = self.active_version() if version is None else version
        if version is None:
            return MeetingMemory()
        return MeetingMemory(**json.loads(self._path(version).read_text()))


def current_profile():
    return _profile.get() or {"version": 0, "preferences": [], "history": []}


@contextmanager
def learning_scope(profile):
    token = _profile.set(profile)
    try:
        yield
    finally:
        _profile.reset(token)


def instructions(profile=None):
    profile = profile or current_profile()
    lines = [PREFERENCES[item["key"]] for item in profile["preferences"] if item["key"] in PREFERENCES]
    if any(item.get("rating") == "needs_work" and not item.get("reason") for item in profile["history"]):
        lines.append("A previous preparation was rated as needing improvement without a specific reason. "
                     "Recheck focus alignment, evidence coverage and actionable questions; do not infer a style preference or an error from that rating alone.")
    return "\n".join(lines)


def metadata(brief, profile=None):
    profile = profile or current_profile()
    return {"schema": "meeting-learning-v1", "scope": "client_in_this_workspace",
            "identity_scope": "workspace_demo_not_authenticated_advisor",
            "brief_id": brief["id"], "client_id": brief["client_id"],
            "event_id": (brief.get("calendar_event") or {}).get("id"),
            "revision": 1, "created_at": brief["generated_at"],
            "memory_version": profile["version"],
            "applied_preferences": deepcopy(profile["preferences"]),
            "previous_feedback": deepcopy(profile["history"])}


class LearningStore:
    def __init__(self, path=None):
        self.path = str(path or settings.db_path)
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS meeting_learning_events "
                       "(id TEXT PRIMARY KEY, brief_id TEXT, client_id TEXT, kind TEXT, "
                       "revision INTEGER, payload TEXT, created_at TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS meeting_learning_actions "
                       "(id TEXT PRIMARY KEY, client_id TEXT, kind TEXT, payload TEXT)")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def memory(self, client_id):
        workspace = hashlib.sha256(str(Path(self.path).resolve()).encode()).hexdigest()[:12]
        client = hashlib.sha256(client_id.encode()).hexdigest()[:20]
        return MeetingMemoryStore(Path(self.path).parent / "meeting_memory" / workspace / client)

    def events(self, brief_id=None, client_id=None):
        field, value = ("brief_id", brief_id) if brief_id else ("client_id", client_id)
        with self.db() as db:
            rows = db.execute(f"SELECT id,brief_id,kind,revision,payload,created_at FROM "
                              f"meeting_learning_events WHERE {field}=? ORDER BY rowid DESC LIMIT 100",
                              (value,)).fetchall()
        return [dict(zip(("id", "brief_id", "kind", "revision", "payload", "created_at"),
                         (a, b, c, d, json.loads(e), f))) for a, b, c, d, e, f in rows]

    def profile(self, client_id, meeting_date, event_id=None, meeting_time="23:59"):
        memory = self.memory(client_id).load()
        target = meeting_date + "T" + meeting_time[:5]
        preferences = [{"key": key, "label": LABELS[key], **value}
                       for key, value in memory.preferences.items() if key in PREFERENCES
                       and value.get("available_after", value["meeting_start"]) < target
                       and (not event_id or value.get("event_id") != event_id)]
        history, seen = [], set()
        for event in self.events(client_id=client_id):
            payload = event["payload"]
            if event["brief_id"] in seen or payload.get("available_after", payload.get("meeting_start", "9999")) >= target:
                continue
            if event_id and payload.get("event_id") == event_id:
                continue
            seen.add(event["brief_id"])
            history.append({"brief_id": event["brief_id"], "meeting_date": payload["meeting_start"][:10],
                            "kind": event["kind"], "summary": payload["summary"],
                            "feedback_id": event["id"], "rating": payload.get("rating"),
                            "reason": payload.get("reason")})
            if len(history) == 3:
                break
        return {"version": memory.version, "preferences": preferences, "history": history}

    def remember(self, brief, keys, event_id, reason, *, available_after=None, adoption_type="advisor_personalization_not_statistical_policy_improvement"):
        """Explicit corrections/preferences are personalization, not a benchmark gain."""
        if not keys:
            return
        with _write_lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            store = self.memory(brief["client_id"])
            memory = store.load()
            for key in keys:
                if key not in PREFERENCES:
                    raise ValueError("Unknown preference")
                memory.preferences[key] = {
                    "source_brief_id": brief["id"], "feedback_id": event_id, "reason": reason,
                    "meeting_start": brief["meeting_date"] + "T" + brief["meeting_time"][:5],
                    "event_id": (brief.get("calendar_event") or {}).get("id"),
                    **({"available_after": available_after} if available_after else {}),
                }
            store.adopt(memory, reason=reason, feedback_id=event_id,
                        adoption_type=adoption_type)

    def forget(self, client_id, key):
        with _write_lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            store = self.memory(client_id)
            memory = store.load()
            memory.preferences.pop(key, None)
            store.adopt(memory, reason="Advisor removed a client preference")

    def record(self, brief, kind, revision, payload, db=None):
        event_id = uuid4().hex
        payload = {**payload, "meeting_start": brief["meeting_date"] + "T" + brief["meeting_time"][:5],
                   "event_id": (brief.get("calendar_event") or {}).get("id")}
        args = (event_id, brief["id"], brief["client_id"], kind, revision,
                json.dumps(payload), datetime.now(UTC).isoformat())
        if db is not None:
            db.execute("INSERT INTO meeting_learning_events VALUES (?,?,?,?,?,?,?)", args)
        else:
            with self.db() as connection:
                connection.execute("INSERT INTO meeting_learning_events VALUES (?,?,?,?,?,?,?)", args)
        return event_id

    def save_edits(self, original, sections, expected_revision, quality, remember=True):
        """Persist the server-owned document and its exact edit history atomically."""
        from self_improving_ai.agents.briefing.store import DraftStore

        before = original["brief"]
        edits = []
        for old_section, new_section in zip(before["sections"], sections, strict=True):
            for old, new in zip(old_section["items"], new_section["items"], strict=True):
                for field in ("title", "text", "why", "question"):
                    if old.get(field, "") != new.get(field, ""):
                        edits.append({"section_id": old_section["id"], "item_id": old["id"],
                                      "field": field, "before": old.get(field, ""), "after": new.get(field, "")})
        if not edits:
            revised = deepcopy(before)
            revised["workflow"]["quality"] = quality
            with self.db() as db:
                cursor = db.execute("UPDATE meeting_drafts SET brief=? WHERE id=? AND revision=? AND digest=?",
                                    (json.dumps(revised), before["id"], expected_revision, original["digest"]))
                if cursor.rowcount != 1:
                    raise ValueError("This brief changed elsewhere. Reopen it before saving.")
            pending = next((e for e in self.events(brief_id=before["id"]) if e["kind"] == "edit"), None)
            if pending and remember and quality["verdict"] == "pass" and pending["payload"].get("remember"):
                payload = pending["payload"]
                if payload["words_after"] <= payload["words_before"] * .85 and payload["words_before"] - payload["words_after"] >= 20:
                    memory = self.memory(before["client_id"]).load()
                    if memory.preferences.get("concise", {}).get("feedback_id") != pending["id"]:
                        self.remember(before, ["concise"], pending["id"], "Advisor shortened a checked brief")
            return DraftStore(self.path).get(before["id"])
        revised = {**deepcopy(before), "sections": sections}
        revision = expected_revision + 1
        revised["learning"] = {**before.get("learning", metadata(before)), "revision": revision,
                               "last_edited_at": datetime.now(UTC).isoformat()}
        revised["workflow"] = {**before["workflow"], "quality": quality}
        # Keep the claim text aligned with the edited presentation for future checks.
        claims = {item["id"]: item for item in revised["workflow"]["work"]["claims"]}
        for section in sections:
            for item in section["items"]:
                if len(item.get("claim_ids", [])) == 1:
                    claims[item["claim_ids"][0]]["text"] = item["text"]
        revised["workflow"]["work"]["sections"] = deepcopy(sections)
        old_words = sum(len(item["text"].split()) for s in before["sections"] for item in s["items"])
        new_words = sum(len(item["text"].split()) for s in sections for item in s["items"])
        shortened = new_words <= old_words * .85 and old_words - new_words >= 20
        learned = ["concise"] if remember and shortened and quality["verdict"] == "pass" else []
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute("UPDATE meeting_drafts SET brief=?,revision=?,status='draft',digest=? "
                                "WHERE id=? AND revision=? AND digest=?",
                                (json.dumps(revised), revision, DraftStore.digest(revised), before["id"],
                                 expected_revision, original["digest"]))
            if cursor.rowcount != 1:
                raise ValueError("This brief changed elsewhere. Reopen it before saving.")
            event_id = self.record(revised, "edit", revision, {
                "changes": edits, "words_before": old_words, "words_after": new_words,
                "summary": f"Advisor edited {len(edits)} fields" + (" and shortened the brief." if shortened else "."),
                "quality": quality["verdict"], "learned": learned, "remember": remember,
            }, db=db)
        self.remember(revised, learned, event_id, "Advisor shortened a checked brief")
        return DraftStore(self.path).get(before["id"])

    def action(self, action_id, client_id, kind, payload):
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO meeting_learning_actions VALUES (?,?,?,?)",
                       (action_id, client_id, kind, json.dumps(payload)))

    def actions(self):
        with self.db() as db:
            rows = db.execute("SELECT id,client_id,kind,payload FROM meeting_learning_actions ORDER BY rowid").fetchall()
        return [{"id": a, "client_id": b, "kind": c, "payload": json.loads(d)} for a, b, c, d in rows]


def personalize_demo(sections):
    """Deterministic formatting for offline demos; never drop confirmation caveats."""
    keys = {item["key"] for item in current_profile()["preferences"]}
    if any(item.get("rating") == "needs_work" and not item.get("reason") for item in current_profile()["history"]):
        priorities = next(s for s in sections if s["id"] == "priorities")["items"]
        priorities.insert(0, {"id": "feedback-focus-review", "title": "Confirm what will make this meeting useful",
            "text": "Confirm the current priorities and the decision this meeting needs to support.",
            "source_ids": ["PROFILE"], "why": "Your earlier rating calls for a fresh check of the meeting's purpose.",
            "question": "What decision or outstanding concern should this meeting resolve?"})
    if "concise" in keys:
        for section in sections:
            if section["id"] == "changes":
                # Correspondence stays available in full in the evidence pane.
                for item in section["items"]:
                    if item["id"].startswith("mail-"):
                        item["text"] = "Review the linked correspondence: " + item["title"] + ". Confirm reported intentions against current client records."
    if "actions_first" in keys:
        actions = next(s for s in sections if s["id"] == "actions")["items"]
        priorities = next(s for s in sections if s["id"] == "priorities")["items"]
        if actions:
            action = actions[0]
            priorities.insert(0, {"id": "learned-open-action", "title": "Follow up: " + action["title"][:180],
                "text": action["text"], "source_ids": action["source_ids"],
                "why": "Previous meeting experience highlighted the need to surface outstanding actions.",
                "question": "What is the current status and who owns the next step?"})
    if "more_context" in keys:
        changes = next(s for s in sections if s["id"] == "changes")["items"]
        priorities = next(s for s in sections if s["id"] == "priorities")["items"]
        if changes:
            item = changes[0]
            priorities.insert(0, {"id": "learned-client-context", "title": "Discuss: " + item["title"][:180],
                "text": item["text"], "source_ids": item["source_ids"],
                "why": "Your previous feedback asked for more context from recent client records.",
                "question": "Does this recorded update still reflect the client's current priorities?"})
