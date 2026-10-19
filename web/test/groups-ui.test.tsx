import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GroupList } from "@/components/GroupList";

afterEach(cleanup);

const routerPush = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: routerPush }),
  usePathname: () => "/gambling/themes",
  useSearchParams: () => search,
}));
let pushState: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  pushState = vi.spyOn(window.history, "pushState").mockImplementation(() => {});
});
afterEach(() => pushState.mockRestore());
const pushedUrl = () => pushState.mock.lastCall?.[2];

const now = new Date("2026-10-16T14:20:23Z");
const member = (id: string, d: string) => ({ id, source: "parliament", title: `Signal ${id}`, published_at: d, newsworthiness_score: 45, why_it_matters: "Why.", canonical_category: "Policy and legislation", canonical_entities: ["Lisa Nandy"], entities: [] });
const group = {
  id: "Policy and legislation", kind: "theme", title: "Policy and legislation", tier: "High", heat: 210,
  summary: "Parliamentary scrutiny intensified.", meta: "2 signals · 1 company · 1 Oct – 6 Oct",
  members: [member("a", "2026-10-06T00:00:00Z"), member("b", "2026-10-01T00:00:00Z")],
  flags: [{ text: "Building", icon: "trending_up", accent: true }],
  companies: ["Lisa Nandy", "A", "B", "C", "D", "E", "F"], keyPoints: ["Point one."],
  primaryCompany: null, themeIcon: "account_balance", weeklyCounts: [0,0,0,0,0,0,0,0,0,0,0,1,1], active: true,
} as never;

describe("GroupList", () => {
  it("opens the panel when a card is clicked, via a history entry rather than a server round trip", async () => {
    search = new URLSearchParams();
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    expect(screen.queryByRole("complementary", { name: /Policy and legislation/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Preview Policy and legislation" }));
    expect(pushedUrl()).toBe("/gambling/themes?theme=Policy+and+legislation");
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("shows the panel for the selected group, signals newest first", () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    const pane = screen.getByRole("complementary", { name: /Policy and legislation/ });
    const titles = [...pane.querySelectorAll("[data-signal-title]")].map((e) => e.textContent);
    expect(titles).toEqual(["Signal a", "Signal b"]);
    expect(screen.getByRole("button", { name: "Policy and legislation, showing in preview" })).toHaveAttribute("aria-pressed", "true");
  });

  it("closes with the ×", async () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    await userEvent.click(screen.getByRole("button", { name: "Close preview" }));
    expect(pushedUrl()).toBe("/gambling/themes");
  });

  it("keeps the summary behind Show summary, and swaps in every company when open", async () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    const pane = screen.getByRole("complementary", { name: /Policy and legislation/ });
    const toggle = pane.querySelector("details.sp-toggle") as HTMLDetailsElement;
    expect(toggle.open).toBe(false);
    expect(pane.textContent).toContain("+2 more");
    await userEvent.click(screen.getByText("Show summary"));
    expect(toggle.open).toBe(true);
  });

  it("ignores a selection that isn't in the list", () => {
    search = new URLSearchParams("theme=Nope");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    expect(screen.queryByRole("complementary")).toBeNull();
  });

  it("leaves focus alone when the pane comes from a deep link", () => {
    search = new URLSearchParams("theme=Policy and legislation");
    render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    expect(screen.getByRole("button", { name: "Close preview" })).not.toHaveFocus();
  });

  it("moves focus into the pane when a card opens it, and back to the card on close", async () => {
    search = new URLSearchParams();
    const { rerender } = render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    await userEvent.click(screen.getByRole("button", { name: "Preview Policy and legislation" }));
    search = new URLSearchParams("theme=Policy and legislation"); // what Next does after pushState
    rerender(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    const close = screen.getByRole("button", { name: "Close preview" });
    expect(close).toHaveFocus();
    await userEvent.click(close);
    expect(screen.getByRole("button", { name: "Policy and legislation, showing in preview" })).toHaveFocus();
  });

  it("renders the activity pill as phrasing content inside the card button", () => {
    search = new URLSearchParams();
    const { container } = render(<GroupList groups={[group]} param="theme" scale={2} now={now} />);
    const pill = container.querySelector(".pa-pill")!;
    expect(pill.tagName).toBe("SPAN");
    expect(container.querySelector("button div")).toBeNull();
  });
});
