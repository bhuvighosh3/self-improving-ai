import React, { useEffect, useState, useCallback, useRef } from "react";
import "./calendar.css";
import "./calendar-prep.css";
import useCalendar from "./useCalendar";
import PreparationControls from "./PreparationControls";
import { requestJson } from "./connectionRequest";
import { clientMeetings, preparationState } from "./calendarWorkflow";
import { CalendarSymbol, meetingLabel } from "./calendarFormat";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const EVENT_TYPES = [
  { value: "quarterly_review", label: "Quarterly Review" },
  { value: "follow_up", label: "Follow-Up" },
  { value: "portfolio_review", label: "Portfolio Review" },
  { value: "annual_review", label: "Annual Review" },
  { value: "goal_review", label: "Goal Review" },
];
const TYPE_LABELS = Object.fromEntries(EVENT_TYPES.map(t => [t.value, t.label]));

function buildGrid(year, month) {
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const daysInPrev = new Date(year, month - 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i++) {
    cells.push({ day: daysInPrev - firstDay + 1 + i, overflow: true });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, overflow: false, dateStr: `${year}-${String(month).padStart(2,"0")}-${String(d).padStart(2,"0")}` });
  }
  const remaining = 42 - cells.length;
  for (let i = 1; i <= remaining; i++) {
    cells.push({ day: i, overflow: true });
  }
  return cells;
}

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}

const EMPTY_FORM = { title: "", client_id: "", date: "", start_time: "09:00", end_time: "10:00", type: "quarterly_review", notes: "", location: "" };

