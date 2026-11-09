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

An older manually generated brief may have no matching Calendar appointment. Such
briefs remain under Saved briefs, grouped as “Briefs without a calendar meeting”.
They do not appear as upcoming appointments and do not create new Calendar events.
The previous “Not linked to Calendar” wording described this same situation.

Validation: the new API and scripted ADK regressions failed before the fix; 77
related offline tests and 24 subtests pass afterward. Four mocked desktop/mobile
browser checks cover category removal, uniform colors, retained edit inputs,
absence of duplicated cards, and saved-brief separation. The frontend build passes
and the UI detector reports no findings. Ruff findings in the touched files are
pre-existing; the change adds none. No additional live Gemini call was made.
