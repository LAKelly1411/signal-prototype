import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SectorMenu } from "@/components/SectorMenu";

vi.mock("next/navigation", () => ({ useSelectedLayoutSegment: () => "themes" }));

const items = [{ slug: "gambling", name: "Gambling", note: "3" }, { slug: "fintech", name: "Fintech", note: "Update failed" }];

describe("SectorMenu", () => {
  it("links each sector to the current tab", () => {
    render(<SectorMenu items={items} current={items[0]} />);
    expect(screen.getByRole("link", { name: /Fintech/ })).toHaveAttribute("href", "/fintech/themes");
    expect(screen.getByRole("link", { name: /Gambling/ })).toHaveAttribute("aria-current", "true");
  });
});
