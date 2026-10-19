// Port of compute_heat / compute_theme_heat in src/cluster.py.
import type { SectorRules, Signal } from "@/lib/data/types";
import { isExcluded, signalEntities } from "@/lib/signals/entities";
import { parseDate } from "@/lib/signals/time";

export const CLUSTER_WINDOW_DAYS = 90;
export const RECENCY_MAX = 30;
export const SIGNIFICANT_SCORE = 40;
export const MIN_THEME_COMPANIES = 3;
export const PEAK_SCORE_MAX = 30;
export const MODEL_SIGNIFICANCE_MAX = 25;

const DAY_MS = 86_400_000;

const score = (m: Signal) => m.newsworthiness_score || 0;

function daysSince(members: Signal[], now: Date): number {
  const recent = Math.max(...members.map((m) => parseDate(m.published_at).getTime()));
  return Math.max(0, Math.floor((now.getTime() - recent) / DAY_MS));
}

export function computeThemeHeat(
  members: Signal[],
  now: Date,
  rules: SectorRules | null,
  windowDays = CLUSTER_WINDOW_DAYS,
): number {
  const companies = new Set<string>();
  for (const m of members)
    for (const e of signalEntities(m)) if (!isExcluded(e, rules)) companies.add(e.trim().toLowerCase());
  const best = Math.max(...members.map(score));
  return (
    members.length * 5 +
    companies.size * 10 +
    (PEAK_SCORE_MAX * best) / 100 +
    (RECENCY_MAX * Math.max(0, windowDays - daysSince(members, now))) / windowDays
  );
}

export function computeHeat(members: Signal[], now: Date, windowDays = CLUSTER_WINDOW_DAYS): number {
  const significant = members.filter((m) => score(m) >= SIGNIFICANT_SCORE);
  const numSources = new Set(significant.map((m) => m.source)).size;
  const peak = (PEAK_SCORE_MAX * Math.max(...members.map(score))) / 100;
  const recency = (RECENCY_MAX * Math.max(0, windowDays - daysSince(members, now))) / windowDays;
  const sig = members.find((m) => m.cluster_significance != null)?.cluster_significance;
  const model = sig != null ? (MODEL_SIGNIFICANCE_MAX * sig) / 100 : 0;
  return significant.length * 10 + numSources * 20 + peak + recency + model;
}
