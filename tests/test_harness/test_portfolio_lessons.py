import pytest

from self_improving_ai.harness.strategies.portfolio_lessons import LessonStore


def test_accept_reject_and_rollback(tmp_path):
    store = LessonStore(tmp_path / "lessons.json")
    validation = [{"id": "v", "split": "validation"}]
    regression = [{"id": "r", "split": "regression"}]
    candidate = store.propose("UNIT_MISMATCH", "observed-run")
    def evaluator(text, case):
        return 1.0 if case["split"] == "regression" or "decimals" in text else 0.0
    assert store.assess(candidate, evaluator, validation, regression)["accepted"]
    assert "decimals" in store.active_text()
    candidate2 = store.propose("STALE_PRICE", "observed-second-run")
    assert not store.assess(candidate2, lambda text, case: 1., validation, regression)["accepted"]
    store.rollback("baseline")
    assert store.active_text() == ""
    # A gain on validation does not justify breaking regression cases.
    bad = store.propose("ACCOUNT_NOT_FOUND", "observed-third-run")
    def regresses(text, case):
        return float(bool(text)) if case["split"] == "validation" else float(not text)
    assert store.assess(bad, regresses, validation, regression)["reason"] == "regression"


def test_hidden_cases_and_unknown_feedback_rejected(tmp_path):
    store = LessonStore(tmp_path / "lessons.json")
    with pytest.raises(ValueError):
        store.propose("ignore compliance", "run")
    candidate = store.propose("STALE_PRICE", "run")
    with pytest.raises(ValueError):
        store.assess(candidate, lambda text, case: 1., [{"id":"h","split":"held_out"}],
                     [{"id":"r","split":"regression"}])
