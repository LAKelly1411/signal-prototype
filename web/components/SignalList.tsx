import type { Signal } from "@/lib/data/types";
import { isPerson, signalEntities, sourceName } from "@/lib/signals/entities";
import { fullDate, parseDate, weekIndex } from "@/lib/signals/time";
import { Icon } from "./Icon";
import { RelevanceRing } from "./RelevanceRing";
import { safeUrl } from "./SignalCard";
import { SourceLogo } from "./SourceLogo";
import { Tag } from "./Tag";
import styles from "./pane.module.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function shortDate(iso: string, now: Date): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return "";
  const year = +m[1];
  return `${+m[3]} ${MONTHS[+m[2] - 1]}${year !== now.getUTCFullYear() ? ` ${year}` : ""}`;
}

/** The pane's signals, newest first; each row opens in place (one at a time per group). */
export function SignalList({
  members, now, groupId, onWeek,
}: { members: Signal[]; now: Date; groupId: string; onWeek: (week: number | null) => void }) {
  const sorted = [...members].sort((a, b) => parseDate(b.published_at).getTime() - parseDate(a.published_at).getTime());
  return (
    <div className={styles.list} role="list">
      {sorted.map((m) => {
        const estimated = !!m.published_at_estimated;
        const date = (estimated ? "~" : "") + shortDate(m.published_at, now);
        const exact = fullDate(m.published_at) + (estimated ? " · estimated from when we collected it" : "");
        const week = weekIndex(m, now);
        const category = m.canonical_category || m.category;
        const score = m.newsworthiness_score;
        const entities = signalEntities(m);
        const href = safeUrl(m.source_url);
        return (
          <details
            key={m.id}
            role="listitem"
            className={styles.item}
            name={`sp-${groupId}`}
            data-week={week ?? undefined}
            onMouseEnter={() => onWeek(week)}
            onMouseLeave={() => onWeek(null)}
          >
            <summary className={styles.row}>
              <time className={styles.date} title={exact}>{date}</time>
              <span className={styles.main}>
                <span className={styles.sigTitle} data-signal-title>{m.title}</span>
                {m.why_it_matters ? <span className={styles.sigBody}>{m.why_it_matters}</span> : null}
                <span className={styles.sigMeta}>
                  <span className={styles.src}><SourceLogo source={m.source} />{sourceName(m.source)}</span>
                  {category ? <><span className={styles.sep} aria-hidden="true">·</span>{category}</> : null}
                  {score != null ? (
                    <><span className={styles.sep} aria-hidden="true">·</span>
                      <span className={styles.rel} title={`${score}% relevant`}><RelevanceRing score={score} />{score}%</span></>
                  ) : null}
                </span>
              </span>
            </summary>
            <div className={styles.more}>
              {entities.length ? (
                <div className={styles.sigTags}>
                  {entities.map((e) => <Tag key={e} kind="entity" icon={isPerson(e) ? "person" : "corporate"}>{e}</Tag>)}
                </div>
              ) : null}
              <div className={styles.when}>{exact}</div>
              {href ? (
                <a className={styles.open} href={href} target="_blank" rel="noopener noreferrer">
                  Open source <Icon name="link" size={12} />
                </a>
              ) : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}
