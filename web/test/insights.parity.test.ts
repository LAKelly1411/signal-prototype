import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { scoredSignals } from "@/lib/signals/filters";
import { buildPatterns } from "@/lib/signals/groups";
import { computeThemeHeat } from "@/lib/signals/heat";
import { categoryHeatmap, companyMovers, headlineTiles, themeTrend, weeklyVolume } from "@/lib/signals/insights";
import { parseDate } from "@/lib/signals/time";

const fx0 = path.join(__dirname, "fixtures/parity");
const src = new FileDataSource({ dataDir: path.join(fx0, "data"), configDir: path.join(fx0, "config") });

describe.each([gambling, fintech])("$slug: insights match Python", (fx) => {
  const now = parseDate(fx.now);
  const load = async () => {
    const [signals, rules, status] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug), src.getRunStatus(fx.slug)]);
    return { signals, rules, status: status as Record<string, unknown> | null, scored: scoredSignals(signals) };
  };
  const themesOf = (scored: Awaited<ReturnType<typeof load>>["scored"], rules: Awaited<ReturnType<typeof load>>["rules"]) => {
    const by = new Map<string, typeof scored>();
    for (const s of scored) if (s.theme_id) by.set(s.theme_id, [...(by.get(s.theme_id) ?? []), s]);
    return [...by].map(([name, m]) => {
      const [direction, recent, prior] = themeTrend(m, now);
      return { name, heat: computeThemeHeat(m, now, rules), direction, recent, prior };
    }).sort((a, b) => b.heat - a.heat);
  };

  it("headline tiles", async () => {
    const { scored, rules, status } = await load();
    const active = buildPatterns(scored, rules, now).filter((p) => p.active).length;
    const building = themesOf(scored, rules).filter((t) => t.direction === "building").length;
    const ok = status && !("error" in status);
    expect(headlineTiles(scored, now, active, building, ok ? (status.healthy_sources as number) ?? null : null, ok ? (status.total_sources as number) ?? null : null)).toEqual(fx.insights.tiles);
  });

  it("weekly volume", async () => {
    const { scored } = await load();
    const v = weeklyVolume(scored, now);
    expect({ counts: v.counts, marks: v.marks, top: v.top }).toEqual(fx.insights.volume);
  });

  it("category heat map", async () => {
    const { scored } = await load();
    const h = categoryHeatmap(scored, now);
    expect({ rows: h.rows, thresholds: h.thresholds }).toEqual(fx.insights.heatmap);
  });

  it("company movers", async () => {
    const { scored, rules } = await load();
    expect(companyMovers(scored, now, rules)).toEqual(fx.insights.movers);
  });

  it("theme trends", async () => {
    const { scored, rules } = await load();
    expect(themesOf(scored, rules)).toEqual(fx.insights.themes);
  });
});
