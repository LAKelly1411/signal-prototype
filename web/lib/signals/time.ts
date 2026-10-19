// Port of the date/week helpers in dashboard/app.py.
import type { Signal } from "@/lib/data/types";

export const SPARK_WEEKS = 13;
const DAY_MS = 86_400_000;
const WEEK_SECONDS = 7 * 86400;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** An ISO timestamp with no zone is UTC (Python: tzinfo None -> utc). */
export function parseDate(iso: string): Date {
  const hasZone = /Z$/i.test(iso) || /[+-]\d{2}(:?\d{2})?$/.test(iso.slice(10));
  return new Date(hasZone ? iso : `${iso}Z`);
}

/** The wall-clock fields as written in the string (Python's dt.date()/dt.hour
 *  are read in the timestamp's own offset, with no conversion). */
function localFields(iso: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):?(\d{2})?:?(\d{2})?)?/.exec(iso);
  if (!m) throw new Error(`bad ISO date: ${iso}`);
  return {
    y: +m[1],
    mo: +m[2],
    d: +m[3],
    h: +(m[4] ?? 0),
    mi: +(m[5] ?? 0),
    s: +(m[6] ?? 0),
  };
}

/** Day number (days since epoch) of a calendar date. */
const dayNumber = (y: number, mo: number, d: number) => Math.floor(Date.UTC(y, mo - 1, d) / DAY_MS);

export function niceScale(peak: number): number {
  const scales = [2, 4, 6, 8, 10, 12, 16, 20, 30, 40, 50, 60, 80, 100];
  const hit = scales.find((n) => n >= peak);
  return hit ?? -Math.floor(-peak / 20) * 20;
}

function weeksAgo(published: string, now: Date): number {
  const dt = parseDate(published);
  return Math.floor((now.getTime() - dt.getTime()) / 1000 / WEEK_SECONDS);
}

export function weeklyCounts(members: Signal[], now: Date): number[] {
  const counts = new Array<number>(SPARK_WEEKS).fill(0);
  for (const m of members) {
    const w = weeksAgo(m.published_at, now);
    if (w >= 0 && w < SPARK_WEEKS) counts[SPARK_WEEKS - 1 - w] += 1;
  }
  return counts;
}

export function weekIndex(signal: Signal, now: Date): number | null {
  const w = weeksAgo(signal.published_at, now);
  return w >= 0 && w < SPARK_WEEKS ? SPARK_WEEKS - 1 - w : null;
}

export function weekRange(start: Date): string {
  const end = new Date(start.getTime() + 6 * DAY_MS);
  const sd = start.getUTCDate(), ed = end.getUTCDate();
  const sm = MONTHS[start.getUTCMonth()], em = MONTHS[end.getUTCMonth()];
  const sy = start.getUTCFullYear(), ey = end.getUTCFullYear();
  if (start.getUTCMonth() === end.getUTCMonth() && sy === ey) return `${sd}–${ed} ${em} ${ey}`;
  if (sy === ey) return `${sd} ${sm} – ${ed} ${em} ${ey}`;
  return `${sd} ${sm} ${sy} – ${ed} ${em} ${ey}`;
}

export function humaniseAge(deltaSeconds: number): string {
  const minutes = Math.floor(deltaSeconds / 60);
  if (minutes < 60) return `${Math.max(minutes, 0)} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours !== 1 ? "s" : ""} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days !== 1 ? "s" : ""} ago`;
}

export function relativeTime(publishedAt: string, now: Date): string {
  const f = localFields(publishedAt);
  const dt = parseDate(publishedAt);
  if (f.h !== 0 || f.mi !== 0 || f.s !== 0) {
    const age = (now.getTime() - dt.getTime()) / 1000;
    if (age >= 0 && age < 24 * 3600) return humaniseAge(age);
  }
  const days = dayNumber(now.getUTCFullYear(), now.getUTCMonth() + 1, now.getUTCDate()) - dayNumber(f.y, f.mo, f.d);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return `${f.d} ${MONTHS[f.mo - 1]} ${f.y}`;
}

const londonParts = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function fullDate(publishedAt: string): string {
  const f = localFields(publishedAt);
  if (f.h === 0 && f.mi === 0 && f.s === 0) {
    const wd = WEEKDAYS[new Date(Date.UTC(f.y, f.mo - 1, f.d)).getUTCDay()];
    return `${wd} ${f.d} ${MONTHS_LONG[f.mo - 1]} ${f.y}`;
  }
  const p: Record<string, string> = {};
  for (const part of londonParts.formatToParts(parseDate(publishedAt))) p[part.type] = part.value;
  return `${p.weekday} ${Number(p.day)} ${p.month} ${p.year}, ${p.hour}:${p.minute}`;
}

export function dateBucket(pub: Date, today: Date): "Today" | "Yesterday" | "This week" | "Earlier" {
  const delta = Math.floor((today.getTime() - pub.getTime()) / DAY_MS);
  if (delta <= 0) return "Today";
  if (delta === 1) return "Yesterday";
  if (delta <= 7) return "This week";
  return "Earlier";
}

export function dateSpan(members: Signal[]): string {
  const dates = members
    .map((m) => localFields(m.published_at))
    .sort((a, b) => dayNumber(a.y, a.mo, a.d) - dayNumber(b.y, b.mo, b.d));
  const first = dates[0], last = dates[dates.length - 1];
  const fmt = (x: typeof first) => `${x.d} ${MONTHS[x.mo - 1]}`;
  if (dayNumber(first.y, first.mo, first.d) === dayNumber(last.y, last.mo, last.d)) return fmt(last);
  return `${fmt(first)} – ${fmt(last)}`;
}
