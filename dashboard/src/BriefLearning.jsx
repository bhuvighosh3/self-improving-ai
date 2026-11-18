/* Extend the incumbent advisor workspace: edit -> feedback -> next preparation.
   Keep learning next to the brief, with concise provenance and reversible preferences.
   Calendar suggestions use the same records, never a separate learning dashboard. */
import React, { useState } from "react";
import { requestJson } from "./connectionRequest";

export function LearningSummary({ state, brief, onChange, onError }) {
  const [busy, setBusy] = useState(false);
  const applied = brief.learning?.applied_preferences || [];
  const previous = brief.learning?.previous_feedback || [];
  const retrospective = state?.history.find(item => item.kind === "retrospective");
  async function forget(key) {
    setBusy(true);
    try { onChange(await requestJson(`/api/meeting-learning/briefs/${brief.id}/preferences/${key}`, { method: "DELETE" })); }
    catch (err) { onError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="brief-learning no-meeting-print" aria-label="Learning from your feedback">
    <div className="brief-learning-intro"><strong>{applied.length ? "Personalized for this meeting" : "Your feedback shapes the next brief"}</strong>
      <p>{applied.length ? applied.map(item => item.label).join(" · ") + ". Applied from previous meetings and feedback for this client."
        : "Edits and feedback are remembered for this client. One-time facts stay with their original meeting."}</p></div>
    {retrospective && <p><strong>Learned from a later meeting:</strong> {retrospective.payload.summary}</p>}
    <details className="brief-learning-details"><summary>Feedback & edit history</summary>
      <p>Meeting {brief.meeting_date} · Revision {state?.revision || 1} · Prepared with memory v{brief.learning?.memory_version || 0} · Current memory v{state?.memory_version || 0}</p>
      {previous.length > 0 && <><h4>Considered for this preparation</h4><ul>{previous.map(item => <li key={item.brief_id}>{item.meeting_date}: {item.summary}</li>)}</ul></>}
      <h4>Remembered for future meetings</h4>
      {!state?.preferences.length && <p>No reusable preferences yet. Save edits or leave feedback below.</p>}
      {state?.preferences.map(item => <div className="brief-preference" key={item.key}><span>{item.label}<small>From meeting {item.meeting_start.slice(0, 10)} · {item.reason}</small></span><button className="meeting-btn" disabled={busy} onClick={() => forget(item.key)}>Forget</button></div>)}
      <h4>This brief</h4>
      {!state?.history.length && <p>No edits or feedback recorded yet.</p>}
      <ul>{state?.history.slice(0, 8).map(item => <li key={item.id}>Revision {item.revision}: {item.payload.summary}
        {item.kind === "retrospective" && <p>Follow-up review after {item.payload.later_meeting_date}. Used to improve future preparation.</p>}
        {item.kind === "edit" && <details><summary>View changes</summary>{item.payload.changes.map((change, index) => <p key={index}><strong>{change.section_id} · {change.field}</strong><del>{change.before}</del><ins>{change.after}</ins></p>)}</details>}
      </li>)}</ul>
      <p className="meeting-muted">Client-scoped workspace memory. This demo does not identify individual advisors.</p>
    </details>
  </section>;
}

export function LearningFeedback({ brief, state, disabled, onChange }) {
  const [pending, setPending] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const rating = state?.feedback?.rating;
  const current = state?.feedback?.revision === state?.revision;
  async function rate(value) {
    if (pending || disabled || !state) return;
    setPending(value); setMessage(""); setError("");
    try {
      onChange(await requestJson(`/api/meeting-learning/briefs/${brief.id}/feedback`, {
        method: "POST", body: JSON.stringify({ revision: state.revision, rating: value }),
      }));
      setMessage("Feedback saved");
      window.dispatchEvent(new Event("sia-meeting-learning-changed"));
    } catch (err) { setError(err.message); }
    finally { setPending(null); }
  }
  return <section id="brief-feedback" className="brief-feedback no-meeting-print" aria-label="Meeting preparation feedback" aria-busy={Boolean(pending)}>
    <h3>Was this prep helpful?</h3>
    <div className="meeting-actions">
      <button type="button" className="meeting-btn" aria-pressed={Boolean(current && rating === "helpful")} disabled={disabled || Boolean(pending) || !state} onClick={() => rate("helpful")}>{pending === "helpful" ? "Saving…" : "Helpful"}</button>
      <button type="button" className="meeting-btn" aria-pressed={Boolean(current && rating === "needs_work")} disabled={disabled || Boolean(pending) || !state} onClick={() => rate("needs_work")}>{pending === "needs_work" ? "Saving…" : "Needs improvement"}</button>
      <span className={error ? "meeting-error" : "brief-feedback-saved"} role={error ? "alert" : "status"}>{error || message || (current && rating ? "Feedback saved" : "")}</span>
    </div>
  </section>;
}
