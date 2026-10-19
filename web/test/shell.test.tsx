import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusStrip } from "@/components/StatusStrip";
import { EmptyState, UpdateNotice } from "@/components/EmptyState";
import { Tabs } from "@/components/Tabs";

vi.mock("next/navigation", () => ({ useSelectedLayoutSegment: () => null }));

const now = new Date("2026-10-16T16:20:23Z");

describe("StatusStrip", () => {
  it("says when it updated and how many sources worked", () => {
    render(<StatusStrip now={now} status={{ finished_at: "2026-10-16T14:20:23Z", healthy_sources: 8, total_sources: 9, sources: { AsaCollector: { items: 0, ok: false, error: false } } } as never} />);
    expect(screen.getByText(/Updated 2 hours ago · 8\/9 sources/)).toBeInTheDocument();
    expect(screen.getByText("Which sources returned nothing?")).toBeInTheDocument();
  });
  it("renders nothing without a status", () => {
    const { container } = render(<StatusStrip now={now} status={null} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("says so when the last update failed", () => {
    render(<StatusStrip now={now} status={{ finished_at: "2026-10-16T14:20:23Z", error: "boom", healthy_sources: 0, total_sources: 0, sources: {} } as never} />);
    expect(screen.getByText(/Last update failed · 2 hours ago/)).toBeInTheDocument();
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
  });
});
