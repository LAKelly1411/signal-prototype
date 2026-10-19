import { describe, expect, it } from "vitest";
import { calendarDay, DAY_MS, utcDay } from "@/lib/signals/time";

describe("calendar-day helpers", () => {
  it("reads the date as written, ignoring the offset", () => {
    expect(calendarDay("2026-10-19T23:30:00-05:00")).toBe(Date.UTC(2026, 9, 19) / DAY_MS);
    expect(calendarDay("2026-10-19")).toBe(Date.UTC(2026, 9, 19) / DAY_MS);
    expect(calendarDay("not a date")).toBeNaN();
  });
  it("takes a moment's UTC day", () => {
    expect(utcDay(new Date("2026-10-19T23:59:59Z"))).toBe(Date.UTC(2026, 9, 19) / DAY_MS);
    expect(utcDay(new Date("2026-10-20T00:30:00+01:00"))).toBe(Date.UTC(2026, 9, 19) / DAY_MS);
  });
});
