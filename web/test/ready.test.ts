import { describe, expect, it, vi } from "vitest";

describe("/api/ready", () => {
  it("is 200 when sectors load and 503 when they don't", async () => {
    vi.resetModules();
    vi.doMock("@/lib/data/source", () => ({ getDataSource: () => ({ listSectors: async () => [] }) }));
    expect((await (await import("@/app/api/ready/route")).GET()).status).toBe(200);
    vi.resetModules();
    vi.doMock("@/lib/data/source", () => ({ getDataSource: () => ({ listSectors: async () => { throw new Error("down"); } }) }));
    expect((await (await import("@/app/api/ready/route")).GET()).status).toBe(503);
  });
});
