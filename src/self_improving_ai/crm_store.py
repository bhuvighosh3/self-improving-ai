"""Firestore-backed CRM store for meeting context and source records."""

from __future__ import annotations

from google.cloud import firestore

from self_improving_ai.config import settings

_CRM_CONTEXT = "crm_context"
_CRM_RECORDS = "crm_records"
_CRM_SETTINGS = "crm_settings"


class CrmStore:
    def __init__(self, project: str | None = None):
        self.db = firestore.Client(project=project or settings.google_cloud_project or None)

    def get_settings(self) -> dict:
        doc = self.db.collection(_CRM_SETTINGS).document("global").get()
        if not doc.exists:
            return {"data_as_of": "2026-10-27", "holdings_as_of": "2026-10-24"}
        return doc.to_dict()

    def set_settings(self, data: dict) -> None:
        self.db.collection(_CRM_SETTINGS).document("global").set(data)

    def get_client_context(self, client_id: str) -> dict | None:
        doc = self.db.collection(_CRM_CONTEXT).document(client_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["client_id"] = doc.id
        return data

    def set_client_context(self, client_id: str, data: dict) -> None:
        self.db.collection(_CRM_CONTEXT).document(client_id).set(data)

    def list_records(self, client_id: str | None = None) -> list[dict]:
        query = self.db.collection(_CRM_RECORDS)
        if client_id:
            query = query.where("client_id", "==", client_id)
        docs = query.get()
        results = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            results.append(d)
        return sorted(results, key=lambda r: r.get("event_at", ""))

    def get_record(self, record_id: str) -> dict | None:
        doc = self.db.collection(_CRM_RECORDS).document(record_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    def set_record(self, record_id: str, data: dict) -> None:
        self.db.collection(_CRM_RECORDS).document(record_id).set(data)
