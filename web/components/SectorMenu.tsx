import Link from "next/link";
import type { SectorEntry } from "@/lib/data/types";
import { sectorNote } from "@/lib/load";
import styles from "./shell.module.css";

/** The sector name set as the page title, opening a menu of sectors (links to the same tab). */
export function SectorMenu({ sectors, current, tab = "feed" }: { sectors: SectorEntry[]; current: SectorEntry; tab?: string }) {
  return (
    <details className={styles.menu}>
      <summary>{current.name || current.slug}</summary>
      <ul className={styles.list}>
        {sectors.map((s) => (
          <li key={s.slug}>
            <Link href={`/${s.slug}/${tab}`} className={styles.option} aria-current={s.slug === current.slug ? "true" : undefined}>
              <span>{s.name || s.slug}</span>
              <span className={styles.note}>{sectorNote(s)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
