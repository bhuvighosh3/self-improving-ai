# Meeting Brief evaluation proposal v0.1

Status: preliminary design, based on the supplied 2026-10-28 evaluation draft and
workflow v0.5. [Architecture and implementation audit](README.md).

No weights, pass thresholds, follow-up counts, sample size or scoring technology
are fixed by this proposal. There is no implemented evaluator in the repository.
This is not a method already validated by a paper or by project experiments.

## Evaluate results and verifiable work

Assess the agent as a wealth-management assistant: can it reliably prepare useful,
evidence-backed materials and answer questions about its work within its authority?
Assess the final artifact and the observable process separately. A fluent answer
or retrospective explanation cannot substitute for actual evidence and execution.

| Layer | Assessment | Evidence |
| --- | --- | --- |
| Basic duties | Correct client, cutoff-visible sources, arithmetic, coverage, references, required sections and delivery | Independent case facts, actual source reads, calculation inputs/results and saved version/location |
| Analysis quality | Supported comparisons, goal impact, topic relevance, priorities and uncertainty | Source-to-fact-to-calculation/comparison-to-conclusion-to-agenda links, including contrary information |
| Proactive contribution | Correct, useful discoveries beyond explicit requirements | Original sources, actual trace, relevance, expert review and incremental cost |

Record dimensions initially as `pass / partial / fail` with evidence and a written
reason. Mark unobservable process evidence as unavailable, rather than inventing a
trace. Do not aggregate into an uncalibrated total score. Serious client/privacy/
fabrication errors must remain visible; initiative should not mask them. Specific
severity handling and reward rules still require agreement.

## Independent case package

Each case needs two separately controlled parts:

- **Agent-visible inputs:** task/authority, meeting type, cutoff/timezone, approved
  routine template, authorized sources and mock tools.
- **Evaluator-only notes:** key facts and source locations, expected discoveries,
  unsupported conclusions, missing/conflicting information, valid alternative
  plans and applicable duties. These are not a single required wording of a brief.

The agent, production quality reviewer and normal tool runtime must not access
hidden notes. Evaluate against both event time and recorded-at visibility; a
backdated record entered after cutoff is unavailable for that historical run.
Correct unexpected discoveries have an expert-review path instead of being
penalized merely for absence from the initial reference notes.

## Evaluation procedure

1. Freeze model/configuration, tool/data versions, rubric, task and permissions;
   run on a declared case/split/seed where supported.
2. Preserve complete artifacts and observable trace, including drafts, actual tool
   arguments/results/statuses, source reads, calculation records, quality findings,
   repairs, advisor feedback, versions, timing and cost.
3. Inspect final facts, numbers, omissions, agenda value, priority and delivery.
4. Ask standardized follow-ups about selected important judgments: why important,
   which source, what comparison, contrary evidence, assumptions and remaining gaps.
5. Check responses against the execution record. Snapshot the trace before
   follow-ups; label explanations of completed work separately from new searches,
   calculations or revisions performed during questioning. Tool permissions and
   follow-up budget/count remain to be specified.
6. Attribute errors to retrieval, source selection, calculation, judgment,
   expression or delivery. Preserve initial errors even if a later draft recovers.
   Label injected checker-test errors separately from naturally occurring errors.
7. Repeat across clients, meeting types, tool/condition changes and missing/conflict
   patterns; report incomplete/blocked runs as well as successful runs.

Production `quality_check` repairs a current draft using authorized evidence.
Independent evaluation assesses the run using hidden notes and a frozen rubric.
Evaluation does not create customer facts or feed test answers back into that run.

## Candidate dimensions

| Dimension | What to check | Primary reviewer |
| --- | --- | --- |
| Identity and temporal validity | Correct household, authority and sources visible at cutoff | Program |
| Facts and calculations | Values, tentative wording, dates, currency and account/household scope | Program plus expert for semantic scope |
| Coverage and routine duty | Prior minutes, tasks in all states, subsequent client/investment/service updates, meeting-type routine items | Program plus expert |
| Analytical support | Evidence supports comparison and goal impact; rationale and uncertainty fit conclusions | Expert; optionally calibrated LLM |
| Agenda/service value | Client concerns, commitments, relevance, priority and concrete desired outcomes | Expert |
| Evidence fidelity | Cited originals were read; explanations match actual work; prose and claims agree | Program plus semantic review |
| Behavior and efficiency | Authorized actions, failed/empty-result handling, justified calls and retries | Actual tool trace, not declared names |
| Recovery and review | Error detection, correction persistence, current-version check and approval | Version diffs and review/save records |
| Initiative | Useful supported unexpected discoveries without overreach | Expert |
| Stability and cost | Behavior across cases; tokens/time/tool calls and regressions | Program and cross-case analysis |

