"""Start a reproducible Part B demo with automatic preparation paused."""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def prepare_database(path, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS calendar_simulation (id INTEGER PRIMARY KEY, state TEXT)")
        row = db.execute("SELECT state FROM calendar_simulation WHERE id=1").fetchone()
        state = json.loads(row[0]) if row else {"now": "2026-11-11T15:00:00-05:00"}
        state.update(enabled=False, mode=mode, presentation="workspace-v1")
        db.execute("INSERT OR REPLACE INTO calendar_simulation VALUES (1, ?)", (json.dumps(state),))
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='calendar_preparations'").fetchone():
            db.execute("UPDATE calendar_preparations SET status='failed', requested=0, "
                       "error='Preparation interrupted by restart. Retry to continue.' "
                       "WHERE status IN ('queued','preparing')")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--db-path", type=Path, default=ROOT / ".local-settings" / "briefing-demo.db")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mode", choices=("agent", "simulation"), default="agent")
    parser.add_argument("--workspace-store", choices=("firestore", "local"))
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    load_dotenv(args.env_file)
    os.environ["SIA_DB_PATH"] = str(args.db_path.resolve())
    if args.workspace_store:
        os.environ["SIA_WORKSPACE_STORE"] = args.workspace_store
    sys.path.insert(0, str(ROOT / "src"))

    import uvicorn

    from self_improving_ai.config import settings

    if settings.workspace_store == "firestore" and not settings.google_cloud_project:
        parser.error("Configure SIA_GOOGLE_CLOUD_PROJECT in the environment file")
    prepare_database(args.db_path, args.mode)
    print(f"Part B demo: {settings.workspace_store} workspace, {args.mode} preparation, automatic scanning paused.", flush=True)
    print("Use a new labeled test meeting to verify generation. Agent preparation uses the configured Gemini quota.", flush=True)
    uvicorn.run("self_improving_ai.dashboard.app:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
