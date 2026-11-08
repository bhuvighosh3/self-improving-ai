import { test } from "node:test";
import assert from "node:assert/strict";
import { arrangeDay, calendarMonths, timeBounds } from "../src/calendarLayout.js";

const meeting = (id, start_time, end_time) => ({ id, start_time, end_time });

test("overlapping meetings occupy distinct lanes without changing records", () => {
  const events = [meeting("b", "10:30", "11:00"), meeting("a", "10:00", "12:00"), meeting("c", "11:00", "11:30")];
  const before = JSON.stringify(events);
  const layout = arrangeDay(events);
  assert.equal(layout.find(item => item.event.id === "a").lane, 0);
  assert.equal(layout.find(item => item.event.id === "b").lane, 1);
  assert.equal(layout.find(item => item.event.id === "c").lane, 1);
  assert.ok(layout.every(item => item.columns === 2));
  assert.equal(JSON.stringify(events), before);
});

test("back-to-back meetings use full width", () => {
  const layout = arrangeDay([meeting("a", "09:00", "10:00"), meeting("b", "10:00", "11:00")]);
  assert.ok(layout.every(item => item.columns === 1));
});

test("an overlap chain does not carry lanes into later independent meetings", () => {
  const layout = arrangeDay([meeting("a", "09:00", "10:00"), meeting("b", "09:45", "10:45"), meeting("c", "10:30", "11:00"), meeting("d", "11:00", "12:00")]);
  assert.deepEqual(layout.map(item => item.columns), [2, 2, 2, 1]);
});

test("early and late meetings expand the visible hours", () => {
  assert.deepEqual(timeBounds([meeting("early", "06:15", "07:00"), meeting("late", "22:00", "23:30")]), { start: 6, end: 24 });
  assert.deepEqual(timeBounds([]), { start: 8, end: 18 });
});

test("cross-year weeks request both canonical calendar months exactly once", () => {
  assert.deepEqual(calendarMonths(["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"]), ["2026-12", "2027-01"]);
});
