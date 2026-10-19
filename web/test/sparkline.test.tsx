import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { Sparkline } from "@/components/Sparkline";

afterEach(cleanup);

describe("Sparkline", () => {
  it("plots one point per week on the shared scale, with a dot on the latest", () => {
    const { container } = render(<Sparkline counts={[0, 2, 4]} scale={4} start={new Date("2026-09-28T00:00:00Z")} />);
    const pts = container.querySelector("polyline")!.getAttribute("points")!.trim().split(/\s+/);
    expect(pts).toHaveLength(3);
    const lastY = Number(pts[2].split(",")[1]);
    const firstY = Number(pts[0].split(",")[1]);
    expect(lastY).toBeLessThan(firstY);
    expect(container.querySelector("[data-latest]")).not.toBeNull();
  });

  it("draws stretches with no signals as a separate quiet segment, grey first", () => {
    const { container } = render(<Sparkline counts={[0, 0, 0, 3, 1]} scale={4} start={new Date("2026-09-28T00:00:00Z")} />);
    const lines = [...container.querySelectorAll("polyline")];
    expect(lines).toHaveLength(2);
    expect(lines[0].getAttribute("class")).toMatch(/lineQuiet/i);
    expect(lines[0].getAttribute("points")!.trim().split(/\s+/)).toHaveLength(3);
    expect(lines[1].getAttribute("class")).not.toMatch(/lineQuiet/i);
  });
});
