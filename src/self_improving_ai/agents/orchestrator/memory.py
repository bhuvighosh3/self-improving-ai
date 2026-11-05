"""Learned memory for Component C, the three improvement mechanisms from the scope:

1. Intent memory: misread requests and their corrections (plus confirmed examples),
   retrieved for similar future requests.
2. Tool notes: the orchestrator's own notes on what each tool is actually good for, learned
   from outcomes rather than trusted from the catalog.
3. Plan templates: plans that worked, saved per intent and adapted to new requests.

Safeguards built in (Test Suite rows in brackets):
- Client names, IDs and dollar amounts are scrubbed before anything is stored [H-8].
- Tool notes record the tool's contract fingerprint and are dropped when the catalog
  changes that tool [H-4].
- Contradictory intent corrections are surfaced as conflicts, not resolved by recency [H-7].
- Memory is capped and pruned so retrieval stays precise [H-11].
- Every adopted change is a new version with an audit-log entry; any version can be
  restored [H-6].
"""

from __future__ import annotations

import copy
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from self_improving_ai.tools.orchestrator.catalog import Catalog

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "orchestrator"

MAX_EXAMPLES_PER_INTENT = 6
MAX_NOTES_PER_TOOL = 2

_SHORTHAND = {"4": "for", "b4": "before", "pls": "please", "w/": "with", "tmrw": "tomorrow",
              "u": "you", "px": "price", "rebal": "rebalance", "tlh": "harvest", "today's": "today",
              "s": ""}
_STOPWORDS = {"a", "an", "the", "to", "of", "and", "or", "for", "on", "in", "at", "is", "are", "be", "me", "my", "i", "we", "our", "it", "this", "that", "with", "what", "whats", "can", "could", "you", "your", "their", "they", "them", "do", "does", "how", "much", "any", "please", "need", "get", "give"}
# Request-specific argument values are stored as placeholders in plan templates.
_SLOT_ARGS = {"ticker": "<ticker>", "date": "<date>", "shock_bps": "<bps>", "currency_pair": "<pair>",
              "goal_amount": "<amount>", "meeting_time": "<time>", "tickers": "<tickers>", "focus": "<focus>",
              "topic": "<topic>", "event_id": "<event_id>"}
# Lessons that would make the copilot less safe are never stored [H-1].
_BLOCKED_PHRASES = ["not to worry", "no action needed", "will recover", "guarantee",
                    "place the trade", "send it directly", "skip compliance"]


def _load_client_terms() -> list[str]:
    path = _DATA_DIR / "clients.json"
    if not path.exists():
        return []
    terms: set[str] = set()
    for c in json.loads(path.read_text()):
        terms.update([c["name"], c["primary_contact"], *c["aliases"]])
        for part in c["primary_contact"].split() + c["name"].split():
            if part[0].isupper() and part.lower() not in {"family", "household", "trust",
                                                           "retirement", "account", "the"}:
                terms.add(part)
    terms.update(["J. Chen", "Chens", "Garcias", "Okafors", "Smiths", "Nguyens", "Rossis",
                  "Johnsons", "Haddads", "Kowalskis"])
    return sorted(terms, key=len, reverse=True)


_CLIENT_TERMS = _load_client_terms()


def scrub(text: str) -> str:
    """Remove client identifiers so lessons generalize and never leak across clients."""
    out = re.sub(r"CLI-\d+", "<client_id>", text)
    out = re.sub(r"ACC-[\w]+", "<account_id>", out)
    out = re.sub(r"\$\s?[\d,.]+\s?[kKmM]?\b", "<amount>", out)
    for term in _CLIENT_TERMS:
        out = re.sub(rf"\b{re.escape(term)}\b", "<client>", out, flags=re.IGNORECASE)
    out = re.sub(r"(<client>\s*)+", "<client> ", out)
    return out.strip()


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9/<>_+]+", text.lower())
    words = [_SHORTHAND.get(w, w) for w in words]
    return [w for w in words if len(w) > 1 and w not in _STOPWORDS and w not in {"<client>", "<amount>"}]


def similarity(a: list[str], b: list[str]) -> float:
    """Cosine similarity over token counts; cheap and good enough for short requests."""
    if not a or not b:
        return 0.0
    ca, cb = Counter(a), Counter(b)
    shared = set(ca) & set(cb)
    if len(shared) < 2 and not (len(ca) == 1 and shared):
        return 0.0  # one common word is not enough evidence on its own
    dot = sum(ca[t] * cb[t] for t in shared)
    return dot / (math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values())))


def is_safe_lesson(text: str) -> bool:
    low = text.lower()
    return not any(p in low for p in _BLOCKED_PHRASES)


@dataclass
class IntentExample:
    text: str
    intent: str
    kind: str = "confirmation"  # "correction" | "confirmation"
    wrong_intent: str = ""
    note: str = ""
    evidence: int = 1


