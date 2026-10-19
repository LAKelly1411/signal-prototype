import { ACTIVITY_LABELS, ACTIVITY_RING, type Tier } from "@/lib/signals/tiers";
import { RelevanceRing } from "./RelevanceRing";

export function ActivityPill({ tier }: { tier: Tier }) {
  return (
    <div className="pa-pill">
      <RelevanceRing score={ACTIVITY_RING[tier]} />
      <span>{ACTIVITY_LABELS[tier]}</span>
    </div>
  );
}
