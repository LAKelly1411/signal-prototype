import type { SectorRules, Signal } from "@/lib/data/types";
import { categoryIconName } from "@/lib/brand";
import { isExcluded, signalEntities } from "@/lib/signals/entities";
import { computeHeat, computeThemeHeat } from "@/lib/signals/heat";
import { heatTier, themeHeatTier, type Tier } from "@/lib/signals/tiers";
import { dateSpan, niceScale, weeklyCounts } from "@/lib/signals/time";

export type Flag = { text: string; icon: string | null; accent: boolean };
export type Group = {
  id: string;
  kind: "pattern" | "theme";
  title: string;
  tier: Tier;
  heat: number;
  summary: string | null;
  meta: string;
  members: Signal[];
  flags: Flag[];
  companies: string[];
  keyPoints: string[];
  primaryCompany: string | null;
  themeIcon: string | null;
  weeklyCounts: number[];
  active: boolean;
};

export const NOTABLE_PATTERN_TYPES: Record<string, string> = { escalation: "Escalating", wave: "Sector-wide" };
export const DIRECTION_TAGS: Record<string, [string, string, boolean]> = {
  building: ["Building", "trending_up", true],
  steady: ["Steady", "trending_flat", false],
  easing: ["Easing", "trending_down", false],
};

const has = (o: object, k: string) => Object.prototype.hasOwnProperty.call(o, k);

function groupBy(signals: Signal[], key: "cluster_id" | "theme_id"): Map<string, Signal[]> {
  const grouped = new Map<string, Signal[]>();
  for (const s of signals) {
    const k = s[key];
    if (!k) continue;
    const list = grouped.get(k);
    if (list) list.push(s);
    else grouped.set(k, [s]);
  }
  return grouped;
}

/** Counter.most_common(): count descending, first-seen order for ties. */
function mostCommon(names: string[]): string[] {
  const counts = new Map<string, number>();
  for (const n of names) counts.set(n, (counts.get(n) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([n]) => n);
}

export function clusterVerdict(members: Signal[]) {
  return {
    summary: members.find((m) => m.cluster_summary)?.cluster_summary ?? null,
    patternType: members.find((m) => m.cluster_pattern_type)?.cluster_pattern_type ?? null,
    significance: members.find((m) => m.cluster_significance != null)?.cluster_significance ?? null,
    coherent: !members.some((m) => m.cluster_coherent === false),
  };
}

export function buildPatterns(scored: Signal[], rules: SectorRules | null, now: Date): Group[] {
  const coherent = [...groupBy(scored, "cluster_id").values()].filter((m) => clusterVerdict(m).coherent);
  const clusters = coherent
    .map((members) => ({ heat: computeHeat(members, now), members }))
    .sort((a, b) => b.heat - a.heat);

  return clusters.map(({ heat, members }) => {
    const verdict = clusterVerdict(members);
    const companies = mostCommon(members.flatMap((m) => signalEntities(m))).filter((n) => !isExcluded(n, rules));
    const primary = companies.length ? companies[0] : null;
    const sources = new Set(members.map((m) => m.source));
    const flags: Flag[] = [];
    const type = verdict.patternType;
    if (type && has(NOTABLE_PATTERN_TYPES, type)) flags.push({ text: NOTABLE_PATTERN_TYPES[type], icon: "trending_up", accent: true });
    else if (type === "routine") flags.push({ text: "Routine filings", icon: null, accent: false });
    const tier = heatTier(heat).tier;
    return {
      id: members[0].cluster_id as string,
      kind: "pattern" as const,
      title: primary ?? "Unnamed pattern",
      tier,
      heat,
      summary: verdict.summary,
      meta: `${members.length} signals · ${sources.size} ${sources.size === 1 ? "source" : "sources"} · ${dateSpan(members)}`,
      members,
      flags,
      companies: companies.slice(1),
      keyPoints: [],
      primaryCompany: primary,
      themeIcon: null,
      weeklyCounts: weeklyCounts(members, now),
      active: tier !== "Low" && type !== "routine",
    };
  });
}

export function buildThemes(signals: Signal[], rules: SectorRules | null, now: Date): Group[] {
  const themes = [...groupBy(signals, "theme_id").entries()]
    .map(([theme, members]) => ({ heat: computeThemeHeat(members, now, rules), theme, members }))
    .sort((a, b) => b.heat - a.heat);

  return themes.map(({ heat, theme, members }) => {
    const companies = mostCommon(members.flatMap((m) => signalEntities(m)).filter((e) => !isExcluded(e, rules)));
    const direction = members.find((m) => m.theme_direction)?.theme_direction ?? null;
    const flags: Flag[] = [];
    if (direction && has(DIRECTION_TAGS, direction)) {
      const [text, icon, accent] = DIRECTION_TAGS[direction];
      flags.push({ text, icon, accent });
    }
    return {
      id: theme,
      kind: "theme" as const,
      title: theme,
      tier: themeHeatTier(heat).tier,
      heat,
      summary: members.find((m) => m.theme_summary)?.theme_summary ?? null,
      meta: `${members.length} signals · ${companies.length} ${companies.length === 1 ? "company" : "companies"} · ${dateSpan(members)}`,
      members,
      flags,
      companies,
      keyPoints: members.find((m) => m.theme_key_points?.length)?.theme_key_points ?? [],
      primaryCompany: null,
      themeIcon: categoryIconName(theme),
      weeklyCounts: weeklyCounts(members, now),
      active: true,
    };
  });
}

export function sharedScale(groups: Group[]): number {
  return niceScale(Math.max(0, ...groups.map((g) => Math.max(0, ...g.weeklyCounts))));
}
