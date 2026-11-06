import React, { useEffect, useRef, useState } from "react";
import useCalendar from "./useCalendar";
import CalendarEventDialog from "./CalendarEventDialog";
import { clientMeetings, needsPreparation, preparationState } from "./calendarWorkflow";
import { addDays, CalendarSymbol, dateKey, dayLabel, meetingLabel, minuteOfDay, timeRange, weekStart } from "./calendarFormat";
import "./calendar-prep.css";

const HOUR_HEIGHT = 96;
const HOURS = Array.from({ length: 10 }, (_, index) => index + 8);

export default function CalendarPrep({ onOpenEvent, onReplay, preferredDate, onOpenPreparations }) {
  const { data, error, command: sendCommand } = useCalendar();
  const [busy, setBusy] = useState(false), [offset, setOffset] = useState(0);
  const [detail, setDetail] = useState(null);
  const gridScroll = useRef(null), positioned = useRef(false);
  useEffect(() => {
    if (!data || !gridScroll.current || positioned.current) return;
    gridScroll.current.scrollTop = Math.max(0, (minuteOfDay(preferredDate || data.now) - 480 - 120) / 60 * HOUR_HEIGHT);
    positioned.current = true;
  }, [data, preferredDate]);
  const [selectedDay, setSelectedDay] = useState(preferredDate ? dateKey(preferredDate) : "");
  async function command(action, mode) {
    setBusy(true);
    const state = await sendCommand(action, mode);
    if (state && action === "reset") { setOffset(0); setSelectedDay(""); }
    setBusy(false);
  }

  const monday = data ? addDays(weekStart(data.now), offset * 7) : null;
  const days = monday ? Array.from({ length: 5 }, (_, index) => addDays(monday, index)) : [];
  const today = data ? dateKey(data.now) : "";
  const selected = days.includes(selectedDay || today) ? selectedDay || today : days[0];
  const upcoming = data && clientMeetings(data).find(event => new Date(event.starts_at) > new Date(data.now));
  const nextState = upcoming && preparationState(data, upcoming);
  const ready = data?.preparations.filter(job => job.status === "ready" && job.mode === data.mode && data.events.some(event => event.id === job.event_id && event.version === job.version)) || [];
  function moveWeek(direction) { setOffset(value => value + direction); setSelectedDay(addDays(monday, direction * 7)); }

  return <section className="calendar-workspace" aria-label="Weekly calendar">
    <header className="calendar-page-header">
      <div className="calendar-title"><h2>Calendar</h2><span className="calendar-demo-label">Demo calendar</span></div>
      <details className="calendar-demo-settings">
        <summary><CalendarSymbol name="settings" size={15}/>Demo settings</summary>
        <div className="calendar-settings-panel">
          <h3>Presentation controls</h3>
          <p>Sample meetings and client data. The advisor’s calendar stays simple; these controls are for the demo.</p>
          {data && <>
            <p>Demo time: {dayLabel(today, { month: "short", day: "numeric", year: "numeric" })}, {new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" }).format(new Date(data.now))}</p>
            <label>Preparation mode<select value={data.mode} disabled={busy || data.processing} onChange={event => command("pause", event.target.value)}>
              <option value="simulation">Offline demo · No LLM</option><option value="agent">AI Agent · Gemini</option>
            </select></label>
            <p>{data.mode === "agent" ? "Gemini requests use the configured API quota." : "Offline briefs use the repository’s synthetic data."}</p>
            <div className="calendar-demo-actions">
              <button disabled={busy} onClick={() => command(data.enabled ? "pause" : "start")}>{data.enabled ? "Pause automatic prep" : "Resume automatic prep"}</button>
              <button disabled={busy || data.processing} onClick={() => command("advance")}>Advance demo day</button>
              <button disabled={busy || data.processing} onClick={() => command("reset")}>Reset demo</button>
              <button disabled={!ready.length} onClick={() => onReplay(ready[0])}>Replay ready notice</button>
            </div>
          </>}
        </div>
      </details>
    </header>
    {error && <p className="meeting-error" role="alert">{error}</p>}
    {!data ? <div className="calendar-loading" role="status">Loading your calendar…</div> : <>
      {upcoming && <div className="calendar-next-meeting">
        <CalendarSymbol name="document" size={20}/><div><span>Next client meeting · {meetingLabel(upcoming)}</span><strong>{upcoming.client_name} <span>· {upcoming.title}</span></strong></div>
        <span className={`prep-state state-${nextState.tone}`}>{nextState.label}</span>
        <button className="meeting-btn primary" onClick={() => onOpenEvent(upcoming)}>View meeting prep<CalendarSymbol name="next" size={14}/></button>
      </div>}
      <div className="calendar-week-toolbar">
        <div className="calendar-date-navigation">
          <button className="calendar-today" onClick={() => { setOffset(0); setSelectedDay(today); }}>Today</button>
          <div className="calendar-week-arrows"><button aria-label="Previous week" onClick={() => moveWeek(-1)}><CalendarSymbol name="previous"/></button><button aria-label="Next week" onClick={() => moveWeek(1)}><CalendarSymbol name="next"/></button></div>
          <h3>{dayLabel(monday, { month: "long", day: "numeric" })} – {dayLabel(days[4], { day: "numeric", month: monday.slice(0, 7) !== days[4].slice(0, 7) ? "short" : undefined })}, {days[4].slice(0, 4)}</h3>
        </div>
        <div className="calendar-view-context"><span className="calendar-auto-status"><CalendarSymbol name="check" size={15}/>{data.enabled ? "Meeting prep is automatic" : "Automatic prep paused"}</span><span className="calendar-view-label"><CalendarSymbol size={15}/>Work week</span></div>
      </div>
      <div className="calendar-legend"><span><i className="legend-client"/>Client meetings</span><span><i className="legend-internal"/>Internal meetings</span><span><i className="legend-focus"/>Focus & personal time</span><button onClick={onOpenPreparations}>All meeting briefs<CalendarSymbol name="next" size={13}/></button></div>
      <div className="calendar-week-frame">
        <div className="calendar-day-headers">
          <div className="calendar-zone">New<br/>York</div>
          {days.map(day => <button key={day} className={`calendar-day-heading ${day === today ? "is-today" : ""}`} aria-pressed={day === selected} onClick={() => setSelectedDay(day)}>
            <span>{dayLabel(day, { weekday: "short" })}</span><strong>{Number(day.slice(-2))}</strong>
          </button>)}
        </div>
        <div ref={gridScroll} className="calendar-grid-scroll">
          <div className="calendar-time-grid" style={{ height: HOURS.length * HOUR_HEIGHT, "--hour-height": `${HOUR_HEIGHT}px` }}>
            <div className="calendar-time-axis" aria-hidden="true">{HOURS.map((hour, index) => <span key={hour} style={{ top: index * HOUR_HEIGHT }}>{hour > 12 ? hour - 12 : hour} {hour >= 12 ? "PM" : "AM"}</span>)}</div>
            {days.map(day => <div className={`calendar-day-column ${day === today ? "is-today" : ""}`} data-selected={day === selected} key={day} aria-label={dayLabel(day, { weekday: "long", month: "long", day: "numeric" })}>
              {data.events.filter(event => dateKey(event.starts_at) === day).map(event => {
                const client = needsPreparation(event), status = client && preparationState(data, event);
                const top = (minuteOfDay(event.starts_at) - 480) / 60 * HOUR_HEIGHT + 2;
                const compact = event.duration_minutes < 60;
                return <article key={event.id} className={`calendar-meeting category-${event.category} ${event.id === upcoming?.id ? "is-next" : ""} ${compact ? "is-compact" : ""}`} style={{ top, height: (event.duration_minutes || 60) / 60 * HOUR_HEIGHT - 4 }}>
                  <button className="calendar-event-body" aria-label={`Event details: ${event.title}, ${meetingLabel(event)}`} onClick={() => setDetail(event)} title={`${event.client_name || event.title} · ${event.title} · ${meetingLabel(event)}`}>
                    <strong>{client ? event.client_name : event.title}</strong><span className="calendar-meeting-time">{timeRange(event)}</span>{client && !compact && <span className="calendar-meeting-topic">{event.title}</span>}
                  </button>
                  {client && <button className="calendar-meeting-link" aria-label={`View meeting prep for ${event.client_name} on ${dateKey(event.starts_at)} at ${timeRange(event)}`} onClick={() => onOpenEvent(event)}>{status.tone === "ready" ? "Brief ready" : status.tone === "reviewed" ? "Reviewed" : status.tone === "preparing" ? "Preparing brief" : status.tone === "failed" ? "Needs attention" : "View meeting prep"}<CalendarSymbol name={["ready", "reviewed"].includes(status.tone) ? "check" : "next"} size={12}/></button>}
                </article>;
              })}
              {day === today && minuteOfDay(data.now) >= 480 && minuteOfDay(data.now) < 1080 && <div className="calendar-now-line" style={{ top: (minuteOfDay(data.now) - 480) / 60 * HOUR_HEIGHT }} aria-label="Current demo time"/>}
            </div>)}
          </div>
          {!data.events.some(event => days.includes(dateKey(event.starts_at))) && <p className="calendar-empty-week">No meetings scheduled this week. Select Today to return to your current calendar.</p>}
        </div>
      </div>
    </>}
    {detail && <CalendarEventDialog key={detail.id} event={detail} data={data} onClose={() => setDetail(null)} onOpenEvent={onOpenEvent}/>}
  </section>;
}
