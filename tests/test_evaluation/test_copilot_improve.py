"""Golden-set improvement loop: lesson filtering, gate decisions and the cycle driver (offline)."""

import asyncio

from self_improving_ai.agents.orchestrator.memory import OrchestratorMemory, orchestrator_state_for, use_memory
from self_improving_ai.evaluation.copilot import improve
from self_improving_ai.evaluation.copilot.improve import ArmResult, apply_lessons, gate

DEV = [f"G{i:02d}" for i in range(1, 11)]
HOLD = [f"V{i:02d}" for i in range(1, 11)]


def arm(label, passing: set, calls=2, forbidden=frozenset(), repeats=2):
    runs = []
    for _ in range(repeats):
        runs.append([{"case_id": c, "passed": c in passing, "calls": ["t"] * calls, "notes": [], "missing_facts": [],
                      "answer": "", "stages": {"forbidden": 0.0 if c in forbidden else 1.0, "tools": 1.0, "args": 1.0,
                                               "order": 1.0, "calls": 1.0, "facts": 1.0}}
                     for c in DEV + HOLD])
    return ArmResult(label, runs)


def test_lessons_about_live_tools_are_kept_and_scrubbed():
    mem, applied = apply_lessons(OrchestratorMemory(), [
        {"kind": "tool_note", "tool": "get_upcoming_events", "note": "Pass client_id for the Garcias (CLI-001)."},
        {"kind": "tool_note", "tool": "made_up_tool", "note": "never seen"},
        {"kind": "template", "intent": "meeting_prep", "steps": [
            {"tool": "get_upcoming_events", "args": {"client_id": "CLI-001"}},
            {"tool": "meeting_briefing_agent", "args": {}, "depends_on": [1]}]},
        {"kind": "intent", "example": "prepare a meeting brief", "intent": "clarify_client",
         "note": "Ask which client before doing anything."},
        {"kind": "tool_note", "tool": "get_client_info", "note": "Tell clients not to worry."},
    ])
    assert len(applied) == 3 and len(mem.tool_notes) == 1
    assert "Garcia" not in mem.tool_notes[0].note and "CLI-001" not in mem.tool_notes[0].note
    assert mem.plan_templates["meeting_prep"].steps[0]["args"]["client_id"] == "<client_id>"


def test_live_orchestrator_renders_candidate_memory():
    mem, _ = apply_lessons(OrchestratorMemory(), [
        {"kind": "tool_note", "tool": "search_tool_catalog", "note": "Do not use it to find clients."}])
    use_memory(mem)
    try:
        assert "search_tool_catalog: Do not use it to find clients." in orchestrator_state_for("anything")["tool_notes"]
    finally:
        use_memory(None)


def test_gate_adopts_clear_gain_and_rejects_regression():
    incumbent = arm("inc", set(DEV[:5] + HOLD[:5]))
    better = arm("cand", set(DEV + HOLD))
    assert gate(incumbent, better, DEV, HOLD).adopt
    broke = arm("cand2", set(DEV[1:] + HOLD))  # fixes holdout but breaks G01, which always passed
    d = gate(incumbent, broke, DEV, HOLD)
    assert not d.adopt and d.details["regressed_cases"] == ["G01"]


def test_gate_rejects_more_calls_and_new_forbidden_calls():
    incumbent = arm("inc", set(DEV[:5] + HOLD[:5]))
    assert not gate(incumbent, arm("c", set(DEV + HOLD), calls=4), DEV, HOLD).adopt
    assert not gate(incumbent, arm("c", set(DEV + HOLD), forbidden={"V01"}), DEV, HOLD).adopt


def test_cycle_driver_offline(tmp_path, monkeypatch):
    cases = [{"id": c, "split": "dev" if c.startswith("G") else "holdout", "question": c,
              "plan": {"steps": [], "order": "any"}} for c in DEV + HOLD]
    results = {"baseline": set(DEV[:3] + HOLD[:3]), "hand_fixes": set(DEV[:5] + HOLD[:5]),
               "learner_cycle_1": set(DEV + HOLD)}

    async def fake_eval(label, cases, out_dir, repeats, concurrency, timeout_s, runner):
        return arm(label, results[label])

    monkeypatch.setattr(improve, "evaluate_arm", fake_eval)
    monkeypatch.setattr(improve, "propose_lessons", lambda failed, by_id, memory: [
        {"kind": "tool_note", "tool": "get_upcoming_events", "note": "Always pass client_id."}])
    monkeypatch.setattr("self_improving_ai.evaluation.copilot.runner.build_runner", lambda: object())
    # The real agent module builds ADK agents (and Firestore clients) on import; the loop only needs the switch.
    import sys
    import types
    fake_agent = types.ModuleType("self_improving_ai.agents.orchestrator.agent")
    fake_agent.set_context_fixes = lambda enabled: None
    monkeypatch.setitem(sys.modules, "self_improving_ai.agents.orchestrator.agent", fake_agent)
    log = asyncio.run(improve.run_improvement(cases, tmp_path, repeats=2, cycles=1))
    assert log["arms"]["baseline"]["holdout_pass"] == 0.3
    assert log["cycles"][0]["gate"]["adopt"] and log["final"] == "learner_cycle_1"
    assert (tmp_path / "report.md").exists() and (tmp_path / "memory").exists()
