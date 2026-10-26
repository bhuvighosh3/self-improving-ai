"""Tool catalog search for the orchestrator — includes overlapping/outdated entries."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def _load_catalog() -> list[dict]:
    path = _DATA_DIR / "tool_catalog.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def search_tool_catalog(query: str) -> dict:
    """Search the tool catalog for available tools matching a query.

    The catalog may contain overlapping tools, deprecated entries, and tools
    with similar names but different units or behaviors. The orchestrator
    must choose carefully.

    Args:
        query: Natural language description of what the tool should do.

    Returns:
        Dictionary with matching tool entries including name, description,
        parameters, and any known caveats.
    """
    catalog = _load_catalog()
    query_lower = query.lower()
    matches = []
    for tool in catalog:
        searchable = f"{tool.get('name', '')} {tool.get('description', '')}".lower()
        if any(word in searchable for word in query_lower.split()):
            matches.append(tool)
    return {"query": query, "matches": matches}
