import type { Tile } from "@/lib/signals/insights";
import styles from "./insights.module.css";

/** One hero number (the first tile), then the rest as smaller tiles. */
export function StatTiles({ tiles }: { tiles: Tile[] }) {
  return (
    <div className={styles.tiles}>
      {tiles.map((t, i) => (
        <div key={t.label} className={`${styles.tile} ${i === 0 ? styles.hero : ""}`} {...(i === 0 ? { "data-hero": "" } : {})}>
          <div className={styles.tileLabel}>{t.label}</div>
          <div className={styles.tileValue}>{t.value}</div>
          {t.note ? <div className={styles.tileNote}>{t.note}</div> : null}
        </div>
      ))}
    </div>
  );
}
