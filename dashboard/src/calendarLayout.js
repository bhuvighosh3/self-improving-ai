/** Display calculations only; canonical meeting records are never modified. */
export const minutes = value => {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
};

export function calendarMonths(days) {
  return [...new Set(days.map(day => day.slice(0, 7)))];
}

export function timeBounds(events) {
  return {
    start: Math.min(8, ...events.map(event => Math.floor(minutes(event.start_time) / 60))),
    end: Math.max(18, ...events.map(event => Math.ceil(minutes(event.end_time) / 60))),
  };
}

export function arrangeDay(events) {
  const sorted = [...events].sort((a, b) => minutes(a.start_time) - minutes(b.start_time)
    || minutes(b.end_time) - minutes(a.end_time) || a.id.localeCompare(b.id));
  const result = [];
  let group = [], lanes = [], groupEnd = -1;
  function finish() {
    result.push(...group.map(item => ({ ...item, columns: lanes.length })));
    group = []; lanes = []; groupEnd = -1;
  }
  for (const event of sorted) {
    const start = minutes(event.start_time), end = minutes(event.end_time);
    if (group.length && start >= groupEnd) finish();
    let lane = lanes.findIndex(until => until <= start);
    if (lane < 0) lane = lanes.length;
    lanes[lane] = end;
    groupEnd = Math.max(groupEnd, end);
    group.push({ event, lane, start, end });
  }
  if (group.length) finish();
  return result;
}
