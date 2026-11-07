"""Firestore-backed calendar event store. Seed data included for demo."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from self_improving_ai.config import settings

_COLLECTION = "calendar_events"

_SEED = [
    {"id": "EVT-a1b2c3d4", "title": "Q4 Review: Garcia Family", "client_id": "CLI-001",
     "date": "2026-11-12", "start_time": "14:00", "end_time": "15:00",
     "type": "quarterly_review", "notes": "Discuss retirement projections and 529 plan",
     "location": "Conference Room A"},
    {"id": "EVT-e5f6a7b8", "title": "Bond Duration Follow-Up: Thompson Trust", "client_id": "CLI-002",
     "date": "2026-11-14", "start_time": "10:00", "end_time": "10:45",
     "type": "follow_up", "notes": "Rate impact analysis on bond portfolio",
     "location": "Virtual - Zoom"},
    {"id": "EVT-c9d0e1f2", "title": "Tax-Loss Harvesting Review: Chen Household", "client_id": "CLI-003",
     "date": "2026-11-18", "start_time": "11:00", "end_time": "12:00",
     "type": "portfolio_review", "notes": "ARKK position and early retirement update",
     "location": "Conference Room B"},
    {"id": "EVT-a3b4c5d6", "title": "Home Purchase Planning: Okafor Family", "client_id": "CLI-004",
     "date": "2026-11-20", "start_time": "15:30", "end_time": "16:15",
     "type": "goal_review", "notes": "Down payment liquidation strategy",
     "location": "Conference Room A"},
    {"id": "EVT-e7f8a9b0", "title": "Withdrawal Planning: Patel", "client_id": "CLI-005",
     "date": "2026-11-22", "start_time": "09:00", "end_time": "09:45",
     "type": "follow_up", "notes": "Sustainable withdrawal rate and inherited IRA",
     "location": "Virtual - Phone"},
    {"id": "EVT-c1d2e3f4", "title": "Annual Review: Garcia Family", "client_id": "CLI-001",
     "date": "2026-12-10", "start_time": "14:00", "end_time": "15:30",
     "type": "annual_review", "notes": "Full annual review and 2027 planning",
     "location": "Conference Room A"},
    {"id": "EVT-a5b6c7d8", "title": "Q1 Planning: Chen Household", "client_id": "CLI-003",
     "date": "2026-12-15", "start_time": "11:00", "end_time": "12:00",
     "type": "quarterly_review", "notes": "Early retirement Monte Carlo review",
     "location": "Conference Room B"},
    {"id": "EVT-e9f0a1b2", "title": "Portfolio Review: Thompson Trust", "client_id": "CLI-002",
     "date": "2026-10-28", "start_time": "10:00", "end_time": "11:00",
     "type": "portfolio_review", "notes": "Muni bond duration comparison",
     "location": "Virtual - Zoom"},
    {"id": "EVT-c3d4e5f6", "title": "Income Review: Patel", "client_id": "CLI-005",
     "date": "2026-12-05", "start_time": "09:30", "end_time": "10:15",
     "type": "quarterly_review", "notes": "RMD schedule and monthly withdrawal",
     "location": "Conference Room A"},
]


class CalendarStore:
    def __init__(self, project: str | None = None):
        self.db = firestore.Client(project=project or settings.google_cloud_project or None)
        self.collection = self.db.collection(_COLLECTION)
        self._seed_if_empty()

    def _seed_if_empty(self):
        first = self.collection.limit(1).get()
        if list(first):
            return
        batch = self.db.batch()
        now = datetime.now(timezone.utc).isoformat()
        for event in _SEED:
            ref = self.collection.document(event["id"])
            batch.set(ref, {**event, "created_at": now, "updated_at": now})
        batch.commit()

    def _doc_to_dict(self, doc) -> dict:
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    def list_events(self, year: int, month: int) -> list[dict]:
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1}-01-01"
        else:
            end = f"{year}-{month + 1:02d}-01"
        docs = (
            self.collection
            .where(filter=FieldFilter("date", ">=", start))
            .where(filter=FieldFilter("date", "<", end))
            .order_by("date")
            .get()
        )
        results = [self._doc_to_dict(d) for d in docs]
        results.sort(key=lambda e: (e["date"], e["start_time"]))
        return results

    def list_events_for_client(self, client_id: str) -> list[dict]:
        docs = (
            self.collection
            .where(filter=FieldFilter("client_id", "==", client_id))
            .order_by("date")
            .get()
        )
        results = [self._doc_to_dict(d) for d in docs]
        results.sort(key=lambda e: (e["date"], e["start_time"]))
        return results

    def get_event(self, event_id: str) -> dict:
        doc = self.collection.document(event_id).get()
        if not doc.exists:
            raise LookupError("Event not found")
        return self._doc_to_dict(doc)

    def create_event(self, data: dict) -> dict:
        event_id = f"EVT-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        doc_data = {
            "id": event_id,
            "title": data["title"],
            "client_id": data["client_id"],
            "date": data["date"],
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "type": data["type"],
            "notes": data.get("notes", ""),
            "location": data.get("location", ""),
            "created_at": now,
            "updated_at": now,
        }
        self.collection.document(event_id).set(doc_data)
        return doc_data

    def update_event(self, event_id: str, data: dict) -> dict:
        existing = self.get_event(event_id)
        now = datetime.now(timezone.utc).isoformat()
        merged = {**existing, **{k: v for k, v in data.items() if v is not None}, "updated_at": now}
        self.collection.document(event_id).set(merged)
        return merged

    def delete_event(self, event_id: str) -> None:
        self.get_event(event_id)  # raises LookupError if missing
        self.collection.document(event_id).delete()

    def get_last_meeting(self, client_id: str) -> str | None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        docs = (
            self.collection
            .where(filter=FieldFilter("client_id", "==", client_id))
            .where(filter=FieldFilter("date", "<", today))
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(1)
            .get()
        )
        results = list(docs)
        return results[0].to_dict()["date"] if results else None
