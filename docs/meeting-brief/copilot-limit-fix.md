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

## Patel repair-stage follow-up

The local `prepare for Patel Retirement Account` incident on 2026-11-09 exposed a
separate repair-stage problem. The provider returned 7,982 output tokens against
an 8,000-token limit, with 5,662 input tokens. The saved checkpoint showed that the
first writer response used only 1,188 output tokens and produced all six sections.
Its sole objective blocker was `JUDGMENT_BOUNDARY` on `CLAIM-priorities-1`: missing
rationale or uncertainty. Rewriting the complete draft to fix that field triggered
the observed truncation. These counts come from the actual local provider trace.

The bounded repair path now requests only the missing rationale/uncertainty for
the flagged claim IDs, with a 1,200-token budget. It preserves text, original
sources, calculation links, sections and all already nonempty fields. Duplicate,
missing or unknown patch targets are rejected. The entire work product still goes
through the objective checker and independent semantic reviewer before saving;
other defect classes keep the normal repair path. Existing discovery results and
calculations remain reusable through the checkpoint.

The compact writer's instructions also stop requesting the canonical graph IDs
owned by Python. Judgment items explicitly require rationale and uncertainty.
Short commands such as `prepare for Patel Retirement Account` and `prep Patel`
use the calendar preparation flow when the target is a known client alias;
financial-analysis requests are not captured by this shortcut. Output truncation
no longer asks the advisor to narrow an already short request.

Both regressions were red before the fix: the short command took the general
Copilot route, and the field-repair replay requested a full second writer response
and reproduced `MAX_TOKENS`. The focused regressions and 73 related offline tests
(24 subtests) pass after the fix. An additional live Gemini replay was blocked by
automatic approval review because the earlier authorization covered one already
used synthetic case. No additional provider call was made; live follow-up remains
pending fresh user authorization.
