"""Tool catalog for the orchestrator (Component C).

The catalog deliberately contains traps: deprecated tools, near-duplicate names, tools only
another agent may call, and side-effecting tools the copilot must never use. Two versions
exist: v1 (training and main test set) and v2 (renamed, removed and deprecated tools, used for
the "changed tools" generalization tests).
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_ORCH_DIR = _DATA_DIR / "orchestrator"
ORCHESTRATOR = "request_orchestrator"


class Catalog:
    """A versioned tool catalog with the lookups the planner and scorer need."""

    def __init__(self, raw: dict):
        self.version: str = raw["version"]
        self.tools: list[dict] = raw["tools"]
        self.neutral_tools: set[str] = set(raw.get("neutral_tools", []))
        self.forbidden_tools: set[str] = set(raw.get("forbidden_tools", []))
        self._by_name = {t["name"]: t for t in self.tools}

    def get(self, name: str) -> dict | None:
        return self._by_name.get(name)

    def exists(self, name: str) -> bool:
        return name in self._by_name

    def capability(self, name: str) -> str:
        tool = self.get(name)
        return tool["capability"] if tool else "unknown"

    def is_deprecated(self, name: str) -> bool:
        tool = self.get(name)
        return bool(tool and tool.get("status") == "deprecated")

    def callable_by_orchestrator(self, name: str) -> bool:
        tool = self.get(name)
        return bool(tool and ORCHESTRATOR in tool.get("callable_by", []))

    def owner_of(self, name: str) -> str:
        tool = self.get(name)
        if not tool:
            return ""
        owners = [o for o in tool.get("callable_by", []) if o != ORCHESTRATOR]
        return owners[0] if owners else ""

    def fingerprint(self, name: str) -> str:
        """Hash of a tool's contract. A lesson about a tool is stale once this changes."""
        tool = self.get(name)
        if not tool:
            return ""
        contract = {k: tool.get(k) for k in ("name", "description", "params", "returns", "status")}
        return hashlib.sha1(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:12]

    def planner_view(self) -> list[dict]:
        """What the planner sees: no internal scoring metadata."""
        view = []
        for t in self.tools:
            entry = {
                "name": t["name"],
                "description": t["description"],
                "params": [f"{p['name']} ({p['type']}): {p['description']}" for p in t["params"]],
                "returns": t["returns"],
                "callable_by_you": ORCHESTRATOR in t.get("callable_by", []),
            }
            if t.get("status") == "deprecated":
                entry["status"] = "deprecated"
            if t.get("caveat"):
                entry["caveat"] = t["caveat"]
            view.append(entry)
        return view


@lru_cache(maxsize=4)
def load_catalog(version: str = "v1") -> Catalog:
    path = _ORCH_DIR / f"catalog_{version}.json"
    return Catalog(json.loads(path.read_text(encoding="utf-8")))


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
    catalog = load_catalog("v1")
    words = [w for w in query.lower().split() if len(w) > 2]
    matches = []
    for tool in catalog.planner_view():
        searchable = f"{tool['name']} {tool['description']}".lower()
        if any(word in searchable for word in words):
            matches.append(tool)
    return {"query": query, "matches": matches}
