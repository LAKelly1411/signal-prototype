import { CompanyLogo } from "@/components/SourceLogo";
import { RelevanceRing } from "@/components/RelevanceRing";
import styles from "./insights.module.css";
import { TableView } from "./TableView";

type Mover = { name: string; count: number; top: number; change: number; weekly: number[] };

function MiniSpark({ counts }: { counts: number[] }) {
  const peak = Math.max(...counts) || 1;
  const step = counts.length > 1 ? 100 / (counts.length - 1) : 100;
  const pts = counts.map((c, i) => `${(i * step).toFixed(1)},${(24 - (c / peak) * 20).toFixed(1)}`).join(" ");
  return (
    <svg className={styles.spark} viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} />
    </svg>
  );
}

export function Movers({ movers }: { movers: Mover[] }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <h3 className={styles.cardTitle}>Companies in the news</h3>
        <div className={styles.cardSub}>
          Companies behind the most relevant signals of the last 30 days, ranked by their best score. Change is in signals
          against the 30 days before. Regulators and government bodies are left out.
        </div>
      </div>
      {movers.length === 0 ? (
        <div className={styles.empty}>No companies named in the last 30 days.</div>
      ) : (
        <>
          <div className={styles.mhead}><span>Company</span><span>18 weeks</span><span>Top</span><span>Signals</span><span>Change</span></div>
          {movers.map((m) => (
            <div key={m.name} className={styles.mrow}>
              <span className={styles.mname}><CompanyLogo name={m.name} /><span>{m.name}</span></span>
              <MiniSpark counts={m.weekly} />
              <span className={styles.mtop} title="Best relevance score"><RelevanceRing score={m.top} />{m.top}%</span>
              <span className={styles.mcount}>{m.count}</span>
              <span className={styles.mchange} title="Change vs the previous 30 days">
                {m.change !== 0 ? <span aria-hidden="true">{m.change > 0 ? "▲" : "▼"} </span> : null}
                {m.change > 0 ? `+${m.change}` : m.change < 0 ? `−${Math.abs(m.change)}` : "0"}
              </span>
            </div>
          ))}
          <TableView>
            <thead><tr><th>Company</th><th>Best score</th><th>Signals</th><th>Change vs previous 30 days</th></tr></thead>
            <tbody>
              {movers.map((m) => (
                <tr key={m.name}><td>{m.name}</td><td>{m.top}%</td><td>{m.count}</td><td>{m.change > 0 ? `+${m.change}` : m.change < 0 ? `−${Math.abs(m.change)}` : "0"}</td></tr>
              ))}
            </tbody>
          </TableView>
        </>
      )}
    </div>
  );
}
