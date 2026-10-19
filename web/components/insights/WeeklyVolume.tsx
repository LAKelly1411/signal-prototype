import { MARK_SCORE, WEEKS } from "@/lib/signals/insights";
import styles from "./insights.module.css";
import { monthOf, plural, TableView, weekLabel } from "./TableView";

type Props = {
  starts: Date[];
  counts: number[];
  marks: number[];
  top: number;
  /** Titles of signals scoring MARK_SCORE or more, by week index. */
  markTitles: Record<number, string[]>;
  /** The week's highest-scoring story, by week index; falls back to markTitles. */
  topTitles?: Record<number, string>;
};

const HEIGHT = 100;

/** Signals per calendar week: a line with a light area, a hover column per week, a dot on weeks with a high-relevance signal. */
export function WeeklyVolume({ starts, counts, marks, top, markTitles, topTitles }: Props) {
  const n = counts.length;
  const y = (c: number) => HEIGHT - (c / top) * (HEIGHT - 4);
  const step = n > 1 ? 100 / (n - 1) : 100;
  const pts = counts.map((c, i) => [n > 1 ? i * step : 50, y(c)] as const);
  const line = "M" + pts.map(([x, yy]) => `${x.toFixed(2)},${yy.toFixed(2)}`).join(" L");
  const area = `${line} L100,${HEIGHT} L0,${HEIGHT} Z`;
  const ticks = [0, Math.floor(top / 2), top];
  const story = (i: number) => topTitles?.[i] ?? markTitles[i]?.[0];
  const total = counts.reduce((a, b) => a + b, 0);
  const peak = counts.indexOf(Math.max(...counts));
  const label = n
    ? `Signals per week over the last ${n} weeks, ${total} in all. Busiest: ${counts[peak]} in the week of ${starts[peak].getUTCDate()} ${monthOf(starts[peak])}; ${counts[n - 1]} so far this week.`
    : "No weeks";
  const seen = new Set<number>();
  const months: { i: number; text: string }[] = [];
  starts.forEach((ws, i) => {
    if (!seen.has(ws.getUTCMonth()) && (i > 0 || ws.getUTCDate() <= 7)) {
      seen.add(ws.getUTCMonth());
      months.push({ i, text: monthOf(ws) });
    }
  });

  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <h3 className={styles.cardTitle}>Signals per week</h3>
        <div className={styles.cardSub}>
          {total.toLocaleString("en-US")} signals over {n || WEEKS} weeks ·{" "}
          <span className={styles.keyMark} /> week with a signal scoring {MARK_SCORE}% or more
        </div>
      </div>
      <div className={styles.chart} role="img" aria-label={label}>
        <div className={styles.yaxis}>
          {ticks.map((v) => (
            <span key={v} className={styles.ytick} style={{ bottom: `${((HEIGHT - y(v)) / HEIGHT) * 100}%` }}>{v}</span>
          ))}
        </div>
        <div className={styles.plot}>
          <svg className={styles.svg} viewBox={`0 0 ${HEIGHT} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden="true">
            {[Math.floor(top / 2), top].map((v) => (
              <line key={v} className={styles.grid} x1="0" x2="100" y1={y(v).toFixed(2)} y2={y(v).toFixed(2)} />
            ))}
            <line className={styles.base} x1="0" x2="100" y1={HEIGHT} y2={HEIGHT} />
            <path className={styles.area} d={area} />
            <path className={styles.line} d={line} />
          </svg>
          {marks.map((i) => (
            <span key={i} className={styles.mark} style={{ left: `${pts[i][0].toFixed(2)}%`, bottom: `${(((HEIGHT - pts[i][1]) / HEIGHT) * 100).toFixed(1)}%` }} />
          ))}
          <div className={styles.cols}>
            {pts.map(([x, yy], i) => {
              const x0 = Math.max(0, x - step / 2), x1 = Math.min(100, x + step / 2);
              const at = x1 > x0 ? ((x - x0) / (x1 - x0)) * 100 : 50;
              const bottom = ((HEIGHT - yy) / HEIGHT) * 100;
              const edge = i < 2 ? styles.tipStart : i > n - 3 ? styles.tipEnd : "";
              const s = story(i);
              return (
                <div key={i} className={styles.col} data-week={i} style={{ left: `${x0.toFixed(2)}%`, width: `${(x1 - x0).toFixed(2)}%` }}>
                  <span className={styles.guide} style={{ left: `${at.toFixed(1)}%` }} />
                  <span className={styles.hdot} style={{ left: `${at.toFixed(1)}%`, bottom: `${bottom.toFixed(1)}%` }} />
                  <span className={`pa-tooltip ${styles.tip} ${edge}`} style={{ left: `${at.toFixed(1)}%`, bottom: `calc(${bottom.toFixed(1)}% + 14px)` }}>
                    <span>{i === n - 1 ? "This week" : weekLabel(starts[i])}</span>
                    <b>{plural(counts[i], "signal")}</b>
                    {s ? <span className={styles.tipStory}>Top: {s}</span> : null}
                  </span>
                </div>
              );
            })}
          </div>
          <div className={styles.xaxis}>
            {months.map((m) => (
              <span key={m.i} style={{ left: `${(m.i * step).toFixed(2)}%` }}>{m.text}</span>
            ))}
          </div>
        </div>
      </div>
      <TableView>
        <thead><tr><th>Week</th><th>Signals</th><th>Top story</th></tr></thead>
        <tbody>
          {starts.map((ws, i) => (
            <tr key={i}><td>{weekLabel(ws)}</td><td>{counts[i]}</td><td>{story(i) ?? ""}</td></tr>
          ))}
        </tbody>
      </TableView>
    </div>
  );
}
