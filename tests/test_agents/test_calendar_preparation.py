"""Calendar-triggered preparation, idempotence, failure and simulated-time isolation."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import HTTPException

from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.dashboard.preparation import MeetingPreparationMonitor, SimulationCommand
from self_improving_ai.workspace_store import LocalWorkspaceStore


class CalendarTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "simulation.db"
        self.calls = []

        async def prepare(request):
            self.calls.append(request)
            brief = generate_meeting_brief(request)
            DraftStore(self.path).create(brief)
            return brief

        self.prepare = prepare
        self.engine = MeetingPreparationMonitor(self.path, prepare)

    async def test_clock_window_prepares_upcoming_client_meetings_and_retains_briefs(self):
        await self.engine.tick()
        self.assertTrue(self.engine.state()["enabled"])
        await self.engine.tick()
        self.assertEqual([r.client_id for r in self.calls], ["CLI-001"])
        job = next(job for job in self.engine.state()["preparations"] if job["event_id"] == "EVT-a1b2c3d4")
        self.assertEqual(job["status"], "ready")
        brief = self.engine.brief(job["id"])
        self.assertEqual(brief["id"], job["brief_id"])
        self.assertIn("HOLDINGS", {s["id"] for s in brief["sources"]})
        self.assertEqual(DraftStore(self.path).get(brief["id"])["status"], "draft")
        await self.engine.tick()
        await self.engine.command(SimulationCommand(action="pause"))
        await self.engine.command(SimulationCommand(action="start"))
        await self.engine.tick()
        self.assertEqual(len(self.calls), 1)

    async def test_advancing_time_triggers_other_clients_without_manual_inputs(self):
        await self.engine.command(SimulationCommand(action="start"))
        for index in range(3):
            if index:
                await self.engine.command(SimulationCommand(action="advance"))
            await self.engine.tick()
            await self.engine.tick()
        self.assertEqual([r.client_id for r in self.calls], ["CLI-001", "CLI-002"])
        self.assertTrue(all(p["status"] == "ready" for p in self.engine.state()["preparations"]))

    async def test_provider_failure_is_visible_and_never_automatically_flooded(self):
        async def fail(request):
            self.calls.append(request)
            raise HTTPException(503, "Gemini is busy. Progress saved.", headers={"X-Briefing-Run-ID": "retained-run"})

        self.engine.prepare = fail
        await self.engine.command(SimulationCommand(action="start", mode="agent"))
        await self.engine.tick()
        await self.engine.command(SimulationCommand(action="pause"))
        await self.engine.tick()
        job = self.engine.state()["preparations"][0]
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["run_id"], "retained-run")
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(LookupError):
            self.engine.brief(job["id"])
        await self.engine.retry(job["id"])
        await self.engine.tick()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[0], self.calls[1])

    async def test_overlapping_scans_do_not_duplicate_active_work(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def wait(request):
            entered.set()
            await release.wait()
            return await self.prepare(request)

        self.engine.prepare = wait
        await self.engine.command(SimulationCommand(action="start"))
        task = asyncio.create_task(self.engine.tick())
        await entered.wait()
        try:
            await self.engine.tick()
            with self.assertRaises(ValueError):
                await self.engine.command(SimulationCommand(action="advance"))
        finally:
            release.set()
            await task
        self.assertEqual(len(self.calls), 1)

    async def test_events_in_past_are_not_prepared_and_reset_keeps_existing_drafts(self):
        for _ in range(2):
            await self.engine.command(SimulationCommand(action="advance"))
        await self.engine.command(SimulationCommand(action="start"))
        await self.engine.tick()
        self.assertEqual(self.calls[0].client_id, "CLI-002")
        job = self.engine.state()["preparations"][0]
        await self.engine.command(SimulationCommand(action="reset"))
        self.assertEqual(self.engine.state()["preparations"], [])
        self.assertTrue(self.engine.state()["enabled"])
        self.assertEqual(DraftStore(self.path).get(job["brief_id"])["status"], "draft")

    async def test_direct_open_prepares_future_meeting_even_when_monitoring_is_paused(self):
        await self.engine.command(SimulationCommand(action="pause"))
        await self.engine.tick()
        self.assertEqual(self.calls, [])
        queued = await self.engine.request_event("EVT-c9d0e1f2")
        self.assertEqual(queued["status"], "queued")
        await self.engine.tick()
        retained = await self.engine.request_event("EVT-c9d0e1f2")
        self.assertEqual(retained["id"], queued["id"])
        self.assertEqual(retained["status"], "ready")
        await self.engine.tick()
        self.assertEqual([r.client_id for r in self.calls], ["CLI-003"])
        self.assertEqual(self.engine.brief(retained["id"])["id"], retained["brief_id"])
        with self.assertRaises(LookupError):
            await self.engine.request_event("unknown")

    async def test_paused_failed_preparation_can_be_retried_explicitly(self):
        async def fail(request):
            raise HTTPException(503, "Provider busy. Retry later.")
        self.engine.prepare = fail
        await self.engine.tick()
        job = self.engine.state()["preparations"][0]
        await self.engine.command(SimulationCommand(action="pause"))
        self.engine.prepare = self.prepare
        await self.engine.retry(job["id"])
        await self.engine.tick()
        self.assertEqual(self.engine.state()["preparations"][0]["status"], "ready")

    async def test_calendar_changes_replace_jobs_and_deleted_meetings_cannot_open_old_briefs(self):
        await self.engine.tick()
        job = self.engine.state()["preparations"][0]
        store = LocalWorkspaceStore("calendar", self.path)
        store.update_event(job["event_id"], {"start_time":"14:15"})
        self.assertEqual(self.engine.state()["preparations"], [])
        with self.assertRaises(LookupError):
            self.engine.brief(job["id"])
        await self.engine.tick()
        replacement = self.engine.state()["preparations"][0]
        self.assertNotEqual(replacement["id"], job["id"])
        store.delete_event(job["event_id"])
        self.assertEqual(self.engine.state()["preparations"], [])
        with self.assertRaises(LookupError):
            await self.engine.request_event(job["event_id"])

    async def test_meeting_changed_during_generation_does_not_publish_stale_ready_notice(self):
        async def change(request):
            LocalWorkspaceStore("calendar", self.path).update_event(request.calendar_event_id, {"notes":"Updated meeting agenda"})
            return await self.prepare(request)
        self.engine.prepare = change
        await self.engine.tick()
        self.assertEqual(self.engine.state()["preparations"], [])
        with self.engine.db() as db:
            self.assertEqual(db.execute("SELECT status FROM calendar_preparations").fetchone()[0], "superseded")

    async def test_old_ai_job_does_not_masquerade_as_current_discovery(self):
        await self.engine.command(SimulationCommand(action="start", mode="agent"))
        await self.engine.tick()
        old_job = next(job for job in self.engine.state()["preparations"] if job["status"] == "ready")
        with self.engine.db() as db:
            db.execute("UPDATE calendar_preparations SET pipeline_version='legacy-writer-only' WHERE id=?", (old_job["id"],))
        self.assertFalse(any(job["id"] == old_job["id"] for job in self.engine.state()["preparations"]))
        replacement = await self.engine.request_event(old_job["event_id"])
        self.assertNotEqual(replacement["id"], old_job["id"])
        self.assertEqual(replacement["status"], "queued")
        self.assertEqual(DraftStore(self.path).get(old_job["brief_id"])["brief"]["id"], old_job["brief_id"])
