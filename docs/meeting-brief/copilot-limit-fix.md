# Copilot briefing limit fix — 2026-11-09

## Confirmed failure mechanism

General Copilot previously delegated to the raw B writer through `AgentTool`.
Unlike the Calendar/Meeting Prep API, this path requested the full `AgentWork`
graph directly from the model, bypassing the compact writer contract, independent
review and shared draft persistence. Context-tool output also repeated evidence
already present in the writer's instruction. Repeated evidence increases input
size; it does not itself prove that the provider's output limit was exceeded.

An offline replay through the actual ADK runner demonstrated that a provider
`MAX_TOKENS` response lost its finish reason at the structured-output boundary.
The API then returned a generic failure. Separately, the Copilot exception handler
classified any error containing `exceeded` as an LLM-call budget failure, including
an input-token-limit error.

The teammate's exact deployed incident remains unconfirmed: its original query,
provider response and Cloud Trace were unavailable. No production logs, live
Gemini requests or real Firestore records were used for this fix.

## Current behavior

```text
Calendar / Meeting Prep API ───────┐
                                ├─ prepare_brief
Copilot → meeting_briefing_agent ┘    → existing B discovery and calculations
                                     → compact structured writer
                                     → objective and independent model checks
                                     → saved draft
```

- The shared application service preserves the existing primary/fallback model,
  timeouts, frozen Inbox snapshot and persistence behavior. Copilot receives the
  same simulated date as the preparation worker.
- Copilot's B tool requires resolved client, meeting date, New York time and focus.
  It returns a bounded summary, up to three priority titles and a saved draft ID.
  It never returns the full evidence, claims graph, trace or draft to the parent
  model. The full retained draft is attached to the HTTP response separately, so
  the existing **Open Meeting Brief** button still works without regenerating it.
- Duplicate B calls share one preparation task within the current HTTP request,
  including checker retries and parent fallback. Later requests receive a fresh
  scope. The underlying B checkpoint/resume contract remains unchanged.
- B checks `MAX_TOKENS` before ADK validates the output schema. Partial structured
  output is rejected; safe model, output-limit and usage metadata are recorded in
  the checkpoint trace. The parent runtime also rejects truncated final answers.
- Copilot distinguishes output token limits, input context limits, LLM-call
  budgets, quota, timeout and service errors. A delegated B failure is not retried
  by restarting the parent, since B owns its own bounded fallback.

Part A calculations, storage schemas, Calendar meetings and UI styling are
unchanged. Output budgets were not increased, and no silent Offline demo fallback
was introduced.

## Verification

Portable, network-blocked regression suite (no API key or Firestore login needed):

```bash
PYTHONPATH=src python -m pytest tests/test_agents/test_copilot_briefing_limits.py -q
```

The tests use the actual ADK Runner and FunctionTool boundary with scripted provider
responses. They cover the valid-output control, truncation before schema parsing,
parent truncation, error classification, shared persistence, compact model input,
full browser handoff, parallel deduplication, per-request isolation, missing details
and absence of offline fallback after provider failure.

Additional compatibility checks exercise the existing B reliability, API, Copilot
confirmation, discovery, Calendar preparation and workspace integration suites.
Those checks use explicit legacy synthetic records at the Firestore store seams;
they do not certify the deployed database or live Gemini availability. The local
verification used ADK 2.13.0 and google-genai 2.34.0.

Next deployment validation: replay the reported Copilot request on staging when
available, verify that a retained brief opens, and inspect finish reason/usage if
the provider rejects the request. Treat provider capacity and quota separately
from token-limit failures.
