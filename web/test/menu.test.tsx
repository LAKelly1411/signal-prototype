import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SectorMenu } from "@/components/SectorMenu";

vi.mock("next/navigation", () => ({ useSelectedLayoutSegment: () => "themes" }));
vi.mock("next/link", () => ({
  default: ({ href, onClick, children, ...rest }: Record<string, unknown> & { href: string; onClick?: (e: unknown) => void; children: React.ReactNode }) => (
    <a href={href} {...rest} onClick={(e) => { e.preventDefault(); onClick?.(e); }}>{children}</a>
  ),
}));

const items = [{ slug: "gambling", name: "Gambling", note: "3" }, { slug: "fintech", name: "Fintech", note: "Update failed" }];

afterEach(cleanup);

describe("SectorMenu", () => {
  it("links each sector to the current tab", () => {
    render(<SectorMenu items={items} current={items[0]} />);
    expect(screen.getByRole("link", { name: /Fintech/ })).toHaveAttribute("href", "/fintech/themes");
    expect(screen.getByRole("link", { name: /Gambling/ })).toHaveAttribute("aria-current", "true");
  });

  it("the sector title itself is the trigger: a heading inside the menu's summary, with a chevron", () => {
    const { container } = render(<SectorMenu items={items} current={items[0]} />);
    const title = screen.getByRole("heading", { level: 1, name: "Gambling" });
    const summary = container.querySelector("details > summary")!;
    expect(summary).toContainElement(title);
    expect(summary.querySelector("svg")).not.toBeNull();
  });

  it("opens below the title, closes on picking a sector, on a click outside and on Escape", async () => {
    const { container } = render(<div><SectorMenu items={items} current={items[0]} /><p>outside</p></div>);
    const menu = container.querySelector("details")!;
    await userEvent.click(screen.getByRole("heading", { name: "Gambling" }));
    expect(menu).toHaveAttribute("open");
    await userEvent.click(screen.getByRole("link", { name: /Fintech/ }));
    expect(menu).not.toHaveAttribute("open");
    await userEvent.click(screen.getByRole("heading", { name: "Gambling" }));
    await userEvent.click(screen.getByText("outside"));
    expect(menu).not.toHaveAttribute("open");
    await userEvent.click(screen.getByRole("heading", { name: "Gambling" }));
    await userEvent.keyboard("{Escape}");
    expect(menu).not.toHaveAttribute("open");
  });

  it("shows each sector's note", () => {
    render(<SectorMenu items={items} current={items[0]} />);
    expect(screen.getByText("Update failed")).toBeInTheDocument();
  });
});
