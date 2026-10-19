import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoginPanel } from "@/app/login/page";

describe("LoginPanel", () => {
  it("shows the Microsoft button when Entra is set up", () => {
    render(<LoginPanel entra dev={false} />);
    expect(screen.getByRole("button", { name: "Sign in with Microsoft" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).toBeNull();
  });
  it("shows the dev password form only when enabled", () => {
    render(<LoginPanel entra={false} dev />);
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });
  it("says sign-in isn't set up when neither is available", () => {
    render(<LoginPanel entra={false} dev={false} />);
    expect(screen.getByText("Sign-in isn't set up yet.")).toBeInTheDocument();
  });
  it("shows the wrong-password message", () => {
    render(<LoginPanel entra={false} dev error="CredentialsSignin" />);
    expect(screen.getByText("That password isn't right. Try again.")).toBeInTheDocument();
  });
});
