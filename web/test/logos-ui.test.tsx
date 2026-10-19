import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { CompanyLogo, LogosProvider, SourceLogo } from "@/components/SourceLogo";

afterEach(cleanup);

describe("logos without LOGO_DEV_TOKEN", () => {
  it("render initials and never ask /api/logo", () => {
    const { container } = render(<><SourceLogo source="asa" /><CompanyLogo name="bet365" /></>);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("ASA");
  });
  it("still use bundled local logos", () => {
    const { container } = render(<SourceLogo source="gambling_commission" />);
    expect(container.querySelector("img")?.getAttribute("src")).toBe("/logos/gambling_commission.png");
  });
});

describe("logos with LOGO_DEV_TOKEN", () => {
  it("go through the proxy", () => {
    const { container } = render(
      <LogosProvider enabled>
        <SourceLogo source="asa" />
        <CompanyLogo name="bet365" />
      </LogosProvider>,
    );
    expect([...container.querySelectorAll("img")].map((i) => i.getAttribute("src"))).toEqual(["/api/logo/asa.org.uk", "/api/logo/bet365.com"]);
  });
});
