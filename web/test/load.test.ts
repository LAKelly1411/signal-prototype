import { describe, expect, it, vi } from "vitest";
import { DataError } from "@/lib/data/errors";
import { loadSector } from "@/lib/load";

vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("NEXT_NOT_FOUND"); } }));

const sectors = [
  { slug: "demo", name: "Demo", status: "ready", signal_count: 1 },
  { slug: "newbie", name: "New", status: "setting_up", signal_count: 0 },
];
const fake = (over: Partial<Record<string, unknown>> = {}) => ({
  listSectors: async () => sectors,
  getSignals: async (s: string) => { if (s === "newbie") throw new DataError("not_found", "x"); return [{ id: "a", source: "x", title: "t", published_at: "2026-10-15T00:00:00Z", newsworthiness_score: 50, entities: [] }]; },
  getRunStatus: async () => null,
  getSectorRules: async () => ({ slug: "demo", name: "Demo", categories: [], companies: [], excludedBodies: [] }),
  ...over,
}) as never;

describe("loadSector", () => {
  it("loads a ready sector", async () => expect((await loadSector("demo", fake())).state).toBe("ready"));
  it("reports setting up rather than erroring", async () => expect((await loadSector("newbie", fake())).state).toBe("setting_up"));
  it("reports empty when there are no signals", async () => expect((await loadSector("demo", fake({ getSignals: async () => [] }))).state).toBe("empty"));
  it("keeps going when the rules fail to load", async () => {
    const v = await loadSector("demo", fake({ getSectorRules: async () => { throw new DataError("not_found", "x"); } }));
    expect(v.state === "ready" && v.rules).toBeNull();
  });
  it("404s an unknown sector without reading signals", async () => {
    const getSignals = vi.fn();
    await expect(loadSector("nope", fake({ getSignals }))).rejects.toThrow("NEXT_NOT_FOUND");
    expect(getSignals).not.toHaveBeenCalled();
  });
  it("404s a hostile slug without reading anything", async () => {
    const listSectors = vi.fn(async () => sectors);
    await expect(loadSector("..%2F", fake({ listSectors }))).rejects.toThrow("NEXT_NOT_FOUND");
    expect(listSectors).not.toHaveBeenCalled();
  });
  it("says unavailable when the data can't be reached", async () => {
    const down = fake({ listSectors: async () => { throw new DataError("unreachable", "down"); } });
    expect((await loadSector("demo", down)).state).toBe("unavailable");
  });
});
