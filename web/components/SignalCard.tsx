import type { Signal } from "@/lib/data/types";
import { categoryIconName } from "@/lib/brand";
import { ACTIVITY_LABELS, RELEVANCE_LABELS, heatTier, scoreTier } from "@/lib/signals/tiers";
import { fullDate, relativeTime } from "@/lib/signals/time";
import { isPerson, signalEntities, sourceName } from "@/lib/signals/entities";
import { Icon } from "./Icon";
import { RelevanceRing } from "./RelevanceRing";
import { SourceLogo } from "./SourceLogo";
import { Tag } from "./Tag";
import styles from "./card.module.css";

export const MAX_ENTITY_TAGS = 4;

/** Only http(s) links render; anything else (javascript:, data:, junk) is dropped. */
export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const { protocol } = new URL(url);
    return protocol === "http:" || protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

export interface ClusterInfo { heat: number; size: number }

export function SignalCard({
  signal, now, clusterInfo, compact = false,
}: { signal: Signal; now: Date; clusterInfo?: ClusterInfo; compact?: boolean }) {
  const score = signal.newsworthiness_score ?? 0;
  const tier = scoreTier(score).tier;
  let when = relativeTime(signal.published_at, now);
  let exact = fullDate(signal.published_at);
  if (signal.published_at_estimated) {
    when += " (date estimated)";
    exact += " · estimated from when we collected it";
  }
  const entities = signalEntities(signal);
  const category = signal.canonical_category || signal.category;
  const href = safeUrl(signal.source_url);

  return (
    <div className={`${styles.card}${compact ? ` ${styles.compact}` : ""}`}>
      <div className={styles.head}>
        <div className={styles.source}>
          <SourceLogo source={signal.source} />
          <span className={styles.sourceName}>{sourceName(signal.source)}</span>
          <span className={styles.sep} aria-hidden="true">|</span>
          <span className={styles.time} tabIndex={0}>
            {when}
            <span className={styles.timeTip} role="tooltip">{exact}</span>
          </span>
        </div>
        <div className={styles.relevance}>
          <RelevanceRing score={score} />
          <span><b>{RELEVANCE_LABELS[tier]}</b> ({score}%)</span>
        </div>
      </div>
      <div className={styles.title}>{signal.title}</div>
      <div className={styles.body}>{signal.why_it_matters || ""}</div>
      {clusterInfo ? (
        <div className={styles.pattern}>
          Part of a pattern &middot; {clusterInfo.size} signals &middot; {ACTIVITY_LABELS[heatTier(clusterInfo.heat).tier]} — see Patterns tab
        </div>
      ) : null}
      <div className={styles.foot}>
        <div className={styles.tags}>
          {entities.slice(0, MAX_ENTITY_TAGS).map((e) => (
            <Tag key={e} kind="entity" icon={isPerson(e) ? "person" : "corporate"}>{e}</Tag>
          ))}
          {entities.length > MAX_ENTITY_TAGS ? <Tag kind="plain">{`+${entities.length - MAX_ENTITY_TAGS} more`}</Tag> : null}
          {category ? <Tag kind="accent" icon={categoryIconName(category)}>{category}</Tag> : null}
        </div>
        {href ? (
          <a className={styles.link} href={href} target="_blank" rel="noopener noreferrer">
            Source <Icon name="link" size={16} />
          </a>
        ) : null}
      </div>
    </div>
  );
}
