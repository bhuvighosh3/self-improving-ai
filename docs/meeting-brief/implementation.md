# Meeting Brief workflow implementation

This file describes executable changes on `feat/meeting-brief-workflow`. The
[architecture document](README.md) retains the pre-implementation audit and larger
proposal; not every proposed capability is complete.

## Available now

- One ADK briefing agent loads three business skills and returns typed context
  comparisons, findings, fact/calculation/judgment/unknown claims, six sections and
  a separate client agenda. It remains callable by the existing orchestrator.
- Read-only adapters recover available prior minutes, all task states and
  subsequent synthetic communications/investment/service records. Sources are
  filtered by client, event date and recorded-at date at the backend fixture
  cutoff. Search snippets are followed by original reads. Optional relevant mock
  news is included. Current connectors are local fixtures, not real email/calendar.
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

Confirmed Copilot requests still use the shared endpoint and default to Offline
demo. The mode selector is currently on Meeting Prep. Direct ADK delegation loads
the same skills/tools, but the bounded independent-review/repair service is the
dashboard AI path; do not treat raw CLI output as approved delivery.

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

No Gemini key was available during implementation: real remote model quality and
provider compatibility have not been validated. Mocked responses and a local ADK
test model verify integration, not LLM quality. Human calibration is still needed.

This remains a local synthetic prototype: review records have no authenticated
advisor identity, meeting-type templates await business approval, fixture cutoff
is a date rather than an intraday historical database, and source permissions are
client-scoped fixture filtering rather than production authorization. There is no
automatic client delivery, trade, CRM write, self-learning loop or new LangGraph
dependency. The evaluator does not yet adjudicate service value or prove learning
gains. Failed provider calls are reported to the caller; complete durable failed-run
traces, resume/checkpoint recovery and interactive advisor revision requests are
not implemented. The server's reviewed snapshot is separate from newer local
unsaved browser edits; recheck/review those edits before using approved delivery.
