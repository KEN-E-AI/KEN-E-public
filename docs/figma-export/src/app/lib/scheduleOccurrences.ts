// Parse human-readable `Workflow.schedule` strings into occurrence dates.
// Supports the formats seen in mockData (Daily, Every <Day>, Weekly on <Day>,
// Bi-weekly on <Day>, Monthly on Nth, 1st of every month, Every N hours,
// Every N minutes). Returns occurrences within [start, end] inclusive.

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function parseTime(s: string): { hour: number; minute: number } {
  const m = s.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
  if (!m) return { hour: 9, minute: 0 };
  let hour = parseInt(m[1], 10);
  const minute = parseInt(m[2], 10);
  const ampm = m[3]?.toUpperCase();
  if (ampm === 'PM' && hour < 12) hour += 12;
  if (ampm === 'AM' && hour === 12) hour = 0;
  return { hour, minute };
}

function parseDayOfWeek(s: string): number | null {
  const m = s.match(/Sun|Mon|Tue|Wed|Thu|Fri|Sat/i);
  if (!m) return null;
  const prefix = m[0].toLowerCase();
  return DAY_NAMES.findIndex(d => d.toLowerCase().startsWith(prefix));
}

function parseOrdinalDay(s: string): number | null {
  const m = s.match(/(\d{1,2})(st|nd|rd|th)?/);
  return m ? parseInt(m[1], 10) : null;
}

function dateAt(base: Date, hour: number, minute: number): Date {
  const d = new Date(base);
  d.setHours(hour, minute, 0, 0);
  return d;
}

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / 86_400_000);
}

/**
 * Generate occurrences of a schedule within a date range.
 * Returns an empty array for "On demand" / "Real-time" / unrecognized formats.
 */
export function scheduleOccurrencesInRange(
  schedule: string,
  start: Date,
  end: Date,
): Date[] {
  const s = schedule.trim();
  const occurrences: Date[] = [];

  // On demand / Real-time — no scheduled occurrences.
  if (/on demand|real-time/i.test(s)) return [];

  // "Every N hours" / "Every N minutes"
  const everyHoursMatch = s.match(/Every\s+(\d+)\s+hours?/i);
  if (everyHoursMatch) {
    const step = parseInt(everyHoursMatch[1], 10) * 60;
    let t = start.getTime();
    while (t <= end.getTime()) {
      occurrences.push(new Date(t));
      t += step * 60_000;
    }
    return occurrences;
  }
  const everyMinMatch = s.match(/Every\s+(\d+)\s+minutes?/i);
  if (everyMinMatch) {
    // Too noisy for the calendar — collapse to one marker at range start.
    return [new Date(start)];
  }

  const { hour, minute } = parseTime(s);

  // Daily
  if (/^Daily/i.test(s)) {
    const cur = startOfDay(start);
    while (cur <= end) {
      const occ = dateAt(cur, hour, minute);
      if (occ >= start && occ <= end) occurrences.push(occ);
      cur.setDate(cur.getDate() + 1);
    }
    return occurrences;
  }

  // Weekly / Every <Day> / Weekly on <Day>
  const dayOfWeek = parseDayOfWeek(s);
  if (dayOfWeek !== null && /every|weekly/i.test(s)) {
    const biWeekly = /bi-?weekly/i.test(s);
    const cur = startOfDay(start);
    // Advance to first matching weekday on/after `start`.
    const shift = (dayOfWeek - cur.getDay() + 7) % 7;
    cur.setDate(cur.getDate() + shift);
    const step = biWeekly ? 14 : 7;
    while (cur <= end) {
      const occ = dateAt(cur, hour, minute);
      if (occ >= start && occ <= end) occurrences.push(occ);
      cur.setDate(cur.getDate() + step);
    }
    return occurrences;
  }

  // Monthly on Nth / 1st of every month
  if (/monthly|of every month/i.test(s)) {
    const day = parseOrdinalDay(s) ?? 1;
    const cur = new Date(start.getFullYear(), start.getMonth(), day, hour, minute);
    while (cur <= end) {
      if (cur >= start) occurrences.push(new Date(cur));
      cur.setMonth(cur.getMonth() + 1);
    }
    return occurrences;
  }

  return occurrences;
}

export function hasOccurrenceInRange(schedule: string, start: Date, end: Date): boolean {
  return scheduleOccurrencesInRange(schedule, start, end).length > 0;
}

export function nextOccurrence(schedule: string, from: Date): Date | null {
  // Look up to 60 days ahead.
  const horizon = new Date(from);
  horizon.setDate(horizon.getDate() + 60);
  const list = scheduleOccurrencesInRange(schedule, from, horizon);
  return list[0] ?? null;
}

export { daysBetween };
