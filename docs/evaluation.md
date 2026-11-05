# Evaluation and lesson validation

The 15 handoff cases are public development tasks. Independent stdlib reference
code supplies numerical checks; it does not call the production calculation tools.
Projection references use independently generated paths and fixed tolerances, with
analytic boundary tests covering deterministic behavior separately.

The scorer binds each result to a unique real call ID and tool name. It checks
arguments, allowed alternatives, dependencies, extra calls, numerical results,
units, provenance and structured final answers. Independent comparison calls may
reorder; final client order and identity remain required. Free prose needs additional review.

Scripted mode runs real ADK and tools with a declared offline transport. It tests
wiring and scoring, not natural-language reasoning. Live mode uses saved Gemini
settings and records real provider results, including failures.

## Minimal lesson gate

`portfolio_lessons.py` stores versioned candidate lessons. Candidates are frozen
against their active baseline. The paired experiment runner uses fresh sessions,
fixed tasks/projection seeds, code/data/model fingerprints and persisted trace-derived
scores before accepting or rejecting a candidate. Validation and regression sets
must be disjoint. Versions can be rolled back.

The demo injects a final currency error, proposes a unit-check lesson and runs 20
offline ADK sessions over two public cases and five repeats. The scripted model
ignores lessons, so no validation gain is observed and the candidate is rejected.
This is an engineering demonstration, not proof of learned improvement or significance.

For actual validation, `validate_portfolio_lesson.py` takes real development evidence,
feedback and an independently authored frozen validation/regression suite. It rejects
scripted or hidden-task evidence. Only validated active lesson files should be passed
to the CLI with `--lessons-file`; the endpoint does not accept arbitrary lessons.

## Remaining research

Skill-library and tool-preference experiments, multiple baselines, ablations,
paired statistics and independently held hidden tasks remain to be completed.
Five projection seeds/repeat IDs do not seed Gemini or establish statistical gain.
Fee drag remains the held-out task-family boundary. The dashboard does not
automatically learn from every request or correction.
