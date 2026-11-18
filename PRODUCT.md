# Wealth Management Copilot

The project is a wealth management advisor copilot with portfolio analysis,
meeting preparation and request orchestration components. Employer demonstrations
use synthetic households, holdings, CRM notes, tasks and market news.

## Meeting Prep extension

An opt-in AI workflow now complements the default deterministic demo. See the
[implementation status](docs/meeting-brief/implementation.md) for the three skills,
evidence/quality pipeline, local versioned review and evaluation entry point.
Descriptions below of no LLM calls refer to Offline demo mode; authenticated
production approval remains outside this implementation. Bounded client-scoped
personalization is implemented as described below; global prompt evolution is not.

Part B helps an advisor prepare for a selected client meeting: specify the client,
New York meeting date/time and focus; generate a structured brief; inspect evidence
and relevant news; edit and review the draft; download a PDF or print it.

The brief covers client overview, recent requests, portfolio highlights, discussion
priorities, open actions and items to confirm. Calculated facts retain references
to the original mock records. Missing facts are explicit. The latest draft and its
review status are restored by brief ID in the current browser. Saved revisions and
exact before/after edit history also persist in local SQLite; editing invalidates
the review.

Copilot offers a second entry to the same generation service. It asks the advisor
to confirm the client, date, time and focus, then displays a summary and opens the
same generated brief in Meeting Prep. Conversation history survives navigation
during the current page session. Local drafts are restored by brief ID so reopening
an older chat result retains its edits without loading another client's draft.

Offline demo mode is deterministic and explicitly labeled as synthetic. It calls
mock tools and makes no LLM or live market requests. The opt-in **AI Agent · Gemini**
mode connects the dashboard to the ADK brief writer and independent model reviewer.
Both modes use the same Meeting Prep surfaces and evidence/review workflow.

## Feedback and client-scoped personalization

The existing **Edit prep → Save changes** flow saves exact before/after field
changes in SQLite and runs the checks automatically. There is no separate
**Check draft** button. Saved edits clear review; failed checks stay visible and
prevent those edits from becoming reusable preferences. An advisor can opt out of
remembering presentation changes. A sufficiently shortened, passing revision can
record the bounded `concise` preference.

**Helpful / Needs improvement** saves immediately in one click. There is no
feedback form, reason selector, comment field or separate save action. A generic
negative rating asks the next preparation to recheck focus and useful questions;
it never invents a specific preference. Earlier structured feedback records remain
readable through the API. Only `concise`, `actions_first` and `more_context` become
reusable presentation preferences.
Free-text comments and factual corrections remain historical records and never
become instructions or reusable client facts. Preferences apply only to later
meetings for the same client in this workspace; they are not isolated by an
authenticated advisor identity.

`MeetingMemoryStore` adapts C's existing `MemoryStore` payload codec and reuses its
versioned adoption, audit and rollback machinery without changing C's business
behavior. Preference metadata records its source brief/feedback, meeting and
reason. Each generated brief records the memory version and applied preferences.
The visible **Personalized for this meeting** summary and **Feedback & edit
history** show what was applied, the version used for generation, current memory,
prior feedback and exact changes. **Forget** removes an active preference through
a new memory version.

New preparation supplies trusted, bounded preference instructions through
`advisor_corrections`. Offline demo mode applies deterministic formatting: concise
correspondence summaries retain linked evidence and caveats; outstanding actions
or recent client context can be promoted into discussion priorities. AI mode
injects the allowlisted preference instructions into the writer. These behaviors
are personalization, not evidence of statistically validated general improvement.
Global prompt evolution and GEPA are not implemented.

After a later meeting's scheduled end, the existing preparation monitor compares
adjacent, checked preparations for the same client. If an originally sourced
open action was absent from the earlier agenda but reappears in the later
preparation, it adds a linked follow-up review to the earlier brief's history and
can adopt the bounded `actions_first` lesson. Original brief text and its reviewed
revision are preserved. The lesson has an availability cutoff at the later
meeting's end; earlier preparations cannot retrieve future lessons. Repeated
scans are idempotent, edited Calendar inputs invalidate the comparison, and a
covered topic does not create a gap lesson. This observes preparation coverage,
not meeting attendance, discussion transcripts or proof an action was completed.

## Calendar follow-up suggestions

Suggested follow-ups stay in Calendar and the existing Meeting Prep workflow.
They require explicit prior feedback requesting a follow-up, or open actions plus
at least three observed meeting additions that establish usable intervals. The
suggestion explains its source. Without a learned scheduling pattern, its proposed
time is described as a starting suggestion rather than learned cadence.

**Review suggestion** opens the existing **Add meeting** dialog with editable
fields. A meeting is added only after confirmation. Accepted, adjusted and
dismissed choices are logged; retrying an accepted suggestion does not create a
duplicate meeting. This adds no separate learning dashboard and changes no A/C
business behavior.

## User commitments

- Preserve the existing dashboard UI style: DM Sans, white/gray surfaces, restrained
  bordered cards, blue actions and the current sidebar.
- All repository code, comments, commit messages, PR descriptions and interface
  copy are English. Collaboration with the user may be in Chinese.
- Keep client-detail entry and the Meeting Prep navigation item easy to find.
- Clearly distinguish synthetic data and advisor edits from original source records.

## Implementation boundaries

The [Meeting Brief architecture](docs/meeting-brief/README.md),
[implementation status](docs/meeting-brief/implementation.md) and
[evaluation design](docs/meeting-brief/evaluation.md) record the staged architecture
and evaluation plans. The implemented personalization scope and limitations are
stated here; authenticated production approval remains future work.

The React/Vite dashboard uses FastAPI. Meeting Prep uses the same mock CRM, news
and holdings tools as the Python agents, with deterministic and opt-in AI paths.
ReportLab renders the edited draft and source index as a PDF. Persistence uses
local files and SQLite; it is not durable cross-instance Cloud Run storage.
There is no authenticated per-advisor isolation.

This extension was previewed locally with the existing synthetic fixture. No
fresh Gemini validation, cloud writes or deployment were performed for this task.
No CRM writes, outreach delivery or transactions are part of this extension.