@dataclass
class ToolNote:
    tool: str
    note: str
    tool_fingerprint: str
    catalog_version: str
    evidence: int = 1


@dataclass
class PlanTemplate:
    intent: str
    steps: list[dict]
    evidence: int = 1


@dataclass
class OrchestratorMemory:
    version: int = 0
    intent_examples: list[IntentExample] = field(default_factory=list)
    tool_notes: list[ToolNote] = field(default_factory=list)
    plan_templates: dict[str, PlanTemplate] = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)
    rejected_lessons: list[str] = field(default_factory=list)

    # Retrieval

    def similar_examples(self, request_text: str, k: int = 4, min_sim: float = 0.3) -> list[tuple[float, IntentExample]]:
        q = tokens(scrub(request_text))
        scored = [(similarity(q, tokens(e.text)), e) for e in self.intent_examples]
        scored = [s for s in scored if s[0] >= min_sim]
        scored.sort(key=lambda s: (-s[0], s[1].kind != "correction"))
        return scored[:k]

    def valid_tool_notes(self, catalog: Catalog) -> list[ToolNote]:
        """Notes whose tool still exists with the same contract; stale notes are skipped."""
        return [n for n in self.tool_notes if catalog.fingerprint(n.tool) == n.tool_fingerprint]

    def stale_tool_notes(self, catalog: Catalog) -> list[ToolNote]:
        return [n for n in self.tool_notes if catalog.fingerprint(n.tool) != n.tool_fingerprint]

    def render(self, request_text: str, catalog: Catalog) -> dict[str, str]:
        """Text blocks for the planner prompt and the ADK orchestrator's session state."""
        hits = self.similar_examples(request_text)
        lines = []
        for sim, e in hits:
            if e.kind == "correction":
                line = f'- "{e.text}" -> intent {e.intent} (not {e.wrong_intent})'
            else:
                line = f'- "{e.text}" -> intent {e.intent}'
            if e.note:
                line += f". {e.note}"
            lines.append(line)
        intent_block = ""
        if lines:
            intent_block = "## Lessons from similar past requests\n" + "\n".join(lines)

        notes = self.valid_tool_notes(catalog)
        tool_block = ""
        if notes:
            tool_block = "## Your notes on tools (learned from past outcomes)\n" + "\n".join(
                f"- {n.tool}: {n.note}" for n in notes
            )

        intents = []
        for _, e in hits:
            if e.intent not in intents:
                intents.append(e.intent)
        tmpl_lines = []
        for intent in intents[:2]:
            t = self.plan_templates.get(intent)
            if not t:
                continue
            if not t.steps:
                tmpl_lines.append(f"- {intent}: no tool calls")
                continue
            ok = all(catalog.exists(s["tool"]) for s in t.steps)
            if not ok:
                continue
            steps = "; ".join(
                f"{s['id']}. {s['tool']}({', '.join(f'{k}={v}' for k, v in s.get('args', {}).items())})"
                + (f" after {s['depends_on']}" if s.get("depends_on") else "")
                for s in t.steps
            )
            tmpl_lines.append(f"- {intent}: {steps}")
        tmpl_block = ""
        if tmpl_lines:
            tmpl_block = "## Plan templates that worked before\n" + "\n".join(tmpl_lines)

        return {"intent_corrections": intent_block, "tool_notes": tool_block, "plan_templates": tmpl_block}

    # Updates (always on a copy; the harness decides whether to adopt)

    def add_intent_example(self, ex: IntentExample) -> None:
        ex.text = scrub(ex.text)
        ex.note = scrub(ex.note)
        if not is_safe_lesson(ex.note):
            self.rejected_lessons.append(ex.note)
            return
        q = tokens(ex.text)
        for existing in self.intent_examples:
            if similarity(q, tokens(existing.text)) > 0.95:
                if existing.intent == ex.intent:
                    existing.evidence += 1
                    if ex.kind == "correction":
                        existing.kind, existing.wrong_intent = "correction", ex.wrong_intent
                        existing.note = ex.note or existing.note
                    return
                # Contradicts an existing lesson: flag for a human instead of overwriting.
                self.conflicts.append({
                    "text": ex.text, "existing_intent": existing.intent, "new_intent": ex.intent,
                })
                return
        self.intent_examples.append(ex)
        self._prune_examples(ex.intent)

    def add_tool_note(self, tool: str, note: str, catalog: Catalog) -> None:
        note = scrub(note)
        if not is_safe_lesson(note):
            self.rejected_lessons.append(note)
            return
        fp = catalog.fingerprint(tool)
        if not fp:
            return
        for n in self.tool_notes:
            if n.tool == tool and n.note == note:
                n.evidence += 1
                return
        self.tool_notes.append(ToolNote(tool, note, fp, catalog.version))
        same = [n for n in self.tool_notes if n.tool == tool]
        if len(same) > MAX_NOTES_PER_TOOL:
            weakest = min(same, key=lambda n: n.evidence)
            self.tool_notes.remove(weakest)

    def set_plan_template(self, intent: str, steps: list[dict]) -> None:
        clean = []
        for s in steps:
            args = {}
            for k, v in s.get("args", {}).items():
                if str(v).startswith("CLI-") or k == "client_id":
                    v = "<client_id>"
                elif k in _SLOT_ARGS:
                    v = _SLOT_ARGS[k]
                args[k] = v
            clean.append({"id": s["id"], "tool": s["tool"], "args": args, "depends_on": s.get("depends_on", [])})
        existing = self.plan_templates.get(intent)
        if existing and existing.steps == clean:
            existing.evidence += 1
        else:
            self.plan_templates[intent] = PlanTemplate(intent, clean)

    def drop_stale(self, catalog: Catalog) -> list[str]:
        """Remove notes about tools that changed; returns the tools affected."""
        stale = self.stale_tool_notes(catalog)
        self.tool_notes = [n for n in self.tool_notes if n not in stale]
        return sorted({n.tool for n in stale})

    def _prune_examples(self, intent: str) -> None:
        same = [e for e in self.intent_examples if e.intent == intent and e.kind == "confirmation"]
        while len(same) > MAX_EXAMPLES_PER_INTENT:
            weakest = min(same, key=lambda e: e.evidence)
            self.intent_examples.remove(weakest)
            same.remove(weakest)

    def size(self) -> dict[str, int]:
        return {
            "intent_examples": len(self.intent_examples),
            "tool_notes": len(self.tool_notes),
            "plan_templates": len(self.plan_templates),
            "conflicts": len(self.conflicts),
        }

    def copy(self) -> OrchestratorMemory:
        return copy.deepcopy(self)

    # Persistence

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "intent_examples": [vars(e) for e in self.intent_examples],
            "tool_notes": [vars(n) for n in self.tool_notes],
            "plan_templates": {k: vars(v) for k, v in self.plan_templates.items()},
            "conflicts": self.conflicts,
            "rejected_lessons": self.rejected_lessons,
        }

    @classmethod
    def from_dict(cls, d: dict) -> OrchestratorMemory:
        return cls(
            version=d.get("version", 0),
            intent_examples=[IntentExample(**e) for e in d.get("intent_examples", [])],
            tool_notes=[ToolNote(**n) for n in d.get("tool_notes", [])],
            plan_templates={k: PlanTemplate(**v) for k, v in d.get("plan_templates", {}).items()},
            conflicts=d.get("conflicts", []),
            rejected_lessons=d.get("rejected_lessons", []),
        )


