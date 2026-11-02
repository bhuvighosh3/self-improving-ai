"""Package source and selected existing evidence without environments or secrets."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "artifacts/reports"
LIVE = ROOT / "artifacts/live/2026-11-02"
SKIP = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache",
        ".local-tmp", ".local-settings", ".git", "dist", "test-results",
        "playwright-report", "work", "releases", "artifacts"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None


def source_files():
    files = []
    for directory, dirs, names in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in SKIP]
        for name in names:
            path = Path(directory) / name
            if name.startswith(".env") and name != ".env.example":
                continue
            if path.suffix not in {".pyc", ".log", ".db", ".sqlite"}:
                files.append(path)
    return files


def evidence_files():
    files = [REPORTS / name for name in ("pytest.xml", "browser-tests.json",
             "development_evaluation.json", "original_integrity.json")]
    files.extend((ROOT / "artifacts/screenshots").glob("*.png"))
    files.extend(LIVE.glob("*.json"))
    files.extend(LIVE.glob("live_development*/report.json"))
    transport = ROOT / "artifacts/agent_transport/report.json"
    report = read_json(transport)
    if report:
        files.append(transport)
        files.extend(transport.parent / "runs" / (row["run"]["run_id"] + ".json")
                     for row in report["records"])
    index = ROOT / "artifacts/gate_demo/latest.json"
    latest = read_json(index)
    if latest:
        report_path = Path(latest["report"])
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        gate = report_path.parent.resolve()
        if not gate.is_relative_to((ROOT / "artifacts/gate_demo").resolve()):
            raise ValueError("Gate evidence must stay inside this project")
        files.append(index)
        files.extend(gate.rglob("*.json"))
    return [path for path in files if path.is_file()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    local_baseline = ROOT.parents[1] / "review_work/component-a-starter"
    parser.add_argument("--baseline", type=Path,
                        default=local_baseline if local_baseline.is_dir() else None)
    parser.add_argument("--original-zip", type=Path)
    parser.add_argument("--output", type=Path,
                        default=ROOT.parent / "releases/component-a-development.zip")
    args = parser.parse_args()
    baseline = args.baseline.resolve() if args.baseline else None
    if baseline is not None and not baseline.is_dir():
        parser.error("The baseline directory does not exist")
    REPORTS.mkdir(parents=True, exist_ok=True)
    if args.original_zip:
        integrity = {"zip_sha256": sha(args.original_zip.read_bytes()),
                     "review_copy_matches_original_zip": None}
        if baseline:
            differences = []
            with zipfile.ZipFile(args.original_zip) as archive:
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    relative = Path(item.filename)
                    if relative.parts[0] == "component-a-starter":
                        relative = Path(*relative.parts[1:])
                    local = baseline / relative
                    if not local.is_file() or local.read_bytes() != archive.read(item):
                        differences.append(relative.as_posix())
            if differences:
                raise ValueError("Original review copy differs from ZIP: " + str(differences))
            integrity.update(review_copy_matches_original_zip=True, differences=[])
        (REPORTS / "original_integrity.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")

    sources = source_files()
    target = args.output.resolve()
    if target.is_relative_to(ROOT):
        parser.error("Write the archive outside the source directory")
    changes = []
    for path in sources:
        relative = path.relative_to(ROOT)
        old = baseline / relative if baseline else None
        if old is None or not old.is_file() or old.read_bytes() != path.read_bytes():
            changes.append({"path": relative.as_posix(),
                            "change": "modified" if old and old.is_file() else "added",
                            "sha256": sha(path.read_bytes())})
    if baseline:
        for old in baseline.rglob("*"):
            relative = old.relative_to(baseline)
            if old.is_file() and not any(part in SKIP for part in relative.parts) and not (ROOT / relative).exists():
                changes.append({"path": relative.as_posix(), "change": "removed_or_relocated"})

    validation = {"draft_assumptions_approved": False, "learning_gain_demonstrated": False}
    junit = REPORTS / "pytest.xml"
    if junit.exists():
        suite = ElementTree.parse(junit).getroot().find("testsuite")
        count = len(suite.findall("testcase"))
        validation.update(pytest=count, pytest_subtests=int(suite.attrib["tests"]) - count, junit=suite.attrib)
    browser = read_json(REPORTS / "browser-tests.json")
    if browser:
        validation.update(browser_tests=browser["stats"]["expected"],
                          browser_failures=browser["stats"]["unexpected"])
    live = read_json(LIVE / "live_audit_summary.json")
    if live:
        validation["historical_live_audit"] = live
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "baseline_available": baseline is not None, "changes": changes, "validation": validation}
    manifest_path = REPORTS / "implementation-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files = [*sources, *evidence_files(), manifest_path]

    private = read_json(ROOT / ".local-settings/connections.json") or {}
    keys = [value.encode() for name, value in private.items() if name.endswith("API_KEY") and value]
    if (ROOT / ".env").exists():
        from dotenv import dotenv_values
        keys.extend(value.encode() for name, value in dotenv_values(ROOT / ".env").items()
                    if name.endswith("API_KEY") and value)
    for path in files:
        if any(key in path.read_bytes() for key in keys):
            raise ValueError("A local credential was found in release inputs")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(set(files)):
                member = "component-a/" + path.relative_to(ROOT).as_posix()
                if path == ROOT / "artifacts/gate_demo/latest.json":
                    # This generated index must work on another checkout. Raw run
                    # and scoring evidence is preserved without rewriting it.
                    index = read_json(path)
                    for key in ("report", "observation"):
                        recorded = Path(index[key])
                        if recorded.is_absolute() and recorded.is_relative_to(ROOT):
                            index[key] = recorded.relative_to(ROOT).as_posix()
                    archive.writestr(member, json.dumps(index, indent=2))
                else:
                    archive.write(path, member)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("Release archive integrity check failed")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"archive": str(target), "bytes": target.stat().st_size,
                      "source_changes": len(changes), "credential_scan": "passed",
                      "original_verified_this_run": args.original_zip is not None}, indent=2))


if __name__ == "__main__":
    main()
