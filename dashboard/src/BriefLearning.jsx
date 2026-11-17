/* Extend the incumbent advisor workspace: edit -> feedback -> next preparation.
   Keep learning next to the brief, with concise provenance and reversible preferences.
   Calendar suggestions use the same records, never a separate learning dashboard. */
import React, { useState } from "react";
import { requestJson } from "./connectionRequest";

const reasons = [
  ["concise", "Too long"], ["actions_first", "Highlight open actions"],
  ["more_context", "Missing client context"], ["incorrect", "Inaccurate"], ["other", "Other"],
];

export function LearningSummary({ state, brief, onChange, onError }) {
  const [busy, setBusy] = useState(false);
  const applied = brief.learning?.applied_preferences || [];
  const previous = brief.learning?.previous_feedback || [];
  async function forget(key) {
    setBusy(true);
    try { onChange(await requestJson(`/api/meeting-learning/briefs/${brief.id}/preferences/${key}`, { method: "DELETE" })); }
    catch (err) { onError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="brief-learning no-meeting-print" aria-label="Learning from your feedback">
    <div className="brief-learning-intro"><strong>{applied.length ? "Personalized for this meeting" : "Your feedback shapes the next brief"}</strong>
      <p>{applied.length ? applied.map(item => item.label).join(" · ") + ". Applied from your previous feedback for this client."
        : "Edits and feedback are remembered for this client. One-time facts stay with their original meeting."}</p></div>
    <details className="brief-learning-details"><summary>Feedback & edit history</summary>
      <p>Meeting {brief.meeting_date} · Revision {state?.revision || 1} · Prepared with memory v{brief.learning?.memory_version || 0} · Current memory v{state?.memory_version || 0}</p>
      {previous.length > 0 && <><h4>Considered for this preparation</h4><ul>{previous.map(item => <li key={item.brief_id}>{item.meeting_date}: {item.summary}</li>)}</ul></>}
      <h4>Remembered for future meetings</h4>
      {!state?.preferences.length && <p>No reusable preferences yet. Save edits or leave feedback below.</p>}
      {state?.preferences.map(item => <div className="brief-preference" key={item.key}><span>{item.label}<small>From meeting {item.meeting_start.slice(0, 10)} · {item.reason}</small></span><button className="meeting-btn" disabled={busy} onClick={() => forget(item.key)}>Forget</button></div>)}
      <h4>This brief</h4>
      {!state?.history.length && <p>No edits or feedback recorded yet.</p>}
      <ul>{state?.history.slice(0, 8).map(item => <li key={item.id}>Revision {item.revision}: {item.payload.summary}
        {item.kind === "edit" && <details><summary>View changes</summary>{item.payload.changes.map((change, index) => <p key={index}><strong>{change.section_id} · {change.field}</strong><del>{change.before}</del><ins>{change.after}</ins></p>)}</details>}
      </li>)}</ul>
      <p className="meeting-muted">Client-scoped workspace memory. This demo does not identify individual advisors.</p>
    </details>
  </section>;
}

export function LearningFeedback({ brief, state, disabled, onChange, onError }) {
  const [rating, setRating] = useState("");
  const [reason, setReason] = useState("concise");
  const [note, setNote] = useState("");
  const [followUp, setFollowUp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function submit(event) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      onChange(await requestJson(`/api/meeting-learning/briefs/${brief.id}/feedback`, {
        method: "POST", body: JSON.stringify({ revision: state.revision, rating,
          reason: rating === "needs_work" ? reason : null, note, follow_up: followUp }),
      }));
      setMessage(followUp ? "Feedback saved. Calendar can suggest a follow-up after this meeting."
        : "Feedback saved for future meetings with this client.");
      setRating("");
      window.dispatchEvent(new Event("sia-meeting-learning-changed"));
    } catch (err) { onError(err.message); }
    finally { setBusy(false); }
  }
  return <section id="brief-feedback" className="brief-feedback no-meeting-print" aria-label="Meeting preparation feedback">
    <div><h3>Was this preparation useful?</h3><p>Help the next meeting start better prepared.</p></div>
    <div className="meeting-actions"><button className="meeting-btn" aria-pressed={rating === "helpful"} disabled={disabled || busy || !state} onClick={() => { setRating("helpful"); setFollowUp(state?.feedback?.follow_up || false); }}>Helpful</button>
      <button className="meeting-btn" aria-pressed={rating === "needs_work"} disabled={disabled || busy || !state} onClick={() => { setRating("needs_work"); setFollowUp(state?.feedback?.follow_up || false); }}>Needs improvement</button></div>
    {!rating && state?.feedback && <p className="brief-feedback-saved">Last feedback: {state.feedback.summary}{state.feedback.follow_up ? " · Follow-up requested" : ""}</p>}
    {rating && <form onSubmit={submit} className="brief-feedback-form">
      {rating === "needs_work" && <label>What should improve?<select aria-label="What should improve?" disabled={busy || disabled} value={reason} onChange={event => setReason(event.target.value)}>{reasons.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
      <label>Anything else? <span className="meeting-muted">Optional</span><textarea disabled={busy || disabled} maxLength={1000} rows={2} value={note} onChange={event => setNote(event.target.value)} placeholder="What would help next time?"/></label>
      <label className="brief-learning-check"><input type="checkbox" disabled={busy || disabled} checked={followUp} onChange={event => setFollowUp(event.target.checked)}/>A follow-up meeting is needed</label>
      <p className="meeting-muted">Presentation preferences can guide future briefs. Written comments and factual corrections stay in the feedback history.</p>
      <div className="meeting-actions"><button className="meeting-btn primary" disabled={busy || disabled}>{busy ? "Saving feedback…" : "Save feedback"}</button><button type="button" className="meeting-btn" disabled={busy} onClick={() => setRating("")}>Cancel</button></div>
    </form>}
    {message && <p className="brief-feedback-saved" role="status">{message}</p>}
  </section>;
}
