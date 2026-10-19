import type { RunStatus } from "@/lib/data/types";
import { humaniseAge, parseDate } from "@/lib/signals/time";
import { sourceName } from "@/lib/signals/entities";
import styles from "./shell.module.css";

/** Freshness and source health at a glance, so a quiet collector doesn't read as a slow news week. */
export function StatusStrip({ status, now }: { status: RunStatus | null; now: Date }) {
  if (!status) return null;
  const finished = parseDate(status.finished_at);
  if (Number.isNaN(finished.getTime())) return null;

  const age = (now.getTime() - finished.getTime()) / 1000;
  const healthy = status.healthy_sources ?? 0;
  const total = status.total_sources ?? 0;

  if ("error" in status && status.error) {
    // A failed run writes no source counts; don't read that as healthy.
    return <div className={`pa-status is-error ${styles.strip}`}>Last update failed · {humaniseAge(age)}</div>;
  }

  let cls: string;
  let detail: string;
  if (age > 12 * 3600) { cls = "is-error"; detail = "pipeline may have stopped running"; }
  else if (healthy < total) { cls = "is-warn"; detail = `${total - healthy} source(s) returned nothing`; }
  else { cls = styles.ok; detail = "all sources healthy"; }
  const unscored = Number((status as { unscored?: number }).unscored ?? 0);
  if (unscored) detail += ` · ${unscored} awaiting scoring`;

  const failing = Object.entries(status.sources ?? {}).filter(([, i]) => !i.ok).map(([n]) => n).sort();
  return (
    <div>
      <div className={`pa-status ${cls} ${styles.strip}`}>{`Updated ${humaniseAge(age)} · ${healthy}/${total} sources · ${detail}`}</div>
      {failing.length > 0 && (
        <details className={styles.sources}>
          <summary>Which sources returned nothing?</summary>
          {failing.map(sourceName).join(", ")}
        </details>
      )}
    </div>
  );
}
