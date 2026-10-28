"""Check confirmation and shared generation across the two meeting entry points."""

import asyncio
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.dashboard.app import ChatRequest, chat
from self_improving_ai.dashboard.meeting_requests import collect_meeting_details

CLIENTS = json.loads((Path(__file__).resolve().parents[2] / "src/self_improving_ai/data/clients/households.json").read_text())


class CopilotMeetingTests(unittest.TestCase):
    def test_explicit_details_are_suggestions_until_the_advisor_confirms(self):
        details = collect_meeting_details(
            "Prepare a meeting for Wei Chen tomorrow at 2pm — ARKK tax-loss harvesting",
            CLIENTS, today=date(2026, 10, 28),
        )
        self.assertEqual(details, {"client_id": "CLI-003", "meeting_date": "2026-10-29",
                                  "meeting_time": "14:00", "focus": "ARKK tax-loss harvesting"})
        with patch("self_improving_ai.dashboard.app.generate_meeting_brief") as generate:
            response = asyncio.run(chat(ChatRequest(message="Prepare a meeting for Wei Chen")))
            self.assertIn("meeting_details", response)
            self.assertNotIn("brief", response)
            generate.assert_not_called()

    def test_missing_and_ambiguous_details_are_not_invented(self):
        details = collect_meeting_details("Prepare my meeting", CLIENTS)
        self.assertTrue(all(value == "" for value in details.values()))
        for message, selected in [("Prepare a meeting for Chen and Garcia", None),
                                  ("Prepare a meeting for Chen", "CLI-001")]:
            self.assertEqual(collect_meeting_details(message, CLIENTS, selected)["client_id"], "")

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
        response = asyncio.run(chat(ChatRequest(message="How much tax if we sold AAPL for Garcia?")))
        self.assertEqual(response["intent"], "tax_estimation")
        self.assertNotIn("meeting_details", response)


if __name__ == "__main__":
    unittest.main()
