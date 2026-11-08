"""Firestore-backed client store. Seeds from households.json on first use."""

from __future__ import annotations

import json
from pathlib import Path

from google.cloud import firestore

from self_improving_ai.config import settings

_COLLECTION = "clients"
_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_seed_data() -> list[dict]:
    path = _DATA_DIR / "clients" / "households.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


class ClientStore:
    def __init__(self, project: str | None = None):
        self.db = firestore.Client(project=project or settings.google_cloud_project or None)
        self.collection = self.db.collection(_COLLECTION)
        self._seed_if_empty()

    def _seed_if_empty(self):
        first = self.collection.limit(1).get()
        if list(first):
            return
        batch = self.db.batch()
        for client in _load_seed_data():
            ref = self.collection.document(client["client_id"])
            batch.set(ref, client)
        batch.commit()

    def _doc_to_dict(self, doc) -> dict:
        data = doc.to_dict()
        data["client_id"] = doc.id
        return data

    def list_clients(self) -> list[dict]:
        docs = self.collection.get()
        results = [self._doc_to_dict(d) for d in docs]
        results.sort(key=lambda c: c.get("client_id", ""))
        return results

    def get_client(self, client_id: str) -> dict:
        doc = self.collection.document(client_id).get()
        if not doc.exists:
            raise LookupError(f"Client {client_id} not found")
        return self._doc_to_dict(doc)

    def update_client(self, client_id: str, data: dict) -> dict:
        existing = self.get_client(client_id)
        merged = {**existing, **{k: v for k, v in data.items() if v is not None}}
        self.collection.document(client_id).set(merged)
        return merged

    def create_client(self, data: dict) -> dict:
        client_id = data["client_id"]
        self.collection.document(client_id).set(data)
        return data


def load_households() -> list[dict]:
    """Load clients from Firestore, falling back to JSON fixture."""
    try:
        return ClientStore().list_clients()
    except Exception:
        return _load_seed_data()
