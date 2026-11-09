import React, { useEffect, useRef, useState } from "react";
import { requestJson } from "./connectionRequest";
import "./calendar.css";

export default function CalendarEventDialog({ clients, event, defaultDate, selectedClient, onClose, onSaved, onPrepare }) {
  const dialog = useRef(null);
  const [form, setForm] = useState(() => event ? {
    title: event.title, client_id: event.client_id, date: event.date,
    start_time: event.start_time, end_time: event.end_time, location: event.location || "", notes: event.notes || "",
  } : { title: "", client_id: selectedClient?.client_id || "", date: defaultDate || "",
    start_time: "09:00", end_time: "10:00", location: "", notes: "" });
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const title = event ? "Edit Event" : "New Event";
  useEffect(() => { dialog.current.showModal(); }, []);
  const update = (key, value) => setForm(current => ({ ...current, [key]: value }));
  async function save(submission) {
    submission.preventDefault();
    setBusy(true); setError("");
    try {
      const record = await requestJson(event ? `/api/calendar/events/${event.id}` : "/api/calendar/events", {
        method: event ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      onSaved(record);
    } catch (err) { setError(err.message); setBusy(false); }
  }
  async function remove() {
    if (!confirm("Delete this event?")) return;
    setBusy(true); setError("");
    try { await requestJson(`/api/calendar/events/${event.id}`, { method: "DELETE" }); onSaved(null); }
    catch (err) { setError(err.message); setBusy(false); }
  }
  return <dialog ref={dialog} className="cal-modal-dialog" aria-label={title}
    onCancel={e => { if (busy) e.preventDefault(); else onClose(); }}
    onClick={e => { if (e.target === dialog.current && !busy) onClose(); }}>
    <form className="cal-modal" onSubmit={save}>
      <h3>{title}</h3>
      {error && <p className="cal-error" role="alert">{error}</p>}
      <div className="cal-modal-fields">
        <label>Title<input required maxLength={200} disabled={busy} value={form.title} onChange={e => update("title", e.target.value)} placeholder="Meeting title"/></label>
        <label>Client<select aria-label="Client" required disabled={busy} value={form.client_id} onChange={e => update("client_id", e.target.value)}>
          <option value="">Select client…</option>{clients.map(client => <option key={client.client_id} value={client.client_id}>{client.profile?.name || client.client_id}</option>)}
        </select></label>
        <label>Date<input required type="date" disabled={busy} value={form.date} onChange={e => update("date", e.target.value)}/></label>
        <div className="cal-modal-row">
          <label>Start Time<input required type="time" disabled={busy} value={form.start_time} onChange={e => update("start_time", e.target.value)}/></label>
          <label>End Time<input required type="time" disabled={busy} value={form.end_time} onChange={e => update("end_time", e.target.value)}/></label>
        </div>
        <label>Location<input maxLength={200} disabled={busy} value={form.location} onChange={e => update("location", e.target.value)}/></label>
        <label>Notes<textarea maxLength={1000} rows={3} disabled={busy} value={form.notes} onChange={e => update("notes", e.target.value)} placeholder="What should this meeting cover?"/></label>
      </div>
      <div className="cal-modal-actions">
        {onPrepare && <button type="button" className="cal-modal-cancel" disabled={busy} onClick={onPrepare}>Meeting prep</button>}
        {event && <button type="button" className="cal-modal-delete" disabled={busy} onClick={remove}>Delete</button>}
        <button type="button" className="cal-modal-cancel" disabled={busy} onClick={onClose}>Cancel</button>
        <button className="cal-modal-save" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
      </div>
    </form>
  </dialog>;
}
