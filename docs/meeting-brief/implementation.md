# Meeting Brief workflow implementation

This file describes the merged workflow and integration fixes on
`codex/proactive-meeting-prep`. The
[architecture document](README.md) retains the pre-implementation audit and larger
proposal; not every proposed capability is complete.

## Shared workspace integration (2026-11-07)

The earlier private weekly calendar was replaced by the teammate's canonical
monthly Calendar and Inbox from main (`4316af3`, PR #4). Part B's monitor, ready
notice and brief review now use those records; linked correspondence enters the
same scoped evidence pipeline. Local persistence runs without cloud credentials;
Firestore is an explicit configuration. See the current
[Calendar/Inbox integration](calendar-simulation.md). Earlier live-run timings and
fixture-based descriptions below are historical until independently rerun.

## Available now

- Content-v2 uses six required named content slots. Python owns section titles,
  item/claim/finding IDs and evidence links; Gemini writes atomic sourced content.
  Prepared context and verified metrics are supplied before writing, so the normal
  path needs one native structured writing call and one independent reviewer call.
  C delegates through a bounded tool that calls this same checked, persisted
  workflow and returns a compact summary with the retained draft ID.
- A simulated calendar worker prepares upcoming meetings autonomously within a
  24-hour window and posts an advisor notification. It shares the existing B
  service, checks and draft store; it never creates a second UI-specific brief.
  See [calendar simulation](calendar-simulation.md) for the demonstration flow.
- One ADK briefing agent loads three business skills and returns typed context
  comparisons, findings, fact/calculation/judgment/unknown claims, six sections and
  a separate client agenda. It remains callable by the existing orchestrator.
- Read-only adapters recover available prior minutes, all task states and
  subsequent synthetic communications/investment/service records. Sources are
  filtered by client, event date and recorded-at date at the backend fixture
  cutoff. Search snippets are followed by original reads. Optional relevant mock
  news is included. Calendar/Inbox records use the shared local/Firestore adapter; CRM/holdings remain fixtures. No external mailbox/calendar synchronization is implemented.
- The Decimal calculator accepts original JSON fields with declared currency,
  preserves operands/results and registers derived sources for chained arithmetic.
  It does not execute arbitrary code or infer a household shortfall from cash.
- The dashboard has explicit Offline demo and AI Agent modes. Both retain the
  existing six-section UI/PDF. Offline mode performs deterministic comparisons,
  tracks coverage and actual calculator calls; it is not labeled as an LLM run.
- AI mode uses ADK Runner with bounded model calls and an overall timeout. Objective
  checks and a separate model reviewer examine the draft, claims and underlying
  evidence. Up to two repairs are allowed; failures do not silently switch modes.
  Sources are data, not instructions; reviewers do not see evaluation references.
- Model inputs exclude execution traces while retaining original evidence and
  coverage. Generation constrains original source references and requires rationale
  and questions on agenda items. A backend preflight computes the snapshot total
  with the same sourced Decimal calculator used by ADK tools, explicitly marked
  `backend_preflight` in traces. It is not presented as a model-chosen tool call.
- Each Gemini HTTP request has a 30-second timeout and at most three attempts for
  transient 502/503/504 responses; credentials, input errors and quota errors are
  not retried. SDK retries preserve the failed request and completed tool work.
- Local SQLite checkpoints retain drafts, tool state and quality feedback on
  interruption. Repeating identical inputs with the same model/cutoff resumes
  the interrupted stage. `GET /api/briefings/runs/{run_id}` exposes diagnostic
  progress, never an approved delivery artifact. Reviewer interruptions resume
  review of the same draft. Quality-blocked runs retain diagnostics for inspection.
- Independent review explicitly compares original and draft evidence for tentative
  intentions and funding scope. A failing boundary overrides an inconsistent pass.
- Check and review endpoints use server-retained evidence rather than browser
  evidence. Local SQLite stores drafts and version/digest-specific review records;
  stale review attempts are rejected. Edited content needs a new revision/check.
  Draft exports remain available; `/api/briefings/{id}/approved` returns only the
  server's approved snapshot.
- The independent evaluator checks final artifacts and recorded work, reports
  located errors/costs, preserves quality history, and records initiative candidates
  for expert adjudication. No fixed weights or total score are introduced.

## Try it

Run the existing backend and Vite commands from the project README. On Windows,
use UTF-8 mode (`python -X utf8 -m uvicorn ...`) for the existing fixture readers.
In Meeting Prep, generate an Offline demo with:

| Client | Scenario |
| --- | --- |
| Okafor / CLI-004 | New synthetic prior-minutes/email fixtures show a tentative change to home-purchase timing and down payment. External savings remain unknown. |
| Thompson / CLI-002 | A scoped synthetic confirmation supports no significant changes; routine review and unfinished duration work remain. |
| Chen / CLI-003 | Available records do not establish complete history; status stays insufficient_information. |

Expand **Preparation process** to inspect coverage, rationale, uncertainty and
recorded tools. Use **Check draft**, edit if needed, then **Mark as reviewed**.

For live generation, configure `GOOGLE_API_KEY` and
`GOOGLE_GENAI_USE_VERTEXAI=FALSE` in the root `.env`, then select **AI Agent**.
The `.env.example` contains placeholders only. No key is required for Offline demo.
The model and reviewer incur API usage when AI mode is selected.

Explicit Copilot preparation requests open the existing confirmation form, with
meeting type and generation mode selectors. Confirming calls the same generation,
server persistence and error handling as Meeting Prep; opening the returned brief
does not generate it again. Both entry points default to Offline demo. Other
Copilot requests continue to use C's live orchestrator. This narrow UI handoff does
does not itself schedule work. The separate simulated calendar worker provides
proactive preparation; there is no external email/calendar connection. C's ADK tool
delegation also calls the bounded independent-review/repair service. The full
draft reaches the browser separately from the compact tool response returned to
the parent model. See [Copilot limit fix](copilot-limit-fix.md) for error handling
and offline verification. Generated drafts still require advisor review.

## Independent evaluation

Keep a reference file outside agent-visible data, for example:

```json
{
  "client_id": "CLI-004",
  "rubric_version": "proposal-v0.1",
  "required_text": ["Possibly six months"],
  "forbidden_text": ["proven household shortfall"],
  "required_tools": ["read_source", "calculate_metrics"],
  "routine_finding_ids": ["FINDING-workflow-routine"]
}
```

Use the brief ID returned by generation or the browser network response:

```bash
python -m self_improving_ai.evaluation.meeting_brief --brief-id ID --reference /path/to/reference.json --output evaluation.json
```

Text assertions are case-specific checks, not semantic truth verification.
Analysis quality and initiative remain pending expert review. Follow-up records
can distinguish declared additional tool work from explanations and retain the
pre-question trace digest; an interactive standardized questioning harness and
automated verification of follow-up answers remain future work.

## Verification and remaining boundaries

Python tests cover all three branches, cutoff/client isolation, source and
calculation tampering, currency/denominator checks, stale approval, repair flow,
and a real ADK Runner using a local test model. Browser tests cover workflow
generation, coverage, review/edit invalidation and mode selection.

No Gemini key was available during initial implementation. Live verification on
2026-11-05 reached actual model output and calculator calls on Gemini 3.5 Flash-Lite,
but two runs were interrupted by provider 503 errors. Gemini 3.8 Flash timed out
after 180 seconds. Those initial results are superseded by the content-v2 calendar
acceptance: real Gemini generation, one repair, independent review and persistence
passed in 29.25 seconds. See [verification results](integration-verification.md).
Human calibration is still needed; one acceptance case is not a reliability SLA.

The opt-in live acceptance command uses the shared B/C `SIA_AGENT_MODEL` setting
(default `gemini-2.5-flash`) for generation and the separate reviewer invocation.
It does not change Component A's independent model selection. After configuring
the ignored root `.env`, run one public fixture case:

```bash
python scripts/audit_live_briefing.py --live --case changed
```

The `unchanged` and `missing_history` cases can be selected separately or with
repeated `--case` arguments. Actual tool events, model usage, objective/semantic
checks, repair history and the final document are saved under the ignored
`artifacts/briefing/live-acceptance.json`. Failure retains collected events and
exits nonzero; it never substitutes Offline demo. The command needs a Developer
API key and consumes quota. Check the brief against its originals before making
a quality claim. Failed live attempts are recorded in the verification results.

This remains a local synthetic prototype: review records have no authenticated
advisor identity, meeting-type templates await business approval, fixture cutoff
is a date rather than an intraday historical database, and source permissions are
client-scoped fixture filtering rather than production authorization. There is no
automatic client delivery, trade, CRM write, self-learning loop or new LangGraph
dependency. The evaluator does not yet adjudicate service value or prove learning
gains. Failed provider calls are reported to the caller with a retained run ID when
available. Checkpoints cover stage boundaries and handled errors/cancellation;
hard process crashes may lose events after the latest checkpoint. Interactive
advisor revision requests remain future work. The server's reviewed snapshot is separate from newer local
unsaved browser edits; recheck/review those edits before using approved delivery.

## Briefing catalog tools and proposed investigation stage

The four dashboard Briefing tools are now implemented as read-only fixture
functions, including `check_compliance_flags`. The tool is called during B evidence
collection; relevant sourced follow-ups reach new drafts. See the
[tool handoff](briefing-tool-handoff.md) for compatible imports, result envelopes,
cutoff/provenance behavior and the distinction between flags and clearance.

Verification: 18 tool tests include actual offline ADK dispatch of all four
functions; the full offline suite passes 250 tests and 78 subtests. No new live
Gemini acceptance was run for this change. The existing real writer/reviewer is
retained; autonomous, scoped tool investigation is a
[concrete proposed design](agent-integration-design.md), not an enabled runtime
feature. Component A/C registrations and their catalog entries remain unchanged.


## Connected AI investigation — 2026-11-05

AI mode now runs `meeting_context_investigator` before writing and review. The
configured `SIA_AGENT_MODEL` is shared by these B stages; A/C behavior and models
are unchanged. The investigator has client-locked read-only tools, a server-owned
cutoff and a source registry constructed only from executed reads. It is limited
to four model turns, ten actual tool executions, eighteen requests and one news
search. Duplicate reads reuse their exact checkpointed result. Minimum coverage
reads that the backend supplies are labeled `backend_required`, never represented
as model-selected behavior. Search snippets cannot become original citations.

Each completed read checkpoints source results and counters. A handled provider
failure retries discovery with cached reads in a new ADK session; it does not
claim full persistent conversation replay. Later writer/reviewer checkpoints
retain their existing resume behavior. Exhausted budgets require inspection rather
than indefinite automated retry. AI-mode default is `SIA_BRIEFING_DISCOVERY=agent`;
explicit `backend` mode is retained for diagnostics, without silent fallback.

Calendar AI job links include the pipeline/strategy version so a ready draft from
the old pipeline does not masquerade as a new investigator result. Historical
draft records and offline preparations are retained. Ready still means a checked
saved draft, not advisor approval.

Verification: 258 offline tests and 78 subtests pass. The new tests exercise actual
ADK dispatch, client denial, unread source coverage, budgets, cached-read retry,
writer/reviewer integration and historical calendar-cache replacement. Earlier
writer-only tests explicitly select the backend collector; discovery has its own
enabled-path integration tests.

Real direct acceptance (`artifacts/briefing/discovery-live-acceptance-initial.json`):
Okafor, 13.06 seconds, eight model-selected reads, 14,751 reported tokens, first
objective/reviewer pass. Manual inspection then tightened tentative wording in
why/rationale as well as main text.

Real calendar acceptance (`artifacts/briefing/discovery-calendar-live.json`): the
normal worker and shared B service saved Okafor and Patel drafts, 34.04 seconds
total, 47,152 reported tokens across both jobs including repairs/reviews. Okafor
retains tentative timing/expected down payment, unknown external funding and the
state-of-residence confirmation; Patel retains original beneficiary/distribution
verification work. The initial acceptance helper's second idempotence tick also
processed Patel; it now verifies retained-job identity by reopening the selected
job, without an extra tick. The artifact records this distinction and token scope.

To repeat one calendar acceptance, provide a new isolated database (the helper
changes its fixture clock and consumes Gemini quota):

```bash
SIA_DB_PATH=/tmp/meeting-prep-live.db python scripts/audit_calendar_briefing.py --live
```

Next work is content acceptance and remaining client cases, not additional UI or
framework changes. See [current agent integration](agent-integration-design.md).
