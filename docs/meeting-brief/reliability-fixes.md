# B reliability fixes — 2026-11-05

The failure was reproducible at the prompt and provider boundaries. A source bundle
contained both originals and execution logs repeating those originals. The output
contract permitted free-text source IDs and optional empty agenda explanations.
The calculator exposed an unconstrained operation string; live traces showed six
invalid guesses such as `SUM`, `ADD` and `IDENTIFY`. A subsequent provider failure
discarded in-memory progress from the caller's perspective.

## Changes

- Exclude logs from generator/reviewer inputs and context-tool responses; retain
  them on the server. Original evidence and coverage are preserved. The measured
  evidence-JSON character reduction is 64.7% for Okafor, 62.8% for Thompson and
  62.2% for Chen. These are input-size measurements, not a token-price benchmark.
- Constrain original source IDs in the generation schema and require nonempty
  agenda rationale/questions. Derived IDs still need actual calculator-ledger
  verification. Unresolved claim references and duplicate/missing sections remain
  blocking checks. No fabricated IDs or missing sections are silently repaired.
- Declare calculator operations as an enum and operands as typed fields. Normalize
  operation casing, report legal operations/actual numeric field paths on error,
  and compute the basic holdings total before writing. Trace origin distinguishes
  backend preflight from model-selected actions. Completed calculations are reused.
- Use the existing ADK/Gemini stack with a bounded request timeout and three total
  attempts for transient service errors. No automatic model/provider switch or
  Offline demo fallback. Quota/credential errors are not retried.
- Retain run checkpoints in SQLite, including the latest draft, calculations,
  feedback and safe error type/status. Identical inputs resume interrupted work;
  reviewer failure does not cause regeneration. API errors include a run ID header
  and the diagnostic endpoint always reports `approved: false`.
- Require separate source/draft comparisons for modality and funding scope in the
  model reviewer. Manual inspection caught an earlier reviewer missing a tentative
  purchase date; model-review passes are not expert certification.

## Verification

- Initial regression loop: `pytest tests/test_agents/test_brief_reliability.py`
  failed on duplicated prompt data and absent generation/provider constraints.
  A separate calculator regression reproduced the uppercase-operation failure.
- Final offline repository suite: **222 tests passed, 78 subtests passed**, with
  network connections blocked. The actual Google SDK + ADK retry test injects an
  HTTP 503, checks identical retry payloads and verifies one retained calculation.
- Four existing browser workflow tests passed, including desktop/mobile Copilot
  handoff and review/edit behavior. Existing UI styling is unchanged.
- A real intermediate Gemini run returned a draft in 17.56 seconds and passed
  objective/model review, but correctly failed acceptance because no calculator
  was executed. Manual content inspection also found a modality error, motivating
  the stricter boundary review. This intermediate run is not a successful final
  acceptance result.
- Final real HTTP acceptance and any remaining provider limitations are recorded
  in [integration verification](integration-verification.md) and local ignored
  `artifacts/briefing/fixed-live-http.json`.

Keep Gemini 3.5 Flash-Lite as the local shared-model override, matching A's default.
The provider can still return capacity errors; bounded retries cannot guarantee
external availability. There is no learning-gain claim. A subsequent content-v2
change moved IDs/section assembly to Python and added a simulated calendar trigger;
see [calendar simulation](calendar-simulation.md) and the latest acceptance below.
