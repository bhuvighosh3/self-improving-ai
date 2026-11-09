# Calendar purpose and saved briefs

The Calendar week previously displayed fixed category colors and a category legend,
then repeated the selected day's events below the grid. The event editor also
required a category even though the advisor had already supplied a title and notes.

Calendar now uses the existing blue theme for every event. Editing and preparation
remain available directly inside each event. The repeated cards and category
selector are removed. Creating an event without a type defaults to `general_meeting`;
editing through the UI omits type, preserving legacy metadata and all other meeting
details. Existing category values remain accepted by the API.

In AI mode, the existing Part B investigator selects a preparation routine from the
meeting focus and authorized client context in its final response. Python validates
the routine and a bounded reason, then supplies the selected checklist to the writer
and saved brief metadata. An absent or unsupported selection uses the general
checklist. Selection is a planning judgment, not evidence of a client fact or complete
coverage. These checklists do not restrict the topics the agent can address. No extra
model call is introduced, and Calendar records are never rewritten by classification.
Offline demonstrations continue using their deterministic preparation path. Previously
saved or resumed completed investigations retain their original snapshots.

Calendar is the sole source of meetings. The Meeting Prep workspace lists only
Calendar event IDs and exposes New meeting through the same event editor as
Calendar. There is no standalone brief form or unlinked-brief group. Copilot's
missing-meeting form explicitly adds the appointment before preparing its brief;
requests with an existing ID must match that appointment. Repeated preparation
for the same event version, mode, focus and cutoff reuses the saved brief. Concurrent
same-slot requests are serialized within the process. Older orphaned drafts remain
archived in SQLite, but do not create appointments or appear in the workspace.

Editing an already prepared/requested Calendar event queues its current version
immediately, including meetings outside the normal 24-hour window and explicit
edits while automatic scanning is paused. Synchronous Copilot generation is also
registered with the monitor, so an edit during generation can enqueue the replacement.
Before saving, the generator rechecks the appointment and mailbox revision. An
obsolete result is rejected. The workspace replaces stale incoming Copilot snapshots
with current preparation; outdated snapshots cannot be newly checked or approved.
Historical drafts and review records remain retained on the server. The product
shows one current preparation entry per Calendar event.

The Edit Event preparation action also submits unsaved changes. Its label becomes
Save & view prep when fields differ, and navigation waits for a successful save.
Calendar preparation links fetch the current normalized appointment rather than
using the previous polling snapshot. Both save-and-open and save-first/immediate-open
have browser regressions, including changed Notes with unchanged date and time.
Check draft validates retained content and references; it does not regenerate from
new Calendar notes, as its tooltip now explains.

Validation: creation, repeated preparation, editing outside the time window, and
editing during generation have offline API regressions. The related 84 tests and
24 subtests pass. Nine mocked desktop/mobile browser checks cover the shared
editor, Calendar visibility, stale Copilot replacement, category removal, and the
absence of orphaned briefs. The frontend build passes and the UI detector reports
no findings. The initial interface checks used the local synthetic workspace. Subsequent
explicitly authorized Firestore and Gemini acceptance passed; see
[the cloud acceptance record](cloud-acceptance-2026-11-09.md).
