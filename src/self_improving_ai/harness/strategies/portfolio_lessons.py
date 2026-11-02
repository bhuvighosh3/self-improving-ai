"""Minimal local validation/regression gate. Not a statistical research harness."""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from uuid import uuid4

LESSONS = {
    "STALE_PRICE": "Check source dates and timeliness before using a quote; never treat a stale fixture as a current price.",
    "UNIT_MISMATCH": "Keep weights and annual returns as decimals; present allocation drift in percentage points.",
    "ACCOUNT_NOT_FOUND": "An invalid account is an error, not a zero-value portfolio; stop dependent calculations.",
}


class LessonStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"active": "baseline", "versions": [{"id": "baseline", "text": ""}], "audit": [], "candidates": []}

    def write(self, document: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(document, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(self.path)

    def active_text(self) -> str:
        doc = self.read()
        return next(version["text"] for version in doc["versions"] if version["id"] == doc["active"])

    def propose(self, failure_code: str, evidence_run_id: str) -> dict:
        if failure_code not in LESSONS or not evidence_run_id:
            raise ValueError("Only supported, observed feedback can create a candidate.")
        document = self.read()
        candidate = {"id": uuid4().hex, "base": document["active"],
                "text": (self.active_text() + "\n" + LESSONS[failure_code]).strip(),
                "failure_code": failure_code, "evidence_run_id": evidence_run_id,
                "generator": "deterministic_feedback_template"}
        document.setdefault("candidates", []).append(candidate)
        self.write(document)
        return candidate

    def assess(self, candidate: dict, evaluator, validation: list[dict], regression: list[dict],
               evaluation_evidence: dict | None = None) -> dict:
        """Evaluator receives (lesson_text, case) and returns a fresh, frozen score 0..1.

        Cases must be disjoint and labeled validation/regression, never hidden tests.
        Callers must create fresh sessions, freeze the model/data and avoid memory updates.
        """
        doc = self.read()
        saved = next((item for item in doc.get("candidates", []) if item["id"] == candidate.get("id")), None)
        if saved != candidate:
            raise ValueError("Candidate was not registered or was modified after proposal.")
        if any(item.get("id") == candidate["id"] for item in doc["audit"]):
            raise ValueError("This candidate was already evaluated; do not retry until it happens to pass.")
        if candidate["base"] != doc["active"]:
            raise ValueError("Candidate is based on an obsolete version.")
        if not validation or not regression:
            raise ValueError("Both validation and regression cases are required.")
        cases = validation + regression
        if len({case["id"] for case in cases}) != len(cases) or any(
            case.get("split") != split for split, group in (("validation", validation),
            ("regression", regression)) for case in group
        ):
            raise ValueError("Cases must be disjoint and correctly split.")
        baseline = self.active_text()
        scores = []
        for case in cases:
            before, after = evaluator(baseline, case), evaluator(candidate["text"], case)
            if any(isinstance(x, bool) or not isinstance(x, (float, int))
                   or not math.isfinite(x) or not 0 <= x <= 1 for x in (before, after)):
                raise ValueError("Invalid evaluator score.")
            scores.append({"case_id": case["id"], "split": case["split"],
                           "before": before, "after": after})
        improved = mean(s["after"] - s["before"] for s in scores if s["split"] == "validation") > 0
        regressed = any(s["after"] < s["before"] for s in scores if s["split"] == "regression")
        accepted = improved and not regressed
        record = {**candidate, "accepted": accepted, "scores": scores,
                  "evaluation_evidence": evaluation_evidence,
                  "reason": "accepted" if accepted else "regression" if regressed else "no_validation_gain"}
        if self.read()["active"] != candidate["base"]:
            raise ValueError("Active version changed during evaluation.")
        if accepted:
            doc["versions"].append({"id": candidate["id"], "text": candidate["text"],
                                    "evaluation_evidence": evaluation_evidence})
            doc["active"] = candidate["id"]
        doc["audit"].append(record)
        self.write(doc)
        return record

    def rollback(self, version: str):
        doc = self.read()
        if version not in {item["id"] for item in doc["versions"]}:
            raise ValueError("Version does not exist.")
        doc["audit"].append({"action": "rollback", "from": doc["active"], "to": version})
        doc["active"] = version
        self.write(doc)
