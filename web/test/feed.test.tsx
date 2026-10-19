import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeedFilters } from "@/components/FeedFilters";
import { SortMenu } from "@/components/SortMenu";
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

  it("is a sidebar labelled Filters, with the five Streamlit sections", () => {
    render(<FeedFilters options={options} />);
    const aside = screen.getByRole("complementary", { name: "Filters" });
    expect(aside).toHaveAttribute("data-feed-sidebar");
    expect(screen.getByRole("heading", { name: "Filters" })).toBeInTheDocument();
    const heads = [...aside.querySelectorAll("summary")].map((s) => s.textContent);
    expect(heads).toEqual(["Sources", "Categories", "Minimum score", "Company / entity", "Published"]);
    expect(aside.querySelector("select")).toBeNull();
  });

  it("the disclosure button opens and closes the filters on narrow screens", async () => {
    render(<FeedFilters options={options} />);
    const aside = screen.getByRole("complementary", { name: "Filters" });
    const button = screen.getByRole("button", { name: "Filters" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(aside).not.toHaveAttribute("data-open");
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(aside).toHaveAttribute("data-open");
  });
});

describe("FeedFilters minimum score slider", () => {
  it("is a 0–100 range showing the URL's value", () => {
    query = "min=55";
    render(<FeedFilters options={options} />);
    const slider = screen.getByRole("slider", { name: "Minimum score" });
    expect(slider).toHaveAttribute("min", "0");
    expect(slider).toHaveAttribute("max", "100");
    expect(slider).toHaveValue("55");
  });

  it("writes once, after the slider is released, not on every step", () => {
    render(<FeedFilters options={options} />);
    const slider = screen.getByRole("slider", { name: "Minimum score" });
    fireEvent.change(slider, { target: { value: "50" } });
    fireEvent.change(slider, { target: { value: "61" } });
    fireEvent.change(slider, { target: { value: "63" } });
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByText("63")).toBeInTheDocument();
    fireEvent.pointerUp(slider);
    expect(replace).toHaveBeenCalledTimes(1);
    expect(new URL(replace.mock.calls[0][0], "http://x").searchParams.get("min")).toBe("63");
  });

  it("writes after a pause even without a release (keyboard, touch quirks)", async () => {
    render(<FeedFilters options={options} />);
    fireEvent.change(screen.getByRole("slider", { name: "Minimum score" }), { target: { value: "7" } });
    expect(replace).not.toHaveBeenCalled();
    await act(() => wait(400));
    expect(replace).toHaveBeenCalledTimes(1);
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("min=7"), { scroll: false });
  });

  it("dropping back to the default 40 removes min from the URL", () => {
    query = "min=70";
    render(<FeedFilters options={options} />);
    const slider = screen.getByRole("slider", { name: "Minimum score" });
    fireEvent.change(slider, { target: { value: "40" } });
    fireEvent.pointerUp(slider);
    expect(new URL(replace.mock.calls[0][0], "http://x").searchParams.has("min")).toBe(false);
  });
});

describe("FeedFilters published radios", () => {
  it("All time is chosen by default; choosing Last 7 days writes days=7", async () => {
    render(<FeedFilters options={options} />);
    const group = screen.getByRole("radiogroup", { name: "Published" });
    expect(within(group).getByRole("radio", { name: "All time" })).toBeChecked();
    await userEvent.click(within(group).getByRole("radio", { name: "Last 7 days" }));
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("days=7"), { scroll: false });
  });

  it("follows days in the URL", () => {
    query = "days=30";
    render(<FeedFilters options={options} />);
    expect(screen.getByRole("radio", { name: "Last 30 days" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "All time" })).not.toBeChecked();
  });
});

describe("FeedFilters company search", () => {
  const many = { ...options, entities: ["Entain", "Rank Group", "Evoke", "Flutter"], entityCounts: new Map([["Entain", 3], ["Rank Group", 2], ["Evoke", 1], ["Flutter", 1]]) };

  it("filters the companies as you type and picking one writes company= to the URL", async () => {
    render(<FeedFilters options={many} />);
    const box = screen.getByRole("combobox", { name: "Search by company" });
    await userEvent.type(box, "ev");
    const list = screen.getByRole("listbox", { name: "Companies" });
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["Evoke1"]);
    await userEvent.click(within(list).getByRole("option", { name: /Evoke/ }));
    expect(replace).toHaveBeenLastCalledWith(expect.stringContaining("company=Evoke"), { scroll: false });
    expect(box).toHaveValue("");
  });

  it("picks with the keyboard", async () => {
    render(<FeedFilters options={many} />);
    const box = screen.getByRole("combobox", { name: "Search by company" });
    await userEvent.type(box, "e");
    await userEvent.keyboard("{ArrowDown}{Enter}");
    // Matches for "e": Entain, Evoke, Flutter; ArrowDown moves to the second.
    expect(new URL(replace.mock.calls.at(-1)![0], "http://x").searchParams.getAll("company")).toEqual(["Evoke"]);
  });

  it("lists chosen companies with a remove button, and leaves them out of the matches", async () => {
    query = "company=Entain&company=Flutter";
    render(<FeedFilters options={many} />);
    const chosen = screen.getByRole("list", { name: "Chosen companies" });
    expect(within(chosen).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["EEntain", "FFlutter"]); // initials logo + name
    await userEvent.click(screen.getByRole("combobox", { name: "Search by company" }));
    expect(within(screen.getByRole("listbox")).queryByRole("option", { name: /Entain/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Remove Entain" }));
    expect(new URL(replace.mock.calls.at(-1)![0], "http://x").searchParams.getAll("company")).toEqual(["Flutter"]);
  });

  it("Escape closes the matches", async () => {
    render(<FeedFilters options={many} />);
    await userEvent.type(screen.getByRole("combobox", { name: "Search by company" }), "r");
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});

describe("FeedFilters (search and clear)", () => {
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

describe("SortMenu", () => {
  it("closes once an order is chosen, keeping the filters in the links", async () => {
    const { container } = render(<SortMenu basePath="/gambling/feed" query="q=acme" />);
    const menu = container.querySelector("details")!;
    expect(screen.getByText("Most recent", { selector: "strong" })).toBeInTheDocument();
    await userEvent.click(screen.getByText("Sort by:", { exact: false }));
    expect(menu).toHaveAttribute("open");
    const link = screen.getByRole("link", { name: "Highest score" });
    expect(link).toHaveAttribute("href", "/gambling/feed?q=acme&sort=score");
    await userEvent.click(link);
    expect(menu).not.toHaveAttribute("open");
  });

  it("reads the current order from the query and marks it", () => {
    render(<SortMenu basePath="/gambling/feed" query="sort=score&q=a" />);
    expect(screen.getByText("Highest score", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Highest score" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: "Most recent" })).toHaveAttribute("href", "/gambling/feed?q=a");
  });

  it("closes on a click outside and on Escape", async () => {
    const { container } = render(<div><SortMenu basePath="/gambling/feed" query="" /><p>elsewhere</p></div>);
    const menu = container.querySelector("details")!;
    await userEvent.click(screen.getByText("Sort by:", { exact: false }));
    expect(menu).toHaveAttribute("open");
    await userEvent.click(screen.getByText("elsewhere"));
    expect(menu).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("Sort by:", { exact: false }));
    await userEvent.keyboard("{Escape}");
    expect(menu).not.toHaveAttribute("open");
  });
});