class MemoryStore:
    """Versioned storage with an audit log, so every adopted change can be rolled back."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.root / "audit_log.jsonl"
        self.active_path = self.root / "ACTIVE"

    def _path(self, version: int) -> Path:
        return self.root / f"memory_v{version:03d}.json"

    def versions(self) -> list[int]:
        return sorted(int(p.stem.split("_v")[1]) for p in self.root.glob("memory_v*.json"))

    def active_version(self) -> int | None:
        if self.active_path.exists():
            return int(self.active_path.read_text().strip())
        return None

    def load(self, version: int | None = None) -> OrchestratorMemory:
        version = self.active_version() if version is None else version
        if version is None:
            return OrchestratorMemory()
        return OrchestratorMemory.from_dict(json.loads(self._path(version).read_text()))

    def log(self, action: str, **details) -> None:
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, **details}
        with self.audit_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def adopt(self, memory: OrchestratorMemory, reason: str, **details) -> int:
        existing = self.versions()
        memory.version = (existing[-1] + 1) if existing else 1
        self._path(memory.version).write_text(json.dumps(memory.to_dict(), indent=2))
        previous = self.active_version()
        self.active_path.write_text(str(memory.version))
        self.log("adopt", version=memory.version, previous=previous, reason=reason, **details)
        return memory.version

    def reject(self, reason: str, **details) -> None:
        self.log("reject", active=self.active_version(), reason=reason, **details)

    def rollback(self, version: int, reason: str = "manual rollback") -> OrchestratorMemory:
        if version not in self.versions():
            raise ValueError(f"No memory version {version}")
        previous = self.active_version()
        self.active_path.write_text(str(version))
        self.log("rollback", version=version, previous=previous, reason=reason)
        return self.load(version)


def default_store() -> MemoryStore:
    from self_improving_ai.config import settings

    return MemoryStore(Path(settings.data_dir).parent / "store" / "orchestrator_memory")


def orchestrator_state_for(request_text: str, store: MemoryStore | None = None) -> dict[str, str]:
    """Session-state values for the ADK orchestrator's instruction placeholders."""
    from self_improving_ai.tools.orchestrator.catalog import load_catalog

    store = store or default_store()
    memory = store.load()
    return memory.render(request_text, load_catalog("v1"))
