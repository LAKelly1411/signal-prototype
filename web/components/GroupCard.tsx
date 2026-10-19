import type { ReactNode } from "react";
import type { Flag, Group } from "@/lib/signals/groups";
import { isPerson } from "@/lib/signals/entities";
import { ActivityPill } from "./ActivityPill";
import { CompanyLogo } from "./SourceLogo";
import { Icon } from "./Icon";
import { Tag } from "./Tag";
import { Sparkline } from "./Sparkline";
import styles from "./groups.module.css";

export const MAX_COMPANY_TAGS = 3;
export const SP_COMPANY_TAGS = 5;

export function GroupTile({ group }: { group: Group }) {
  if (group.kind === "pattern" && group.primaryCompany) return <CompanyLogo name={group.primaryCompany} />;
  return (
    <span className={styles.themeTile}>
      <Icon name={group.themeIcon ?? "label"} size={18} />
    </span>
  );
}

export function FlagTag({ flag }: { flag: Flag }) {
  if (!flag.icon) return <span className={`pa-tag ${flag.accent ? "pa-tag-accent " : ""}pa-tag-plain`}>{flag.text}</span>;
  return <Tag kind={flag.accent ? "accent" : "entity"} icon={flag.icon}>{flag.text}</Tag>;
}

/** Flags, then the first `limit` companies (all if null), then "+N more". */
export function TagRow({ group, limit, className }: { group: Group; limit: number | null; className: string }): ReactNode {
  const shown = limit === null ? group.companies : group.companies.slice(0, limit);
  const rest = group.companies.length - shown.length;
  if (!group.flags.length && !shown.length) return null;
  return (
    <span className={className}>
      {group.flags.map((f) => <FlagTag key={f.text} flag={f} />)}
      {shown.map((c) => <Tag key={c} kind="entity" icon={isPerson(c) ? "person" : "corporate"}>{c}</Tag>)}
      {rest > 0 ? <Tag kind="plain">{`+${rest} more`}</Tag> : null}
    </span>
  );
}

export function GroupCard({
  group, selected, scale, now, onSelect,
}: { group: Group; selected: boolean; scale: number; now: Date; onSelect: () => void }) {
  const start = new Date(now.getTime() - group.weeklyCounts.length * 7 * 86_400_000);
  return (
    <button
      type="button"
      className={`${styles.card}${selected ? ` ${styles.selected}` : ""}`}
      aria-pressed={selected}
      data-group-id={group.id}
      aria-label={selected ? `${group.title}, showing in preview` : `Preview ${group.title}`}
      onClick={onSelect}
    >
      <span className={styles.head}>
        <span className={styles.source}>
          <GroupTile group={group} />
          <span className={styles.title}>{group.title}</span>
        </span>
        <ActivityPill tier={group.tier} />
      </span>
      {group.summary ? <span className={styles.summary}>{group.summary}</span> : null}
      <span className={styles.meta}>{group.meta}</span>
      <Sparkline counts={group.weeklyCounts} scale={scale} start={start} />
      <TagRow group={group} limit={MAX_COMPANY_TAGS} className={`${styles.tags} gc-tags`} />
    </button>
  );
}
