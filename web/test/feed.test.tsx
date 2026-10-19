import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeedFilters } from "@/components/FeedFilters";
import { sourceName } from "@/lib/signals/entities";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/gambling/feed",
  useSearchParams: () => new URLSearchParams("q=fine"),
}));

const options = { sources: ["gazette", "asa"], categories: ["Insolvency", "Other"], entities: ["Entain", "Rank"], entityCounts: new Map([["Entain", 3], ["Rank", 1]]) };

afterEach(() => { cleanup(); replace.mockClear(); });

describe("FeedFilters", () => {
  it("shows the current search from the URL", () => {
    render(<FeedFilters options={options} />);
    expect(screen.getByRole("searchbox", { name: "Search signals" })).toHaveValue("fine");
  });

  it("switching a source off writes it to the URL", async () => {
    render(<FeedFilters options={options} />);
    await userEvent.click(screen.getByRole("checkbox", { name: sourceName("gazette") }));
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("off=gazette"), { scroll: false });
  });

  it("selecting a company and a minimum score writes them to the URL", async () => {
    render(<FeedFilters options={options} />);
    await userEvent.click(screen.getByRole("checkbox", { name: /Entain/ }));
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("company=Entain"), { scroll: false });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Minimum relevance" }), "70");
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("min=70"), { scroll: false });
  });

  it("clear all resets the URL", async () => {
    render(<FeedFilters options={options} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(replace).toHaveBeenLastCalledWith("/gambling/feed", { scroll: false });
  });
});
