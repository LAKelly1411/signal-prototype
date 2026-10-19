import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { criteriaFromSearchParams, criteriaToSearchParams, DEFAULT_MIN_SCORE, filterOptions, filterSignals, scoredSignals } from "@/lib/signals/filters";
import { parseDate } from "@/lib/signals/time";

const fx0 = path.join(__dirname, "fixtures/parity");
const src = new FileDataSource({ dataDir: path.join(fx0, "data"), configDir: path.join(fx0, "config") });

describe.each([gambling, fintech])("$slug: filters match Python", (fx) => {
  it("options", async () => {
    const opts = filterOptions(scoredSignals(await src.getSignals(fx.slug)));
    expect(opts.sources).toEqual(fx.filters.options.sources);
    expect(opts.categories).toEqual(fx.filters.options.categories);
    expect(opts.entities).toEqual(fx.filters.options.entities);
  });

  it.each(fx.filters.cases)("case $name", async (c) => {
    const scored = scoredSignals(await src.getSignals(fx.slug));
    const crit = { sourcesOff: c.criteria.sources_off, categoriesOff: c.criteria.categories_off, companies: c.criteria.companies, minScore: c.criteria.min_score, days: c.criteria.days, search: c.criteria.search };
    expect(filterSignals(scored, crit, parseDate(fx.now)).map((s) => s.id)).toEqual(c.ids);
  });
});

describe("date presets and URL round trip", () => {
  const signals = [
    { id: "new", source: "a", title: "t", published_at: "2026-10-15T00:00:00Z", newsworthiness_score: 50, entities: [] },
    { id: "old", source: "a", title: "t", published_at: "2026-08-01T00:00:00Z", newsworthiness_score: 50, entities: [] },
  ] as never[];
  const today = parseDate("2026-10-16T12:00:00Z");
  const base = { sourcesOff: [], categoriesOff: [], companies: [], minScore: 0, search: "" };

  it("last 30 days drops older signals", () => {
    expect(filterSignals(signals, { ...base, days: 30 }, today).map((s) => s.id)).toEqual(["new"]);
    expect(filterSignals(signals, { ...base, days: null }, today)).toHaveLength(2);
  });

  it("defaults leave the URL empty and survive a round trip", () => {
    const opts = filterOptions(signals);
    const def = criteriaFromSearchParams(new URLSearchParams(), opts);
    expect(def.minScore).toBe(DEFAULT_MIN_SCORE);
    expect(criteriaToSearchParams(def).toString()).toBe("");
    const custom = { ...def, search: "fine", sourcesOff: ["a"], days: 7 };
    expect(criteriaFromSearchParams(criteriaToSearchParams(custom), opts)).toEqual(custom);
  });

  it("ignores unknown values in the URL", () => {
    const opts = filterOptions(signals);
    const crit = criteriaFromSearchParams(new URLSearchParams("off=zzz&company=Nobody&min=abc&days=999"), opts);
    expect(crit).toMatchObject({ sourcesOff: [], companies: [], minScore: DEFAULT_MIN_SCORE, days: null });
  });
});
