import React, { useState } from "react";

export default function CopilotMeetingForm({ details, clients, busy, onGenerate, onLookup, resolution, choices = [] }) {
  const [fields, setFields] = useState({ mode: "agent", ...details });
  const update = (field, value) => setFields(current => ({ ...current, [field]: value }));
  if (resolution === "multiple_meetings") return <div className="co-meeting-form co-meeting-choices">
    {choices.map(({ title, ...meeting }) => <button className="meeting-btn" key={meeting.calendar_event_id} disabled={busy} onClick={() => onGenerate(meeting)}>
      <span>{title}<small>{meeting.meeting_date} at {meeting.meeting_time} · New York</small></span><span>Prepare this meeting</span>
    </button>)}
  </div>;
  if (resolution === "client_required") return <form className="co-meeting-form" onSubmit={event => { event.preventDefault(); onLookup(fields.client_id); }}>
    <div className="meeting-fields">
      <label>Client<select aria-label="Client" required value={fields.client_id} disabled={busy} onChange={event => update("client_id", event.target.value)}>
        <option value="">Select a client</option>
        {clients.map(client => <option key={client.client_id} value={client.client_id}>{client.profile.name}</option>)}
      </select></label>
      <button type="submit" className="meeting-btn primary" disabled={busy || !fields.client_id}>{busy ? "Finding your meeting…" : "Find next meeting"}</button>
    </div>
  </form>;
  return (
    <form className="co-meeting-form" onSubmit={event => { event.preventDefault(); onGenerate(fields); }}>
      <div className="meeting-fields">
        <label>Client<select aria-label="Client" required value={fields.client_id} disabled={busy} onChange={event => update("client_id", event.target.value)}>
          <option value="">Select a client</option>
          {clients.map(client => <option key={client.client_id} value={client.client_id}>{client.profile.name}</option>)}
        </select></label>
        <label>Meeting date<input required type="date" value={fields.meeting_date} disabled={busy} onChange={event => update("meeting_date", event.target.value)} /></label>
        <label>Time · New York<input required type="time" value={fields.meeting_time} disabled={busy} onChange={event => update("meeting_time", event.target.value)} /></label>
        <label className="meeting-focus">Meeting focus<input required minLength={3} maxLength={500} value={fields.focus} disabled={busy} placeholder="What should this meeting focus on?" onChange={event => update("focus", event.target.value)} /></label>
        <button type="submit" className="meeting-btn primary" disabled={busy}>{busy ? "Preparing brief…" : fields.calendar_event_id ? "Prepare meeting" : "Add to Calendar & prepare"}</button>
      </div>
    </form>
  );
}