## Proactive contribution and rising expectations

A candidate contribution must be correct, sourced, relevant to this meeting,
beyond explicit requirements, uncertainty-aware and within authority. Repeated
facts, verbosity, speculation and unnecessary tool calls are not automatic credit.
Record the finding, evidence, why it was extra, value, cost, expert decision and
rubric version. For example, a stale-task discrepancy is extra only if the current
rubric has not already made task reconciliation a basic duty.

One good example is a case record, not an automatic new requirement. After expert
agreement and evidence of repeatability/value/cost across cases, the team may
promote it to routine duty. Stop awarding extra credit for that behavior under the
new rubric. Report a **fixed rubric** for version comparisons and a separately
versioned **growth rubric** for rising expectations; do not conflate their scores.

## Case matrix to build

| Case family | Required behavior |
| --- | --- |
| Significant client change | Compare old/new goal, preserve tentative intentions, adjust agenda with rationale. |
| Supported no significant change | Continue routine progress/commitment review and state what was actually checked. |
| Missing updates, no results or tool failure | Preserve uncertainty and search scope; never equate absence of evidence with no change. |
| Investment/service change | Use valid period, cash flows and scope; discuss execution/service progress without inventing returns. |
| First meeting | Explain absent history and use appropriate baseline; do not fabricate prior commitments. |
| Conflicting/stale records | Preserve originals, identify conflict and ask targeted questions; no unauthorized CRM update. |
| Cutoff, pagination and distractors | Exclude post-cutoff records, disclose incomplete scope and read relevant originals. |
| Wrong-client source or embedded instructions | Reject unauthorized data/actions; record failure accurately. |
| Numerical boundary trap | USD 180,000 less known account cash USD 50,000 is USD 130,000 difference, not proven household shortfall. |
| Revision and obsolete approval | Recheck new version; reject old-version approval; preserve failure/recovery history. |
| Exhaustion/save failure | Report incomplete or retryable save failure; never claim successful delivery. |
| Unanticipated useful discovery | Permit expert adjudication with actual evidence and cost record. |

## Relationship to existing tests and group evaluation

Existing Python tests verify deterministic behavior and API integration; browser
draft checks verify local storage. They are regression assets, not evidence that
LLM analysis or autonomous workflow quality has been evaluated. Current source
references and tool-name lists provide partial observability only.

Keep the README's shared static/hand-tuned/retrieval-only baselines and
train/validation/held-out split proposal. Candidate improvements use validation;
held-out cases must remain separate, including cross-team authorship where agreed.
Allow justified alternative tool orders: assess required coverage and dependency
constraints rather than exact replay of the attachment's example trace. Report
regressions and cost alongside quality; planned baseline wins or multi-seed claims
are not existing results. The README's five-seed and approximately 100 human-label
targets are group proposals, not calibrated Component B scoring decisions.

Programs should check objective identity, dates, numbers, references and delivery.
Experts judge service value, priorities and appropriate initiative. If LLM judging
is used, calibrate against human-labeled cases and retain disagreement review.

## Open decisions for Lopa and the team

- Representative meetings, input packages, strong briefs and routine templates.
- Universal duties versus conditional client-specific requirements.
- Weights, severity handling, thresholds and contribution rewards, if any.
- Follow-up selection, count, permissions and separation of explanation from new work.
- Reviewer calibration, disagreement handling and feasible sample sizes.
- How to prevent rubric gaming, verbosity and unnecessary tool use.
- How feedback becomes a validated improvement on unseen cases.

## Proposed evaluation record

Keep separate identifiers for run, case, agent/model/tool/data/template versions,
rubric and split. Store final-artifact references, dimension verdicts with evidence,
stage-attributed errors, initial/repaired/injected errors, follow-up boundary and
answers, initiative candidates/adjudication, costs and reviewer disagreements.
An illustrative structure appears in the [technical appendix](appendix.md).
