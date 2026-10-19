import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { buildPatterns, buildThemes, sharedScale } from "@/lib/signals/groups";
import { parseDate } from "@/lib/signals/time";

const fxDir = path.join(__dirname, "fixtures/parity");
const src = new FileDataSource({ dataDir: path.join(fxDir, "data"), configDir: path.join(fxDir, "config") });

describe.each([gambling, fintech])("$slug: groups match Python", (fx) => {
  const now = parseDate(fx.now);

  it("patterns: same clusters, order, titles, tiers, meta, companies, weeks", async () => {
    const [signals, rules] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug)]);
    const scored = signals.filter((s) => s.newsworthiness_score != null).sort((a, b) => b.published_at.localeCompare(a.published_at));
    const got = buildPatterns(scored, rules, now);
    expect(got.map((g) => g.id)).toEqual(fx.patterns.map((p) => p.id));
    got.forEach((g, i) => {
      const p = fx.patterns[i];
      expect({ title: g.title, tier: g.tier, active: g.active, summary: g.summary, meta: g.meta, companies: g.companies, weekly: g.weeklyCounts, members: g.members.map((m) => m.id) })
        .toEqual({ title: p.title, tier: p.tier, active: p.active, summary: p.summary, meta: p.meta, companies: p.companies, weekly: p.weekly_counts, members: p.member_ids });
    });
    expect(sharedScale(got)).toBe(fx.pattern_scale);
  });

  it("themes: same themes, order, tiers, meta, companies, direction, key points, weeks", async () => {
    const [signals, rules] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug)]);
    const got = buildThemes(signals, rules, now);
    expect(got.map((g) => g.id)).toEqual(fx.themes.map((t) => t.id));
    got.forEach((g, i) => {
      const t = fx.themes[i];
      expect({ tier: g.tier, summary: g.summary, meta: g.meta, companies: g.companies, keyPoints: g.keyPoints, weekly: g.weeklyCounts, direction: g.flags[0]?.text ?? null })
        .toEqual({ tier: t.tier, summary: t.summary, meta: t.meta, companies: t.companies, keyPoints: t.key_points, weekly: t.weekly_counts, direction: t.direction ? ({ building: "Building", steady: "Steady", easing: "Easing" } as Record<string, string>)[t.direction] ?? null : null });
    });
    expect(sharedScale(got)).toBe(fx.theme_scale);
  });
});
