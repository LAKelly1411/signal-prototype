import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { StatTiles } from "@/components/insights/StatTiles";
import { HeatMap } from "@/components/insights/HeatMap";
import { WeeklyVolume } from "@/components/insights/WeeklyVolume";
import { ThemeMomentum } from "@/components/insights/ThemeMomentum";
import { Movers } from "@/components/insights/Movers";
import { heatThresholds } from "@/lib/signals/insights";

afterEach(cleanup);

describe("Insights components", () => {
  it("makes the first tile the hero", () => {
    const { container } = render(<StatTiles tiles={[{ label: "A", value: "1", note: "" }, { label: "B", value: "2", note: "x" }]} />);
    expect(container.querySelectorAll("[data-hero]")).toHaveLength(1);
  });

  it("weekly volume offers a table and escapes titles", () => {
    render(<WeeklyVolume starts={[new Date("2026-10-05T00:00:00Z")]} counts={[3]} marks={[0]} top={4} markTitles={{ 0: ["<b>Big</b>"] }} />);
    expect(screen.getByText("Show as a table")).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain("<b>Big</b>");
    expect(screen.getByText(/scoring 75% or more/)).toBeInTheDocument();
  });

  it("heat map lists rows busiest first with totals and the darkest step on the peak", () => {
    const rows = [{ category: "Policy and legislation", counts: [12, 3], total: 15 }, { category: "Insolvency", counts: [1, 0], total: 1 }];
    const thresholds = heatThresholds(rows.flatMap((r) => r.counts));
    const { container } = render(<HeatMap starts={[new Date("2026-09-28T00:00:00Z"), new Date("2026-10-05T00:00:00Z")]} rows={rows} thresholds={thresholds} />);
    const labels = within(container.querySelector<HTMLElement>('[role="table"]')!).getAllByRole("rowheader").map((e) => e.textContent);
    expect(labels).toEqual(["Policy and legislation", "Insolvency"]);
    const cells = container.querySelectorAll<HTMLElement>("[data-cell]");
    expect(cells[0].style.background).toBe("rgb(0, 51, 173)"); // the peak (12): top of the ramp, #0033ad
    expect(cells[1].style.background).not.toBe("rgb(0, 51, 173)");
    expect(cells[3].style.background).toBe("rgb(239, 237, 230)"); // zero: HEAT_EMPTY
  });

  it("theme momentum states direction in words", () => {
    render(<ThemeMomentum themes={[{ name: "Insolvency", heat: 200, direction: "building", recent: 11, prior: 5 }, { name: "Tax", heat: 50, direction: null }]} />);
    const row = screen.getAllByText("Insolvency")[0].closest("[data-theme]")!;
    expect(within(row as HTMLElement).getByText("Building")).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText("11 vs 5")).toBeInTheDocument();
  });

  it("movers show change in words and signs", () => {
    render(<Movers movers={[{ name: "Acme", count: 4, top: 80, change: -2, weekly: [0, 1, 2] }]} />);
    expect(screen.getAllByText("Acme").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/−2/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("80%").length).toBeGreaterThan(0);
  });
});
