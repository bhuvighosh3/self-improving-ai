"""Exercise the HTTP workflow, persistence and provider failure boundaries."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from self_improving_ai.agents.briefing.contract import content_from_work

from fastapi.testclient import TestClient
from google.genai.errors import ClientError, ServerError

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.dashboard.app import app


REQUEST = {"client_id": "CLI-004", "meeting_date": "2026-11-06", "meeting_time": "14:00",
           "focus": "Home purchase funding", "meeting_type": "goal_review", "mode": "simulation"}


class BriefingApiTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = DraftStore(Path(directory.name) / "drafts.db")
        patcher = patch("self_improving_ai.dashboard.app.DraftStore", return_value=self.store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.http = TestClient(app)
        self.addCleanup(self.http.close)

    def test_offline_generation_check_review_and_approved_snapshot(self):
        generated = self.http.post("/api/briefings", json=REQUEST)
        self.assertEqual(generated.status_code, 200, generated.text)
        brief = generated.json()
        self.assertEqual(self.store.get(brief["id"])["status"], "draft")
        self.assertEqual(self.http.get(f"/api/briefings/{brief['id']}/approved").status_code, 409)
        check = self.http.post("/api/briefings/check", json={"brief": brief})
        self.assertEqual(check.status_code, 200, check.text)
        self.assertEqual(check.json()["verdict"], "pass")
        edited = deepcopy(brief)
        edited["sections"][0]["items"][0]["text"] = "Advisor question: confirm meeting priorities."
        # Browser metadata is not allowed to replace server-retained originals.
        edited["sources"] = []
        edited["workflow"]["evidence"]["sources"] = []
        review = self.http.post("/api/briefings/review", json={
            "brief": edited, "revision": 2, "expected_revision": 1, "decision": "approve"})
        self.assertEqual(review.status_code, 200, review.text)
        approved = self.http.get(f"/api/briefings/{brief['id']}/approved").json()
        self.assertEqual(approved["brief"]["sources"], brief["sources"])
        self.assertEqual(approved["brief"]["sections"], edited["sections"])
        stale = self.http.post("/api/briefings/review", json={
            "brief": brief, "revision": 1, "expected_revision": 1, "decision": "approve"})
        self.assertEqual(stale.status_code, 409)

    def test_copilot_agent_confirmation_uses_the_shared_service_once(self):
        brief = generate_meeting_brief(MeetingBriefRequest(**REQUEST))
        brief["mode"] = "agent"
        for endpoint in ("/api/chat", "/api/briefings"):
            brief["id"] = str(uuid4())
            with self.subTest(endpoint=endpoint), patch(
                "self_improving_ai.agents.briefing.runtime.generate_agent_brief",
                new=AsyncMock(return_value=deepcopy(brief)),
            ) as generate:
                payload = {**REQUEST, "mode": "agent"}
                if endpoint == "/api/chat":
                    payload = {"message": "Confirmed meeting", "meeting": payload}
                response = self.http.post(endpoint, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                generate.assert_awaited_once()
                result = response.json().get("brief", response.json())
                self.assertEqual(result, brief)
                self.assertEqual(self.store.get(result["id"])["brief"], result)

    def test_provider_failures_and_timeouts_never_create_offline_drafts(self):
        for error, status in [
            (RuntimeError("Provider unavailable"), 502), (TimeoutError(), 504),
            (ServerError(503, {"error": {"message": "Provider busy"}}), 503),
            (ClientError(429, {"error": {"message": "Quota reached"}}), 429),
            (ClientError(404, {"error": {"message": "Model unavailable"}}), 502),
        ]:
            with self.subTest(status=status), patch(
                "self_improving_ai.agents.briefing.runtime.generate_agent_brief",
                new=AsyncMock(side_effect=error),
            ), patch("self_improving_ai.dashboard.app.generate_meeting_brief") as offline:
                result = self.http.post("/api/briefings", json={**REQUEST, "mode": "agent"})
                self.assertEqual(result.status_code, status)
                offline.assert_not_called()
                with self.store.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM meeting_drafts").fetchone()[0], 0)

    def test_semantic_rejection_cannot_be_approved(self):
        brief = self.http.post("/api/briefings", json=REQUEST).json()
        with patch("self_improving_ai.dashboard.app.check_draft", new=AsyncMock(
            return_value={"verdict": "revise", "findings": []},
        )):
            response = self.http.post("/api/briefings/review", json={
                "brief": brief, "revision": 1, "expected_revision": 1, "decision": "approve"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.get(brief["id"])["status"], "draft")

    def test_interrupted_agent_run_is_inspectable_and_retry_resumes_review(self):
        from self_improving_ai.agents.briefing.runs import BriefRunStore

        brief = generate_meeting_brief(MeetingBriefRequest(**REQUEST))
        state = {"meeting_evidence": brief["workflow"]["evidence"],
                 "meeting_calculations": brief["workflow"]["calculations"]}
        runs = BriefRunStore(self.store.path)
        with patch("self_improving_ai.config.settings.briefing_discovery", "backend"), \
             patch("self_improving_ai.agents.briefing.runs.BriefRunStore", return_value=runs), \
             patch("self_improving_ai.agents.briefing.runtime.BriefRunStore", return_value=runs), \
             patch("self_improving_ai.agents.briefing.runtime.run_adk", new=AsyncMock(
                 return_value=(content_from_work(brief["workflow"]["work"]), state))) as generate, \
             patch("self_improving_ai.agents.briefing.runtime.semantic_check", new=AsyncMock(side_effect=[
                 ServerError(503, {"error": {"message": "Busy"}}), {"verdict": "pass", "findings": []}])):
            first = self.http.post("/api/briefings", json={**REQUEST, "mode": "agent"})
            self.assertEqual(first.status_code, 503)
            self.assertIn("Progress is saved", first.json()["detail"])
            run_id = first.headers["X-Briefing-Run-ID"]
            progress = self.http.get(f"/api/briefings/runs/{run_id}")
            self.assertEqual(progress.status_code, 200)
            self.assertEqual(progress.json()["status"], "interrupted")
            self.assertFalse(progress.json()["approved"])
            second = self.http.post("/api/briefings", json={**REQUEST, "mode": "agent"})
            self.assertEqual(second.status_code, 200, second.text)
            self.assertEqual(second.json()["workflow"]["run_id"], run_id)
            generate.assert_awaited_once()
            self.assertEqual(self.store.get(second.json()["id"])["status"], "draft")
