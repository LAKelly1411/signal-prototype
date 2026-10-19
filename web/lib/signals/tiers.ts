// Port of dashboard/app.py tier tables (lines 41-91, 2157, 2698-2699).
export type Tier = "High" | "Medium" | "Low";
type TierRow = [number, Tier, string, string]; // [min, tier, bg, fg]
export interface TierStyle {
  tier: Tier;
  bg: string;
  fg: string;
}

export const SCORE_TIERS: TierRow[] = [
  [70, "High", "#000000", "#ffffff"],
  [40, "Medium", "#dedad9", "#000000"],
  [0, "Low", "#ffffff", "#000000"],
];

export const HEAT_TIERS: TierRow[] = [
  [90, "High", "#000000", "#ffffff"],
  [60, "Medium", "#dedad9", "#000000"],
  [0, "Low", "#ffffff", "#000000"],
];

export const THEME_HEAT_TIERS: TierRow[] = [
  [200, "High", "#000000", "#ffffff"],
  [130, "Medium", "#dedad9", "#000000"],
  [0, "Low", "#ffffff", "#000000"],
];

function tierOf(value: number, tiers: TierRow[]): TierStyle {
  for (const [min, tier, bg, fg] of tiers) if (value >= min) return { tier, bg, fg };
  const last = tiers[tiers.length - 1];
  return { tier: last[1], bg: last[2], fg: last[3] };
}

export const scoreTier = (score: number): TierStyle => tierOf(score, SCORE_TIERS);
export const heatTier = (heat: number): TierStyle => tierOf(heat, HEAT_TIERS);
export const themeHeatTier = (heat: number): TierStyle => tierOf(heat, THEME_HEAT_TIERS);

export const ACTIVITY_LABELS: Record<Tier, string> = { High: "Very active", Medium: "Active", Low: "Quiet" };
export const ACTIVITY_RING: Record<Tier, number> = { High: 90, Medium: 60, Low: 30 };
export const RELEVANCE_LABELS: Record<Tier, string> = {
  High: "Highly relevant",
  Medium: "Relevant",
  Low: "Low relevance",
};
