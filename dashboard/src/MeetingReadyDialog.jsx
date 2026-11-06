import React, { useEffect, useRef } from "react";
import { CalendarSymbol, meetingLabel } from "./calendarFormat";

export default function MeetingReadyDialog({ event, onView, onDismiss }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);
  return <dialog ref={dialog} className="meeting-ready-dialog" aria-labelledby="meeting-ready-title"
    aria-describedby="meeting-ready-description" onCancel={e => { e.preventDefault(); onDismiss(); }}>
    <button className="meeting-ready-close" aria-label="Dismiss meeting preparation notice" onClick={onDismiss}><CalendarSymbol name="close"/></button>
    <div className="meeting-ready-symbol"><CalendarSymbol name="document" size={28}/></div>
    <h2 id="meeting-ready-title">Your brief for {event.client_name} is ready</h2>
    <div className="meeting-ready-appointment"><strong>{event.title}</strong><span>{meetingLabel(event)}</span></div>
    <p id="meeting-ready-description">Your client context, portfolio snapshot and discussion priorities are prepared for this meeting.</p>
    <div className="meeting-ready-actions"><button className="meeting-btn" onClick={onDismiss}>Later</button><button autoFocus className="meeting-btn primary" onClick={() => onView(event)}>View meeting prep<CalendarSymbol name="next" size={16}/></button></div>
  </dialog>;
}
