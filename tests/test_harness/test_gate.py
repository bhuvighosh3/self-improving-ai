"""Adoption gate: must reproduce the Test Suite spreadsheet's Adoption Gate sheet."""

import pytest

from self_improving_ai.harness.gate import decide, paired_t_test

CURRENT = [0.72, 0.70, 0.74, 0.71, 0.73]
CANDIDATE_A = [0.76, 0.75, 0.77, 0.74, 0.78]
CANDIDATE_B = [0.78, 0.71, 0.73, 0.70, 0.74]


def test_candidate_a_matches_spreadsheet():
    d = decide(CURRENT, CANDIDATE_A, regressions=0, safety_flags=0, cost_ratio=1.1)
    assert d.adopt
    assert d.mean_gain_pp == pytest.approx(4.0)
    assert d.t_stat == pytest.approx(8.94427191, rel=1e-6)
    assert d.p_value == pytest.approx(0.000864211, rel=1e-5)


def test_candidate_b_matches_spreadsheet():
    d = decide(CURRENT, CANDIDATE_B, regressions=3, safety_flags=0, cost_ratio=1.3)
    assert not d.adopt
    assert d.p_value == pytest.approx(0.401787663, rel=1e-5)
    assert not d.checks["significant"]
    assert not d.checks["no_regressions"]
    assert not d.checks["cost_within_limit"]


def test_one_seed_spike_is_not_adopted():
    # H-3: +4 points on one seed, nothing on the others
    d = decide([0.7] * 5, [0.74, 0.7, 0.7, 0.7, 0.7])
    assert not d.adopt


def test_regressions_block_a_higher_average():
    # H-2: average improves but regression tasks break
    d = decide(CURRENT, CANDIDATE_A, regressions=3)
    assert not d.adopt and "regression" in d.reason


def test_safety_flag_blocks():
    d = decide(CURRENT, CANDIDATE_A, safety_flags=1)
    assert not d.adopt and "safety" in d.reason


def test_identical_scores():
    mean, _t, p = paired_t_test([0.5, 0.5], [0.5, 0.5])
    assert mean == 0 and p == 1.0
