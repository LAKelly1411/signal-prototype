import { GroupList } from "@/components/GroupList";
import { MIN_THEME_COMPANIES } from "@/lib/signals/heat";
import { buildThemes, sharedScale } from "@/lib/signals/groups";
import styles from "@/components/groups.module.css";
import { loadSector } from "@/lib/load";

export default async function ThemesPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector } = await params;
  const view = await loadSector(sector);
  if (view.state !== "ready") return null;

  const groups = buildThemes(view.signals, view.rules, view.now);
  if (!groups.length) {
    return (
      <p className={styles.note} role="status">
        {`No sector-wide themes yet — a theme needs signals of the same kind naming at least ${MIN_THEME_COMPANIES} different companies within the last 90 days.`}
      </p>
    );
  }
  return (
    <>
      <p className={styles.caption}>
        Themes group signals by what happened rather than who it happened to, so a run of similar events across different companies reads as one pattern.
      </p>
      <GroupList groups={groups} param="theme" scale={sharedScale(groups)} now={view.now} />
    </>
  );
}
