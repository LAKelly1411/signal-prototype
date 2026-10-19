"use client";

import { useRef } from "react";
import Link from "next/link";
import { Glyph } from "./Glyph";
import { useDismiss } from "./useDismiss";
import styles from "./shell.module.css";

export type SortOrder = "recent" | "score";
const LABELS: Record<SortOrder, string> = { recent: "Most recent", score: "Highest score" };

/** "Sort by: Most recent" at the right of the tab row. The links keep the filters in the URL. */
export function SortMenu({ basePath, query }: { basePath: string; query: string }) {
  const sort: SortOrder = new URLSearchParams(query).get("sort") === "score" ? "score" : "recent";
  const href = (order: SortOrder) => {
    const sp = new URLSearchParams(query);
    sp.delete("sort");
    if (order === "score") sp.set("sort", "score");
    const qs = sp.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };
  const menu = useRef<HTMLDetailsElement>(null);
  useDismiss(menu);
  return (
    <details className={styles.sort} ref={menu}>
      <summary>
        <Glyph name="sort" size={20} /> <span>Sort by: <strong>{LABELS[sort]}</strong></span>
      </summary>
      <ul className={styles.sortList}>
        {(Object.keys(LABELS) as SortOrder[]).map((o) => (
          <li key={o}>
            <Link
              href={href(o)} replace scroll={false} className={styles.option} aria-current={o === sort ? "true" : undefined}
              onClick={() => menu.current?.removeAttribute("open")}
            >
              <Glyph name="check" size={20} className={styles.tick} />
              <span className={styles.optionLabel}>{LABELS[o]}</span>
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
