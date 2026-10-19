import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import path from "node:path";
import { StatusStrip } from "@/components/StatusStrip";
import { FileDataSource } from "@/lib/data/files";
import { EmptyBlock, EmptyState, UpdateNotice } from "@/components/EmptyState";
import { Tabs } from "@/components/Tabs";

let segment: string | null = null;
vi.mock("next/navigation", () => ({
  useSelectedLayoutSegment: () => segment,
  usePathname: () => "/gambling/feed",
  useSearchParams: () => new URLSearchParams("q=acme"),
}));

afterEach(() => { cleanup(); segment = null; });

const now = new Date("2026-10-16T16:20:23Z");

describe("StatusStrip", () => {
  it("says when it updated and how many sources worked", () => {
    render(<StatusStrip now={now} status={{ finished_at: "2026-10-16T14:20:23Z", healthy_sources: 8, total_sources: 9, sources: { AsaCollector: { items: 0, ok: false, error: false } } } as never} />);
    expect(screen.getByText(/Updated 2 hours ago · 8\/9 sources/)).toBeInTheDocument();
    expect(screen.getByText("Which sources returned nothing?")).toBeInTheDocument();
  });
  it("lists the quiet sources in a card under the strip", () => {
    const { container } = render(<StatusStrip now={now} status={{ finished_at: "2026-10-16T14:20:23Z", healthy_sources: 8, total_sources: 9, sources: { AsaCollector: { items: 0, ok: false, error: false }, GazetteCollector: { items: 3, ok: true, error: false } } } as never} />);
    const details = container.querySelector("details")!;
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Which sources returned nothing?"));
    expect(details).toHaveAttribute("open");
    expect(details.querySelector("p")).toHaveTextContent(/^\S.*$/);
    expect(details.textContent).not.toContain("Gazette");
  });
  it("renders nothing without a status", () => {
    const { container } = render(<StatusStrip now={now} status={null} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("says so when the last update failed", () => {
    render(<StatusStrip now={now} status={{ finished_at: "2026-10-16T14:20:23Z", error: "boom", healthy_sources: 0, total_sources: 0, sources: {} } as never} />);
    expect(screen.getByText(/Last update failed · 2 hours ago/)).toBeInTheDocument();
  });
  it("shows the failed-run message for the pipeline's real failed-run file", async () => {
    const src = new FileDataSource({ dataDir: path.join(__dirname, "fixtures/failed-data"), configDir: path.join(__dirname, "fixtures/config") });
    const { container } = render(<StatusStrip now={now} status={await src.getRunStatus("broken")} />);
    expect(container.textContent).toBe("Last update failed · 2 hours ago");
  });
});

describe("EmptyState", () => {
  it("shows the unavailable message", () => {
    render(<EmptyState kind="unavailable" />);
    expect(screen.getByText("We couldn't load the latest signals. Try again in a few minutes.")).toBeInTheDocument();
  });
});

describe("UpdateNotice", () => {
  it("says the last update didn't finish", () => {
    render(<UpdateNotice />);
    expect(screen.getByText("The last update didn't finish. Showing the latest data we have.")).toBeInTheDocument();
  });
  it("has the error_empty copy", () => {
    render(<EmptyState kind="error_empty" name="Demo" />);
    expect(screen.getByText("We couldn't load Demo yet. We'll try again on the next scheduled update.")).toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("links each tab and marks the current one", () => {
    render(<Tabs slug="gambling" current="themes" />);
    expect(screen.getByRole("link", { name: "Themes" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Feed" })).toHaveAttribute("href", "/gambling/feed");
    expect(screen.getByRole("link", { name: "Feed" })).not.toHaveAttribute("aria-current");
  });
  it("on the Feed, puts the sort menu at the end of the tab row, keeping the filters", () => {
    segment = "feed";
    const { container } = render(<Tabs slug="gambling" />);
    expect(screen.getByRole("link", { name: "Feed" })).toHaveAttribute("aria-current", "page");
    const nav = screen.getByRole("navigation", { name: "Sections" });
    const sort = container.querySelector("details")!;
    expect(sort).toHaveTextContent("Sort by: Most recent");
    expect(nav.nextElementSibling).toBe(sort);
    expect(nav).not.toContainElement(sort);
    expect(within(sort).getByRole("link", { name: "Highest score", hidden: true })).toHaveAttribute("href", "/gambling/feed?q=acme&sort=score");
  });
  it("has no sort menu on the other tabs", () => {
    segment = "patterns";
    const { container } = render(<Tabs slug="gambling" />);
    expect(container.querySelector("details")).toBeNull();
  });
});

describe("EmptyBlock", () => {
  it("shows the inbox icon, bold title and body", () => {
    const { container } = render(<EmptyBlock title="Nothing new yet today."><p>We check our sources throughout the day.</p></EmptyBlock>);
    expect(container.querySelector("svg")).not.toBeNull();
    expect(screen.getByText("Nothing new yet today.")).toBeInTheDocument();
  });
});

describe("error boundaries", () => {
  it.each([
    ["sector", () => import("@/app/[sector]/error")],
    ["root", () => import("@/app/error")],
  ])("the %s boundary shows the unavailable message and retries", async (_, load) => {
    const { default: Boundary } = await load();
    const reset = vi.fn();
    const { container } = render(<Boundary error={new Error("boom")} reset={reset} />);
    expect(container).toHaveTextContent("We couldn't load the latest signals. Try again in a few minutes.");
    fireEvent.click(within(container).getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
