import { QuietToggle } from "@/components/QuietToggle";
import { GroupList } from "@/components/GroupList";
import { buildPatterns, sharedScale } from "@/lib/signals/groups";
import styles from "@/components/groups.module.css";
import { loadSector } from "@/lib/load";

export default async function PatternsPage({
  params, searchParams,
}: { params: Promise<{ sector: string }>; searchParams: Promise<{ quiet?: string }> }) {
  const { sector } = await params;
  const { quiet } = await searchParams;
  const view = await loadSector(sector);
  if (view.state !== "ready") return null;

  const showQuiet = quiet === "1";
  const scored = view.signals.filter((s) => s.newsworthiness_score != null);
  const all = buildPatterns(scored, view.rules, view.now);
  if (!all.length) {
    return (
      <p className={styles.note} role="status">
        No emerging patterns yet — a pattern needs two or more signals naming the same company within the last 90 days.
      </p>
    );
  }
  const shown = showQuiet ? all : all.filter((g) => g.active);
  const caption = showQuiet ? `All ${shown.length} patterns.` : `${shown.length} active patterns of ${all.length}.`;
  return (
    <>
      <QuietToggle checked={showQuiet} href={showQuiet ? `/${sector}/patterns` : `/${sector}/patterns?quiet=1`} />
      <p className={styles.caption}>{caption}</p>
      {shown.length ? (
        <GroupList groups={shown} param="pattern" scale={sharedScale(shown)} now={view.now} />
      ) : (
        <p className={styles.note} role="status">No active patterns right now — show quieter patterns to see the rest.</p>
      )}
    </>
  );
}
