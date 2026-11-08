"""Regressions for prompt duplication, output contracts and transient failures."""

from copy import deepcopy
import json
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from self_improving_ai.agents.briefing.instructions import briefing_instructions
from self_improving_ai.agents.briefing.schemas import MeetingBriefRequest
from self_improving_ai.agents.briefing.service import generate_meeting_brief
from self_improving_ai.agents.briefing.contract import content_from_work, assemble_work, work_schema


def fixture():
    return generate_meeting_brief(MeetingBriefRequest(client_id="CLI-004",
        meeting_date="2026-11-11", meeting_time="14:00", focus="Home purchase funding"))


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        strategy = patch("self_improving_ai.config.settings.briefing_discovery", "backend")
        strategy.start()
        self.addCleanup(strategy.stop)

    def test_prompt_keeps_originals_but_excludes_execution_trace(self):
        brief = fixture()
        evidence = deepcopy(brief["workflow"]["evidence"])
        evidence["trace"].append({"tool": "debug", "result": "TRACE_MUST_STAY_SERVER_SIDE"})
        prompt = briefing_instructions(SimpleNamespace(state={"meeting_evidence": evidence,
            "meeting_calculations": brief["workflow"]["calculations"]}))
        self.assertNotIn("TRACE_MUST_STAY_SERVER_SIDE", prompt)
        self.assertIn("MINUTES-004", prompt)
        self.assertIn("EMAIL-004", prompt)

    def test_generation_contract_rejects_the_observed_unread_reference_and_empty_agenda(self):
        from self_improving_ai.agents.briefing.contract import work_schema

        brief = fixture()
        schema = work_schema(brief["workflow"]["evidence"], brief["workflow"]["calculations"])
        good = content_from_work(brief["workflow"]["work"])
        schema.model_validate(good)
        bad = deepcopy(good)
        bad["findings"][0]["source_ids"] = ["UNREAD-REFERENCE"]
        with self.assertRaises(ValidationError):
            schema.model_validate(bad)
        bad = deepcopy(good)
        priority = bad["sections"]["priorities"][0]
        priority["why"] = ""
        priority["question"] = ""
        with self.assertRaises(ValidationError):
            schema.model_validate(bad)
        # The actual generation schema exposes allowed IDs and required agenda fields.
        serialized = json.dumps(schema.model_json_schema())
        self.assertIn('"MINUTES-004"', serialized)

    def test_backend_owns_all_six_sections_and_reference_ids(self):
        brief = fixture()
        content = content_from_work(brief["workflow"]["work"])
        schema = work_schema(
            brief["workflow"]["evidence"], brief["workflow"]["calculations"])
        content["sections"] = dict(reversed(list(content["sections"].items())))
        result = assemble_work(schema.model_validate(content).model_dump())
        self.assertEqual([s["id"] for s in result["sections"]],
            ["overview", "changes", "portfolio", "priorities", "actions", "confirm"])
        claim_ids = {c["id"] for c in result["claims"]}
        self.assertEqual(len(claim_ids), len(result["claims"]))
        for section in result["sections"]:
            for item in section["items"]:
                self.assertTrue(set(item["claim_ids"]) <= claim_ids)
        del content["sections"]["confirm"]
        with self.assertRaises(ValidationError):
            schema.model_validate(content)

    def test_provider_client_has_bounded_call_timeout_and_transient_retry(self):
        from self_improving_ai.agents.briefing.model import create_model

        model = create_model("gemini-3.5-flash-lite")
        self.assertEqual(model.retry_options.attempts, 3)
        self.assertIn(503, model.retry_options.http_status_codes)
        self.assertNotIn(429, model.retry_options.http_status_codes)
        self.assertEqual(model.request_timeout_ms, 30000)

    def test_calculator_explains_supported_operations_and_real_field_paths(self):
        from self_improving_ai.tools.briefing.agent_tools import calculate_metrics

        context = SimpleNamespace(state={"meeting_evidence": fixture()["workflow"]["evidence"],
                                         "meeting_calculations": []})
        operand = {"source_id": "HOLDINGS", "field": "total_market_value", "currency": "USD"}
        self.assertEqual(calculate_metrics("SUM", [operand], context)["status"], "ok")
        invalid = calculate_metrics("ADD", [operand], context)
        self.assertEqual(invalid["allowed_operations"], ["sum", "difference", "ratio"])
        invalid = calculate_metrics("sum", [{**operand, "field": "market_value"}], context)
        self.assertIn("total_market_value", invalid["valid_numeric_fields"]["HOLDINGS"])

    def test_snapshot_total_is_sourced_and_completed_calculation_is_reused(self):
        from self_improving_ai.agents.briefing.preflight import prepare_snapshot_total
        from self_improving_ai.tools.briefing.context import prepare_context

        state = {"meeting_evidence": prepare_context("CLI-004"), "meeting_calculations": []}
        trace = []
        prepare_snapshot_total(state, trace)
        self.assertEqual(state["meeting_calculations"][0]["value"], "32000")
        self.assertEqual(trace[0]["origin"], "backend_preflight")
        self.assertIn("not household liquidity", state["meeting_metrics"]["scope"])
        prepare_snapshot_total(state, trace)
        self.assertEqual(len(trace), 2)
        self.assertEqual(len(state["meeting_calculations"]), 1)

    def test_reviewer_boundary_failure_overrides_inconsistent_overall_pass(self):
        from self_improving_ai.agents.briefing.runtime import semantic_check

        brief = fixture()
        result = {"verdict": "pass", "findings": [], "modality": {"verdict": "revise",
            "source_evidence": "We may buy in six months", "draft_evidence": "Confirmed six-month timeline",
            "reason": "Tentative intention was presented as confirmed"}, "funding_scope": {
            "verdict": "pass", "source_evidence": "External savings balance unknown",
            "draft_evidence": "Confirm external savings", "reason": "Unknown remains explicit"}}
        with patch("self_improving_ai.agents.briefing.runtime.run_adk",
                   new=AsyncMock(return_value=(result, {}))):
            report = asyncio.run(semantic_check(brief["workflow"]["work"],
                brief["workflow"]["evidence"], brief["workflow"]["calculations"], []))
        self.assertEqual(report["verdict"], "revise")
        self.assertIn("MODALITY", {f["code"] for f in report["findings"]})

    def test_interrupted_reviewer_resumes_the_same_draft_without_regeneration(self):
        from google.genai.errors import ServerError
        from self_improving_ai.agents.briefing.runtime import generate_agent_brief
        from self_improving_ai.agents.briefing.runs import BriefRunStore

        brief = fixture()
        state = {"meeting_evidence": brief["workflow"]["evidence"],
                 "meeting_calculations": brief["workflow"]["calculations"]}
        request = MeetingBriefRequest(client_id="CLI-004", meeting_date="2026-11-11",
            meeting_time="14:00", focus="Home purchase funding", mode="agent")
        with TemporaryDirectory() as directory:
            store = BriefRunStore(Path(directory) / "runs.db")
            with patch("self_improving_ai.agents.briefing.runtime.BriefRunStore", return_value=store), \
                 patch("self_improving_ai.agents.briefing.runtime.run_adk",
                       new=AsyncMock(return_value=(content_from_work(brief["workflow"]["work"]), state))) as generate, \
                 patch("self_improving_ai.agents.briefing.runtime.semantic_check", new=AsyncMock(side_effect=[
                     ServerError(503, {"error": {"message": "Busy"}}), {"verdict": "pass", "findings": []}])):
                with self.assertRaises(ServerError) as caught:
                    asyncio.run(generate_agent_brief(request))
                run_id = caught.exception.briefing_run_id
                interrupted = store.get(run_id)
                self.assertEqual(interrupted["status"], "interrupted")
                self.assertEqual(interrupted["snapshot"]["phase"], "review")
                self.assertFalse(interrupted["approved"])
                result = asyncio.run(generate_agent_brief(request))
            self.assertEqual(generate.await_count, 1)
            self.assertEqual(result["workflow"]["run_id"], run_id)
            self.assertEqual(store.get(run_id)["status"], "complete")
            self.assertTrue(any(e.get("event") == "resumed" for e in result["workflow"]["trace"]))

    def test_real_sdk_retries_only_failed_http_request_and_keeps_tool_results(self):
        import httpx
        from google import genai
        from self_improving_ai.agents.briefing.agent import briefing_agent
        from self_improving_ai.agents.briefing.contract import work_schema
        from self_improving_ai.agents.briefing.model import create_model
        from self_improving_ai.agents.briefing.runtime import run_adk

        bodies = []
        work = content_from_work(fixture()["workflow"]["work"])

        def respond(request):
            bodies.append(json.loads(request.content))
            if len(bodies) == 2:
                return httpx.Response(503, json={"error": {"code": 503, "message": "Busy", "status": "UNAVAILABLE"}})
            part = {"functionCall": {"name": "calculate_metrics", "args": {"operation": "sum",
                "operands": [{"source_id": "HOLDINGS", "field": "total_market_value", "currency": "USD"}]}}} \
                if len(bodies) == 1 else {"text": json.dumps(work)}
            return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [part]},
                "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20,
                "totalTokenCount": 30}})

        async def execute():
            client = genai.Client(api_key="local-test-not-a-secret", http_options={
                "async_client_args": {"transport": httpx.MockTransport(respond)}})
            model = create_model("gemini-3.5-flash-lite")
            model.client = client
            model.retry_options.initial_delay = 0.001
            evidence = deepcopy(fixture()["workflow"]["evidence"])
            agent = briefing_agent.clone(update={"model": model, "output_schema": work_schema(
                evidence, fixture()["workflow"]["calculations"])})
            trace = []
            try:
                result, state = await run_adk(agent, "Prepare meeting", {
                    "meeting_evidence": evidence, "meeting_calculations": []}, trace)
                return result, state, trace
            finally:
                await client.aio.aclose()
                client.close()

        result, state, trace = asyncio.run(execute())
        self.assertEqual(len(bodies), 3)
        self.assertEqual(bodies[1], bodies[2])
        self.assertEqual(len(state["meeting_calculations"]), 1)
        self.assertEqual(sum(e.get("event") == "tool_response" for e in trace), 1)
        self.assertEqual(result["change_status"], "changed")

    def test_native_writer_uses_compatible_wire_schema_and_strict_local_validation(self):
        import httpx
        from google import genai
        from self_improving_ai.agents.briefing.agent import briefing_agent
        from self_improving_ai.agents.briefing.model import create_model
        from self_improving_ai.agents.briefing.runtime import run_adk

        brief = fixture()
        content = content_from_work(brief["workflow"]["work"])
        bodies = []

        def respond(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [
                {"text": json.dumps(content)}]}, "finishReason": "STOP"}]})

        async def execute():
            client = genai.Client(api_key="local-test-not-a-secret", http_options={
                "async_client_args": {"transport": httpx.MockTransport(respond)}})
            model = create_model("gemini-3.5-flash-lite")
            model.client = client
            agent = briefing_agent.clone(update={"model": model, "tools": [], "output_schema": work_schema(
                brief["workflow"]["evidence"], brief["workflow"]["calculations"])})
            try:
                return await run_adk(agent, "Prepare content", {"meeting_content_mode": True}, [])
            finally:
                await client.aio.aclose()
                client.close()

        result, _ = asyncio.run(execute())
        self.assertEqual(result, content)
        config = bodies[0]["generationConfig"]
        self.assertIn("responseSchema", config)
        self.assertNotIn("additional_properties", json.dumps(config))
        self.assertNotIn("additionalProperties", json.dumps(config))
        self.assertEqual(len(config["responseSchema"]["properties"]["sections"]["required"]), 6)
