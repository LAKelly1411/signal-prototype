// Port of the feed filters in dashboard/app.py (_filter_options, _filter_signals,
// the sort in apply_filters), with the criteria kept in the URL.
import type { Signal } from "@/lib/data/types";
import { signalEntities, sourceName } from "@/lib/signals/entities";
import { calendarDay, utcDay } from "@/lib/signals/time";

export const DEFAULT_MIN_SCORE = 40;
export const DATE_PRESETS: Record<string, number | null> = { "All time": null, "Last 30 days": 30, "Last 7 days": 7 };

export type Criteria = {
  sourcesOff: string[];
  categoriesOff: string[];
  companies: string[];
  minScore: number;
  days: number | null;
  search: string;
};
export type FilterOptions = { sources: string[]; categories: string[]; entities: string[]; entityCounts: Map<string, number> };

/** Calendar day number of the date as written in the ISO string (Python: fromisoformat(...).date()). */
function pubDay(iso: string): number {
  const day = calendarDay(iso);
  if (Number.isNaN(day)) throw new Error(`bad ISO date: ${iso}`);
  return day;
}

const category = (s: Signal) => s.canonical_category || "Other";

/** Counter.most_common(): count descending, ties in first-seen order. */
function counted(values: string[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const v of values) m.set(v, (m.get(v) ?? 0) + 1);
  return m;
}

export function scoredSignals(signals: Signal[]): Signal[] {
  const scored = signals.filter((s) => s.newsworthiness_score != null);
  return scored.sort((a, b) => (a.published_at < b.published_at ? 1 : a.published_at > b.published_at ? -1 : 0));
}

export function filterOptions(scored: Signal[]): FilterOptions {
  const entityCounts = counted(scored.flatMap((s) => signalEntities(s)));
  const cats = [...counted(scored.map(category)).entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c);
  const sources = [...new Set(scored.map((s) => s.source))].sort((a, b) => {
    const x = sourceName(a).toLowerCase(), y = sourceName(b).toLowerCase();
    return x < y ? -1 : x > y ? 1 : 0;
  });
  const entities = [...entityCounts.keys()].sort((a, b) => {
    const d = (entityCounts.get(b) ?? 0) - (entityCounts.get(a) ?? 0);
    if (d) return d;
    const x = a.toLowerCase(), y = b.toLowerCase();
    return x < y ? -1 : x > y ? 1 : 0;
  });
  return { sources, categories: cats, entities, entityCounts };
}

export function filterSignals(scored: Signal[], crit: Criteria, today: Date): Signal[] {
  const todayDay = utcDay(today);
  const start = crit.days != null ? todayDay - crit.days : null;
  const off = new Set(crit.sourcesOff);
  const catsOff = new Set(crit.categoriesOff);
  const companies = new Set(crit.companies);
  const search = crit.search.trim().toLowerCase();
  return scored.filter((s) => {
    if (off.has(s.source)) return false;
    if (catsOff.has(category(s))) return false;
    if ((s.newsworthiness_score as number) < crit.minScore) return false;
    if (start != null && pubDay(s.published_at) < start) return false;
    if (companies.size && !signalEntities(s).some((e) => companies.has(e))) return false;
    if (search) {
      const hay = [s.title ?? "", s.why_it_matters || "", s.category || "", (s.entities ?? []).join(" "), signalEntities(s).join(" ")]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });
}

/** "recent": newest first; "score": highest score first, then recency. Does not mutate. */
export function sortSignals(list: Signal[], order: "recent" | "score"): Signal[] {
  const byDate = (a: Signal, b: Signal) => (a.published_at < b.published_at ? 1 : a.published_at > b.published_at ? -1 : 0);
  const out = [...list];
  if (order === "recent") return out.sort(byDate);
  return out.sort((a, b) => ((b.newsworthiness_score ?? 0) - (a.newsworthiness_score ?? 0)) || byDate(a, b));
}

export function criteriaFromSearchParams(sp: URLSearchParams, opts: FilterOptions): Criteria {
  const known = (vals: string[], allowed: Set<string>) => [...new Set(vals.filter((v) => allowed.has(v)))];
  const minRaw = sp.get("min");
  const min = minRaw != null && /^\d+$/.test(minRaw) ? Number(minRaw) : NaN;
  const daysRaw = sp.get("days");
  const days = daysRaw === "7" || daysRaw === "30" ? Number(daysRaw) : null;
  return {
    sourcesOff: known(sp.getAll("off"), new Set(opts.sources)),
    categoriesOff: known(sp.getAll("catoff"), new Set(opts.categories)),
    companies: known(sp.getAll("company"), new Set(opts.entities)),
    minScore: min >= 0 && min <= 100 ? min : DEFAULT_MIN_SCORE,
    days,
    search: (sp.get("q") ?? "").trim(),
  };
}

export function criteriaToSearchParams(crit: Criteria): URLSearchParams {
  const sp = new URLSearchParams();
  if (crit.search) sp.set("q", crit.search);
  for (const s of crit.sourcesOff) sp.append("off", s);
  for (const c of crit.categoriesOff) sp.append("catoff", c);
  for (const c of crit.companies) sp.append("company", c);
  if (crit.minScore !== DEFAULT_MIN_SCORE) sp.set("min", String(crit.minScore));
  if (crit.days != null) sp.set("days", String(crit.days));
  return sp;
}
