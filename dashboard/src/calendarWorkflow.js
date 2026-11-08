import { loadMeetingDraft } from "./meetingDraftStore";
import { addDays, dateKey } from "./calendarFormat";

export const needsPreparation = event => event.prep_required ?? Boolean(event.client_id);
export const eventJob = (data, event) => data?.preparations.find(job => job.event_id === event.id && job.version === event.version && job.mode === data.mode);
export function preparationState(data, event) {
  const job = eventJob(data, event);
  if (job?.status === "ready") return loadMeetingDraft(job.brief_id)?.reviewedAt
    ? { label: "Reviewed", tone: "reviewed", job }
    : { label: "Ready to review", tone: "ready", job };
  if (job?.status === "failed") return { label: "Needs attention", tone: "failed", job };
  if (job) return { label: "Preparing", tone: "preparing", job };
  if (new Date(event.starts_at) <= new Date(data.now)) return { label: "Past meeting", tone: "past" };
  return { label: "Scheduled", tone: "scheduled" };
}
export function relativeDay(event, now) {
  const day = dateKey(event.starts_at), today = dateKey(now);
  return day === today ? "Today" : day === addDays(today, 1) ? "Tomorrow" : null;
}
export function clientMeetings(data) {
  return (data?.events || []).filter(needsPreparation).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
}
