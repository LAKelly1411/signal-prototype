"use client";

import { useState } from "react";
import type { Group } from "@/lib/signals/groups";
import { ActivityPill } from "./ActivityPill";
import { GroupTile, SP_COMPANY_TAGS, TagRow } from "./GroupCard";
import { SignalList } from "./SignalList";
import { Sparkline } from "./Sparkline";
import groups from "./groups.module.css";
import styles from "./pane.module.css";

export function PreviewPane({ group, scale, now, onClose }: { group: Group; scale: number; now: Date; onClose: () => void }) {
  const [week, setWeek] = useState<number | null>(null);
  const start = new Date(now.getTime() - group.weeklyCounts.length * 7 * 86_400_000);
  const hasBody = !!group.summary || group.keyPoints.length > 0;
  const manyCompanies = group.companies.length > SP_COMPANY_TAGS;
  return (
    <aside className={styles.pane} aria-label={group.title} data-pane data-week={week ?? undefined}>
      <div className={styles.head}>
        <button type="button" className={styles.close} aria-label="Close preview" onClick={onClose}>
          <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
            <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
        <div className={styles.headBody}>
          <div className={styles.titleRow}>
            <span className={groups.source}>
              <GroupTile group={group} />
              <span className={groups.title}>{group.title}</span>
            </span>
            <ActivityPill tier={group.tier} />
          </div>
          <div className={groups.meta}>{group.meta}</div>
          {hasBody || manyCompanies ? (
            <details className={`${styles.toggle} sp-toggle`}>
              <summary>
                <span className={styles.toggleOpen}>{hasBody ? "Show summary" : "Show all companies"}</span>
                <span className={styles.toggleClose}>Show less</span>
              </summary>
              {group.summary ? <div className={styles.summary}>{group.summary}</div> : null}
              {group.keyPoints.length ? (
                <ul className={styles.points}>{group.keyPoints.map((p) => <li key={p}>{p}</li>)}</ul>
              ) : null}
            </details>
          ) : null}
          <Sparkline counts={group.weeklyCounts} scale={scale} start={start} />
          <TagRow group={group} limit={SP_COMPANY_TAGS} className={`${groups.tags} ${styles.tagsTrim} gc-tags`} />
          {manyCompanies ? <TagRow group={group} limit={null} className={`${groups.tags} ${styles.tagsAll} gc-tags gc-tags-all`} /> : null}
        </div>
      </div>
      <div className={styles.section}>Signals ({group.members.length})</div>
      <SignalList members={group.members} now={now} groupId={group.id} onWeek={setWeek} />
    </aside>
  );
}
