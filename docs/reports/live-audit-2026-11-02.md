# Live acceptance audit and requirement review

Audit date: 2026-11-02. Scope: the standalone local Component A prototype.
Actual Gemini and Twelve Data requests used credentials explicitly authorized by the user.
The original handoff, review baseline and synchronized sources were preserved. No remote
Git changes or live three-agent integration were performed.

Requirements were checked against the team README scope, development plan, handoff
and historical assignment discussion. The original Scope/assignment Word files were
unavailable; this review does not claim to have re-read them.

**Conclusion:** calculations, external prices, real Agent dispatch and the local
interface have been exercised. The prototype supports continued local development
and demonstrations. It does not establish perfect model answers, completed research
scope or demonstrated self-improvement.

## Verification results

| Check | Observed result | Interpretation |
| --- | --- | --- |
| Python regression | 163 passed plus 64 subtests | Two dependency deprecation warnings, no failures |
| Browser regression | 28/28 passed, no flaky results | Includes key reuse, missing input, cancellation, deadlines, failures and mobile layout |
| Handoff tool cases | 15/15 passed | Provider packets are offline fixtures in this suite |
| Scripted ADK cases | 9/9 passed | Real dispatch and tools, scripted language transport |
| Minimal lesson gate | 20 offline ADK runs completed | No-gain candidate rejected; no learning-gain claim |
| Twelve Data quotes | 11/11 succeeded | Ten held symbols plus SPY |
| Twelve Data history | 2/2 succeeded | AAPL/SPY, 2026-10-26 through 2026-10-30 inclusive |
| Final real browser workflow | Passed | Saved-key model change, save, real Gemini calculation plus quote, persisted settings |

Quote symbols: AAPL, ARKK, BND, MUB, QQQ, SPY, TSLA, VTIAX, VTIP, VTSAX and VYM.
The observed fund successes do not promise universal fund/API/subscription coverage.
Quotes retain `timeliness=unverified`. Historical rows were checked for ascending
unique dates, positive prices, range boundaries and inclusion of the end date.
Neither query type automatically revalues fixture holdings.

## Real model rounds and retained failures

Three complete nine-case public development rounds each scored 8/9. They must not
be merged into an all-pass first-attempt claim:

1. Initial round: Chen and Thompson names were assigned to the wrong IDs in the
   final comparison. Identity context was corrected.
2. After that correction: the comparison passed; Garcia's projection tool was
   correct but Gemini returned only `<output>`. Empty template answers are now
   rejected. One explicit separate projection recheck passed the tools, arguments
   and final JSON checks.
3. Final round: eight cases passed; Garcia's projection received provider HTTP 429
   before calculation. The failure remains in the report. Live batch evaluation
   now pauses 15 seconds between cases and stops on rate failure.

A separate 12-case real acceptance suite passed 11 strict checks. It covered a
Chinese-language name-only request, an explicit 60/40 override, zero cash flows,
invalid account handling, conflicting identities, ambiguous clients, unsupported
account-only projection, scenario reading, external quote/history and fixture/live
separation. The comparison returned correct clients, order and values, but a bare
JSON array instead of the requested `results` object, so its format check failed.

Selected-field checks are not complete prose evaluation. A manual review of the
otherwise successful browser flow found an unsupported USD 19,863.71 figure beside
a correct percentage-point drift. That response was retained and the monetary
provenance check below was added. The final browser response was manually checked
and no longer contained that unsupported amount.

## Findings and changes

| Priority | Finding | Resolution or remaining boundary |
| --- | --- | --- |
| P1 | Name/ID mismatch in client comparison | Supply authoritative fixture name/ID/account context; clarify conflicts; comparison and conflict cases checked |
| P1 | Model invented a dollar equivalent of drift | Reinforce units and check dollar/USD amounts against actual tool money values; reject unsupported prose while preserving trace |
| P1 | Analysis waiting had no cancellation/deadline | Add cancellation, 15-second direct and 125-second Agent client deadlines, and protection from stale responses |
| P2 | Empty answers and template tags could appear successful | Require useful text in probes and Agent output; expose retryable errors |
| P2 | Independent comparison call order was overconstrained | Allow independent calls to reorder; retain final identity/order and dependent-step checks |
| P2 | Startup could report readiness too early | Wait for successful frontend/backend health responses |
| P2, open | JSON envelopes can deviate from the requested shape | Keep the failure; require enforced output validation before machine consumers rely on model JSON |
| Provider limit | 503, 504 and 429 responses | Distinguish busy, unavailable and quota failures from key errors; retain editable/recoverable controls |

