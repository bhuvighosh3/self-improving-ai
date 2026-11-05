"""Evaluator references are passed only to the evaluator, not production tools."""

import unittest

from self_improving_ai.evaluation.meeting_brief import evaluate
from tests.test_agents.test_brief_workflow import demo


class EvaluationTests(unittest.TestCase):
    def test_separate_result_process_and_unscored_initiative(self):
        brief = demo("CLI-004")
        report = evaluate(brief, {"client_id": "CLI-004", "required_text": ["Possibly six months"],
            "forbidden_text": ["proven household shortfall"], "required_tools": ["read_source"]},
            [{"question": "Why funding first?", "new_tool_events": [{"tool": "read_source"}]}])
        self.assertEqual(report["dimensions"]["objective_duties"], "pass")
        self.assertIsNone(report["total_score"])
        self.assertTrue(report["follow_ups"][0]["new_work"])
        self.assertTrue(report["initiative_candidates"])
        self.assertTrue(all(x["decision"] == "pending_expert_review" for x in report["initiative_candidates"]))

    def test_unobserved_work_and_wrong_client_fail(self):
        report = evaluate(demo(), {"client_id": "DIFFERENT", "required_tools": ["invented_tool"]})
        self.assertEqual(report["dimensions"]["objective_duties"], "fail")
        self.assertEqual({e["stage"] for e in report["errors"]}, {"identity", "retrieval"})
