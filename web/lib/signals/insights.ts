// Port of the numbers in dashboard/overview.py (never the HTML) and
// _active_pattern_count in dashboard/app.py, on an explicit clock.
import type { SectorRules, Signal } from "@/lib/data/types";
import { isExcluded, signalEntities } from "@/lib/signals/entities";
import { buildPatterns } from "@/lib/signals/groups";
import { DAY_MS, parseDate } from "@/lib/signals/time";

export const WEEKS = 18;
export const HIGH_SCORE = 70;
export const MARK_SCORE = 75;
export const TREND_DAYS = 28;
export const HEAT_RAMP = ["#93afff", "#668eff", "#3b6bff", "#124ced", "#0033ad"];
export const HEAT_EMPTY = "#efede6";

export type Tile = { label: string; value: string; note: string };

const WEEK_MS = 7 * DAY_MS;
const NICE = [2, 4, 6, 8, 10, 12, 16, 20, 30, 40, 50, 60, 80, 100, 120, 160, 200];

const ts = (s: Signal) => parseDate(s.published_at).getTime();
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const grouped = (n: number) => n.toLocaleString("en-US");

/** Python's round(): halves go to the even neighbour. */
function pyRound(x: number): number {
  const f = Math.floor(x);
  const d = x - f;
  if (d < 0.5) return f;
  if (d > 0.5) return f + 1;
  return f % 2 === 0 ? f : f + 1;
}

export function weekStarts(now: Date, weeks = WEEKS): Date[] {
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const monday = today - ((new Date(today).getUTCDay() + 6) % 7) * DAY_MS;
  return Array.from({ length: weeks }, (_, i) => new Date(monday - (weeks - 1 - i) * WEEK_MS));
}

export function weekIndexIn(signal: Signal, starts: Date[]): number | null {
  const t = ts(signal);
  const first = starts[0].getTime();
  if (t < first || t >= starts[starts.length - 1].getTime() + WEEK_MS) return null;
  return Math.min(Math.floor(Math.floor((t - first) / DAY_MS) / 7), starts.length - 1);
}

export function niceTop(peak: number): number {
  const hit = NICE.find((n) => n >= peak);
  return hit ?? -Math.floor(-peak / 50) * 50;
}

function change(nowN: number, thenN: number, period: string): string {
  const diff = pyRound(nowN - thenN);
  if (diff === 0) return `Level with ${period}`;
  return `${diff > 0 ? "+" : "−"}${Math.abs(diff)} vs ${period}`;
}

export function headlineTiles(
  scored: Signal[], now: Date, activePatterns: number, themesBuilding: number,
  healthy: number | null, total: number | null,
): Tile[] {
  const n = now.getTime();
  const weekAgo = n - 7 * DAY_MS, monthAgo = n - 30 * DAY_MS, twoMonths = n - 60 * DAY_MS;
  const thisWeek = scored.filter((s) => ts(s) > weekAgo).length;
  const prior4w = scored.filter((s) => ts(s) > weekAgo - 28 * DAY_MS && ts(s) <= weekAgo).length;
  const high = scored.filter((s) => (s.newsworthiness_score || 0) >= HIGH_SCORE);
  const highNow = high.filter((s) => ts(s) > monthAgo).length;
  const highThen = high.filter((s) => ts(s) > twoMonths && ts(s) <= monthAgo).length;
  const tiles: Tile[] = [
    { label: "Signals this week", value: grouped(thisWeek), note: change(thisWeek, prior4w / 4, "4-week average") },
    { label: "High relevance, last 30 days", value: grouped(highNow), note: change(highNow, highThen, "previous 30 days") },
    { label: "Active patterns", value: grouped(activePatterns), note: "Companies with a run of related signals" },
    { label: "Themes building", value: grouped(themesBuilding), note: "Sector-wide stories gaining pace" },
  ];
  if (healthy != null && total) tiles.push({ label: "Sources healthy", value: `${healthy}/${total}`, note: "At the last update" });
  return tiles;
}

export function weeklyVolume(scored: Signal[], now: Date) {
  const starts = weekStarts(now);
  const counts = new Array<number>(WEEKS).fill(0);
  const top = new Map<number, Signal>();
  const markTitles: Record<number, string[]> = {};
  for (const s of scored) {
    const i = weekIndexIn(s, starts);
    if (i === null) continue;
    counts[i] += 1;
    if ((s.newsworthiness_score || 0) > ((top.get(i)?.newsworthiness_score || 0) || -1)) top.set(i, s);
    if ((s.newsworthiness_score || 0) >= MARK_SCORE) (markTitles[i] ??= []).push(s.title);
  }
  const marks = [...top.keys()].sort((a, b) => a - b).filter((i) => (top.get(i)!.newsworthiness_score || 0) >= MARK_SCORE);
  return { starts, counts, marks, top: niceTop(Math.max(...counts) || 1), markTitles };
}

