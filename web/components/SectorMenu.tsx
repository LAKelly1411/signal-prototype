"use client";
import Link from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { TABS } from "@/lib/tabs";
import styles from "./shell.module.css";

export type SectorItem = { slug: string; name: string; note: string };

/** The sector name set as the page title, opening a menu of sectors (links to the same tab). */
export function SectorMenu({ items, current }: { items: SectorItem[]; current: SectorItem }) {
  const segment = useSelectedLayoutSegment();
  const tab = TABS.some(([k]) => k === segment) ? segment : "feed";
  return (
    <details className={styles.menu}>
      <summary>{current.name || current.slug}</summary>
      <ul className={styles.list}>
        {items.map((s) => (
          <li key={s.slug}>
            <Link
              href={`/${s.slug}/${tab}`}
              className={styles.option}
              aria-current={s.slug === current.slug ? "true" : undefined}
              onClick={(e) => e.currentTarget.closest("details")?.removeAttribute("open")}
            >
              <span>{s.name || s.slug}</span>
              <span className={styles.note}>{s.note}</span>
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
