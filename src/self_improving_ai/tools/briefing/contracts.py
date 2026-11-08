"""Compatibility helpers for the four read-only Briefing catalog tools."""

from __future__ import annotations


def tool_error(code: str, message: str) -> dict:
    return {"status": "error", "error_code": code, "error": message}


def valid_client_id(client_id) -> bool:
    return isinstance(client_id, str) and bool(client_id.strip()) and len(client_id) <= 120


def valid_limit(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def provenance(source: str, *_args, **_kwargs) -> dict:
    """Use the CRM settings cutoff from Firestore."""
    from self_improving_ai.crm_store import CrmStore
    settings = CrmStore().get_settings()
    return {"source": source, "as_of": settings["data_as_of"], "synthetic": False,
            "version": "briefing-tools-v1", "read_only": True}
