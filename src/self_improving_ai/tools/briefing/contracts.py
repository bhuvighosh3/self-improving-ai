"""Compatibility helpers for the four read-only Briefing catalog tools."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def tool_error(code: str, message: str) -> dict:
    return {"status": "error", "error_code": code, "error": message}


def valid_client_id(client_id) -> bool:
    return isinstance(client_id, str) and bool(client_id.strip()) and len(client_id) <= 120


def valid_limit(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def provenance(source: str, data_dir: Path = DATA_DIR) -> dict:
    """Use the shared fixture cutoff; never represent fixtures as live records."""
    manifest = json.loads((data_dir / "clients/meeting_context.json").read_text(encoding="utf-8"))
    return {"source": source, "as_of": manifest["data_as_of"], "synthetic": True,
            "version": "briefing-tools-v1", "read_only": True}
