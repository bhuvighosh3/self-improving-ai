"""Persisted calendar simulation and autonomous, idempotent meeting preparation."""

import asyncio
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Literal
from contextlib import contextmanager

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.briefing.contract import CONTRACT_VERSION
from self_improving_ai.config import settings


def agent_pipeline():
    return CONTRACT_VERSION + ":" + settings.briefing_discovery

from self_improving_ai.calendar_adapter import normalize_event
from self_improving_ai.workspace_store import workspace_snapshot
from self_improving_ai.tools.briefing.workspace_sources import content_version
import hashlib
NY = ZoneInfo("America/New_York")


class SimulationCommand(BaseModel):
    action: Literal["start", "pause", "advance", "reset"]
    mode: Literal["simulation", "agent"] | None = None


class MeetingPreparationMonitor:
    def __init__(self, path, prepare):
        self.path, self.prepare = str(path), prepare
        profiles = json.loads((Path(__file__).resolve().parents[1] / "data/clients/households.json").read_text(encoding="utf-8"))
        self.client_names = {record["client_id"]:record["profile"]["name"] for record in profiles}
        self.lock = asyncio.Lock()
        self.processing = False
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS calendar_simulation (id INTEGER PRIMARY KEY, state TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS calendar_preparations "
                       "(id TEXT PRIMARY KEY, event_id TEXT, version TEXT, mode TEXT, status TEXT, "
                       "request TEXT, brief_id TEXT, error TEXT, run_id TEXT, "
                       "UNIQUE(event_id, version, mode))")
            columns = {row[1] for row in db.execute("PRAGMA table_info(calendar_preparations)")}
            if "requested" not in columns:
                db.execute("ALTER TABLE calendar_preparations ADD COLUMN requested INTEGER NOT NULL DEFAULT 0")
            if "pipeline_version" not in columns:
                db.execute("ALTER TABLE calendar_preparations ADD COLUMN pipeline_version TEXT NOT NULL DEFAULT ''")
            db.execute("INSERT OR IGNORE INTO calendar_simulation VALUES (1, ?)", (json.dumps(self.initial()),))
            state = json.loads(db.execute("SELECT state FROM calendar_simulation WHERE id=1").fetchone()[0])
            if state.get("presentation") != "workspace-v1":
                # Upgrade the earlier technical demo once, preserving its drafts.
                db.execute("UPDATE calendar_simulation SET state=? WHERE id=1", (json.dumps(self.initial()),))
            # A restarted worker must not leave an apparently active job forever.
            db.execute("UPDATE calendar_preparations SET status='failed', "
                       "error='Preparation interrupted by server restart. Retry to continue.' WHERE status='preparing'")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def initial(self):
        return {"now": "2026-11-11T15:00:00-05:00", "enabled": True,
                "mode": "simulation", "presentation": "workspace-v1"}

    def events_at(self, now):
        cutoff = now[:10]
        mail = workspace_snapshot("email", path=self.path)
        events = []
        for record in workspace_snapshot("calendar", path=self.path):
            related = [item for item in mail if item.get("client_id") == record.get("client_id")
                and item.get("folder") in {"inbox","sent","archive"} and item["date"] <= min(cutoff, record["date"])
                and item.get("created_at",item["date"])[:10] <= min(cutoff, record["date"])]
            revision = hashlib.sha256(json.dumps(sorted((item["id"],content_version(item)) for item in related)).encode()).hexdigest()[:20]
            try:
                events.append(normalize_event(record,self.client_names,revision))
            except (ValueError,KeyError):
                continue
        return sorted(events,key=lambda event:event["starts_at"])

    @property
    def events(self):
        with self.db() as db:
            now = json.loads(db.execute("SELECT state FROM calendar_simulation WHERE id=1").fetchone()[0])["now"]
        return self.events_at(now)

    def state(self):
        with self.db() as db:
            state = json.loads(db.execute("SELECT state FROM calendar_simulation WHERE id=1").fetchone()[0])
            rows = db.execute("SELECT id,event_id,version,mode,status,brief_id,error,run_id FROM calendar_preparations "
                              "WHERE mode!='agent' OR pipeline_version=?", (agent_pipeline(),)).fetchall()
        events = self.events_at(state["now"])
        current = {(event["id"],str(event["version"])) for event in events}
        state.update(lookahead_hours=24, processing=self.processing, timezone="America/New_York",
                     storage=settings.workspace_store, events=events, preparations=[dict(zip(
                         ("id", "event_id", "version", "mode", "status", "brief_id", "error", "run_id"), row)) for row in rows
                         if (row[1],str(row[2])) in current])
        return state

    async def command(self, command: SimulationCommand):
        async with self.lock:
            state = await asyncio.to_thread(self.state)
            if self.processing and (command.action in {"advance", "reset"} or command.mode != state["mode"] and command.mode is not None):
                raise ValueError("Wait for the current preparation before changing time or mode")
            updated = {k: state[k] for k in ("now", "enabled", "mode", "presentation")}
            if command.action == "reset":
                updated = self.initial()
            elif command.action == "advance":
                updated["now"] = (datetime.fromisoformat(state["now"]) + timedelta(hours=24)).isoformat()
            else:
                updated["enabled"] = command.action == "start"
            if command.mode is not None:
                updated["mode"] = command.mode
            with self.db() as db:
                if command.action == "reset":
                    db.execute("DELETE FROM calendar_preparations")
                db.execute("UPDATE calendar_simulation SET state=? WHERE id=1", (json.dumps(updated),))
        return await asyncio.to_thread(self.state)

    def _enqueue(self, state):
        now = datetime.fromisoformat(state["now"])
        for event in state["events"]:
            if not event.get("prep_required", bool(event.get("client_id"))):
                continue
            start = datetime.fromisoformat(event["starts_at"]).astimezone(NY)
            if not now < start <= now + timedelta(hours=24):
                continue
            self._enqueue_event(event, state["mode"])

    def _enqueue_event(self, event, mode, requested=False):
        start = datetime.fromisoformat(event["starts_at"]).astimezone(NY)
        request = MeetingBriefRequest(client_id=event["client_id"], meeting_date=start.date(),
            meeting_time=start.time().replace(tzinfo=None), meeting_type=event["meeting_type"],
            focus=event["focus"], mode=mode, calendar_event_id=event["id"])
        with self.db() as db:
            if mode == "agent":
                # Keep historical draft records; replace only outdated calendar job links.
                db.execute("DELETE FROM calendar_preparations WHERE event_id=? AND version=? AND mode='agent' AND pipeline_version!=?",
                           (event["id"], event["version"], agent_pipeline()))
            db.execute("INSERT OR IGNORE INTO calendar_preparations "
                "(id,event_id,version,mode,status,request,requested,pipeline_version) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)",
                (str(uuid4()), event["id"], event["version"], mode, request.model_dump_json(), int(requested), agent_pipeline() if mode == "agent" else "offline-v1"))
            if requested:
                db.execute("UPDATE calendar_preparations SET requested=1 WHERE event_id=? AND version=? AND mode=?",
                           (event["id"], event["version"], mode))

    async def request_event(self, event_id):
        async with self.lock:
            state = await asyncio.to_thread(self.state)
            event = next((event for event in state["events"] if event["id"] == event_id), None)
            if event is None:
                raise LookupError("Calendar meeting not found")
            if not event.get("prep_required", bool(event.get("client_id"))):
                raise ValueError("This calendar event does not need a client meeting brief")
            self._enqueue_event(event, state["mode"], requested=True)
            with self.db() as db:
                row = db.execute("SELECT id,event_id,version,mode,status,brief_id,error,run_id FROM calendar_preparations "
                                 "WHERE event_id=? AND version=? AND mode=?", (event_id,event["version"],state["mode"])).fetchone()
            return dict(zip(("id","event_id","version","mode","status","brief_id","error","run_id"),row))

    async def tick(self):
        async with self.lock:
            state = await asyncio.to_thread(self.state)
            if self.processing:
                return
            if state["enabled"]:
                self._enqueue(state)
            with self.db() as db:
                current = {(event["id"],str(event["version"])) for event in state["events"]}
                for old in db.execute("SELECT id,event_id,version FROM calendar_preparations WHERE status='queued'").fetchall():
                    if (old[1],str(old[2])) not in current:
                        db.execute("UPDATE calendar_preparations SET status='superseded',error='Meeting or client context changed' WHERE id=?",(old[0],))
                row = db.execute("SELECT id,request,event_id,version FROM calendar_preparations WHERE status='queued' AND mode=? "
                                 "AND (? OR requested=1) AND (mode!='agent' OR pipeline_version=?) ORDER BY rowid LIMIT 1",
                                 (state["mode"], state["enabled"], agent_pipeline())).fetchone()
                if not row:
                    return
                cursor = db.execute("UPDATE calendar_preparations SET status='preparing' WHERE id=? AND status='queued'", (row[0],))
                if cursor.rowcount != 1:
                    return
            self.processing = True
        job_id, request_json, event_id, event_version = row
        try:
            brief = await self.prepare(MeetingBriefRequest.model_validate_json(request_json))
            current_events = await asyncio.to_thread(lambda: self.events)
            valid = any(event["id"] == event_id and str(event["version"]) == str(event_version) for event in current_events)
            with self.db() as db:
                db.execute("UPDATE calendar_preparations SET status=?, brief_id=?, error=?, run_id=? WHERE id=?",
                           ("ready" if valid else "superseded", brief["id"], None if valid else "Meeting or client context changed",
                            brief.get("workflow", {}).get("run_id"), job_id))
        except BaseException as exc:
            # The shared HTTP service emits safe messages; never expose provider payloads.
            error = exc.detail if isinstance(exc, HTTPException) and isinstance(exc.detail, str) else "Preparation interrupted. Retry to continue."
            run_id = (exc.headers or {}).get("X-Briefing-Run-ID") if isinstance(exc, HTTPException) else getattr(exc, "briefing_run_id", None)
            with self.db() as db:
                db.execute("UPDATE calendar_preparations SET status='failed',error=?,run_id=? WHERE id=?", (error, run_id, job_id))
            if isinstance(exc, asyncio.CancelledError):
                raise
        finally:
            self.processing = False

    async def retry(self, job_id):
        async with self.lock:
            state = await asyncio.to_thread(self.state)
            if not any(job["id"] == job_id and job["mode"] == state["mode"] for job in state["preparations"]):
                raise ValueError("Meeting or client context changed; open the current preparation")
            with self.db() as db:
                cursor = db.execute("UPDATE calendar_preparations SET status='queued',error=NULL,requested=1 WHERE id=? AND status='failed'", (job_id,))
                if cursor.rowcount != 1:
                    raise ValueError("Only failed preparations can be retried")
        return await asyncio.to_thread(self.state)

    def brief(self, job_id):
        if not any(job["id"] == job_id for job in self.state()["preparations"]):
            raise LookupError("Meeting or client context changed; open the current preparation")
        with self.db() as db:
            row = db.execute("SELECT brief_id FROM calendar_preparations WHERE id=? AND status='ready'", (job_id,)).fetchone()
        if row is None:
            raise LookupError("Preparation is not ready")
        return DraftStore(self.path).get(row[0])["brief"]

    async def serve(self):
        while True:
            try:
                await self.tick()
            except Exception:
                # A configuration outage must not permanently stop future scans.
                logging.getLogger(__name__).warning("Meeting monitor could not read workspace storage; retrying on the next scan")
                await asyncio.sleep(4)
            await asyncio.sleep(1)


router = APIRouter(prefix="/api/meeting-preparations", tags=["meeting preparation"])


@router.get("")
async def calendar_state(request: Request):
    try:
        return await asyncio.to_thread(request.app.state.preparations.state)
    except Exception as exc:
        raise HTTPException(503, "Workspace storage unavailable. Check the selected storage configuration.") from exc


@router.post("/simulation")
async def calendar_command(command: SimulationCommand, request: Request):
    try:
        return await request.app.state.preparations.command(command)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{job_id}/retry")
async def retry_preparation(job_id: str, request: Request):
    try:
        return await request.app.state.preparations.retry(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/events/{event_id}")
async def open_calendar_preparation(event_id: str, request: Request):
    try:
        return await request.app.state.preparations.request_event(event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{job_id}/brief")
async def calendar_brief(job_id: str, request: Request):
    try:
        return await asyncio.to_thread(request.app.state.preparations.brief, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
