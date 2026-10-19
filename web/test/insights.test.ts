import { describe, expect, it } from "vitest";
import {
  HEAT_EMPTY, HEAT_RAMP, WEEKS, categoryHeatmap, companyMovers, headlineTiles, heatStep, heatThresholds,
  niceTop, themeTrend, weekIndexIn, weekStarts,
} from "@/lib/signals/insights";

const NOW = new Date("2026-10-08T12:00:00Z");
const sig = (daysAgo: number, score = 40, category = "Insolvency", entities: string[] = [], title = "t") =>
  ({ id: `${daysAgo}-${score}-${title}-${Math.random()}`, source: "x", title, published_at: new Date(NOW.getTime() - daysAgo * 86_400_000).toISOString(), newsworthiness_score: score, canonical_category: category, entities, canonical_entities: entities }) as never;

describe("weeks", () => {
  it("week starts are Mondays ending this week", () => {
    const starts = weekStarts(NOW);
    expect(starts).toHaveLength(WEEKS);
    expect(starts.every((s) => s.getUTCDay() === 1 && s.getUTCHours() === 0)).toBe(true);
    expect(starts[starts.length - 1].toISOString()).toBe("2026-10-05T00:00:00.000Z");
  });
  it("week index", () => {
    const starts = weekStarts(NOW);
    expect(weekIndexIn(sig(0), starts)).toBe(WEEKS - 1);
    expect(weekIndexIn(sig(7), starts)).toBe(WEEKS - 2);
    expect(weekIndexIn(sig(400), starts)).toBeNull();
  });
  it("nice top", () => {
    expect(niceTop(1)).toBe(2);
    expect(niceTop(44)).toBe(50);
    expect(niceTop(250)).toBe(250);
  });
});

describe("tiles", () => {
  it("counts and comparisons", () => {
    const signals = [sig(1), sig(2), sig(3, 75), ...Array.from({ length: 8 }, (_, i) => sig(10 + i))];
    const by = Object.fromEntries(headlineTiles(signals, NOW, 4, 2, 8, 9).map((t) => [t.label, t]));
    expect(by["Signals this week"].value).toBe("3");
    expect(by["Signals this week"].note).toBe("+1 vs 4-week average");
    expect(by["High relevance, last 30 days"].value).toBe("1");
    expect(by["Active patterns"].value).toBe("4");
    expect(by["Themes building"].value).toBe("2");
    expect(by["Sources healthy"].value).toBe("8/9");
  });
  it("no status drops the sources tile", () => {
    const tiles = headlineTiles([], NOW, 0, 0, null, null);
    expect(tiles[tiles.length - 1].label).toBe("Themes building");
    expect(tiles[0].note).toBe("Level with 4-week average");
  });
});

describe("heat map", () => {
  it("rows busiest first with totals", () => {
    const signals = [sig(0, 40, "Policy and legislation"), sig(0, 40, "Policy and legislation"), sig(0, 40, "Policy and legislation"), sig(0, 40, "Insolvency")];
    expect(categoryHeatmap(signals, NOW).rows.map((r) => [r.category, r.total])).toEqual([["Policy and legislation", 3], ["Insolvency", 1]]);
  });
  it("steps", () => {
    const th = heatThresholds([1, 1, 2, 3, 5, 8, 13, 0, 0]);
    expect(th).toEqual([...th].sort((a, b) => a - b));
    expect(th).toHaveLength(5);
    expect(th[th.length - 1]).toBeGreaterThanOrEqual(13);
    expect(heatStep(0, th)).toBe(HEAT_EMPTY);
    expect(heatStep(1, th)).toBe(HEAT_RAMP[0]);
    expect(heatStep(13, th)).toBe(HEAT_RAMP[HEAT_RAMP.length - 1]);
  });
  it("small counts use one step each", () => {
    expect(heatThresholds([1, 2, 3])).toEqual([1, 2, 3, 4, 5]);
  });
});

describe("movers", () => {
  const rules = { slug: "g", name: "G", categories: [], companies: [], excludedBodies: ["Gambling Commission"] };
  it("ranks by best relevance and excludes regulators", () => {
    const g = ["Global Gaming Ventures", "Gambling Commission"];
    const signals = [
      ...Array.from({ length: 4 }, () => sig(1, 30, "Insolvency", g)),
      sig(2, 78, "Insolvency", ["Rank"]),
      ...Array.from({ length: 5 }, () => sig(40, 20, "Insolvency", ["Global Gaming Ventures"])),
    ];
    const movers = companyMovers(signals, NOW, rules);
    expect(movers.map((m) => m.name)).toEqual(["Rank", "Global Gaming Ventures"]);
    expect(movers[0].top).toBe(78);
    expect(movers[0].count).toBe(1);
    expect(movers[1].count).toBe(4);
    expect(movers[1].change).toBe(-1);
  });
  it("ties on top score go to more total relevance", () => {
    const signals = [sig(1, 60, "Insolvency", ["A"]), sig(1, 60, "Insolvency", ["B"]), sig(2, 50, "Insolvency", ["B"])];
    expect(companyMovers(signals, NOW, null).map((m) => m.name)).toEqual(["B", "A"]);
  });
});

describe("themes", () => {
  it("trend from the data", () => {
    const theme = (recent: number, prior: number) => [...Array.from({ length: recent }, () => sig(5)), ...Array.from({ length: prior }, () => sig(40))];
    expect(themeTrend(theme(11, 5), NOW)).toEqual(["building", 11, 5]);
    expect(themeTrend(theme(7, 39), NOW)).toEqual(["easing", 7, 39]);
    expect(themeTrend(theme(4, 4), NOW)[0]).toBe("steady");
    expect(themeTrend(theme(2, 1), NOW)[0]).toBe("steady");
    expect(themeTrend(theme(1, 0), NOW)[0]).toBe("steady");
  });
});
