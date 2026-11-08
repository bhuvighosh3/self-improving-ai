import React, { useState } from "react";
import { CalendarSymbol, dayLabel, dateKey } from "./calendarFormat";

export default function PreparationControls({ data, command: sendCommand, onReplay }) {
  const [busy, setBusy] = useState(false);
  async function command(action, mode) {
    setBusy(true);
    try { await sendCommand(action, mode); } finally { setBusy(false); }
  }
  const ready = data?.preparations.filter(job => job.status === "ready" && job.mode === data.mode && data.events.some(event => event.id === job.event_id && event.version === job.version && new Date(event.starts_at) > new Date(data.now))) || [];
  return <details className="calendar-demo-settings">
    <summary><CalendarSymbol name="settings" size={15}/>Demo settings</summary>
    <div className="calendar-settings-panel">
      <h3>Presentation controls</h3>
      <p>Calendar and Inbox share {data?.storage === "firestore" ? "the configured Firestore database" : "local demo storage"}. This demo does not send external email.</p>
      {data && <>
        <p>Demo time: {dayLabel(dateKey(data.now), { month: "short", day: "numeric", year: "numeric" })}, {new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" }).format(new Date(data.now))}</p>
        <p>Gemini requests use the configured API quota.</p>
        <div className="calendar-demo-actions">
          <button disabled={busy} onClick={() => command(data.enabled ? "pause" : "start")}>{data.enabled ? "Pause automatic prep" : "Resume automatic prep"}</button>
          <button disabled={busy || data.processing} onClick={() => command("advance")}>Advance demo day</button>
          <button disabled={busy || data.processing} onClick={() => command("reset")}>Reset prep demo</button>
          <button disabled={!ready.length} onClick={() => onReplay(ready[0])}>Replay ready notice</button>
        </div>
      </>}
    </div>
  </details>;
}
