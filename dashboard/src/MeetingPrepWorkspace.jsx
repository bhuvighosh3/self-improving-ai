import React, { useEffect, useRef, useState } from "react";
import useCalendar from "./useCalendar";
import CalendarMeeting from "./CalendarMeeting";
import MeetingPrep from "./MeetingPrep";
import { addDays, CalendarSymbol, dateKey, dayLabel, meetingLabel, weekStart } from "./calendarFormat";
import { clientMeetings, preparationState, relativeDay } from "./calendarWorkflow";

export default function MeetingPrepWorkspace({ clients, initialEvent, onBackToCalendar, onOpened }) {
  const { data, error } = useCalendar();
  const [selection, setSelection] = useState(initialEvent?.id || null);
  const [showDetail, setShowDetail] = useState(Boolean(initialEvent) || window.matchMedia("(min-width: 769px)").matches);
  const [manualOpen, setManualOpen] = useState(false), [manualStarted, setManualStarted] = useState(false);
  const manualHeading = useRef(null);
  useEffect(() => {
    if (manualOpen && showDetail) manualHeading.current?.focus();
  }, [manualOpen, showDetail]);
  const [range, setRange] = useState("upcoming"), [search, setSearch] = useState("");
  if (!data) return <section className="prep-hub"><h2>Meeting Prep</h2>{error ? <p className="meeting-error" role="alert">{error}</p> : <div className="prep-loading" role="status">Loading your meeting briefs…</div>}</section>;
  const all = clientMeetings(data), monday = weekStart(data.now);
  const upcoming = all.filter(event => new Date(event.starts_at) > new Date(data.now));
  const visible = all.filter(event => range === "upcoming" ? new Date(event.starts_at) > new Date(data.now)
    : dateKey(event.starts_at) >= monday && dateKey(event.starts_at) < addDays(monday, 5))
    .filter(event => `${event.client_name} ${event.title}`.toLowerCase().includes(search.toLowerCase()));
  const selected = all.find(event => event.id === selection) || upcoming.find(event => preparationState(data, event).tone === "ready") || upcoming[0];
  const ready = upcoming.filter(event => preparationState(data, event).tone === "ready").length;
  const groups = [...new Set(visible.map(event => dateKey(event.starts_at)))];
  function select(event) { setManualOpen(false); setSelection(event.id); setShowDetail(true); }
  function openManual() { setManualStarted(true); setManualOpen(true); setShowDetail(true); }
  function cancelManual() { setManualOpen(false); setShowDetail(window.matchMedia("(min-width: 769px)").matches); }
  return <section className={`prep-hub ${showDetail ? "is-detail-open" : ""}`} aria-label="Meeting preparation workspace">
    <header className="prep-hub-heading"><div><h2>Meeting Prep</h2><p>{ready ? `${ready} ${ready === 1 ? "brief is" : "briefs are"} ready for your review.` : "Your client meetings and their preparation, together."} {data.enabled ? "Briefs are prepared 24 hours before each client meeting." : "Automatic preparation is paused. Existing briefs remain available."}</p></div><button className="meeting-btn" onClick={() => onBackToCalendar(selected)}><CalendarSymbol size={15}/>Calendar</button></header>
    {error && <p className="meeting-error" role="alert">{error}</p>}
    <div className="prep-hub-layout">
      <aside className="prep-meeting-list" aria-label="Client meetings">
        <div className="prep-list-tools"><h3>Your meetings</h3><label className="prep-search"><CalendarSymbol name="search" size={16}/><input aria-label="Search client meetings" placeholder="Search client or meeting" value={search} onChange={event => setSearch(event.target.value)}/></label>
          <div className="prep-list-tabs" aria-label="Meeting range"><button aria-pressed={range === "upcoming"} onClick={() => setRange("upcoming")}>Upcoming</button><button aria-pressed={range === "week"} onClick={() => setRange("week")}>This week</button></div>
        </div>
        <div className="prep-list-scroll">{groups.map(day => <section key={day} className="prep-date-group"><h4>{relativeDay({ starts_at: `${day}T12:00:00-05:00` }, data.now) || dayLabel(day, { weekday: "short", month: "short", day: "numeric" })}</h4>{visible.filter(event => dateKey(event.starts_at) === day).map(event => {
          const state = preparationState(data, event);
          return <button className={`prep-meeting-row ${!manualOpen && selected?.id === event.id ? "is-selected" : ""}`} key={event.id} aria-label={`Open preparation for ${event.client_name} on ${dateKey(event.starts_at)}`} aria-pressed={!manualOpen && selected?.id === event.id} onClick={() => select(event)}>
            <span className="prep-row-time">{new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" }).format(new Date(event.starts_at))}</span><strong>{event.client_name}</strong><span className="prep-row-topic">{event.title}</span><span className={`prep-state state-${state.tone}`}>{state.label}</span><CalendarSymbol name="next" size={14}/>
          </button>;
        })}</section>)}{!visible.length && <div className="prep-no-results"><h4>No matching meetings</h4><p>{search ? "Try another client or clear your search." : "Choose This week to see recent client meetings, or return to Calendar."}</p>{search && <button className="meeting-btn" onClick={() => setSearch("")}>Clear search</button>}</div>}</div>
        <button className="prep-manual-link" aria-pressed={manualOpen} onClick={openManual}><CalendarSymbol name="plus" size={15}/>Prepare another meeting</button>
      </aside>
      <div className="prep-detail">
        <button className="calendar-back prep-mobile-back" onClick={() => setShowDetail(false)}><CalendarSymbol name="previous" size={14}/>All meetings</button>
        {manualStarted && <section className="prep-manual-panel" aria-label="Prepare another meeting" hidden={!manualOpen || !showDetail}>
          <header className="prep-manual-heading"><h3 ref={manualHeading} tabIndex={-1}>Prepare another meeting</h3><button className="meeting-btn" onClick={cancelManual}>Cancel</button></header>
          <MeetingPrep clients={clients} freshDraft embedded defaultMode={data.mode} defaultDate={addDays(dateKey(data.now), 1)}/>
        </section>}
        <div key={selected?.id || "empty"} hidden={manualOpen}>
        {selected && showDetail && !manualOpen ? <PreparationDetail autoOpen={initialEvent?.id === selected.id} event={selected} data={data} clients={clients} onBackToCalendar={() => onBackToCalendar(selected)} onOpened={onOpened}/>
          : <div className="prep-scheduled"><CalendarSymbol name="calendar" size={30}/><h3>Your next meeting will appear here</h3><p>Client meetings on Calendar receive a brief 24 hours before they start.</p><button className="meeting-btn" onClick={() => onBackToCalendar(selected)}>View calendar</button></div>}
        </div>
      </div>
    </div>
  </section>;
}

function PreparationDetail({ event, data, clients, onBackToCalendar, onOpened, autoOpen }) {
  const [prepareNow, setPrepareNow] = useState(false);
  const state = preparationState(data, event);
  if (state.job || prepareNow || autoOpen) return <CalendarMeeting key={event.id} event={event} clients={clients} onBack={onBackToCalendar} onOpened={onOpened}/>;
  return <section className="prep-scheduled" aria-label="Scheduled preparation"><CalendarSymbol name="document" size={30}/><span className="prep-state state-scheduled">{state.label}</span><h3>{event.client_name}</h3><h4>{event.title}</h4><p>{meetingLabel(event)}</p><p>{event.focus}</p><div className="prep-scheduled-note">{state.tone === "past" ? "This meeting has passed. You can still prepare a brief from the available client records." : `Your brief will be prepared automatically 24 hours before this meeting${data.enabled ? "." : " when automatic prep resumes."}`}</div><button className="meeting-btn primary" onClick={() => setPrepareNow(true)}>Prepare {state.tone === "past" ? "brief" : "early"}<CalendarSymbol name="next" size={14}/></button>{data.mode === "agent" && <p className="meeting-muted">Uses the configured Gemini API quota.</p>}</section>;
}
