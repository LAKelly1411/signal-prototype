import { SPARK_WEEKS, weekRange } from "@/lib/signals/time";
import styles from "./groups.module.css";

const HEIGHT = 56;
const TOP = 4; // headroom so the line's cap and the end-dot aren't clipped
const DAY_MS = 86_400_000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Signals per week, today at the right. Square-root axis on a scale shared by every card on the tab. */
export function Sparkline({ counts, scale, start }: { counts: number[]; scale: number; start: Date }) {
  const n = counts.length;
  const step = n > 1 ? 100 / (n - 1) : 0;
  const y = (c: number) => HEIGHT - Math.sqrt(Math.min(c, scale) / (scale || 1)) * (HEIGHT - TOP);
  const pts = counts.map((c, i) => [i * step, y(c)] as const);
  const line = pts.map(([x, yy]) => `${x.toFixed(2)},${yy.toFixed(2)}`).join(" ");
  const area = `0,${HEIGHT} ${line} 100,${HEIGHT}`;
  const weekStart = (i: number) => new Date(start.getTime() + i * 7 * DAY_MS);
  const peak = Math.max(...counts);
  const label =
    `Signals per week over the last ${n} weeks: ${counts.join(", ")}. ` +
    `Peak ${peak} in the week of ${weekStart(counts.indexOf(peak)).getUTCDate()} ${MONTHS[weekStart(counts.indexOf(peak)).getUTCMonth()]}; ${counts[n - 1]} this week.`;
  const last = pts[n - 1];
  const dotClass = counts[n - 1] > 0 ? styles.tlDot : `${styles.tlDot} ${styles.tlQuiet}`;
  const s0 = start;

  return (
    <div className={styles.tl} role="img" aria-label={label} data-weeks={SPARK_WEEKS}>
      <div className={styles.tlTrack}>
        <svg className={styles.tlSvg} viewBox={`0 0 100 ${HEIGHT}`} preserveAspectRatio="none" aria-hidden="true">
          <line className={styles.tlGrid} x1="0" x2="100" y1={y(scale)} y2={y(scale)} />
          <polygon className={styles.tlArea} points={area} />
          <polyline className={styles.tlLine} points={line} />
        </svg>
        <span className={dotClass} data-latest style={{ bottom: `${(((HEIGHT - last[1]) / HEIGHT) * 100).toFixed(1)}%` }} />
        <div className={styles.tlCols}>
          {pts.map(([x, yy], i) => {
            const x0 = Math.max(0, x - step / 2);
            const x1 = Math.min(100, x + step / 2);
            const at = x1 > x0 ? ((x - x0) / (x1 - x0)) * 100 : 50;
            const bottom = ((HEIGHT - yy) / HEIGHT) * 100;
            const edge = i < 2 ? ` ${styles.tipStart}` : i > n - 3 ? ` ${styles.tipEnd}` : "";
            return (
              <span key={i} className={styles.tlCol} data-week={i} style={{ left: `${x0.toFixed(2)}%`, width: `${(x1 - x0).toFixed(2)}%` }}>
                <span className={styles.tlGuide} style={{ left: `${at.toFixed(1)}%` }} />
                <span className={`${styles.tlHdot}${counts[i] > 0 ? "" : ` ${styles.tlQuiet}`}`} style={{ left: `${at.toFixed(1)}%`, bottom: `${bottom.toFixed(1)}%` }} />
                <span className={`${styles.tlTip}${edge}`} style={{ left: `${at.toFixed(1)}%`, bottom: `calc(${bottom.toFixed(1)}% + 14px)` }}>
                  <span>{weekRange(weekStart(i))}</span>
                  <b>{counts[i]} signal{counts[i] !== 1 ? "s" : ""}</b>
                </span>
              </span>
            );
          })}
        </div>
      </div>
      <div className={styles.tlAxis}>
        <span>{s0.getUTCDate()} {MONTHS[s0.getUTCMonth()]}</span>
        <span>This week</span>
      </div>
    </div>
  );
}
