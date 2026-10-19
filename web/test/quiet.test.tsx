import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuietToggle } from "@/components/QuietToggle";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

afterEach(() => { cleanup(); replace.mockClear(); });

describe("QuietToggle", () => {
  it("is a switch, off by default, that turns quieter patterns on via ?quiet=1", async () => {
    render(<QuietToggle checked={false} href="/gambling/patterns?quiet=1" />);
    const sw = screen.getByRole("switch", { name: "Show quieter patterns" });
    expect(sw).toHaveAttribute("aria-checked", "false");
    await userEvent.click(sw);
    expect(sw).toHaveAttribute("aria-checked", "true");
    expect(replace).toHaveBeenCalledWith("/gambling/patterns?quiet=1", { scroll: false });
  });

  it("when on, switching off goes back to the bare tab", async () => {
    render(<QuietToggle checked href="/gambling/patterns" />);
    const sw = screen.getByRole("switch", { name: "Show quieter patterns" });
    expect(sw).toHaveAttribute("aria-checked", "true");
    await userEvent.click(sw);
    expect(replace).toHaveBeenCalledWith("/gambling/patterns", { scroll: false });
  });

  it("has a (?) help tip describing what it includes", () => {
    render(<QuietToggle checked={false} href="/x" />);
    const help = screen.getByRole("button", { name: "About quieter patterns" });
    expect(help).toHaveAccessibleDescription("Includes quiet patterns and routine runs of filings.");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Includes quiet patterns and routine runs of filings.");
  });
});