export default function CalendarPage({ clients, onOpenEvent, onReplay, preferredDate, onOpenPreparations, onEditing }) {
  const { data, error: preparationError, command } = useCalendar();
  const positioned = useRef(false), modalRef = useRef(null);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [events, setEvents] = useState(null);
  const [selected, setSelected] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const clockDate = data?.now.slice(0, 10) || todayStr();
  useEffect(() => {
    if (!data || positioned.current) return;
    const date = preferredDate || data.now;
    setYear(Number(date.slice(0, 4))); setMonth(Number(date.slice(5, 7)));
    setSelected(date.slice(0, 10)); positioned.current = true;
  }, [data, preferredDate]);
  useEffect(() => {
    if (modal && modalRef.current && !modalRef.current.open) modalRef.current.showModal();
  }, [modal]);

  const fetchEvents = useCallback(async signal => {
    try {
      const records = await requestJson(`/api/calendar/events?year=${year}&month=${month}`, { signal });
      if (!signal?.aborted) { setEvents(records); setError(""); }
    } catch (err) { if (err.kind !== "cancelled") setError(err.message); }
  }, [year, month]);
  const revision = data?.events.map(event => event.id + event.version).join(",");
  useEffect(() => {
    const controller = new AbortController(); fetchEvents(controller.signal);
    return () => controller.abort();
  }, [fetchEvents, revision]);

  const prev = () => { if (month === 1) { setMonth(12); setYear(y => y - 1); } else setMonth(m => m - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(y => y + 1); } else setMonth(m => m + 1); };
  const goToday = () => { setYear(Number(clockDate.slice(0,4))); setMonth(Number(clockDate.slice(5,7))); setSelected(clockDate); };

  const openCreate = (dateStr) => {
    onEditing?.();
    setFormError("");
    setForm({ ...EMPTY_FORM, date: dateStr || clockDate });
    setModal("create");
  };
  const openEdit = (evt) => {
    onEditing?.();
    setFormError("");
    setForm({ title: evt.title, client_id: evt.client_id, date: evt.date, start_time: evt.start_time, end_time: evt.end_time, type: evt.type, notes: evt.notes || "", location: evt.location || "" });
    setModal(evt.id);
  };

  const save = async () => {
    setBusy(true);
    try {
      if (modal === "create") {
        await requestJson("/api/calendar/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      } else {
        await requestJson(`/api/calendar/events/${modal}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      }
      setModal(null);
      fetchEvents();
    } catch (err) { setFormError(err.message); }
    setBusy(false);
  };

  const remove = async () => {
    if (!confirm("Delete this event?")) return;
    setBusy(true);
    try {
      await requestJson(`/api/calendar/events/${modal}`, { method: "DELETE" });
      setModal(null);
      fetchEvents();
    } catch (err) { setFormError(err.message); }
    setBusy(false);
  };

  const cells = buildGrid(year, month);
  const today = clockDate;
  const normalized = evt => data?.events.find(event => event.id === evt.id);
  const upcoming = data && clientMeetings(data).find(event => new Date(event.starts_at) > new Date(data.now));
  const nextState = upcoming && preparationState(data, upcoming);
  function openPreparation(evt) {
    const event = normalized(evt);
    if (event) { setModal(null); onOpenEvent(event); }
  }
  const eventsByDate = {};
  (events || []).forEach(e => { (eventsByDate[e.date] ||= []).push(e); });
  const clientMap = {};
  (clients || []).forEach(c => { clientMap[c.client_id] = c.profile?.name || c.client_id; });

  const f = (key, val) => setForm(prev => ({ ...prev, [key]: val }));
  const canSave = form.title && form.client_id && form.date && form.start_time && form.end_time && form.type;

  return (
    <section className="calendar" aria-label="Client calendar">
      <div className="cal-preparation-heading">
        <span className="calendar-auto-status"><CalendarSymbol name="check" size={15}/>{!data ? "Loading meeting preparation…" : data.enabled ? "Meeting prep is automatic · 24 hours before" : "Automatic prep paused"}</span>
        <button className="calendar-back" onClick={onOpenPreparations}>All meeting briefs<CalendarSymbol name="next" size={14}/></button>
        <PreparationControls data={data} command={command} onReplay={onReplay}/>
      </div>
      {(error || preparationError) && <p className="cal-error" role="alert">{error || preparationError}</p>}
      {upcoming && <div className="calendar-next-meeting">
        <CalendarSymbol name="document" size={20}/><div><span>Next client meeting · {meetingLabel(upcoming)}</span><strong>{upcoming.client_name} <span>· {upcoming.title}</span></strong></div>
        <span className={`prep-state state-${nextState.tone}`}>{nextState.label}</span>
        <button className="meeting-btn primary" onClick={() => onOpenEvent(upcoming)}>View meeting prep<CalendarSymbol name="next" size={14}/></button>
      </div>}
      <div className="cal-header">
        <div className="cal-nav">
          <button className="cal-nav-btn" onClick={prev} aria-label="Previous month">&lsaquo;</button>
          <div className="cal-month-label">{MONTHS[month - 1]} {year}</div>
          <button className="cal-nav-btn" onClick={next} aria-label="Next month">&rsaquo;</button>
        </div>
        <div className="cal-actions">
          <button className="cal-today-btn" onClick={goToday}>Today</button>
          <button className="cal-new-btn" disabled={!data || !clients?.length} onClick={() => openCreate()}>+ New Event</button>
        </div>
      </div>

      {!events && <p className="calendar-loading" role="status">Loading your calendar…</p>}
      <div className="cal-grid" aria-busy={!events}>
        {WEEKDAYS.map(w => <div key={w} className="cal-weekday">{w}</div>)}
        {cells.map((cell, i) => {
          const dayEvents = cell.dateStr ? (eventsByDate[cell.dateStr] || []) : [];
          const isToday = cell.dateStr === today;
          const isSel = cell.dateStr === selected;
          return (
            <div
              key={i}
              className={`cal-cell${cell.overflow ? " overflow" : ""}${isToday ? " today" : ""}${isSel ? " selected" : ""}`}
              onClick={() => !cell.overflow && setSelected(cell.dateStr)}
              onDoubleClick={() => !cell.overflow && openCreate(cell.dateStr)}
            >
              <div className="cal-day">{cell.day}</div>
              {dayEvents.slice(0, 3).map(evt => (
                <div key={evt.id} className={`cal-event-entry cal-chip-${evt.type}`}>
                  <button className="cal-event-chip" title={`${evt.start_time} ${evt.title}`} onClick={e => { e.stopPropagation(); openEdit(evt); }}>{evt.start_time} {evt.title}</button>
                  <button className="cal-prep-link" disabled={!normalized(evt)} aria-label={`View meeting prep for ${clientMap[evt.client_id] || evt.client_id} on ${evt.date}`} onClick={e => { e.stopPropagation(); openPreparation(evt); }}>
                    {normalized(evt) && preparationState(data, normalized(evt)).tone === "ready" ? "Brief ready" : "Meeting prep"}<CalendarSymbol name="next" size={11}/>
                  </button>
                </div>
              ))}
              {dayEvents.length > 3 && <div className="cal-more">+{dayEvents.length - 3} more</div>}
            </div>
          );
        })}
      </div>

      <div className="cal-legend">
        {EVENT_TYPES.map(t => (
          <div key={t.value} className="cal-legend-item">
            <div className={`cal-legend-swatch cal-chip-${t.value}`} />
            <span>{t.label}</span>
          </div>
        ))}
      </div>

      {selected && eventsByDate[selected]?.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
            {new Date(selected + "T00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </h4>
          {eventsByDate[selected].map(evt => (
            <div key={evt.id} className="card cal-selected-event">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{evt.title}</span>
                <span className={`chip cal-chip-${evt.type}`} style={{ fontSize: 10.5 }}>{TYPE_LABELS[evt.type]}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-4)", marginTop: 3 }}>
                {evt.start_time} – {evt.end_time} · {clientMap[evt.client_id] || evt.client_id} · {evt.location || "No location"}
              </div>
              <div className="cal-event-actions">
                <button className="cal-today-btn" onClick={() => openEdit(evt)}>Edit event</button>
                <button className="cal-today-btn" disabled={!normalized(evt)} onClick={() => openPreparation(evt)}>View meeting prep</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <dialog ref={modalRef} className="cal-modal-dialog" aria-label={modal === "create" ? "New Event" : "Edit Event"} onCancel={() => setModal(null)} onClick={e => { if (e.target === modalRef.current) setModal(null); }}>
          <div className="cal-modal">
            <h3 id="calendar-event-title">{modal === "create" ? "New Event" : "Edit Event"}</h3>
            {formError && <p className="cal-error" role="alert">{formError}</p>}
            <div className="cal-modal-fields">
              <label>Title
                <input value={form.title} onChange={e => f("title", e.target.value)} placeholder="e.g. Q4 Review: Garcia Family" />
              </label>
              <label>Client
                <select aria-label="Client" value={form.client_id} onChange={e => f("client_id", e.target.value)}>
                  <option value="">Select client…</option>
                  {(clients || []).map(c => <option key={c.client_id} value={c.client_id}>{c.profile?.name || c.client_id}</option>)}
                </select>
              </label>
              <label>Date
                <input type="date" value={form.date} onChange={e => f("date", e.target.value)} />
              </label>
              <div className="cal-modal-row">
                <label>Start Time
                  <input type="time" value={form.start_time} onChange={e => f("start_time", e.target.value)} />
                </label>
                <label>End Time
                  <input type="time" value={form.end_time} onChange={e => f("end_time", e.target.value)} />
                </label>
              </div>
              <label>Type
                <select aria-label="Type" value={form.type} onChange={e => f("type", e.target.value)}>
                  {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <label>Location
                <input value={form.location} onChange={e => f("location", e.target.value)} placeholder="Conference Room A" />
              </label>
              <label>Notes
                <textarea value={form.notes} onChange={e => f("notes", e.target.value)} rows={3} placeholder="Meeting notes…" />
              </label>
            </div>
            <div className="cal-modal-actions">
              {modal !== "create" && <button className="cal-modal-cancel" disabled={busy || !normalized({id:modal})} onClick={() => openPreparation({id:modal})}>Meeting prep</button>}
              {modal !== "create" && (
                <button className="cal-modal-delete" onClick={remove} disabled={busy}>Delete</button>
              )}
              <button className="cal-modal-cancel" onClick={() => setModal(null)}>Cancel</button>
              <button className="cal-modal-save" onClick={save} disabled={busy || !canSave}>
                {busy ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </dialog>
      )}
    </section>
  );
}
