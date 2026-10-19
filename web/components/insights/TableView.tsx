import type { ReactNode } from "react";
import { DAY_MS } from "@/lib/signals/time";
import styles from "./insights.module.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthOf = (d: Date) => MONTHS[d.getUTCMonth()];

/** "5–11 Oct" or "28 Sep – 4 Oct" for the week starting on `start` (UTC). */
export function weekLabel(start: Date): string {
  const end = new Date(start.getTime() + 6 * DAY_MS);
  if (start.getUTCMonth() === end.getUTCMonth()) return `${start.getUTCDate()}–${end.getUTCDate()} ${monthOf(end)}`;
  return `${start.getUTCDate()} ${monthOf(start)} – ${end.getUTCDate()} ${monthOf(end)}`;
}

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** The data behind a chart, as a real table. */
export function TableView({ children, scroll = false }: { children: ReactNode; scroll?: boolean }) {
  const table = <table>{children}</table>;
  return (
    <details className={styles.table}>
      <summary>Show as a table</summary>
      {scroll ? <div className={styles.tableScroll}>{table}</div> : table}
    </details>
  );
}
