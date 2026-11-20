"""The completion checker must see the end of long answers, or complete answers look cut off."""

from self_improving_ai.agents.orchestrator.checker import _CHECKER_PROMPT, clip_for_checker


def test_short_answers_are_unchanged():
    assert clip_for_checker("All done.") == "All done."


def test_long_answers_keep_their_ending():
    text = "start " + "x" * 9000 + " final sentence."
    clipped = clip_for_checker(text)
    assert clipped.startswith("start ") and clipped.endswith(" final sentence.")
    assert "characters omitted" in clipped and len(clipped) < 6100


def test_prompt_accepts_clarification_and_missing_clients():
    assert "asks the advisor for it" in _CHECKER_PROMPT
    assert "does not exist and the response says so" in _CHECKER_PROMPT
