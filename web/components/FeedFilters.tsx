"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { criteriaFromSearchParams, criteriaToSearchParams, DEFAULT_MIN_SCORE, DATE_PRESETS, type Criteria, type FilterOptions } from "@/lib/signals/filters";
import { sourceName } from "@/lib/signals/entities";
import styles from "@/app/[sector]/feed/feed.module.css";

const COMPANY_PREVIEW = 10;
const MIN_CHOICES: [number, string][] = [
  [0, "Any relevance"],
  [DEFAULT_MIN_SCORE, "Relevant (40+)"],
  [70, "Highly relevant (70+)"],
];

const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export function FeedFilters({ options }: { options: FilterOptions }) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const crit = criteriaFromSearchParams(new URLSearchParams(sp.toString()), options);
  const [search, setSearch] = useState(crit.search);
  const [showAll, setShowAll] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef(crit);
  latest.current = crit;

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  // The sort order isn't a filter; keep it when criteria change.
  const withSort = (next: Criteria) => {
    const qs = criteriaToSearchParams(next);
    if (sp.get("sort") === "score") qs.set("sort", "score");
    const s = qs.toString();
    router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
  };

  const onSearch = (value: string) => {
    setSearch(value);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => withSort({ ...latest.current, search: value.trim() }), 300);
  };
  const active = Boolean(
    crit.search || search || crit.companies.length || crit.sourcesOff.length || crit.categoriesOff.length ||
    crit.minScore !== DEFAULT_MIN_SCORE || crit.days != null,
  );
  const clearAll = () => {
    if (timer.current) clearTimeout(timer.current);
    setSearch("");
    withSort({ sourcesOff: [], categoriesOff: [], companies: [], minScore: DEFAULT_MIN_SCORE, days: null, search: "" });
  };

  const chosen = new Set(crit.companies);
  const visible = showAll ? options.entities : options.entities.filter((e, i) => i < COMPANY_PREVIEW || chosen.has(e));
  const hidden = options.entities.length - visible.length;

  return (
    <aside className={styles.filters} aria-label="Filters">
      <div className={styles.filtersHead}>
        <h2 className={styles.filtersTitle}>Filters</h2>
        <button type="button" className={styles.clear} onClick={clearAll} style={{ visibility: active ? "visible" : "hidden" }} disabled={!active}>
          Clear all
        </button>
      </div>
      <div className={styles.searchWrap}>
        <svg width="20" height="20" viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true" focusable="false">
          <path d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.500-75.500T120-580q0-109 75.500-184.500T380-840q109 0 184.500 75.500T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.500-52.500T560-580q0-75-52.500-127.500T380-760q-75 0-127.500 52.500T200-580q0 75 52.500 127.500T380-400Z" />
        </svg>
        <input
          type="search" className={styles.search} placeholder="Search signals" aria-label="Search signals"
          value={search} onChange={(e) => onSearch(e.target.value)}
        />
      </div>

      <details className={styles.section} open>
        <summary>Sources</summary>
        {options.sources.map((s) => (
          <label key={s} className={styles.check}>
            <input type="checkbox" checked={!crit.sourcesOff.includes(s)} onChange={() => withSort({ ...crit, sourcesOff: toggle(crit.sourcesOff, s) })} />
            <span>{sourceName(s)}</span>
          </label>
        ))}
      </details>

      <details className={styles.section} open>
        <summary>Categories</summary>
        {options.categories.map((c) => (
          <label key={c} className={styles.check}>
            <input type="checkbox" checked={!crit.categoriesOff.includes(c)} onChange={() => withSort({ ...crit, categoriesOff: toggle(crit.categoriesOff, c) })} />
            <span>{c}</span>
          </label>
        ))}
      </details>

      <details className={styles.section} open>
        <summary>Minimum relevance</summary>
        <select aria-label="Minimum relevance" className={styles.select} value={crit.minScore} onChange={(e) => withSort({ ...crit, minScore: Number(e.target.value) })}>
          {MIN_CHOICES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          {!MIN_CHOICES.some(([v]) => v === crit.minScore) && <option value={crit.minScore}>{crit.minScore}+</option>}
        </select>
      </details>

      <details className={styles.section} open>
        <summary>Companies</summary>
        {visible.map((e) => (
          <label key={e} className={styles.check}>
            <input type="checkbox" checked={chosen.has(e)} onChange={() => withSort({ ...crit, companies: toggle(crit.companies, e) })} />
            <span>{e} <span className={styles.count}>({options.entityCounts.get(e) ?? 0})</span></span>
          </label>
        ))}
        {hidden > 0 && <button type="button" className={styles.more} onClick={() => setShowAll(true)}>Show all ({options.entities.length})</button>}
        {showAll && options.entities.length > COMPANY_PREVIEW && (
          <button type="button" className={styles.more} onClick={() => setShowAll(false)}>Show fewer</button>
        )}
      </details>

      <details className={styles.section} open>
        <summary>Published</summary>
        <select aria-label="Published" className={styles.select} value={crit.days == null ? "" : String(crit.days)} onChange={(e) => withSort({ ...crit, days: e.target.value ? Number(e.target.value) : null })}>
          {Object.entries(DATE_PRESETS).map(([label, d]) => <option key={label} value={d == null ? "" : String(d)}>{label}</option>)}
        </select>
      </details>
    </aside>
  );
}
