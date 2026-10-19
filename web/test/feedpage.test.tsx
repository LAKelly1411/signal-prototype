import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  notFound: () => { throw new Error("NEXT_NOT_FOUND"); },
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/demo/feed",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));

process.env.DATA_DIR = path.join(__dirname, "fixtures/data");
process.env.CONFIG_DIR = path.join(__dirname, "fixtures/config");
const { default: FeedPage } = await import("@/app/[sector]/feed/page");

const page = async (searchParams: Record<string, string>) =>
  render(await FeedPage({ params: Promise.resolve({ sector: "demo" }), searchParams: Promise.resolve(searchParams) }));

afterEach(cleanup);

describe("feed empty state", () => {
  it("Clear all keeps the highest-score sort", async () => {
    await page({ q: "nothing-matches-this", sort: "score" });
    expect(screen.getByRole("link", { name: "Clear all" })).toHaveAttribute("href", "/demo/feed?sort=score");
  });
  it("says no signals match, in an empty block", async () => {
    await page({ q: "nothing-matches-this" });
    expect(screen.getByText("No signals match your filters.")).toBeInTheDocument();
    expect(screen.getByText("Showing 0 of", { exact: false })).toBeInTheDocument();
  });
  it("the filters are a sidebar and the old select controls are gone", async () => {
    const { container } = await page({});
    expect(container.querySelector("[data-feed-sidebar]")).not.toBeNull();
    expect(container.querySelector("select")).toBeNull();
    expect(screen.getByRole("slider", { name: "Minimum score" })).toBeInTheDocument();
  });
  it("Today always shows, with the Streamlit empty copy when nothing came in today", async () => {
    await page({});
    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(screen.getByText("Nothing new yet today.")).toBeInTheDocument();
    expect(screen.getByText("We check our sources throughout the day, so new signals will appear here as they come in.")).toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 1 scored signals.")).toBeInTheDocument();
  });
  it("Clear all goes to the bare feed otherwise", async () => {
    await page({ q: "nothing-matches-this" });
    expect(screen.getByRole("link", { name: "Clear all" })).toHaveAttribute("href", "/demo/feed");
  });
});
