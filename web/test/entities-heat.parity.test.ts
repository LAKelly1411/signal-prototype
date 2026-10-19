import { describe, expect, it } from "vitest";
import path from "node:path";
import gambling from "./fixtures/parity/gambling.json";
import fintech from "./fixtures/parity/fintech.json";
import { FileDataSource } from "@/lib/data/files";
import { isExcluded, isPerson, signalEntities } from "@/lib/signals/entities";
import { computeHeat, computeThemeHeat } from "@/lib/signals/heat";
import { parseDate } from "@/lib/signals/time";

const fx0 = path.join(__dirname, "fixtures/parity");
const src = new FileDataSource({ dataDir: path.join(fx0, "data"), configDir: path.join(fx0, "config") });

describe.each([gambling, fintech])("$slug: entities and heat match Python", (fx) => {
  it("person and exclusion checks", async () => {
    const rules = await src.getSectorRules(fx.slug);
    for (const e of fx.entities) {
      expect(isPerson(e.name), e.name).toBe(e.is_person);
      expect(isExcluded(e.name, rules), e.name).toBe(e.excluded);
    }
  });

  it("pattern heat", async () => {
    const signals = await src.getSignals(fx.slug);
    const byId = new Map(signals.map((s) => [s.id, s]));
    for (const p of fx.patterns) {
      const members = p.member_ids.map((id: string) => byId.get(id)!);
      expect(computeHeat(members, parseDate(fx.now))).toBeCloseTo(p.heat, 6);
    }
  });

  it("theme heat", async () => {
    const [signals, rules] = await Promise.all([src.getSignals(fx.slug), src.getSectorRules(fx.slug)]);
    const byId = new Map(signals.map((s) => [s.id, s]));
    for (const t of fx.themes) {
      const members = t.member_ids.map((id: string) => byId.get(id)!);
      expect(computeThemeHeat(members, parseDate(fx.now), rules)).toBeCloseTo(t.heat, 6);
    }
  });
});

describe("signalEntities", () => {
  it("prefers canonical entities and falls back to raw ones", () => {
    expect(signalEntities({ canonical_entities: ["Entain"], entities: ["Entain plc"] } as never)).toEqual(["Entain"]);
    expect(signalEntities({ entities: ["Acme"] } as never)).toEqual(["Acme"]);
    expect(signalEntities({} as never)).toEqual([]);
  });
});
