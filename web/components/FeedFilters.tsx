"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { criteriaFromSearchParams, criteriaToSearchParams, DEFAULT_MIN_SCORE, DATE_PRESETS, type Criteria, type FilterOptions } from "@/lib/signals/filters";
import { sourceName } from "@/lib/signals/entities";
import { CompanyLogo } from "./SourceLogo";
import { Glyph } from "./Glyph";
import styles from "./filters.module.css";

const SEARCH_DEBOUNCE = 300;
const SLIDER_DEBOUNCE = 250;
const COMPANY_MATCHES = 50;

const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

/** A collapsible sidebar section: bold heading with a drop-down arrow at the right. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className={styles.section} open>
      <summary>
        <span>{title}</span>
        <Glyph name="dropDown" size={24} className={styles.caret} />
      </summary>
      <div className={styles.sectionBody}>{children}</div>
    </details>
  );
}

/**
 * The feed filters, in a fixed left sidebar like the Streamlit prototype's
 * (dashboard/app.py apply_filters). Every filter lives in the URL; the search
 * box and the score slider write theirs after a pause, folded into any other
 * change made meanwhile. Below 768px the sidebar is a collapsible section.
 */
export function FeedFilters({ options }: { options: FilterOptions }) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const crit = criteriaFromSearchParams(new URLSearchParams(sp.toString()), options);
  const [search, setSearch] = useState(crit.search);
  const [score, setScore] = useState(crit.minScore);
  const [open, setOpen] = useState(false);
  const pending = useRef<Partial<Criteria>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef(crit);
  latest.current = crit;
  const panelId = useId();

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  // Follow the URL when it changes from outside (back/forward), unless a
  // change is still waiting to be written or the control already says it
  // (modulo the trailing space the URL trims off).
  useEffect(() => {
    if ("search" in pending.current) return;
    setSearch((cur) => (cur.trim() === crit.search ? cur : crit.search));
  }, [crit.search]);
  useEffect(() => {
    if ("minScore" in pending.current) return;
    setScore(crit.minScore);
  }, [crit.minScore]);

  // The sort order isn't a filter; keep it when criteria change.
  const navigate = (next: Criteria) => {
    const qs = criteriaToSearchParams(next);
    if (sp.get("sort") === "score") qs.set("sort", "score");
    const s = qs.toString();
    router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
  };

  /** Write now: anything still waiting on its debounce goes in the same navigation. */
  const commit = (patch: Partial<Criteria> = {}) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const next = { ...latest.current, ...pending.current, ...patch };
    pending.current = {};
    navigate(next);
  };
  /** Write after a pause. */
  const later = (patch: Partial<Criteria>, ms: number) => {
    pending.current = { ...pending.current, ...patch };
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => commit(), ms);
  };

  const onSearch = (value: string) => {
    setSearch(value);
    later({ search: value.trim() }, SEARCH_DEBOUNCE);
  };
  const onScore = (value: number) => {
    setScore(value);
    later({ minScore: value }, SLIDER_DEBOUNCE);
  };
  /** Released: write at once if the slider has a value waiting. */
  const releaseScore = () => { if ("minScore" in pending.current) commit(); };

  const active = Boolean(
    crit.search || search || crit.companies.length || crit.sourcesOff.length || crit.categoriesOff.length ||
    crit.minScore !== DEFAULT_MIN_SCORE || score !== DEFAULT_MIN_SCORE || crit.days != null,
  );
  const clearAll = () => {
    pending.current = {};
    setSearch("");
    setScore(DEFAULT_MIN_SCORE);
    commit({ sourcesOff: [], categoriesOff: [], companies: [], minScore: DEFAULT_MIN_SCORE, days: null, search: "" });
  };

  return (
    <aside className={styles.sidebar} data-feed-sidebar="" data-open={open ? "" : undefined} aria-label="Filters">
      <div className={styles.head}>
        <h2 className={styles.title}>Filters</h2>
        <button
          type="button" className={styles.disclose} aria-expanded={open} aria-controls={panelId}
          onClick={() => setOpen((o) => !o)}
        >
          <Glyph name="tune" size={20} /> Filters <Glyph name="expand" size={20} className={styles.discloseCaret} />
        </button>
        <button type="button" className={styles.clear} onClick={clearAll} data-hidden={active ? undefined : ""} disabled={!active}>
          Clear all
        </button>
      </div>
      <div className={styles.panel} id={panelId}>
        <label className={styles.field}>
          <Glyph name="search" size={20} className={styles.fieldIcon} />
          <input
            type="search" className={styles.input} placeholder="Search signals" aria-label="Search signals"
            value={search} onChange={(e) => onSearch(e.target.value)}
          />
        </label>

        <Section title="Sources">
          {options.sources.map((s) => (
            <label key={s} className={styles.check}>
              <input type="checkbox" checked={!crit.sourcesOff.includes(s)} onChange={() => commit({ sourcesOff: toggle(crit.sourcesOff, s) })} />
              <span>{sourceName(s)}</span>
            </label>
          ))}
        </Section>

        <Section title="Categories">
          {options.categories.map((c) => (
            <label key={c} className={styles.check}>
              <input type="checkbox" checked={!crit.categoriesOff.includes(c)} onChange={() => commit({ categoriesOff: toggle(crit.categoriesOff, c) })} />
              <span>{c}</span>
            </label>
          ))}
        </Section>

        <Section title="Minimum score">
          <ScoreSlider value={score} onChange={onScore} onRelease={releaseScore} />
        </Section>

        <Section title="Company / entity">
          <CompanySearch
            options={options} chosen={crit.companies}
            onPick={(name) => commit({ companies: [...crit.companies, name] })}
            onRemove={(name) => commit({ companies: crit.companies.filter((c) => c !== name) })}
          />
        </Section>

        <Section title="Published">
          <div role="radiogroup" aria-label="Published" className={styles.radios}>
            {Object.entries(DATE_PRESETS).map(([label, d]) => (
              <label key={label} className={styles.radio}>
                <input type="radio" name="published" checked={crit.days === d} onChange={() => commit({ days: d })} />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </Section>
      </div>
    </aside>
  );
}

/** 0–100, cobalt left of the thumb, the value in bold above it, 0 and 100 underneath. */
function ScoreSlider({ value, onChange, onRelease }: { value: number; onChange: (v: number) => void; onRelease: () => void }) {
  return (
    <div className={styles.slider} style={{ "--pct": value } as React.CSSProperties}>
      <div className={styles.sliderValue} aria-hidden="true"><span>{value}</span></div>
      <input
        type="range" min={0} max={100} step={1} value={value} aria-label="Minimum score"
        className={styles.range}
        onChange={(e) => onChange(Number(e.target.value))}
        onPointerUp={onRelease} onKeyUp={onRelease} onBlur={onRelease}
      />
      <div className={styles.ticks} aria-hidden="true"><span>0</span><span>100</span></div>
    </div>
  );
}

/** Type-ahead over the sector's companies; the chosen ones list underneath with a remove button. */
function CompanySearch({ options, chosen, onPick, onRemove }: {
  options: FilterOptions; chosen: string[]; onPick: (name: string) => void; onRemove: (name: string) => void;
}) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const listId = useId();
  const q = text.trim().toLowerCase();
  const taken = new Set(chosen);
  const matches = options.entities.filter((e) => !taken.has(e) && (!q || e.toLowerCase().includes(q))).slice(0, COMPANY_MATCHES);
  const showList = open && matches.length > 0;
  const at = Math.min(cursor, matches.length - 1);

  const pick = (name: string) => {
    onPick(name);
    setText("");
    setCursor(0);
  };
  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setCursor((c) => Math.min(c + 1, matches.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
    else if (e.key === "Enter" && showList) { e.preventDefault(); pick(matches[at]); }
    else if (e.key === "Escape") { setOpen(false); }
  };

  return (
    <div className={styles.company}>
      <div className={styles.field}>
        <Glyph name="search" size={20} className={styles.fieldIcon} />
        <input
          type="text" role="combobox" className={styles.input} placeholder="Search by company" aria-label="Search by company"
          aria-expanded={showList} aria-controls={listId} aria-autocomplete="list"
          aria-activedescendant={showList ? `${listId}-${at}` : undefined}
          value={text}
          onChange={(e) => { setText(e.target.value); setOpen(true); setCursor(0); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
      </div>
      {showList && (
        <ul className={styles.options} role="listbox" id={listId} aria-label="Companies">
          {matches.map((e, i) => (
            <li
              key={e} id={`${listId}-${i}`} role="option" aria-selected={i === at}
              className={styles.option}
              // Pick before the input's blur closes the list.
              onMouseDown={(ev) => { ev.preventDefault(); pick(e); }}
              onMouseEnter={() => setCursor(i)}
            >
              <span className={styles.optionName}>{e}</span>
              <span className={styles.count}>{options.entityCounts.get(e) ?? 0}</span>
            </li>
          ))}
        </ul>
      )}
      {chosen.length > 0 && (
        <ul className={styles.chosen} aria-label="Chosen companies">
          {chosen.map((name) => (
            <li key={name} className={styles.chosenRow}>
              <span className={styles.chosenName}><span className={styles.logo}><CompanyLogo name={name} /></span><span>{name}</span></span>
              <button type="button" className={styles.remove} aria-label={`Remove ${name}`} title={`Remove ${name}`} onClick={() => onRemove(name)}>
                <Glyph name="close" size={20} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
