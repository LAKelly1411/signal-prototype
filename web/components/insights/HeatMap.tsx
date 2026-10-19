import { Icon } from "@/components/Icon";
import { categoryIconName } from "@/lib/brand";
import { HEAT_EMPTY, HEAT_RAMP, heatStep } from "@/lib/signals/insights";
import styles from "./insights.module.css";
import { monthOf, plural, TableView, weekLabel } from "./TableView";

type Row = { category: string; counts: number[]; total: number };

/** Categories (busiest first) by calendar week; the cell shade is the count. */
export function HeatMap({ starts, rows, thresholds }: { starts: Date[]; rows: Row[]; thresholds: number[] }) {
  const n = starts.length;
  const lows = [1, ...thresholds.slice(0, -1).map((t) => t + 1)];
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <h3 className={styles.cardTitle}>What kind of news, week by week</h3>
        <div className={styles.cardSub}>Signals per category each week. Darker means more.</div>
      </div>
      <div className={styles.heat} role="table" aria-label="Signals per category by week" style={{ ["--weeks" as string]: n }}>
        <div className={styles.hrow} role="row" aria-hidden="true">
          <span />
          {starts.map((ws, i) => (
            <span key={i} className={styles.hmonth}>{i === 0 || ws.getUTCMonth() !== starts[i - 1].getUTCMonth() ? monthOf(ws) : ""}</span>
          ))}
          <span />
        </div>
        {rows.map((r) => (
          <div key={r.category} className={styles.hrow} role="row">
            <span className={styles.hname} role="rowheader">
              <span className={styles.hicon}><Icon name={categoryIconName(r.category)} size={16} /></span>
              <span className={styles.hlabel}>{r.category}</span>
            </span>
            {r.counts.map((c, i) => (
              <span
                key={i}
                data-cell=""
                role="cell"
                className={styles.cell}
                tabIndex={0}
                style={{ background: heatStep(c, thresholds) }}
                aria-label={`${r.category}, ${weekLabel(starts[i])}: ${plural(c, "signal")}`}
              >
                <span className={`pa-tooltip ${styles.cellTip} ${i > n - 4 ? styles.tipEnd : ""}`} aria-hidden="true">
                  <span>{r.category} · {weekLabel(starts[i])}</span>
                  <b>{plural(c, "signal")}</b>
                </span>
              </span>
            ))}
            <span className={styles.htotal} role="cell">{r.total}</span>
          </div>
        ))}
      </div>
      <div className={styles.legend}>
        <span className={styles.legendItem}><span className={styles.swatch} style={{ background: HEAT_EMPTY }} />0</span>
        {HEAT_RAMP.map((colour, i) => (
          <span key={colour} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: colour }} />
            {lows[i] === thresholds[i] ? lows[i] : `${lows[i]}–${thresholds[i]}`}
          </span>
        ))}
      </div>
      <TableView scroll>
        <thead>
          <tr>
            <th>Category</th>
            {starts.map((ws, i) => <th key={i}>{ws.getUTCDate()} {monthOf(ws)}</th>)}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.category}>
              {/* A cell, not a row header: the grid above already carries the row headers. */}
              <td><strong>{r.category}</strong></td>
              {r.counts.map((c, i) => <td key={i}>{c}</td>)}
              <td>{r.total}</td>
            </tr>
          ))}
        </tbody>
      </TableView>
    </div>
  );
}