The monetary check is deliberately limited. It recognizes dollar/USD amounts,
allows valid rounding, account subtotals and monetary facts in tool notes, and
avoids mathematical markup. Replaying 42 saved real Agent runs flagged only the
confirmed unsupported amount. Additional regressions cover empty responses,
correct explanatory amounts, the observed error and extreme numbers.
This does not verify every percentage, association, prose claim or unsupported
format. Numerical answers still require independent evaluation and tool evidence.

## Model availability observed

| Model | Actual observation |
| --- | --- |
| Gemini 3.5 Flash-Lite | Successful connection, financial tools and final browser flow; a batch request also received 429 |
| Gemini 3.6 Flash | Successful connection as well as 504; two browser connection attempts failed to complete the success path |
| Gemini 3.1 Flash-Lite | Connection probe returned 504 |
| Gemini 3.8 Flash | Connection probe returned 503 busy |

The audit used 3.5 Flash-Lite for the final browser demonstration, then restored
the user's prior 3.8 selection. A model change requires Save connection to persist;
the saved key can remain blank in the form. Free-tier support does not establish
unlimited account quota. See [pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [limits](https://ai.google.dev/gemini-api/docs/rate-limits).
These statuses describe observed requests, not a permanent availability guarantee.

## Requirement status

| Requirement | Status |
| --- | --- |
| Integrate the colleague's data, market tools and cases | Implemented; original handoff preserved |
| Develop standalone A before three-agent integration | Current boundary; offline delegation checks only |
| Put Portfolio Analysis under Main | Implemented and checked |
| Configure APIs and select models in the frontend | Implemented; actual saved-key reuse and persistence checked |
| Allocation, risk and goal-projection calculations | Implemented with independent numerical and boundary checks |
| Explicit target/horizon/flow overrides including zero | Implemented; unsupported account-only projections are not silently substituted |
| Separate market data from synthetic valuation and assumptions | Implemented and checked |
| Actual tool arguments, outputs, provenance and timing | Available in Execution evidence and saved CLI runs |
| Minimal validated-improvement workflow | Candidate, paired validation/regression, rejection, versions and rollback exist; the UI does not continuously learn |
| Full research scope | Multiple learning mechanisms, baselines, ablations, statistics and hidden tests remain |
| Tax, income, held-out fee drag and security-level trading | Outside the current three core calculations; preserve held-out evaluation boundary |
| Owner approval of targets and market parameters | Pending; draft status remains explicit |

## Next integration step

For B/C consumers, use `/api/portfolio/execute` results or actual call-ID-bound
responses in the Agent trace. Free-form text is not a stable numerical interface.
Model JSON needs an enforced schema and recovery before machine consumption.
No team code was merged during this audit.

Confirm draft inputs, retain real failures as public development material, and
prepare independently authored frozen validation/regression cases. Hidden tasks
remain with the designated team; public cases cannot become hidden by relabeling.

## Evidence map

Paths below are relative to the project root after directory consolidation:

- `artifacts/reports/pytest.xml`, `browser-tests.json`, `development_evaluation.json`:
  offline regression and public tool checks.
- `artifacts/agent_transport/` and `artifacts/gate_demo/`: offline dispatch and gate evidence.
- `artifacts/live/2026-11-02/live_connection_audit.json` and `live_market_coverage.json`:
  real connection and complete symbol coverage.
- Under that same dated directory, `live_development/`, `live_development_after/`
  and `live_development_final/`: the three retained rounds.
- `live_projection_recheck.json` and `live_acceptance.json`: explicit recheck and extra cases.
- `live_browser_audit_3_6.json`, `live_browser_audit_unverified_amount.json` and
  `live_browser_audit.json`: provider failure, unsupported-amount record and final success.
- `currency_guard_replay.json` and `live_audit_summary.json`: replay and aggregate status.
- `artifacts/screenshots/portfolio-live-audit.png`: final real browser capture.

Historical raw evidence retains original requests, response language, timestamps,
run IDs and failures. Paths embedded in old evidence describe the layout at capture;
the evidence was moved, not rewritten into new results.

The recorded 42 Agent runs account for 198,370 reported model tokens, excluding
connection probes; this is not a billing-cost calculation. No new provider calls
are needed solely to reorganize documentation. Keys are excluded from source
archives and Git; the release packager checks actual local key bytes before output.
