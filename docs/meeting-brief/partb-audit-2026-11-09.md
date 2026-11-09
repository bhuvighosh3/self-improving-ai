# Part B regression audit — 2026-11-09

## Scope

The Inbox workspace notice was removed as requested, along with its unused style.
Regression coverage includes Calendar CRUD and week navigation, automatic
preparation, Notes-triggered invalidation, Copilot handoff, saved brief identity,
review/edit persistence, provider failures, references, calculations, client/cutoff
isolation, and PDF export on desktop and mobile layouts.

The audit used a separate SQLite database and explicit synthetic client/CRM stores.
API keys were removed and outgoing socket connections were blocked in the audit
backend. Browser mutations affected only that local test workspace. Shared
Firestore records were not changed, and this audit made no additional Gemini calls.
The earlier authorized live acceptance is recorded separately in
[cloud-acceptance-2026-11-09.md](cloud-acceptance-2026-11-09.md).

## Defects reproduced and fixed

- Offline preparation ignored the fixture-only news context and could contact
  Twelve Data when a key was present. The tool now respects the decorator,
  configured fixture source, and non-AI operational scope. It reports source
  availability and whether a successful search was performed.
- A news-provider error was converted into a successful empty result. Structured
  provider failures are now retained, with empty results for compatible consumers.
- A malformed independent model review was caught and treated as a passing recheck.
  It now fails the request; API check/review regressions confirm no approval is saved.
- The reader retained its old passing display after a failed quality request.
  It now displays Check unavailable and requires a successful retry before approval.
- Reopening an advisor-edited draft restored the original generation's passing
  quality report. Current quality, including a null/revision-required result, is
  now persisted separately from the original workflow report. Older edited caches
  without that field require rechecking. A revise result disables approval.

Each boundary defect and the UI review-state regressions failed before its fix.

## Historical test repairs

Three stale tests prevented the expanded suite from running cleanly: missing
Path/TemporaryDirectory imports, reliance on a removed global news fixture, and
an ADK scripted model that called only four tools although the catalog has six.
The news-ranking test now supplies controlled eligible/distractor/future articles;
the ADK contract test executes all six catalog tools rather than weakening the
catalog assertion.

## Results

- 132 backend/tool tests and 29 subtests passed with external networking blocked.
- 26 browser scenarios passed against the isolated local workspace, including
  failed-review retry, reopening edited drafts, and an actual PDF download.
- The frontend production build passed; the UI detector reported no findings.
- Existing pytest capture shutdown can emit an OpenTelemetry console-exporter
  closed-stream warning after successful completion. It did not fail a test or
  indicate a product request failure.

The cloud preview was reloaded with the backend fixes while automatic preparation
was paused and no jobs were active. These checks cover the exercised scenarios;
the revised failure branches were verified with controlled failures rather than
additional live provider requests.
