"""Behavior checks for the synthetic meeting preparation workflow."""

import asyncio
import unittest

from fastapi import HTTPException

from self_improving_ai.agents.briefing.pdf import render_brief_pdf
from self_improving_ai.agents.briefing.schemas import BriefExportRequest, MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.dashboard.app import create_meeting_brief


def request(client_id="CLI-003", focus="ARKK tax-loss harvesting", **overrides):
    return MeetingBriefRequest(**{
        "client_id": client_id, "meeting_date": "2026-10-28", "meeting_time": "14:00",
        "focus": focus, **overrides,
    })


class MeetingBriefTests(unittest.TestCase):
    def test_chen_uses_correct_position_and_prioritizes_the_requested_news(self):
        brief = generate_meeting_brief(request())
        portfolio = brief["sections"][2]["items"]
        self.assertIn("unrealized loss $17,500", portfolio[1]["text"])
        self.assertIn("$312,700", portfolio[0]["text"])
        self.assertEqual(brief["news"][0]["id"], "N008")
        self.assertIn("tax", brief["sections"][3]["items"][0]["text"].lower())
        self.assertTrue(any("planning horizon" in item["title"] for item in brief["sections"][5]["items"]))

    def test_every_claim_reference_resolves_and_stays_with_the_selected_household(self):
        for client_id in ["CLI-001", "CLI-002", "CLI-003", "CLI-004", "CLI-005"]:
            with self.subTest(client_id=client_id):
                brief = generate_meeting_brief(request(client_id, "Portfolio and goals review"))
                source_ids = {source["id"] for source in brief["sources"]}
                self.assertEqual(len(brief["sections"]), 6)
                for section in brief["sections"]:
                    for item in section["items"]:
                        self.assertTrue(set(item["source_ids"]) <= source_ids)
                self.assertTrue(all(news["date"] <= brief["data_as_of"] for news in brief["news"]))
                self.assertEqual(brief["client_id"], client_id)
                if client_id != "CLI-003":
                    self.assertNotIn("Wei", str(brief["sections"]))

    def test_missing_state_is_explicit_and_unknown_focus_does_not_invent_a_client_request(self):
        brief = generate_meeting_brief(request("CLI-004", "Charitable gifting"))
        self.assertTrue(any("residence is missing" in item["title"] for item in brief["sections"][5]["items"]))
        self.assertEqual(brief["sections"][3]["items"][0]["source_ids"], [])

    def test_bad_client_and_unavailable_historical_snapshot_return_actionable_errors(self):
        for req, status in [(request("missing"), 404), (request(meeting_date="2026-10-01"), 422)]:
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(create_meeting_brief(req))
            self.assertEqual(caught.exception.status_code, status)

    def test_export_preserves_current_edits_and_rejects_missing_sources(self):
        brief = generate_meeting_brief(request())
        brief["sections"][0]["items"][0]["text"] = "Advisor confirmed the meeting focus."
        export = BriefExportRequest(brief=brief, edited=True, revision=2)
        pdf = render_brief_pdf(export)
        self.assertTrue(pdf.startswith(b"%PDF"))
        export.brief.sections[0].items[0].source_ids = ["UNKNOWN"]
        with self.assertRaises(ValueError):
            render_brief_pdf(export)


if __name__ == "__main__":
    unittest.main()
