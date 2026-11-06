---
version: 1
slug: "dashboard-src-calendarprep-jsx"
primary_target: "dashboard/src/CalendarPrep.jsx"
related_targets: ["dashboard/src/MeetingPrepWorkspace.jsx","dashboard/src/CalendarMeeting.jsx","dashboard/src/CalendarEventDialog.jsx","dashboard/src/MeetingReadyDialog.jsx","dashboard/src/calendar-prep.css"]
---

# Calendar and Meeting Prep

Mode: Operate. Audience: a busy wealth advisor with a full working week.
Scope: only Part B's calendar, preparation queue and brief reading/review. Preserve Part A, Part C and their data/logic. Existing DM Sans, neutral surfaces, blue controls and shell are the visual authority.

Calendar owns the schedule: Monday–Friday timed grid, a next-client-meeting strip, synthetic locations/attendees and quiet categories for client/internal/focus/personal events. Thirty-five fixture events across adjacent weeks include twelve client meetings. Only client events trigger preparation. Mobile selects one weekday. Initial scroll stays near demo time or the returned meeting.

Meeting Prep owns the work: a dated client-meeting list (Upcoming/This week, client/topic search) and a selected brief. Ready to review, Preparing, Reviewed, Scheduled and Needs attention describe actual job/local-review states. Future scheduled meetings explain the 24-hour policy and offer deliberate early preparation. Calendar links open their meeting directly. Mobile transitions list-to-detail with All meetings.

A brief opens with meeting context and a sourced-content At a glance summary, then existing edit/check/review/export, six sections and evidence. Review changes synchronously update list, count and detail; edits invalidate review. Manual generation is a secondary Prepare another meeting action; existing Copilot/client entry remains compatible.

One automatic native ready dialog per page visit prevents stacked interruptions; other ready items remain discoverable. Calendar has event detail dialogs, including no-prep explanations for non-client commitments. Demo settings holds mode, pause/resume, advance/reset and replay. Default offline; AI Agent explicitly consumes Gemini quota. Synthetic attribution stays visible. No external calendar/mail or new database integration in this task.

Direction contract: realistic schedule → automatic preparation → one retained brief in the preparation workspace → advisor review. Existing visual world is preserved; no new marketing comp or identity.
