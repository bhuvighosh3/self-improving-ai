# Engineering review history

This records an earlier engineering revision, before the expanded live audit.
For current results use [the 2026-11-02 audit](live-audit-2026-11-02.md).

## Corrections made

| Priority | Finding | Correction |
| --- | --- | --- |
| P1 | Correct tools could hide an incorrect final answer | Bind calls/results by ID and separately score final values, units and provenance |
| P1 | Explicit scenarios could be replaced by defaults | Preserve target, horizon and cash-flow overrides, including zero, and reject unsupported filters |
| P1 | Missing holdings values could become zero | Validate finite nonnegative values and propagate client/account errors |
| P2 | Projection precision could be overstated | Expose sampling intervals, seeds, actual inputs and stored conflicts |
| P2 | Candidate adoption lacked execution evidence | Run paired baseline/candidate sessions and save frozen trace-derived scores before gating |
| P2 | Browser checks could attach to old services | Use dedicated test ports and require fresh server processes |

At that historical revision, 120 Python tests, 64 subtests and 16 browser checks
passed. Those counts are historical, not the current totals.

The unit-error demo ran 20 offline ADK sessions and rejected a candidate with no
validation gain. It establishes plumbing and rejection behavior, not learning.
Subsequent revisions added connection settings, request cancellation, identity
context, model error classification and dollar-amount checks.
