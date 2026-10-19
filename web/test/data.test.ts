import { describe, expect, it, vi } from "vitest";
import path from "node:path";
import { FileDataSource } from "@/lib/data/files";
import { DataError, isSlug } from "@/lib/data/errors";

const dataDir = path.join(__dirname, "fixtures/data");
const configDir = path.join(__dirname, "fixtures/config");
const disk = () => new FileDataSource({ dataDir, configDir });

describe("isSlug", () => {
  it.each(["gambling", "fintech", "a-b-2"])("accepts %s", (s) => expect(isSlug(s)).toBe(true));
  it.each(["", "../etc", "Gambling", "a/b", "a%2Fb", "a b", null, 3])("rejects %s", (s) => expect(isSlug(s)).toBe(false));
});

describe("FileDataSource on disk", () => {
  it("lists sectors", async () => {
    const sectors = await disk().listSectors();
    expect(sectors.map((s) => s.slug)).toEqual(["demo", "newbie"]);
  });

  it("reads signals, keeping optional fields optional", async () => {
    const signals = await disk().getSignals("demo");
    expect(signals).toHaveLength(2);
    expect(signals[1].newsworthiness_score).toBeNull();
    expect(signals[1].canonical_category).toBeUndefined();
  });

  it("reads run status, and null when there is none", async () => {
    expect((await disk().getRunStatus("demo"))?.healthy_sources).toBe(1);
    expect(await disk().getRunStatus("newbie")).toBeNull();
  });

  it("reads sector rules and merges the dashboard watchlist", async () => {
    const rules = await disk().getSectorRules("demo");
    expect(rules.categories).toEqual(["Insolvency", "Enforcement action"]);
    expect(rules.companies.map((c) => c.name)).toEqual(["Acme", "Beta Corp"]);
    expect(rules.excludedBodies).toEqual(["Gambling Commission"]);
  });

  it("throws not_found for a sector with no signals file", async () => {
    await expect(disk().getSignals("newbie")).rejects.toMatchObject({ kind: "not_found" });
  });

  it("refuses a bad slug without touching the disk", async () => {
    await expect(disk().getSignals("../../etc")).rejects.toMatchObject({ kind: "not_found" });
  });

  it("throws invalid for malformed JSON shapes", async () => {
    const bad = new FileDataSource({ dataDir: path.join(__dirname, "fixtures/bad-data"), configDir });
    await expect(bad.listSectors()).rejects.toMatchObject({ kind: "invalid" });
  });
});

describe("FileDataSource over HTTP", () => {
  it("fetches from the base URLs", async () => {
    const fetchFn = vi.fn(async (url: string) =>
      new Response(url.endsWith("sectors.json") ? JSON.stringify([{ slug: "x", name: "X", status: "ready" }]) : "{}"),
    );
    const src = new FileDataSource({ dataBaseUrl: "https://example.test/data/", configBaseUrl: "https://example.test/config/", fetchFn: fetchFn as unknown as typeof fetch });
    expect((await src.listSectors())[0].slug).toBe("x");
    expect(fetchFn).toHaveBeenCalledWith("https://example.test/data/sectors.json", expect.anything());
  });

  it("maps 404 to not_found and network failure to unreachable", async () => {
    const notFound = new FileDataSource({ dataBaseUrl: "https://e.test/data/", configBaseUrl: "https://e.test/config/", fetchFn: (async () => new Response("", { status: 404 })) as unknown as typeof fetch });
    await expect(notFound.getSignals("demo")).rejects.toMatchObject({ kind: "not_found" });
    const down = new FileDataSource({ dataBaseUrl: "https://e.test/data/", configBaseUrl: "https://e.test/config/", fetchFn: (async () => { throw new TypeError("fetch failed"); }) as unknown as typeof fetch });
    await expect(down.listSectors()).rejects.toMatchObject({ kind: "unreachable" });
  });
});

describe("real snapshot", () => {
  const parity = new FileDataSource({
    dataDir: path.join(__dirname, "fixtures/parity/data"),
    configDir: path.join(__dirname, "fixtures/parity/config"),
  });

  it.each(["gambling", "fintech"])("parses %s signals", async (slug) => {
    const signals = await parity.getSignals(slug);
    expect(signals.length).toBeGreaterThan(0);
  });

  it("reads gambling rules the way Python's load_sector does", async () => {
    const rules = await parity.getSectorRules("gambling");
    expect(rules.categories).toContain("Illegal gambling");
    expect(rules.categories.every((c) => typeof c === "string")).toBe(true);
    expect(rules.companies.map((c) => c.name)).toContain("bet365 Group Limited");
    expect(rules.excludedBodies).toEqual(expect.arrayContaining(["gambling commission", "ukgc", "dcms", "bgc"]));
    expect(rules.excludedBodies.every((b) => typeof b === "string")).toBe(true);
  });
});
