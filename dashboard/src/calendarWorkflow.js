import { loadMeetingDraft } from "./meetingDraftStore";
import { addDays, dateKey } from "./calendarFormat";

export const needsPreparation = event => event.prep_required ?? Boolean(event.client_id);
export function eventJob(data, event) {
  const jobs = (data?.preparations || []).filter(job => job.event_id === event.id && job.version === event.version);
  return jobs.filter(job => job.status === "ready").sort((a, b) => new Date(b.generated_at || 0) - new Date(a.generated_at || 0))[0]
    || jobs.find(job => job.mode === data.mode);
}
export function preparationState(data, event) {
  const job = eventJob(data, event);
  const cached = job?.brief_id ? loadMeetingDraft(job.brief_id) : null;
  if (job?.status === "ready") return (cached ? cached.reviewedAt : job.review_status === "approve")
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
  return [...(data?.events || [])].filter(needsPreparation).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
}
