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
  it("Clear all goes to the bare feed otherwise", async () => {
    await page({ q: "nothing-matches-this" });
    expect(screen.getByRole("link", { name: "Clear all" })).toHaveAttribute("href", "/demo/feed");
  });
});
