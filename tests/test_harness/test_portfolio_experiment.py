import json

import pytest

from self_improving_ai.harness.portfolio_experiment import assess_candidate
from self_improving_ai.harness.strategies.portfolio_lessons import LessonStore
from tests.test_agents.test_portfolio_agent import ScriptedModel

CASES=[
    {"id":"v-allocation","split":"validation","question":"CLI-001 allocation",
     "steps":[{"tool":"calculate_allocation_drift","arguments":{"client_id":"CLI-001"},
               "checks":[{"path":["total_market_value"],"value":146750},{"path":["currency"],"value":"USD"}]}]},
    {"id":"r-holdings","split":"regression","question":"CLI-001 holdings",
     "steps":[{"tool":"get_holdings","arguments":{"client_id":"CLI-001"},
               "checks":[{"path":["total_market_value"],"value":146750}]}]}
]


@pytest.mark.asyncio
async def test_real_dispatch_paired_gate_records_no_gain_and_rejects(tmp_path):
    store=LessonStore(tmp_path/"lessons.json")
    candidate=store.propose("UNIT_MISMATCH","unit-test-observation")
    def factory(case,seed):
        item=case["steps"][0]
        return ScriptedModel(tool_name=item["tool"],arguments=item["arguments"])
    report=await assess_candidate(store,candidate,CASES,tmp_path/"experiment",model_factory=factory)
    assert not report["gate"]["accepted"]
    assert report["gate"]["reason"]=="no_validation_gain"
    assert len(report["records"])==10
    assert len(list((tmp_path/"experiment/runs").glob("*.json")))==20
    assert report["mode"]=="adk_scripted_transport_test"
    assert store.read()["active"]=="baseline"
    assert json.loads((tmp_path/"experiment/paired_evidence.json").read_text(encoding="utf-8"))["records"]
    assert report["gate"]["evaluation_evidence"]["sha256"]


@pytest.mark.asyncio
async def test_hidden_suite_is_rejected_before_any_calls(tmp_path):
    store=LessonStore(tmp_path/"lessons.json")
    candidate=store.propose("UNIT_MISMATCH","test-run")
    with pytest.raises(ValueError,match="validation"):
        await assess_candidate(store,candidate,[{**CASES[0],"split":"held_out"}],tmp_path)


def test_candidate_cannot_be_modified_or_retried_until_it_passes(tmp_path):
    store=LessonStore(tmp_path/"lessons.json")
    candidate=store.propose("UNIT_MISMATCH","test-run")
    groups=([{"id":"v","split":"validation"}],[{"id":"r","split":"regression"}])
    with pytest.raises(ValueError,match="modified"):
        store.assess({**candidate,"text":"Completely different instruction"},lambda *_:1.,*groups)
    store.assess(candidate,lambda *_:1.,*groups)
    with pytest.raises(ValueError,match="already evaluated"):
        store.assess(candidate,lambda *_:1.,*groups)

