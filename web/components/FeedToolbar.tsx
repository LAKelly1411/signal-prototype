"use client";

import { useRef } from "react";
import Link from "next/link";
import styles from "@/app/[sector]/feed/feed.module.css";

export type SortOrder = "recent" | "score";
const LABELS: Record<SortOrder, string> = { recent: "Most recent", score: "Highest score" };

/** The count above the feed, with the sort menu at the right. Sort links keep the filters in the URL. */
export function FeedToolbar({ shown, total, sort, basePath, query }: { shown: number; total: number; sort: SortOrder; basePath: string; query: string }) {
  const href = (order: SortOrder) => {
    const sp = new URLSearchParams(query);
    sp.delete("sort");
    if (order === "score") sp.set("sort", "score");
    const qs = sp.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  };
  const menu = useRef<HTMLDetailsElement>(null);
  return (
    <div className={styles.toolbar}>
      <p className={styles.toolbarCount}>Showing {shown} of {total} scored signals.</p>
      <details className={styles.sort} ref={menu}>
        <summary>
          <svg width="20" height="20" viewBox="0 -960 960 960" fill="currentColor" aria-hidden="true" focusable="false">
            <path d="M320-440v-287L217-624l-57-56 200-200 200 200-57 56-103-103v287h-80ZM600-80 400-280l57-56 103 103v-287h80v287l103-103 57 56L600-80Z" />
          </svg> Sort by: <strong>{LABELS[sort]}</strong>
        </summary>
        <ul className={styles.sortList}>
          {(Object.keys(LABELS) as SortOrder[]).map((o) => (
            <li key={o}>
              <Link href={href(o)} replace scroll={false} aria-current={o === sort ? "true" : undefined} onClick={() => menu.current?.removeAttribute("open")}>{LABELS[o]}</Link>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
