import React, { useEffect, useRef, useState } from "react";
import { requestJson } from "./connectionRequest";
import { CalendarSymbol, meetingLabel } from "./calendarFormat";
import MeetingPrep from "./MeetingPrep";

export default function CalendarMeeting({ event, clients, onBack, onOpened }) {
  const [brief, setBrief] = useState(null), [job, setJob] = useState(null);
  const [error, setError] = useState(""), [retry, setRetry] = useState(0);
  const opened = useRef(onOpened);
  opened.current = onOpened;
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function load() {
      try {
        const preparation = await requestJson(`/api/meeting-preparations/events/${event.id}`, {
          method: "POST", signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setJob(preparation);
        if (preparation.status === "ready") {
          const result = await requestJson(`/api/meeting-preparations/${preparation.id}/brief`, { signal: controller.signal });
          if (!controller.signal.aborted) { setBrief(result); setError(""); opened.current(preparation.id); }
        } else if (preparation.status === "failed") {
          setError(preparation.error || "The meeting brief could not be prepared. Please retry.");
        } else timer = setTimeout(load, 1000);
      } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    }
    load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [event.id, retry]);

  async function retryPreparation() {
    setError("");
    try {
      if (job?.status === "failed") await requestJson(`/api/meeting-preparations/${job.id}/retry`, { method: "POST" });
      setRetry(value => value + 1);
    } catch (err) { setError(err.message); }
  }
  if (brief) return <MeetingPrep key={brief.id} clients={clients} incomingBrief={brief} calendarEvent={event} onBackToCalendar={onBack}/>;
  return <section className="calendar-meeting-loading">
    <button className="calendar-back" onClick={onBack}><CalendarSymbol name="previous" size={16}/>Back to calendar</button>
    <div className="calendar-preparing-content"><CalendarSymbol name="document" size={32}/><h2>{event.client_name}</h2><p>{event.title}</p><p>{meetingLabel(event)}</p>
      {error ? <><p className="meeting-error" role="alert">{error}</p><button className="meeting-btn primary" onClick={retryPreparation}>Retry preparation</button></>
        : <div role="status"><h3>Preparing your meeting brief</h3><p>We’re bringing together the client’s updates, portfolio and discussion priorities.</p></div>}
    </div>
  </section>;
}
