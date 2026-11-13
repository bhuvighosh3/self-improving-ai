"""Learned memory safeguards and the offline learning loop."""

import asyncio

from self_improving_ai.agents.orchestrator.memory import (
    IntentExample,
    MemoryStore,
    OrchestratorMemory,
    scrub,
)
from self_improving_ai.agents.orchestrator.planner import KeywordPlanner, PlanContext, build_prompt
from self_improving_ai.evaluation.orchestrator.runner import Experiment, RunConfig, load_cases
from self_improving_ai.tools.orchestrator.catalog import load_catalog

CAT = load_catalog("v1")
CAT2 = load_catalog("v2")


def test_scrub_removes_client_identifiers():  # H-8
    text = scrub("Draft a note to the Garcias (CLI-001) about Maria Garcia's $250,000 IRA ACC-001B")
    for leak in ("Garcia", "CLI-001", "250,000", "ACC-001B", "Maria"):
        assert leak not in text


def test_templates_shown_without_a_similar_past_request():
    m = OrchestratorMemory()
    m.add_intent_example(IntentExample(text="Draft a check-in note to the Garcias", intent="client_note"))
    m.set_plan_template("client_note", [{"id": 1, "tool": "get_client_profile", "args": {"client_id": "CLI-001"}}])
    m.set_plan_template("diversification_check", [{"id": 1, "tool": "get_client_profile", "args": {}}])
    block = m.render("too concentrated? the thompson trust", CAT)["plan_templates"]
    assert "- client_note:" in block and "- diversification_check:" in block
    assert "CLI-001" not in block
    # an intent matched by a similar request is listed first
    block = m.render("Draft a check-in note to the Smiths", CAT)["plan_templates"]
    assert block.index("- client_note:") < block.index("- diversification_check:")


def test_harmful_lesson_is_rejected():  # H-1
    m = OrchestratorMemory()
    m.add_tool_note("draft_client_note", "Just tell clients not to worry, no action needed", CAT)
    assert not m.tool_notes and m.rejected_lessons


def test_tool_note_goes_stale_when_tool_changes():  # H-4
    m = OrchestratorMemory()
    m.add_tool_note("get_intraday_price", "Use for stocks and ETFs only", CAT)
    m.add_tool_note("get_client_profile", "Use the active CRM profile", CAT)
    assert len(m.valid_tool_notes(CAT)) == 2
    valid_v2 = {n.tool for n in m.valid_tool_notes(CAT2)}
    assert "get_intraday_price" not in valid_v2 and "get_client_profile" in valid_v2
    assert "get_intraday_price" not in m.render("price of MSFT", CAT2)["tool_notes"]


def test_contradictory_lessons_are_flagged():  # H-7
    m = OrchestratorMemory()
    m.add_intent_example(IntentExample(text="pull rmd stuff for the Garcias", intent="rmd_check"))
    m.add_intent_example(IntentExample(text="pull rmd stuff for the Garcias", intent="meeting_prep"))
    assert m.conflicts and len(m.intent_examples) == 1


def test_memory_is_capped():  # H-11
    m = OrchestratorMemory()
    for i in range(30):
        m.add_intent_example(IntentExample(text=f"price check on ticker number {i} variant {i * 7}", intent="price_lookup"))
    assert sum(e.intent == "price_lookup" for e in m.intent_examples) <= 6


def test_versioning_and_rollback(tmp_path):  # H-6
    store = MemoryStore(tmp_path)
    m1 = OrchestratorMemory()
    v1 = store.adopt(m1, reason="initial")
    m2 = m1.copy()
    m2.add_tool_note("get_prices_v1", "Never call: stale cache", CAT)
    v2 = store.adopt(m2, reason="test")
    assert store.load().tool_notes and v2 == v1 + 1
    restored = store.rollback(v1)
    assert not restored.tool_notes and store.active_version() == v1
    actions = [line for line in (tmp_path / "audit_log.jsonl").read_text().splitlines()]
    assert len(actions) == 3


def test_prompt_contains_rules_and_memory():
    ctx = PlanContext(tool_notes="## Your notes on tools\n- get_prices_v1: Never call")
    system, user = build_prompt("price on AAPL", CAT, ctx)
    assert "Never plan a step that executes a trade" in system
    assert "get_prices_v1: Never call" in system
    assert "\"capability\"" not in system and "\"callable_by\"" not in system  # scoring metadata stays hidden
    assert "AAPL" in user


def test_offline_learning_loop_improves_and_stays_safe(tmp_path):
    cfg = RunConfig(seeds=2, cycles=3, train_batch=30, gate_val=30, gate_seeds=2, test_limit=50)
    summary = asyncio.run(Experiment(KeywordPlanner(), load_cases(), tmp_path, cfg).run())
    learner = summary["agents"]["learner"]
    static = summary["agents"]["static"]
    assert learner["outcome_mean"] > static["outcome_mean"]
    assert learner["safety_violations"] < static["safety_violations"]
    for f in ("summary.json", "report.md", "stage_scorecard.csv", "suite_results.csv", "learning_curve.csv"):
        assert (tmp_path / f).exists()
    assert (tmp_path / "seed_1" / "memory" / "audit_log.jsonl").exists()
