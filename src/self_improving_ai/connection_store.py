"""Local connection overrides shared by the web service and standalone commands.

Secrets stay in a git-ignored directory and are never returned by status endpoints.
This is a single-user local application; values are persisted on this computer.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
STORE_PATH = ROOT / ".local-settings" / "connections.json"
ALLOWED = {"TWELVE_DATA_API_KEY", "SIA_PORTFOLIO_API_KEY",
           "SIA_PORTFOLIO_MODEL", "SIA_MARKET_DATA_PROVIDER"}
LOCK = threading.RLock()


def read_connections() -> dict[str, str]:
    if not STORE_PATH.exists():
        return {}
    document = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or any(key not in ALLOWED or not isinstance(value, str)
                                              for key, value in document.items()):
        raise ValueError("Invalid local connection configuration")
    return document


def restore_connections() -> None:
    """Saved UI settings override environment/dotenv values, including explicit removal."""
    with LOCK:
        os.environ.update(read_connections())


def update_connections(values: dict[str, str]) -> None:
    if any(key not in ALLOWED or not isinstance(value, str) for key, value in values.items()):
        raise ValueError("Unsupported connection setting")
    with LOCK:
        document = {**read_connections(), **values}
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STORE_PATH.with_name("connections." + uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as output:
                try:
                    os.chmod(temporary, 0o600)
                except OSError:
                    pass
                json.dump(document, output, indent=2, allow_nan=False)
            temporary.replace(STORE_PATH)
        finally:
            temporary.unlink(missing_ok=True)
        os.environ.update(values)
