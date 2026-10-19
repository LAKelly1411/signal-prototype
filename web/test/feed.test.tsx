import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeedFilters } from "@/components/FeedFilters";
import { FeedToolbar } from "@/components/FeedToolbar";
import { sourceName } from "@/lib/signals/entities";

const replace = vi.fn();
let query = "q=fine";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/gambling/feed",
  useSearchParams: () => new URLSearchParams(query),
}));

vi.mock("next/link", () => ({
  default: ({ href, onClick, children, replace: _r, scroll: _s, ...rest }: Record<string, unknown> & { href: string; onClick?: (e: unknown) => void; children: React.ReactNode }) => (
    <a href={href} {...rest} onClick={(e) => { e.preventDefault(); onClick?.(e); }}>{children}</a>
  ),
}));

const options = { sources: ["gazette", "asa"], categories: ["Insolvency", "Other"], entities: ["Entain", "Rank"], entityCounts: new Map([["Entain", 3], ["Rank", 1]]) };

afterEach(() => { cleanup(); replace.mockClear(); query = "q=fine"; });
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

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

  it("follows the URL's search when it changes from outside (back/forward)", () => {
    const { rerender } = render(<FeedFilters options={options} />);
    query = "q=other";
    rerender(<FeedFilters options={options} />);
    expect(screen.getByRole("searchbox", { name: "Search signals" })).toHaveValue("other");
  });

  it("a filter change while the search is still debouncing writes the typed text in the same navigation", async () => {
    render(<FeedFilters options={options} />);
    const box = screen.getByRole("searchbox", { name: "Search signals" });
    await userEvent.clear(box);
    await userEvent.type(box, "acme");
    await userEvent.click(screen.getByRole("checkbox", { name: sourceName("gazette") }));
    expect(replace).toHaveBeenCalledTimes(1);
    const url = new URL(replace.mock.calls[0][0], "http://x");
    expect(url.searchParams.get("q")).toBe("acme");
    expect(url.searchParams.getAll("off")).toEqual(["gazette"]);
    await wait(400);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(box).toHaveValue("acme");
  });

  it("debounced search writes once, after typing stops", async () => {
    render(<FeedFilters options={options} />);
    const box = screen.getByRole("searchbox", { name: "Search signals" });
    await userEvent.clear(box);
    await userEvent.type(box, "rank");
    expect(replace).not.toHaveBeenCalled();
    await wait(400);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(replace).toHaveBeenLastCalledWith("/gambling/feed?q=rank", { scroll: false });
  });

  it("clear all resets the URL", async () => {
    render(<FeedFilters options={options} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(replace).toHaveBeenLastCalledWith("/gambling/feed", { scroll: false });
  });
});

describe("FeedToolbar", () => {
  it("closes the sort menu once an order is chosen, keeping the filters in the links", async () => {
    const { container } = render(<FeedToolbar shown={2} total={5} sort="recent" basePath="/gambling/feed" query="q=acme" />);
    const menu = container.querySelector("details")!;
    await userEvent.click(screen.getByText("Sort by:", { exact: false }));
    expect(menu).toHaveAttribute("open");
    const link = screen.getByRole("link", { name: "Highest score" });
    expect(link).toHaveAttribute("href", "/gambling/feed?q=acme&sort=score");
    await userEvent.click(link);
    expect(menu).not.toHaveAttribute("open");
  });
});
