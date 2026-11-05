# Wealth Management Copilot

The project is a wealth management advisor copilot with portfolio analysis,
meeting preparation and request orchestration components. Employer demonstrations
use synthetic households, holdings, CRM notes, tasks and market news.

## Meeting Prep extension

An opt-in AI workflow now complements the default deterministic demo. See the
[implementation status](docs/meeting-brief/implementation.md) for the three skills,
evidence/quality pipeline, local versioned review and evaluation entry point.
Descriptions below of no LLM calls refer to Offline demo mode; authenticated
production approval and self-improvement are still outside this implementation.

Part B helps an advisor prepare for a selected client meeting: specify the client,
New York meeting date/time and focus; generate a structured brief; inspect evidence
and relevant news; edit and review the draft; download a PDF or print it.

The brief covers client overview, recent requests, portfolio highlights, discussion
priorities, open actions and items to confirm. Calculated facts retain references
to the original mock records. Missing facts are explicit. The latest draft and its
review status persist in the current browser; editing invalidates the review.

Copilot offers a second entry to the same generation service. It asks the advisor
to confirm the client, date, time and focus, then displays a summary and opens the
same generated brief in Meeting Prep. Conversation history survives navigation
during the current page session. Local drafts are restored by brief ID so reopening
an older chat result retains its edits without loading another client's draft.

The dashboard workflow is deterministic and explicitly labeled as a synthetic
demo. It calls mock tools and makes no LLM or live market requests. The repository's
separate Google ADK agent is not connected to this dashboard workflow. Self-improvement
is outside the scope of this extension.

## User commitments

- Preserve the existing dashboard UI style: DM Sans, white/gray surfaces, restrained
  bordered cards, blue actions and the current sidebar.
- All repository code, comments, commit messages, PR descriptions and interface
  copy are English. Collaboration with the user may be in Chinese.
- Keep client-detail entry and the Meeting Prep navigation item easy to find.
- Clearly distinguish synthetic data and advisor edits from original source records.

## Implementation boundaries

The proposed next-stage [Meeting Brief architecture](docs/meeting-brief/README.md)
and [evaluation design](docs/meeting-brief/evaluation.md) distinguish existing
features from planned skills, temporal comparisons, independent checks and
authenticated approval. They do not change the current demo boundaries below.

The React/Vite dashboard uses FastAPI. Meeting Prep uses the same mock CRM, news
and holdings tools as the Python agents, with a dedicated deterministic service.
ReportLab renders the edited draft and source index as a PDF. No CRM writes,
outreach delivery, transactions or deployment are part of this extension.
