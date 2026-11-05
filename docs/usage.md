# Portfolio Analysis and connections

Open the local application and select **Main → Portfolio Analysis**. Main is a
navigation group, independent of the Git branch named `main`.

## Calculations

Choose **Portfolio calculations**, a client and an analysis:

| Analysis | Result |
| --- | --- |
| Holdings | Fixture accounts, holdings and total value |
| Allocation drift | Actual and target stock/bond weights, drift in percentage points, hypothetical adjustments |
| Risk and return | Annual expected return and volatility from the draft stock/bond model |
| Goal projection | Goal inputs, success probability, ending-value distribution and depletion probability |
| External quote | Latest available provider price, currency, dates and timing limitations |
| External history | Daily split-adjusted closes in the requested inclusive interval |

Blank override fields use stored draft values. An explicit zero contribution or
withdrawal replaces the stored cash flow. Changing the client or calculation clears
previous results and scenario overrides. **Execution evidence** shows actual tool data.

## Gemini requests

Choose **Ask Portfolio Agent (Gemini)** and enter a request, for example:

- Show Garcia Family CLI-001 allocation drift against its draft 60/40 target.
- For Thompson Trust CLI-002, use a hypothetical 60% stock target.
- Project Chen CLI-003 toward USD 2 million in 10 years and show the inputs used.

The backend supplies the synthetic client directory. Ambiguous or conflicting
identities should be clarified. Account-only projections and tax/fee scenarios are
outside the current calculation contract.

## Connection settings

**Market data** configures Twelve Data. **Portfolio Agent** configures a Gemini
Developer API key and a model from the supplied dropdown.

- **Test** uses the current form without saving it. An empty field uses a saved key.
- **Save connection** applies the key/model to new analyses immediately.
- Changing models reuses the same Gemini key. Draft keys remain while switching tabs.
- **Remove API key** explicitly disables that connection, including after restart.
- Closing the dialog clears draft keys. Saved keys are not returned to the browser.

The backend stores settings under `.local-settings/`, excluded from Git and releases.
Saved UI settings override A's `SIA_PORTFOLIO_API_KEY` and `SIA_PORTFOLIO_MODEL`,
including explicit removal. Without an A key override, an existing `GOOGLE_API_KEY`
or `GEMINI_API_KEY` may be used as a fallback. A's save/remove actions do not change
those shared keys, `SIA_AGENT_MODEL`, the judge model or Vertex AI mode. The CLI
restores the same A overrides. `.env.example` is an optional setup template.

## Errors and waiting

Missing keys produce immediate prompts. Connection tests have a 15-second browser
deadline and can be cancelled or closed. Analysis waiting can be cancelled; direct
requests have a 15-second client deadline and Agent requests a 125-second deadline.
Already-sent provider requests may still consume quota after cancellation.

Authentication, model access, busy responses, network errors and quota limits are
reported separately. Empty model answers and unsupported dollar amounts are rejected;
the amount check is limited and does not verify every statement. Inspect tool evidence
for numerical results. There is no silent model or fixture fallback.

The 2026-11-02 audit found 3.5 Flash-Lite usable for the final browser flow. Model
availability and quota remain account-dependent. Tests restore the saved model after
temporary checks; choose and save your desired model explicitly.
