import React from "react";

export const CALENDAR_ZONE = "America/New_York";
const parts = value => Object.fromEntries(new Intl.DateTimeFormat("en-US", {
  timeZone: CALENDAR_ZONE, year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
}).formatToParts(new Date(value)).map(part => [part.type, part.value]));
export function dateKey(value) { const p = parts(value); return `${p.year}-${p.month}-${p.day}`; }
export function minuteOfDay(value) { const p = parts(value); return Number(p.hour) * 60 + Number(p.minute); }
export function addDays(key, count) {
  const date = new Date(`${key}T12:00:00Z`); date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0, 10);
}
export function weekStart(value) {
  const key = dateKey(value), weekday = new Date(`${key}T12:00:00Z`).getUTCDay();
  return addDays(key, -(weekday + 6) % 7);
}
export const dayLabel = (key, options) => new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC", ...options,
}).format(new Date(`${key}T12:00:00Z`));
export function timeRange(event) {
  const format = value => new Intl.DateTimeFormat("en-US", {
    timeZone: CALENDAR_ZONE, hour: "numeric", minute: "2-digit",
  }).format(new Date(value));
  if (event.kind === "saved_brief") return format(event.starts_at);
  return `${format(event.starts_at)} – ${format(new Date(event.starts_at).getTime() + (event.duration_minutes || 60) * 60000)}`;
}
export function meetingLabel(event) {
  return `${dayLabel(dateKey(event.starts_at), { weekday: "long", month: "short", day: "numeric" })} · ${timeRange(event)} · New York`;
}

export function CalendarSymbol({ name = "calendar", size = 18 }) {
  const paths = {
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></>,
    previous: <path d="m14 6-6 6 6 6"/>, next: <path d="m10 6 6 6-6 6"/>,
    check: <><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    document: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    settings: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
