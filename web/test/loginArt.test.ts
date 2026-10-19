import { describe, expect, it } from "vitest";
import { loginArt } from "@/lib/loginArt";

describe("loginArt", () => {
  it("is deterministic", () => expect(loginArt()).toEqual(loginArt()));
  it("has 22 weekly values between 0.08 and 0.9, drawn twice", () => {
    const art = loginArt();
    expect(art.values).toHaveLength(22);
    for (const v of art.values) expect(v).toBeGreaterThanOrEqual(0.08), expect(v).toBeLessThanOrEqual(0.9);
    expect(art.cols).toBe(45);
    expect(art.shift).toBeCloseTo(22 / 45, 6);
  });
  it("starts every animation mid-cycle (negative delays) so it moves on the first frame", () => {
    for (const c of loginArt().cells) expect(c.delay).toBeLessThanOrEqual(0);
  });
  it("picks the 3 busiest weeks, at least 5 apart", () => {
    const idx = loginArt().picks.map((p) => p.idx).sort((a, b) => a - b);
    expect(idx).toHaveLength(3);
    expect(idx[1] - idx[0]).toBeGreaterThanOrEqual(5);
    expect(idx[2] - idx[1]).toBeGreaterThanOrEqual(5);
  });
});

import { noise } from "@/lib/loginArt";

describe("noise", () => {
  // Reference values from Python: int.from_bytes(blake2b(repr(k).encode(), digest_size=4).digest(), "big") / 0xFFFFFFFF
  it("matches the Python dashboard's blake2b noise", () => {
    expect(noise(7, 0)).toBeCloseTo(0.9675121596007403, 12);
    expect(noise(7, 5)).toBeCloseTo(0.5260672542560071, 12);
    expect(noise(3, 9, 4)).toBeCloseTo(0.3111686874905528, 12);
    expect(noise(21, 13, 7)).toBeCloseTo(0.24121003114646533, 12);
  });
});
