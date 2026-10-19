import { beforeEach, describe, expect, it, vi } from "vitest";
import { CredentialsSignin } from "next-auth";

const signIn = vi.fn();
const homePath = vi.fn();
class Redirect extends Error {
  constructor(public url: string) {
    super("NEXT_REDIRECT");
  }
}
vi.mock("@/auth", () => ({ signIn: (...a: unknown[]) => signIn(...a) }));
vi.mock("@/lib/load", () => ({ homePath: () => homePath() }));
vi.mock("next/navigation", () => ({ redirect: (url: string) => { throw new Redirect(url); } }));

const { signInWithDev, signInWithEntra } = await import("@/app/login/actions");

const form = (fields: Record<string, string>) => {
  const f = new FormData();
  for (const [k, v] of Object.entries(fields)) f.set(k, v);
  return f;
};
const redirectOf = async (p: Promise<unknown>) => {
  try {
    await p;
  } catch (e) {
    if (e instanceof Redirect) return e.url;
    throw e;
  }
  throw new Error("expected a redirect");
};

beforeEach(() => {
  signIn.mockReset();
  homePath.mockReset().mockResolvedValue("/gambling/feed");
});

describe("signInWithDev", () => {
  it("signs in without Auth.js's redirect, then goes straight to the first sector's feed", async () => {
    signIn.mockResolvedValue("http://localhost:3000/");
    expect(await redirectOf(signInWithDev(form({ password: "local", next: "/" })))).toBe("/gambling/feed");
    expect(signIn).toHaveBeenCalledWith("dev-password", { password: "local", redirect: false });
  });

  it("returns to a safe next path as given", async () => {
    signIn.mockResolvedValue("x");
    expect(await redirectOf(signInWithDev(form({ password: "local", next: "/demo/themes?theme=t" })))).toBe("/demo/themes?theme=t");
    expect(homePath).not.toHaveBeenCalled();
  });

  it("falls back to / when there are no sectors", async () => {
    signIn.mockResolvedValue("x");
    homePath.mockResolvedValue(null);
    expect(await redirectOf(signInWithDev(form({ password: "local", next: "//evil.test" })))).toBe("/");
  });

  it("sends a wrong password back to the login page with the error and next", async () => {
    signIn.mockRejectedValue(new CredentialsSignin());
    const url = await redirectOf(signInWithDev(form({ password: "nope", next: "/demo/feed?q=a" })));
    const u = new URL(url, "http://x");
    expect(u.pathname).toBe("/login");
    expect(u.searchParams.get("error")).toBe("CredentialsSignin");
    expect(u.searchParams.get("next")).toBe("/demo/feed?q=a");
  });

  it("rethrows anything that isn't an Auth.js error", async () => {
    signIn.mockRejectedValue(new Error("disk on fire"));
    await expect(signInWithDev(form({ password: "x", next: "/" }))).rejects.toThrow("disk on fire");
  });
});

describe("signInWithEntra", () => {
  it("keeps Auth.js's redirect to Microsoft, returning to a resolved relative path", async () => {
    await signInWithEntra(form({ next: "/" }));
    expect(signIn).toHaveBeenCalledWith("microsoft-entra-id", { redirectTo: "/gambling/feed" });
  });
  it("never hands an off-site next to Auth.js", async () => {
    await signInWithEntra(form({ next: "/\\evil.test" }));
    expect(signIn).toHaveBeenCalledWith("microsoft-entra-id", { redirectTo: "/gambling/feed" });
  });
});
