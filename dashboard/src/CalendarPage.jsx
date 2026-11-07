import React, { useEffect, useState, useCallback } from "react";
import "./calendar.css";

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

export default function CalendarPage({ clients }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [busy, setBusy] = useState(false);

  const fetchEvents = useCallback(() => {
    fetch(`/api/calendar/events?year=${year}&month=${month}`)
      .then(r => r.json()).then(setEvents).catch(() => setEvents([]));
  }, [year, month]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  const prev = () => { if (month === 1) { setMonth(12); setYear(y => y - 1); } else setMonth(m => m - 1); };
  const next = () => { if (month === 12) { setMonth(1); setYear(y => y + 1); } else setMonth(m => m + 1); };
  const goToday = () => { const d = new Date(); setYear(d.getFullYear()); setMonth(d.getMonth() + 1); };

  const openCreate = (dateStr) => {
    setForm({ ...EMPTY_FORM, date: dateStr || todayStr() });
    setModal("create");
  };
  const openEdit = (evt) => {
    setForm({ title: evt.title, client_id: evt.client_id, date: evt.date, start_time: evt.start_time, end_time: evt.end_time, type: evt.type, notes: evt.notes || "", location: evt.location || "" });
    setModal(evt.id);
  };

  const save = async () => {
    setBusy(true);
    try {
      if (modal === "create") {
        await fetch("/api/calendar/events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      } else {
        await fetch(`/api/calendar/events/${modal}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      }
      setModal(null);
      fetchEvents();
    } catch { /* ignore */ }
    setBusy(false);
  };

  const remove = async () => {
    if (!confirm("Delete this event?")) return;
    setBusy(true);
    try {
      await fetch(`/api/calendar/events/${modal}`, { method: "DELETE" });
      setModal(null);
      fetchEvents();
    } catch { /* ignore */ }
    setBusy(false);
  };

  const cells = buildGrid(year, month);
  const today = todayStr();
  const eventsByDate = {};
  events.forEach(e => { (eventsByDate[e.date] ||= []).push(e); });
  const clientMap = {};
  (clients || []).forEach(c => { clientMap[c.id] = c.name; });

  const f = (key, val) => setForm(prev => ({ ...prev, [key]: val }));
  const canSave = form.title && form.client_id && form.date && form.start_time && form.end_time && form.type;

  return (
    <div className="calendar">
      <div className="cal-header">
        <div className="cal-nav">
          <button className="cal-nav-btn" onClick={prev} aria-label="Previous month">&lsaquo;</button>
          <div className="cal-month-label">{MONTHS[month - 1]} {year}</div>
          <button className="cal-nav-btn" onClick={next} aria-label="Next month">&rsaquo;</button>
        </div>
        <div className="cal-actions">
          <button className="cal-today-btn" onClick={goToday}>Today</button>
          <button className="cal-new-btn" onClick={() => openCreate()}>+ New Event</button>
        </div>
      </div>

      <div className="cal-grid">
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
                <div
                  key={evt.id}
                  className={`cal-event-chip cal-chip-${evt.type}`}
                  title={`${evt.start_time} ${evt.title}`}
                  onClick={e => { e.stopPropagation(); openEdit(evt); }}
                >
                  {evt.start_time} {evt.title}
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
            <div key={evt.id} className="card" style={{ padding: "10px 14px", marginBottom: 6, cursor: "pointer" }} onClick={() => openEdit(evt)}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{evt.title}</span>
                <span className={`chip cal-chip-${evt.type}`} style={{ fontSize: 10.5 }}>{TYPE_LABELS[evt.type]}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-4)", marginTop: 3 }}>
                {evt.start_time} – {evt.end_time} · {clientMap[evt.client_id] || evt.client_id} · {evt.location || "No location"}
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <div className="cal-modal-backdrop" onClick={() => setModal(null)}>
          <div className="cal-modal" onClick={e => e.stopPropagation()}>
            <h3>{modal === "create" ? "New Event" : "Edit Event"}</h3>
            <div className="cal-modal-fields">
              <label>Title
                <input value={form.title} onChange={e => f("title", e.target.value)} placeholder="e.g. Q4 Review: Garcia Family" />
              </label>
              <label>Client
                <select value={form.client_id} onChange={e => f("client_id", e.target.value)}>
                  <option value="">Select client…</option>
                  {(clients || []).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
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
                <select value={form.type} onChange={e => f("type", e.target.value)}>
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
              {modal !== "create" && (
                <button className="cal-modal-delete" onClick={remove} disabled={busy}>Delete</button>
              )}
              <button className="cal-modal-cancel" onClick={() => setModal(null)}>Cancel</button>
              <button className="cal-modal-save" onClick={save} disabled={busy || !canSave}>
                {busy ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
