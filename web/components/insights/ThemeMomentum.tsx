import styles from "./insights.module.css";

type Direction = "building" | "steady" | "easing" | null;
type Theme = { name: string; heat: number; direction: Direction; recent?: number; prior?: number };

const WORDS: Record<string, [string, string]> = { building: ["Building", "↗"], steady: ["Steady", "→"], easing: ["Easing", "↘"] };

/** Themes as bars of heat, busiest first, each with its direction in words. */
export function ThemeMomentum({ themes }: { themes: Theme[] }) {
  const peak = Math.max(0, ...themes.map((t) => t.heat)) || 1;
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <h3 className={styles.cardTitle}>Theme momentum</h3>
        <div className={styles.cardSub}>
          How hot each sector-wide theme is, and which way it is heading: signals in the last 28 days against the 28 before.
        </div>
      </div>
      {themes.length === 0 ? (
        <div className={styles.empty}>No sector-wide themes yet.</div>
      ) : (
        <>
          {themes.map((t) => {
            const word = t.direction ? WORDS[t.direction] : undefined;
            return (
              <div key={t.name} className={styles.trow} data-theme="">
                <span className={styles.tname}>{t.name}</span>
                <span className={styles.tbar}><span style={{ width: `${Math.max(2, (t.heat / peak) * 100).toFixed(1)}%` }} /></span>
                <span className={styles.tdir}>
                  {word ? (
                    <>
                      <span aria-hidden="true">{word[1]}</span> <span>{word[0]}</span>
                      {t.recent !== undefined ? (
                        <> <span className={styles.tcounts} title="Signals in the last 28 days vs the 28 before">{t.recent} vs {t.prior}</span></>
                      ) : null}
                    </>
                  ) : "—"}
                </span>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
