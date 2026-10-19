import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { RelevanceRing } from "@/components/RelevanceRing";
import { ActivityPill } from "@/components/ActivityPill";
import { SignalCard } from "@/components/SignalCard";
import type { Signal } from "@/lib/data/types";

afterEach(cleanup);

const now = new Date("2026-10-16T14:20:23Z");
const signal = {
  id: "a1", source: "gazette", source_url: "https://www.thegazette.co.uk/notice/1", title: "Winding-up petition against Acme",
  published_at: "2026-10-16T02:00:00Z", newsworthiness_score: 45, why_it_matters: "Signals distress.",
  canonical_category: "Insolvency", canonical_entities: ["Acme", "Beta", "Gamma", "Delta", "Epsilon"], entities: [],
} as unknown as Signal;

describe("RelevanceRing", () => {
  it("draws an arc proportional to the score", () => {
    const { container } = render(<RelevanceRing score={50} />);
    const arc = container.querySelectorAll("circle")[1];
    const [len, total] = arc.getAttribute("stroke-dasharray")!.split(" ").map(Number);
    expect(len / total).toBeCloseTo(0.5, 3);
  });
});

describe("ActivityPill", () => {
  it("names the tier in words", () => {
    render(<ActivityPill tier="High" />);
    expect(screen.getByText("Very active")).toBeInTheDocument();
  });
});

describe("SignalCard", () => {
  it("shows title, why it matters, relevance, time and a safe source link", () => {
    render(<SignalCard signal={signal} now={now} />);
    expect(screen.getByText("Winding-up petition against Acme")).toBeInTheDocument();
    expect(screen.getByText("Signals distress.")).toBeInTheDocument();
    expect(screen.getByText(/Relevant/)).toBeInTheDocument();
    expect(screen.getByText(/12 hours ago/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Source/ });
    expect(link).toHaveAttribute("href", "https://www.thegazette.co.uk/notice/1");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("caps entity tags at 4 with a +N more", () => {
    render(<SignalCard signal={signal} now={now} />);
    expect(screen.getByText("+1 more")).toBeInTheDocument();
  });

  it("drops a javascript: source URL", () => {
    render(<SignalCard signal={{ ...signal, source_url: "javascript:alert(1)" } as Signal} now={now} />);
    expect(screen.queryByRole("link", { name: /Source/ })).toBeNull();
  });

  it("shows the pattern line from clusterInfo", () => {
    render(<SignalCard signal={{ ...signal, cluster_id: "c" } as Signal} now={now} clusterInfo={{ heat: 95, size: 3 }} />);
    expect(screen.getByText(/Part of a pattern/)).toHaveTextContent("3 signals");
  });
});
