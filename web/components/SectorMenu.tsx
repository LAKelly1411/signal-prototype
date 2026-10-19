"use client";
import { useRef } from "react";
import Link from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";
import { TABS } from "@/lib/tabs";
import { Glyph } from "./Glyph";
import { useDismiss } from "./useDismiss";
import styles from "./shell.module.css";

export type SectorItem = { slug: string; name: string; note: string };

/** The sector name set as the page title, with a small chevron, opening a menu of sectors (links to the same tab). */
export function SectorMenu({ items, current }: { items: SectorItem[]; current: SectorItem }) {
  const segment = useSelectedLayoutSegment();
  const tab = TABS.some(([k]) => k === segment) ? segment : "feed";
  const menu = useRef<HTMLDetailsElement>(null);
  useDismiss(menu);
  return (
    <details className={styles.menu} ref={menu}>
      <summary title="Switch sector">
        <h1 className={styles.menuName}>{current.name || current.slug}</h1>
        <Glyph name="expand" size={20} className={styles.menuChevron} />
      </summary>
      <ul className={styles.list}>
        {items.map((s) => (
          <li key={s.slug}>
            <Link
              href={`/${s.slug}/${tab}`}
              className={styles.option}
              aria-current={s.slug === current.slug ? "true" : undefined}
              onClick={() => menu.current?.removeAttribute("open")}
            >
              <Glyph name="check" size={20} className={styles.tick} />
              <span className={styles.optionLabel}>{s.name || s.slug}</span>
              {s.note && <span className={styles.note}>{s.note}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
