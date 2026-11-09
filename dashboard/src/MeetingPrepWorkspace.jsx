import React, { useEffect, useRef, useState } from "react";
import useCalendar from "./useCalendar";
import CalendarMeeting from "./CalendarMeeting";
import CalendarEventDialog from "./CalendarEventDialog";
import MeetingPrep from "./MeetingPrep";
import { addDays, CalendarSymbol, dateKey, dayLabel, meetingLabel } from "./calendarFormat";
import { clientMeetings, preparationState, relativeDay } from "./calendarWorkflow";

export default function MeetingPrepWorkspace({ clients, initialEvent, incomingBrief, selectedClient, onBackToCalendar, onOpened }) {
  const { data, error, refresh } = useCalendar();
  const [selection, setSelection] = useState(incomingBrief?.calendar_event?.id || initialEvent?.id || null);
  const [showDetail, setShowDetail] = useState(Boolean(initialEvent || incomingBrief || selectedClient) || window.matchMedia("(min-width: 769px)").matches);
  const [creating, setCreating] = useState(false);
  const selectedRow = useRef(null), opened = useRef(onOpened);
  opened.current = onOpened;
  const [range, setRange] = useState(incomingBrief ? "saved" : "upcoming"), [search, setSearch] = useState(selectedClient?.profile?.name || "");
  const incomingJobId = data?.preparations.find(job => job.brief_id === incomingBrief?.id)?.id;
  useEffect(() => { if (incomingJobId) opened.current?.(incomingJobId); }, [incomingJobId]);
  useEffect(() => {
    if ((window.matchMedia("(min-width: 769px)").matches || !showDetail)) {
      selectedRow.current?.scrollIntoView({ block: "nearest" });
    }
  }, [Boolean(data), selection, range, showDetail]);
  if (!data) return <section className="prep-hub"><h2>Meeting Prep</h2>{error ? <p className="meeting-error" role="alert">{error}</p> : <div className="prep-loading" role="status">Loading your meeting briefs…</div>}</section>;
  const all = clientMeetings(data);
  const incomingEvent = incomingBrief && (all.find(event => event.id === incomingBrief.calendar_event?.id)
    || all.find(event => event.client_id === incomingBrief.client_id && dateKey(event.starts_at) === incomingBrief.meeting_date && event.start_time?.slice(0,5) === incomingBrief.meeting_time?.slice(0,5)));
  const scheduled = all;
  const upcoming = scheduled.filter(event => new Date(event.starts_at) > new Date(data.now));
  const rangeEvents = range === "saved" ? all.filter(event => preparationState(data, event).job)
    : range === "upcoming" ? upcoming
    : scheduled;
  const visible = rangeEvents.filter(event => `${event.client_name} ${event.title}`.toLowerCase().includes(search.toLowerCase()));
  const selected = visible.find(event => event.id === selection) || visible.find(event => event.id === incomingEvent?.id)
    || visible.find(event => event.client_id === selectedClient?.client_id)
    || visible.find(event => preparationState(data, event).tone === "ready") || visible[0];
  const ready = (range === "saved" ? rangeEvents : upcoming).filter(event => preparationState(data, event).tone === "ready").length;
  const groupKey = event => dateKey(event.starts_at);
  const groups = [...new Set(visible.map(groupKey))];
  const incomingIsCurrent = incomingBrief?.calendar_event?.version === selected?.version;
  function select(event) { setSelection(event.id); setShowDetail(true); }
  async function added(event) {
    setCreating(false);
    if (!event) return;
    setSelection(event.id); setRange("all"); setSearch(""); setShowDetail(true);
    await refresh();
  }
  return <section className={`prep-hub ${showDetail ? "is-detail-open" : ""}`} aria-label="Meeting preparation workspace">
    <header className="prep-hub-heading"><div><h2>Meeting Prep</h2><p>{ready ? `${ready} ${ready === 1 ? "brief is" : "briefs are"} ready for your review.` : "Your client meetings and their preparation, together."} {range !== "saved" && (data.enabled ? "Briefs are prepared 24 hours before each client meeting." : "Automatic preparation is paused. Existing briefs remain available.")}</p></div><button className="meeting-btn" onClick={() => onBackToCalendar(selected)}><CalendarSymbol size={15}/>Calendar</button></header>
    {error && <p className="meeting-error" role="alert">{error}</p>}
    <div className="prep-hub-layout">
      <aside className="prep-meeting-list" aria-label="Client meetings">
        <div className="prep-list-tools"><h3>Your meetings</h3><label className="prep-search"><CalendarSymbol name="search" size={16}/><input aria-label="Search client meetings" placeholder="Search client or meeting" value={search} onChange={event => setSearch(event.target.value)}/></label>
          <div className="prep-list-tabs" aria-label="Meeting range"><button aria-pressed={range === "upcoming"} onClick={() => setRange("upcoming")}>Upcoming</button><button aria-pressed={range === "all"} onClick={() => setRange("all")}>All meetings</button><button aria-pressed={range === "saved"} onClick={() => setRange("saved")}>Saved briefs</button></div>
        </div>
        <div className="prep-list-scroll">{groups.map(day => <section key={day} className="prep-date-group"><h4>{relativeDay({ starts_at: `${day}T12:00:00-05:00` }, data.now) || dayLabel(day, { weekday: "short", month: "short", day: "numeric" })}</h4>{visible.filter(event => groupKey(event) === day).map(event => {
          const state = preparationState(data, event);
          return <button ref={selected?.id === event.id ? selectedRow : null} className={`prep-meeting-row ${selected?.id === event.id ? "is-selected" : ""}`} key={event.id} aria-label={`Open preparation for ${event.client_name} on ${dateKey(event.starts_at)}`} aria-pressed={selected?.id === event.id} onClick={() => select(event)}>
            <span className="prep-row-time">{new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" }).format(new Date(event.starts_at))}</span><strong>{event.client_name}</strong><span className="prep-row-topic">{event.title}</span><span className={`prep-state state-${state.tone}`}>{state.label}</span><CalendarSymbol name="next" size={14}/>
          </button>;
        })}</section>)}{!visible.length && <div className="prep-no-results"><h4>No matching meetings</h4><p>{search ? "Try another client or clear your search." : "Choose All meetings or add a meeting to your calendar."}</p>{search && <button className="meeting-btn" onClick={() => setSearch("")}>Clear search</button>}</div>}</div>
        <button className="prep-new-meeting" onClick={() => setCreating(true)}><CalendarSymbol name="plus" size={15}/>New meeting</button>
      </aside>
      <div className="prep-detail">
        <button className="calendar-back prep-mobile-back" onClick={() => setShowDetail(false)}><CalendarSymbol name="previous" size={14}/>All meetings</button>
        <div key={selected?.id || "empty"}>
        {selected && showDetail ? incomingBrief && incomingIsCurrent && incomingEvent?.id === selected.id
          ? <MeetingPrep key={incomingBrief.id} clients={clients} incomingBrief={incomingBrief} calendarEvent={selected} onBackToCalendar={() => onBackToCalendar(selected)}/>
          : <PreparationDetail autoOpen={initialEvent?.id === selected.id} event={selected} data={data} clients={clients} onBackToCalendar={() => onBackToCalendar(selected)} onOpened={onOpened}/>
          : <div className="prep-scheduled"><CalendarSymbol name="calendar" size={30}/><h3>Your next meeting will appear here</h3><p>Client meetings on Calendar receive a brief 24 hours before they start.</p><button className="meeting-btn" onClick={() => onBackToCalendar(selected)}>View calendar</button></div>}
        </div>
      </div>
    </div>
    {creating && <CalendarEventDialog clients={clients} selectedClient={selectedClient} defaultDate={addDays(dateKey(data.now), 1)}
      onClose={() => setCreating(false)} onSaved={added}/>}
  </section>;
}

function PreparationDetail({ event, data, clients, onBackToCalendar, onOpened, autoOpen }) {
  const [prepareNow, setPrepareNow] = useState(false);
  const state = preparationState(data, event);
  if (state.job || prepareNow || autoOpen) return <CalendarMeeting key={`${event.id}:${event.version}:${state.job?.brief_id || ""}`} event={event} preparation={state.job} clients={clients} onBack={onBackToCalendar} onOpened={onOpened}/>;
  return <section className="prep-scheduled" aria-label="Scheduled preparation"><CalendarSymbol name="document" size={30}/><span className="prep-state state-scheduled">{state.label}</span><h3>{event.client_name}</h3><h4>{event.title}</h4><p>{meetingLabel(event)}</p><p>{event.focus}</p><div className="prep-scheduled-note">{state.tone === "past" ? "This meeting has passed. You can still prepare a brief from the available client records." : `Your brief will be prepared automatically 24 hours before this meeting${data.enabled ? "." : " when automatic prep resumes."}`}</div><button className="meeting-btn primary" onClick={() => setPrepareNow(true)}>Prepare {state.tone === "past" ? "brief" : "early"}<CalendarSymbol name="next" size={14}/></button>{data.mode === "agent" && <p className="meeting-muted">Uses the configured Gemini API quota.</p>}</section>;
}