export function heatThresholds(counts: number[]): number[] {
  const nonzero = counts.filter((c) => c > 0).sort((a, b) => a - b);
  if (!nonzero.length) return [1, 2, 3, 4, 5];
  const peak = nonzero[nonzero.length - 1];
  if (peak <= 5) return [1, 2, 3, 4, 5];
  const qs = [0.3, 0.55, 0.75, 0.9].map((q) => nonzero[Math.min(nonzero.length - 1, Math.floor(nonzero.length * q))]);
  const bounds: number[] = [];
  let last = 0;
  qs.forEach((q, i) => {
    last = Math.min(Math.max(last + 1, q), peak - (qs.length - i));
    bounds.push(last);
  });
  return [...bounds, peak];
}

export function heatStep(count: number, thresholds: number[]): string {
  if (count <= 0) return HEAT_EMPTY;
  for (let i = 0; i < Math.min(HEAT_RAMP.length, thresholds.length); i++) if (count <= thresholds[i]) return HEAT_RAMP[i];
  return HEAT_RAMP[HEAT_RAMP.length - 1];
}

export function categoryHeatmap(scored: Signal[], now: Date) {
  const starts = weekStarts(now);
  const grid = new Map<string, number[]>();
  for (const s of scored) {
    const i = weekIndexIn(s, starts);
    if (i === null) continue;
    const cat = s.canonical_category || "Other";
    let row = grid.get(cat);
    if (!row) grid.set(cat, (row = new Array<number>(WEEKS).fill(0)));
    row[i] += 1;
  }
  const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
  const rows = [...grid.entries()]
    .map(([category, counts]) => ({ category, counts, total: sum(counts) }))
    .sort((a, b) => b.total - a.total || cmp(a.category, b.category));
  return { starts, rows, thresholds: heatThresholds(rows.flatMap((r) => r.counts)) };
}

export function companyMovers(scored: Signal[], now: Date, rules: SectorRules | null, limit = 8) {
  const starts = weekStarts(now);
  const n = now.getTime();
  const monthAgo = n - 30 * DAY_MS, twoMonths = n - 60 * DAY_MS;
  const scores = new Map<string, number[]>();
  const before = new Map<string, number>();
  const weekly = new Map<string, number[]>();
  for (const s of scored) {
    const names = new Set(signalEntities(s).filter((e) => !isExcluded(e, rules)));
    const t = ts(s);
    const i = weekIndexIn(s, starts);
    for (const name of names) {
      if (t > monthAgo) {
        const l = scores.get(name);
        if (l) l.push(s.newsworthiness_score || 0);
        else scores.set(name, [s.newsworthiness_score || 0]);
      } else if (t > twoMonths) before.set(name, (before.get(name) ?? 0) + 1);
      if (i !== null) {
        let w = weekly.get(name);
        if (!w) weekly.set(name, (w = new Array<number>(WEEKS).fill(0)));
        w[i] += 1;
      }
    }
  }
  const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
  return [...scores.entries()]
    .sort(([an, a], [bn, b]) => Math.max(...b) - Math.max(...a) || sum(b) - sum(a) || cmp(an, bn))
    .slice(0, limit)
    .map(([name, v]) => ({
      name,
      count: v.length,
      top: Math.max(...v),
      change: v.length - (before.get(name) ?? 0),
      weekly: weekly.get(name) ?? new Array<number>(WEEKS).fill(0),
    }));
}

export function themeTrend(members: Signal[], now: Date): ["building" | "steady" | "easing", number, number] {
  const n = now.getTime();
  const recentFrom = n - TREND_DAYS * DAY_MS, priorFrom = n - 2 * TREND_DAYS * DAY_MS;
  const recent = members.filter((m) => ts(m) > recentFrom).length;
  const prior = members.filter((m) => ts(m) > priorFrom && ts(m) <= recentFrom).length;
  if (recent - prior >= 2 && recent >= prior * 1.25) return ["building", recent, prior];
  if (prior - recent >= 2 && recent <= prior * 0.75) return ["easing", recent, prior];
  return ["steady", recent, prior];
}

export function activePatternCount(scored: Signal[], now: Date): number {
  return buildPatterns(scored, null, now).filter((p) => p.active).length;
}
