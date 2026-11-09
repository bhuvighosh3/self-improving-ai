"""Check confirmation and shared generation across the two meeting entry points."""

import asyncio
import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.dashboard.app import ChatRequest, chat
from self_improving_ai.dashboard.meeting_requests import collect_meeting_details, is_meeting_request

from self_improving_ai.client_store import load_households
CLIENTS = load_households()


class CopilotMeetingTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = DraftStore(Path(directory.name) / "drafts.db")
        patcher = patch("self_improving_ai.dashboard.app.DraftStore", return_value=store)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_client_request_uses_calendar_details_without_a_confirmation_form(self):
        details = collect_meeting_details(
            "Prepare a meeting for Wei Chen tomorrow at 2pm — ARKK tax-loss harvesting",
            CLIENTS, today=date(2026, 10, 28),
        )
        self.assertEqual(details, {"client_id": "CLI-003", "meeting_date": "2026-10-29",
                                  "meeting_time": "14:00", "focus": "ARKK tax-loss harvesting"})
        event = {"id": "CHEN-MEETING", "client_id": "CLI-003", "date": "2026-11-18", "start_time": "11:00",
                 "title": "Chen discussion", "notes": "ARKK tax-loss harvesting", "type": "portfolio_review"}
        brief = generate_meeting_brief(MeetingBriefRequest(client_id="CLI-003", meeting_date=event["date"],
            meeting_time=event["start_time"], focus=event["notes"]))
        with patch("self_improving_ai.dashboard.app._meeting_workspace", return_value={
            "now": "2026-11-11T15:00:00-05:00", "mode": "agent", "events": [event]}), patch(
            "self_improving_ai.dashboard.app.create_meeting_brief", new=AsyncMock(return_value=brief)) as generate:
            response = asyncio.run(chat(ChatRequest(message="Prepare a meeting for Wei Chen")))
            self.assertNotIn("meeting_details", response)
            self.assertEqual(response["brief"], brief)
            self.assertEqual(generate.await_args.args[0].calendar_event_id, event["id"])
            self.assertEqual(generate.await_args.args[0].mode, "agent")
            generate.assert_awaited_once()

    def test_missing_and_ambiguous_details_are_not_invented(self):
        details = collect_meeting_details("Prepare my meeting", CLIENTS)
        self.assertTrue(all(value == "" for value in details.values()))
        for message, selected in [("Prepare a meeting for Chen and Garcia", None),
                                  ("Prepare a meeting for Chen", "CLI-001")]:
            self.assertEqual(collect_meeting_details(message, CLIENTS, selected)["client_id"], "")

    def test_short_preparation_commands_cover_clients_without_capturing_financial_tasks(self):
        for client in CLIENTS:
            for prefix in ("prepare for", "prep"):
                message = f"{prefix} {client['profile']['name']}"
                with self.subTest(message=message):
                    self.assertTrue(is_meeting_request(message, CLIENTS))
        for message in ("Prepare for retirement spending", "Prepare tax estimates for Patel"):
            self.assertFalse(is_meeting_request(message, CLIENTS))

    def test_selected_client_and_supported_clock_formats(self):
        details = collect_meeting_details("Meeting today at 09:30, focus on college funding", CLIENTS,
                                          "CLI-001", today=date(2026, 10, 28))
        self.assertEqual(details["client_id"], "CLI-001")
        self.assertEqual(details["meeting_time"], "09:30")
        self.assertEqual(details["meeting_date"], "2026-10-28")
        self.assertEqual(details["focus"], "college funding")
        self.assertEqual(collect_meeting_details("Meeting at 12am", CLIENTS)["meeting_time"], "00:00")
        self.assertEqual(collect_meeting_details("Meeting at 12pm", CLIENTS)["meeting_time"], "12:00")

    def test_confirmation_uses_the_existing_service_once_and_returns_the_exact_brief(self):
        meeting = MeetingBriefRequest(client_id="CLI-003", meeting_date="2026-10-29",
                                      meeting_time="14:00", focus="ARKK tax-loss harvesting")
        expected = generate_meeting_brief(meeting)
        with patch("self_improving_ai.dashboard.app.generate_meeting_brief", return_value=expected) as generate:
            response = asyncio.run(chat(ChatRequest(message="Confirmed meeting", meeting=meeting)))
        generate.assert_called_once_with(meeting)
        self.assertEqual(response["brief"], expected)
        self.assertIn("$17,500", response["response"])
        self.assertEqual(response["steps"][0]["tools_called"], expected["tools_called"])

    def test_bad_confirmed_client_uses_the_same_error_handling(self):
        meeting = MeetingBriefRequest(client_id="unknown", meeting_date="2026-10-29",
                                      meeting_time="14:00", focus="Portfolio review")
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(chat(ChatRequest(message="Confirmed meeting", meeting=meeting)))
        self.assertEqual(caught.exception.status_code, 404)

    def test_non_meeting_requests_keep_the_existing_flow(self):
        from google.adk.events import Event
        from google.genai import types

        async def events(**kwargs):
            yield Event(author="request_orchestrator", content=types.Content(
                role="model", parts=[types.Part(text="Live C response")]))

        with patch("self_improving_ai.dashboard.app._runner.run_async", side_effect=events) as run:
            response = asyncio.run(chat(ChatRequest(message="How much tax if we sold AAPL for Garcia?")))
        run.assert_called_once()
        self.assertEqual(response["intent"], "gemini")
        self.assertEqual(response["response"], "Live C response")
        self.assertNotIn("meeting_details", response)

    def test_preparation_handoff_is_narrow_and_includes_existing_hint(self):
        for message in ["Get me ready for my 2pm with the Garcias", "Meeting briefing for Chen",
                        "Prepare an annual review for Okafor"]:
            with self.subTest(message=message):
                self.assertTrue(is_meeting_request(message))
        for message in ["Quick summary of Thompson Trust", "What happened at the last meeting?",
                        "Review Garcia's portfolio risk", "Get ready cash balances for Garcia"]:
            with self.subTest(message=message):
                self.assertFalse(is_meeting_request(message))


if __name__ == "__main__":
    unittest.main()
