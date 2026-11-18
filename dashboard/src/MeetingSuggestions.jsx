import React, { useEffect, useState } from "react";
import { requestJson } from "./connectionRequest";

export default function MeetingSuggestions({ onChoose, clientId = null, compact = false, refreshKey = "" }) {
  const [items, setItems] = useState(null), [error, setError] = useState("");
  const [busy, setBusy] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    const load = () => requestJson("/api/meeting-learning/suggestions", { signal: controller.signal })
      .then(result => { setItems(result); setError(""); })
      .catch(err => { if (err.kind !== "cancelled") setError(err.message); });
    load(); window.addEventListener("sia-meeting-learning-changed", load);
    return () => { controller.abort(); window.removeEventListener("sia-meeting-learning-changed", load); };
  }, [refreshKey]);
  async function dismiss(id) {
    setBusy(id);
    try {
      await requestJson(`/api/meeting-learning/suggestions/${id}/dismiss`, { method: "POST" });
      setItems(current => current.filter(item => item.id !== id));
    } catch (err) { setError(err.message); }
    finally { setBusy(null); }
  }
  const visible = (items || []).filter(item => !clientId || item.client_id === clientId);
  if (compact && !error && !visible.length) return null;
  return <section className="meeting-suggestions" aria-label="Suggested follow-up meetings">
    <h3>Suggested follow-ups</h3>
    <p>Based on previous meeting feedback and your scheduling choices. Added only when you confirm.</p>
    {error && <p className="meeting-error" role="alert">{error}</p>}
    {!items && !error && <p role="status">Looking for follow-ups…</p>}
    {items && !visible.length && <p className="meeting-muted">No follow-ups suggested yet. Mark “A follow-up meeting is needed” in a brief’s feedback to give the agent a starting point.</p>}
    {visible.slice(0, compact ? 2 : 5).map(item => <div className="meeting-suggestion" key={item.id}>
      <div><strong>{item.event.title}</strong><p>{item.reason}</p><small>{item.event.date} · {item.event.start_time}–{item.event.end_time} · New York</small></div>
      <div className="meeting-actions"><button type="button" className="meeting-btn primary" disabled={busy === item.id} onClick={() => onChoose(item)}>Review suggestion</button><button type="button" className="meeting-btn" disabled={busy === item.id} onClick={() => dismiss(item.id)}>Dismiss</button></div>
    </div>)}
  </section>;
}
