import React, { useEffect, useRef } from "react";
import { CalendarSymbol, dayLabel, minuteOfDay } from "./calendarFormat";
import { arrangeDay, timeBounds } from "./calendarLayout";
import { preparationState } from "./calendarWorkflow";

const HOUR_HEIGHT = 96;
const hourLabel = hour => `${hour % 12 || 12} ${hour >= 12 ? "PM" : "AM"}`;

export default function CalendarWeek({ days, events, now, selected, onSelect, onEdit, onPrepare, normalized, clientMap, data, loading }) {
  const scroll = useRef(null);
  const { start, end } = timeBounds(events);
  const hours = Array.from({ length: end - start }, (_, index) => start + index);
  const today = now.slice(0, 10);
  const selectedDay = days.includes(selected) ? selected : days[0];
  const selectedMeetingTime = events.find(event => event.date === selectedDay)?.start_time;
  useEffect(() => {
    if (!scroll.current || loading) return;
    const minute = !events.some(event => days.includes(event.date)) ? start * 60 : selectedMeetingTime ? Number(selectedMeetingTime.slice(0, 2)) * 60 + Number(selectedMeetingTime.slice(3))
      : days.includes(today) ? minuteOfDay(now) : 9 * 60;
    scroll.current.scrollTop = Math.max(0, (minute - start * 60 - 90) / 60 * HOUR_HEIGHT);
  }, [days[0], selectedDay, selectedMeetingTime, loading, start]);

  return <div className="cal-week-frame" style={{ "--cal-day-count": days.length, "--cal-hour-height": `${HOUR_HEIGHT}px` }}>
    <div className="cal-week-headings">
      <div className="cal-time-zone">New<br/>York</div>
      {days.map(day => <button key={day} className={`cal-day-heading${day === today ? " is-today" : ""}`} aria-label={dayLabel(day, { weekday: "long", month: "long", day: "numeric" })} aria-pressed={day === selectedDay} onClick={() => onSelect(day)}>
        <span>{dayLabel(day, { weekday: "short" })}</span><strong>{Number(day.slice(-2))}</strong>
      </button>)}
    </div>
    {!loading && !events.some(event => days.includes(event.date)) && <p className="cal-week-empty">No meetings this {days.length === 5 ? "work week" : "week"}. Use the arrows to browse your calendar.</p>}
    {!loading && !events.some(event => event.date === selectedDay) && <p className="cal-day-empty">No meetings on {dayLabel(selectedDay, { weekday: "long" })}.</p>}
    <div ref={scroll} className="cal-week-scroll" aria-busy={loading}>
      {loading ? <p className="calendar-loading" role="status">Loading your calendar…</p> : <>
        <div className="cal-time-grid" style={{ height: hours.length * HOUR_HEIGHT }}>
          <div className="cal-hour-gutter" aria-hidden="true">{hours.map((hour, index) => <span key={hour} style={{ top: index * HOUR_HEIGHT }}>{hourLabel(hour)}</span>)}</div>
          {days.map(day => <div key={day} className={`cal-day-column${day === today ? " is-today" : ""}`} data-selected={day === selectedDay} aria-label={dayLabel(day, { weekday: "long", month: "long", day: "numeric" })}>
            {hours.map(hour => <div className="cal-hour-line" key={hour} style={{ top: (hour - start) * HOUR_HEIGHT }}/>) }
            {arrangeDay(events.filter(event => event.date === day)).map(({ event, lane, columns, start: begins, end: ends }) => {
              const preparedEvent = normalized(event);
              const status = preparedEvent && preparationState(data, preparedEvent);
              const duration = ends - begins;
              return <article key={event.id} className={`cal-event-entry cal-chip-${event.type}${duration < 60 ? " is-compact" : ""}${duration < 30 ? " is-short" : ""}`} style={{ top: (begins - start * 60) / 60 * HOUR_HEIGHT + 1, height: Math.max(22, duration / 60 * HOUR_HEIGHT - 2), left: `calc(${lane / columns * 100}% + 4px)`, width: `calc(${100 / columns}% - 8px)` }}>
                <button className="cal-event-chip" title={`${event.start_time}–${event.end_time} ${event.title}`} aria-label={`Edit event: ${event.title}, ${event.date} at ${event.start_time}`} onClick={() => onEdit(event)}>
                  <strong>{clientMap[event.client_id] || event.title}</strong><span className="cal-event-time">{event.start_time} – {event.end_time}</span><span className="cal-event-topic">{event.title}</span>
                </button>
                <button className="cal-prep-link" disabled={!preparedEvent} aria-label={`View meeting prep for ${clientMap[event.client_id] || event.client_id} on ${event.date}`} onClick={() => onPrepare(event)}>
                  <span>{status?.tone === "ready" ? "Brief ready" : status?.tone === "reviewed" ? "Reviewed" : "Meeting prep"}</span><CalendarSymbol name={status?.tone === "ready" ? "check" : "next"} size={12}/>
                </button>
              </article>;
            })}
            {day === today && minuteOfDay(now) >= start * 60 && minuteOfDay(now) < end * 60 && <div className="cal-now-line" aria-label="Current demo time" style={{ top: (minuteOfDay(now) - start * 60) / 60 * HOUR_HEIGHT }}/>}
          </div>)}
        </div>
      </>}
    </div>
  </div>;
}
