import { HeatMap } from "@/components/insights/HeatMap";
import styles from "@/components/insights/insights.module.css";
import { Movers } from "@/components/insights/Movers";
import { StatTiles } from "@/components/insights/StatTiles";
import { ThemeMomentum } from "@/components/insights/ThemeMomentum";
import { WeeklyVolume } from "@/components/insights/WeeklyVolume";
import { loadSector } from "@/lib/load";
import type { Signal } from "@/lib/data/types";
import { scoredSignals } from "@/lib/signals/filters";
import { computeThemeHeat } from "@/lib/signals/heat";
import {
  activePatternCount, categoryHeatmap, companyMovers, headlineTiles, themeTrend, weeklyVolume, weekIndexIn,
} from "@/lib/signals/insights";

export const dynamic = "force-dynamic";

export default async function InsightsPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector: slug } = await params;
  const view = await loadSector(slug);
  if (view.state !== "ready") return null;
  const { signals, status, rules, now } = view;
  const scored = scoredSignals(signals);

  // Themes as render_insights builds them: from scored signals, heat-descending.
  const byTheme = new Map<string, Signal[]>();
  for (const s of scored) if (s.theme_id) (byTheme.get(s.theme_id) ?? byTheme.set(s.theme_id, []).get(s.theme_id)!).push(s);
  const themes = [...byTheme.entries()]
    .map(([name, members]) => {
      const [direction, recent, prior] = themeTrend(members, now);
      return { name, heat: computeThemeHeat(members, now, rules), direction, recent, prior };
    })
    .sort((a, b) => b.heat - a.heat);
  // As render_insights: a failed run (an "error" key) has no source counts.
  const ok = status != null && !("error" in status);
  const tiles = headlineTiles(
    scored, now, activePatternCount(scored, now), themes.filter((t) => t.direction === "building").length,
    ok ? status.healthy_sources ?? null : null, ok ? status.total_sources ?? null : null,
  );

  const volume = weeklyVolume(scored, now);
  // The week's top story: highest score, first seen on a tie (as weekly_volume_html).
  const topSignals = new Map<number, Signal>();
  for (const s of scored) {
    const i = weekIndexIn(s, volume.starts);
    if (i !== null && (s.newsworthiness_score || 0) > ((topSignals.get(i)?.newsworthiness_score || 0) || -1)) topSignals.set(i, s);
  }
  const topTitles = Object.fromEntries([...topSignals].map(([i, s]) => [i, s.title]));
  const heat = categoryHeatmap(scored, now);
  const movers = companyMovers(scored, now, rules);

  return (
    <div>
      <StatTiles tiles={tiles} />
      <WeeklyVolume {...volume} topTitles={topTitles} />
      <HeatMap {...heat} />
      <div className={styles.pair}>
        <Movers movers={movers} />
        <ThemeMomentum themes={themes.slice(0, 8)} />
      </div>
    </div>
  );
}
