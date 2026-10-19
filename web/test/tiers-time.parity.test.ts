import { describe, expect, it } from "vitest";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { heatTier, scoreTier, themeHeatTier } from "@/lib/signals/tiers";
import { dateBucket, fullDate, niceScale, parseDate, relativeTime } from "@/lib/signals/time";

describe.each([gambling, fintech])("$slug: tiers and time match Python", (fx) => {
  const now = parseDate(fx.now);

  it.each(fx.tiers)("tiers for $value", (t) => {
    expect(scoreTier(t.value).tier).toBe(t.score_tier);
    expect(heatTier(t.value).tier).toBe(t.heat_tier);
    expect(themeHeatTier(t.value).tier).toBe(t.theme_heat_tier);
  });

  it.each(fx.nice_scale)("nice scale for peak $peak", ({ peak, scale }) => expect(niceScale(peak)).toBe(scale));

  it("relative times", () => {
    for (const r of fx.relative_time) expect(relativeTime(r.published_at, now)).toBe(r.text);
  });

  it("full dates", () => {
    for (const r of fx.full_date) expect(fullDate(r.published_at)).toBe(r.text);
  });

  it("date buckets", () => {
    const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
    for (const b of fx.date_bucket) {
      const pub = new Date(today.getTime() - b.days_ago * 86_400_000);
      expect(dateBucket(pub, today)).toBe(b.bucket);
    }
  });
});

describe("parseDate", () => {
  it("treats a date with no zone as UTC", () => {
    expect(parseDate("2026-10-14T00:00:00").toISOString()).toBe("2026-10-14T00:00:00.000Z");
  });
});

describe("weeklyCounts matches a Python pattern", () => {
  it("agrees with the fixture's weekly_counts", async () => {
    const { FileDataSource } = await import("@/lib/data/files");
    const { weeklyCounts } = await import("@/lib/signals/time");
    const ds = new FileDataSource({
      dataDir: process.cwd() + "/test/fixtures/parity/data",
      configDir: process.cwd() + "/test/fixtures/parity/config",
    });
    const signals = await ds.getSignals("gambling");
    const now = parseDate(gambling.now);
    for (const p of gambling.patterns.slice(0, 5)) {
      const ids = new Set(p.member_ids);
      expect(weeklyCounts(signals.filter((s) => ids.has(s.id)), now)).toEqual(p.weekly_counts);
    }
  });
});
