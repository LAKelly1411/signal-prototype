import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  notFound: () => { throw new Error("NEXT_NOT_FOUND"); },
  redirect: (to: string) => { throw new Error(`REDIRECT ${to}`); },
}));

import SectorIndex from "@/app/[sector]/page";

describe("/[sector]", () => {
  it("redirects a valid slug to its feed", async () => {
    await expect(SectorIndex({ params: Promise.resolve({ sector: "gambling" }) })).rejects.toThrow("REDIRECT /gambling/feed");
  });
  it("404s a hostile slug instead of building a URL from it", async () => {
    await expect(SectorIndex({ params: Promise.resolve({ sector: "..%2Fx" }) })).rejects.toThrow("NEXT_NOT_FOUND");
  });
});
