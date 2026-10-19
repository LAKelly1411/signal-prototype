import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { StatTiles } from "@/components/insights/StatTiles";
import { HeatMap } from "@/components/insights/HeatMap";
import { WeeklyVolume } from "@/components/insights/WeeklyVolume";
import { ThemeMomentum } from "@/components/insights/ThemeMomentum";
import { Movers } from "@/components/insights/Movers";

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
    const rows = [{ category: "Policy and legislation", counts: [3, 0], total: 3 }, { category: "Insolvency", counts: [1, 0], total: 1 }];
    const { container } = render(<HeatMap starts={[new Date("2026-09-28T00:00:00Z"), new Date("2026-10-05T00:00:00Z")]} rows={rows} thresholds={[1, 2, 3, 4, 5]} />);
    const labels = screen.getAllByRole("rowheader").map((e) => e.textContent);
    expect(labels).toEqual(["Policy and legislation", "Insolvency"]);
    const cells = container.querySelectorAll<HTMLElement>("[data-cell]");
    expect(cells[0].style.background).toBe("rgb(59, 107, 255)");
    expect(cells[1].style.background).toBe("rgb(239, 237, 230)");
  });

  it("theme momentum states direction in words", () => {
    render(<ThemeMomentum themes={[{ name: "Insolvency", heat: 200, direction: "building", recent: 11, prior: 5 }, { name: "Tax", heat: 50, direction: null }]} />);
    const row = screen.getByText("Insolvency").closest("[data-theme]")!;
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
