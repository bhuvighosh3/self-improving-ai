"""Behavior and integration tests for the evidence-driven briefing workflow."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.agents.briefing.checks import check_work
from self_improving_ai.agents.briefing.store import DraftStore
from self_improving_ai.agents.briefing.review import check_draft
from self_improving_ai.tools.briefing.context import prepare_context, read_source, search_sources
from self_improving_ai.tools.briefing.calculator import calculate


def demo(client="CLI-003"):
    return generate_meeting_brief(MeetingBriefRequest(client_id=client, meeting_date="2026-10-30",
                                  meeting_time="14:00", focus="Portfolio and goals review"))


class WorkflowTests(unittest.TestCase):
    def test_changed_unchanged_and_missing_are_distinct(self):
        for client, expected in [("CLI-004", "changed"), ("CLI-002", "unchanged"),
                                 ("CLI-003", "insufficient_information")]:
            brief = demo(client)
            self.assertEqual(brief["workflow"]["work"]["change_status"], expected)
            self.assertEqual(brief["workflow"]["quality"]["verdict"], "pass")
            self.assertTrue(any(i["id"] == "workflow-routine" for i in brief["sections"][3]["items"]))
        changed = demo("CLI-004")
        self.assertIn("Possibly six months", json.dumps(changed["sections"]))
        self.assertIn("MINUTES-004", {s["id"] for s in changed["sources"]})

    def test_missing_cannot_be_relabelled_unchanged(self):
        brief = demo()
        workflow = brief["workflow"]
        work = deepcopy(workflow["work"])
        work["change_status"] = "unchanged"
        report = check_work(work, workflow["evidence"], [])
        self.assertIn("MISSING_IS_NOT_UNCHANGED", {f["code"] for f in report["findings"]})

    def test_unread_sources_and_missing_calculations_are_rejected(self):
        brief = demo()
        workflow = brief["workflow"]
        work = deepcopy(workflow["work"])
        work["claims"][0].update(source_ids=["INVENTED"], kind="calculation", calculation_ids=[])
        codes = {f["code"] for f in check_work(work, workflow["evidence"], [])["findings"]}
        self.assertTrue({"UNKNOWN_SOURCE", "MISSING_CALCULATION"} <= codes)

    def test_cross_client_and_post_cutoff_sources_are_unavailable(self):
        self.assertEqual(read_source("CLI-003", "EMAIL-004")["status"], "denied")
        with TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "clients").mkdir()
            (path / "clients/meeting_context.json").write_text(json.dumps({
                "data_as_of": "2026-10-27", "holdings_as_of": "2026-10-24",
                "households": {"C": {"previous_meeting": "2026-09-01"}}}))
            (path / "clients/meeting_sources.json").write_text(json.dumps([
                {"id": "LATE", "client_id": "C", "kind": "email", "event_at": "2026-10-01",
                 "recorded_at": "2026-10-28", "title": "Late", "text": "Backdated"}]))
            with patch("self_improving_ai.tools.briefing.context.DATA_DIR", path):
                self.assertEqual(search_sources("C")["status"], "no_results")
                self.assertEqual(read_source("C", "LATE")["status"], "denied")

    def test_decimal_calculator_checks_scope_currency_and_real_inputs(self):
        sources = [{"id": "ACCOUNT", "currency": "USD", "content": '{"cash":50000,"stock":130000,"total":650000}'}]
        operands = [{"source_id": "ACCOUNT", "field": field, "currency": "USD"}
                    for field in ("stock", "total")]
        self.assertEqual(calculate("ratio", operands, sources)["value"], "0.2")
        operands[1]["currency"] = "EUR"
        with self.assertRaises(ValueError):
            calculate("sum", operands, sources)
        operands[1]["currency"] = "USD"
        sources[0]["content"] = '{"stock":130000,"total":0}'
        with self.assertRaises(ValueError):
            calculate("ratio", operands, sources)

    def test_tampered_calculation_is_detected(self):
        brief = demo()
        workflow = brief["workflow"]
        operands = [{"source_id": "HOLDINGS", "field": "total_market_value", "currency": "USD"}]
        result = calculate("sum", operands, workflow["evidence"]["sources"])
        result["value"] = "999999"
        self.assertIn("CALCULATION", {f["code"] for f in check_work(
            workflow["work"], workflow["evidence"], [result])["findings"]})

    def test_review_uses_retained_sources_and_rejects_changed_identity(self):
        original = demo()
        submitted = deepcopy(original)
        submitted["workflow"]["evidence"]["sources"] = []
        report = asyncio.run(check_draft(submitted, original))
        self.assertEqual(report["verdict"], "pass")
        submitted["client_id"] = "CLI-004"
        with self.assertRaises(ValueError):
            asyncio.run(check_draft(submitted, original))

    def test_server_versions_prevent_stale_approval(self):
        with TemporaryDirectory() as directory:
            store = DraftStore(Path(directory) / "drafts.db")
            brief = demo()
            store.create(brief)
            changed = deepcopy(brief)
            changed["sections"][0]["items"][0]["text"] = "Advisor edit"
            with self.assertRaises(ValueError):
                store.review(changed, 1, 1, "approve", "")
            store.review(changed, 2, 1, "revise", "Check revised wording")
            with self.assertRaises(ValueError):
                store.review(brief, 1, 1, "approve", "")
            self.assertEqual(store.get(brief["id"])["status"], "revise")

    def test_runtime_retries_failed_quality_without_silent_demo_fallback(self):
        from self_improving_ai.agents.briefing.runtime import generate_agent_brief

        original = demo()
        work = original["workflow"]["work"]
        state = {"meeting_calculations": original["workflow"]["calculations"],
                 "meeting_evidence": original["workflow"]["evidence"]}
        reviewer = AsyncMock(side_effect=[{"verdict": "revise", "findings": [
            {"code": "TEST", "reason": "Test injection", "severity": "blocking", "location": "claims"}]},
            {"verdict": "pass", "findings": []}])
        with patch("self_improving_ai.agents.briefing.runtime.prepare_context", return_value=original["workflow"]["evidence"]), \
             patch("self_improving_ai.agents.briefing.runtime.run_adk", new=AsyncMock(return_value=(work, state))) as run, \
             patch("self_improving_ai.agents.briefing.runtime.semantic_check", new=reviewer):
            result = asyncio.run(generate_agent_brief(MeetingBriefRequest(client_id="CLI-003",
                meeting_date="2026-10-30", meeting_time="14:00", focus="Review goals", mode="agent")))
        self.assertEqual(run.await_count, 2)
        self.assertEqual(result["mode"], "agent")
        self.assertEqual(len(result["workflow"]["quality_history"]), 2)

    def test_actual_adk_runner_accepts_schema_and_tools_without_network(self):
        from google.adk.models.base_llm import BaseLlm
        from google.adk.models.llm_response import LlmResponse
        from google.genai import types
        from self_improving_ai.agents.briefing.agent import briefing_agent
        from self_improving_ai.agents.briefing.runtime import run_adk

        work = demo()["workflow"]["work"]

        class LocalModel(BaseLlm):
            turn: int = 0

            async def generate_content_async(self, llm_request, stream=False):
                self.turn += 1
                if self.turn == 1:
                    part = types.Part(function_call=types.FunctionCall(name="calculate_metrics", args={
                        "operation": "sum", "operands": [{"source_id": "HOLDINGS",
                        "field": "total_market_value", "currency": "USD"}]}))
                else:
                    part = types.Part(text=json.dumps(work))
                yield LlmResponse(content=types.Content(role="model", parts=[part]))

        agent = briefing_agent.clone(update={"model": LocalModel(model="offline-test")})
        trace = []
        result, state = asyncio.run(run_adk(agent, "Prepare this meeting", {
            "meeting_evidence": prepare_context("CLI-003"), "meeting_calculations": []}, trace))
        self.assertEqual(result["change_status"], "insufficient_information")
        self.assertIn("briefing_result", state)
        self.assertEqual(len(state["meeting_calculations"]), 1)
        self.assertTrue(any(e.get("event") == "tool_response" for e in trace))


if __name__ == "__main__":
    unittest.main()
