"""Compact replay fingerprints without recording credentials or environment contents."""
import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path


def run_metadata(lessons: str = "") -> dict:
    package = Path(__file__).resolve().parents[2]
    files = [package / "data/clients/households.json", *sorted((package / "data/portfolio").glob("*.json"))]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes())
    code = hashlib.sha256()
    for directory in (package / "agents/portfolio", package / "tools/portfolio"):
        for path in sorted(directory.glob("*.py")):
            code.update(path.relative_to(package).as_posix().encode())
            code.update(path.read_bytes())
    return {"schema_version": 2, "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "data_sha256": digest.hexdigest(),
            "implementation_sha256": code.hexdigest(),
            "lesson_sha256": hashlib.sha256(lessons.encode()).hexdigest()}
