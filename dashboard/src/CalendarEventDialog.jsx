import React, { useEffect, useRef } from "react";
import { CalendarSymbol, meetingLabel } from "./calendarFormat";
import { needsPreparation, preparationState } from "./calendarWorkflow";

export default function CalendarEventDialog({ event, data, onClose, onOpenEvent }) {
  const ref = useRef(null);
  const client = needsPreparation(event), state = client && preparationState(data, event);
  useEffect(() => { const dialog = ref.current; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className="meeting-ready-dialog calendar-event-dialog" aria-labelledby="event-detail-title" onCancel={e => { e.preventDefault(); onClose(); }}>
    <button className="meeting-ready-close" aria-label="Close event details" onClick={onClose}><CalendarSymbol name="close"/></button>
    <h2 id="event-detail-title">{event.title}</h2>
    {client && <p className="event-client-name">{event.client_name}</p>}
    <dl className="calendar-event-facts"><div><dt>Type</dt><dd>{({ client: "Client meeting", internal: "Internal meeting", focus: "Focus time", break: "Personal time" })[event.category]}</dd></div><div><dt>When</dt><dd>{meetingLabel(event)}</dd></div><div><dt>Where</dt><dd>{event.location}</dd></div><div><dt>Who</dt><dd>{event.participants.join(", ")}</dd></div></dl>
    <p>{event.description}</p>
    {client ? <><p className={`prep-state state-${state.tone}`}>{state.label}</p><p className="event-prep-explanation">{state.tone === "scheduled" ? "A brief will be prepared 24 hours before this meeting. You can also open preparation now." : "Client context, portfolio highlights and discussion priorities in one meeting brief."}</p><div className="meeting-ready-actions"><button className="meeting-btn primary" onClick={() => onOpenEvent(event)}>View meeting prep<CalendarSymbol name="next" size={15}/></button></div></>
      : <div className="event-no-prep"><CalendarSymbol name="calendar" size={16}/>No client brief needed for this event.</div>}
  </dialog>;
}
