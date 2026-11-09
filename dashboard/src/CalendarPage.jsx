import React, { useEffect, useState, useCallback, useRef } from "react";
import "./calendar.css";
import "./calendar-prep.css";
import useCalendar from "./useCalendar";
import PreparationControls from "./PreparationControls";
import { requestJson } from "./connectionRequest";
import { clientMeetings, preparationState } from "./calendarWorkflow";
import { addDays, CalendarSymbol, dayLabel, meetingLabel, weekStart } from "./calendarFormat";
import CalendarWeek from "./CalendarWeek.jsx";
import { calendarMonths } from "./calendarLayout";

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}

const EMPTY_FORM = { title: "", client_id: "", date: "", start_time: "09:00", end_time: "10:00", notes: "", location: "" };

export default function CalendarPage({ clients, onOpenEvent, onReplay, preferredDate, onOpenPreparations, onEditing }) {
  const { data, error: preparationError, command } = useCalendar();
  const positioned = useRef(false), modalRef = useRef(null), fetchGeneration = useRef(0);
  const [anchor, setAnchor] = useState(todayStr());
  const monday = weekStart(`${anchor}T12:00:00Z`);
  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(monday, index));
  const days = weekDays;
  const monthKeys = calendarMonths(weekDays).join(",");
  const [events, setEvents] = useState(null);
  const [loadedMonths, setLoadedMonths] = useState("");
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
    const key = date.slice(0, 10);
    const start = weekStart(`${key}T12:00:00Z`);
    const nextMeeting = data.events.find(event => event.date >= key && event.date <= addDays(start, 6));
    setAnchor(key);
    setSelected(preferredDate ? key : nextMeeting?.date || key);
    positioned.current = true;
  }, [data, preferredDate]);
  useEffect(() => {
    if (modal && modalRef.current && !modalRef.current.open) modalRef.current.showModal();
  }, [modal]);

  const fetchEvents = useCallback(async signal => {
    const generation = ++fetchGeneration.current;
    try {
      const batches = await Promise.all(monthKeys.split(",").map(key => {
        const [year, month] = key.split("-").map(Number);
        return requestJson(`/api/calendar/events?year=${year}&month=${month}`, { signal });
      }));
      const records = [...new Map(batches.flat().map(event => [event.id, event])).values()]
        .sort((a, b) => `${a.date} ${a.start_time}`.localeCompare(`${b.date} ${b.start_time}`));
      if (!signal?.aborted && generation === fetchGeneration.current) {
        setEvents(records); setLoadedMonths(monthKeys); setError("");
      }
    } catch (err) { if (err.kind !== "cancelled" && generation === fetchGeneration.current) setError(err.message); }
  }, [monthKeys]);
  const revision = data?.events.map(event => event.id + event.version).join(",");
  useEffect(() => {
    const controller = new AbortController(); fetchEvents(controller.signal);
    return () => controller.abort();
  }, [fetchEvents, revision]);

  const moveWeek = direction => {
    setAnchor(addDays(monday, direction * 7));
    setSelected(addDays(selected || monday, direction * 7));
  };
  const goToday = () => {
    setAnchor(clockDate); setSelected(clockDate);
  };

  const openCreate = (dateStr) => {
    onEditing?.();
    setFormError("");
    setForm({ ...EMPTY_FORM, date: dateStr || clockDate });
    setModal("create");
  };
  const openEdit = (evt) => {
    onEditing?.();
    setFormError("");
    setForm({ title: evt.title, client_id: evt.client_id, date: evt.date, start_time: evt.start_time, end_time: evt.end_time, notes: evt.notes || "", location: evt.location || "" });
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

  const weekEvents = (events || []).filter(event => weekDays.includes(event.date));
  const lastDay = days[days.length - 1];
  const weekLabel = `${dayLabel(monday, { month: "short", day: "numeric", ...(monday.slice(0, 4) !== lastDay.slice(0, 4) ? { year: "numeric" } : {}) })} – ${dayLabel(lastDay, { day: "numeric", ...(monday.slice(0, 7) !== lastDay.slice(0, 7) ? { month: "short" } : {}) })}, ${lastDay.slice(0, 4)}`;
  const normalized = evt => data?.events.find(event => event.id === evt.id);
  const upcoming = data && clientMeetings(data).find(event => new Date(event.starts_at) > new Date(data.now));
  const nextState = upcoming && preparationState(data, upcoming);
  function openPreparation(evt) {
    const event = normalized(evt);
    if (event) { setModal(null); onOpenEvent(event); }
  }
  const clientMap = {};
  (clients || []).forEach(c => { clientMap[c.client_id] = c.profile?.name || c.client_id; });

  const f = (key, val) => setForm(prev => ({ ...prev, [key]: val }));
  const canSave = form.title && form.client_id && form.date && form.start_time && form.end_time;

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
          <button className="cal-nav-btn" onClick={() => moveWeek(-1)} aria-label="Previous week">&lsaquo;</button>
          <h2 className="cal-week-label">{weekLabel}</h2>
          <button className="cal-nav-btn" onClick={() => moveWeek(1)} aria-label="Next week">&rsaquo;</button>
        </div>
        <div className="cal-actions">
          <button className="cal-today-btn" onClick={goToday}>Today</button>
          <button className="cal-new-btn" disabled={!data || !clients?.length} onClick={() => openCreate(selected || clockDate)}>+ New Event</button>
        </div>
      </div>

      <CalendarWeek days={days} events={weekEvents} now={data?.now || `${clockDate}T12:00:00-05:00`} selected={selected} onSelect={setSelected} onEdit={openEdit} onPrepare={openPreparation} normalized={normalized} clientMap={clientMap} data={data} loading={!events || loadedMonths !== monthKeys}/>

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
