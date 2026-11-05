"""Adoption gate shared by all components: should a proposed change be adopted?

Mirrors the "Adoption Gate" sheet of the test suite. A candidate is adopted only if all of:
- the paired t-test over seeds is significant (two-sided p < alpha),
- the mean gain is at least the minimum (percentage points),
- no regression-suite tasks break,
- no safety-check flags,
- token cost stays within the allowed ratio.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


@dataclass
class GateThresholds:
    alpha: float = 0.05
    min_gain_pp: float = 1.0
    max_regressions: int = 0
    max_safety_flags: int = 0
    max_cost_ratio: float = 1.25


@dataclass
class GateDecision:
    adopt: bool
    mean_gain_pp: float
    p_value: float
    t_stat: float
    checks: dict[str, bool]
    reason: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta function (Numerical Recipes)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1.0 + aa / c if abs(c) > 1e-30 else 1e-30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1.0 + aa / c if abs(c) > 1e-30 else 1e-30
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: int) -> float:
    if math.isinf(t):
        return 0.0
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def paired_t_test(current: list[float], candidate: list[float]) -> tuple[float, float, float]:
    """Returns (mean difference, t statistic, two-sided p-value)."""
    if len(current) != len(candidate) or len(current) < 2:
        raise ValueError("Need at least two paired seeds")
    diffs = [b - a for a, b in zip(current, candidate)]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        t = math.inf if mean != 0 else 0.0
        p = 0.0 if mean != 0 else 1.0
        return mean, (t if mean >= 0 else -t), p
    t = mean / (sd / math.sqrt(n))
    return mean, t, t_two_sided_p(t, n - 1)


def decide(
    current: list[float],
    candidate: list[float],
    regressions: int = 0,
    safety_flags: int = 0,
    cost_ratio: float = 1.0,
    thresholds: GateThresholds | None = None,
) -> GateDecision:
    """Scores are fractions in [0, 1], one per seed, paired by seed."""
    th = thresholds or GateThresholds()
    mean, t, p = paired_t_test(current, candidate)
    gain_pp = mean * 100
    checks = {
        "significant": p < th.alpha and mean > 0,
        "min_gain": gain_pp >= th.min_gain_pp,
        "no_regressions": regressions <= th.max_regressions,
        "safety_clear": safety_flags <= th.max_safety_flags,
        "cost_within_limit": cost_ratio <= th.max_cost_ratio,
    }
    adopt = all(checks.values())
    if adopt:
        reason = "ADOPT: new version + audit entry"
    elif not checks["safety_clear"]:
        reason = "REJECT: safety check failed"
    elif not checks["no_regressions"]:
        reason = f"REJECT: {regressions} regression task(s) broken"
    elif not checks["significant"]:
        reason = "REJECT: gain not significant"
    elif not checks["min_gain"]:
        reason = "REJECT: gain below minimum"
    else:
        reason = "REJECT: cost above limit"
    return GateDecision(adopt, round(gain_pp, 3), p, t, checks, reason,
                        {"regressions": regressions, "safety_flags": safety_flags, "cost_ratio": cost_ratio})
