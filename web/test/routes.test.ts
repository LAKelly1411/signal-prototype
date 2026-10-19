import { describe, expect, it } from "vitest";
import { isPublicPath, loginRedirectUrl, safeNext } from "@/lib/routes";

describe("safeNext", () => {
  it.each(["/", "/gambling/feed", "/gambling/feed?q=a%20b&sort=score", "/gambling/themes?theme=x#y"])("keeps the same-site path %s", (p) =>
    expect(safeNext(p)).toBe(p),
  );
  it.each([
    "//evil.test", "/\\evil.test", "/\\\\evil.test", "\\\\evil.test", "http://evil.test", "https://evil.test/x", "evil.test",
    "", "/\t/evil.test", "/\n/evil.test", "/a\u0000b", "/a\u007fb", "/a\rb",
  ])("rejects %j", (p) => expect(safeNext(p)).toBe("/"));
  it("rejects non-strings", () => {
    expect(safeNext(null)).toBe("/");
    expect(safeNext(undefined)).toBe("/");
    expect(safeNext(new Blob())).toBe("/");
  });
});

describe("middleware paths", () => {
  it.each(["/login", "/login/", "/api/health", "/api/ready", "/api/auth/callback/microsoft-entra-id", "/_next/static/x.js", "/favicon.ico", "/pa-logo.svg", "/logos/gc.png"])(
    "lets %s through without signing in",
    (p) => expect(isPublicPath(p)).toBe(true),
  );
  it.each(["/", "/gambling/feed", "/loginx", "/api/logo/example.com", "/api/healthz", "/api/authx", "/pa-logo.svg.map", "/x/login"])(
    "guards %s",
    (p) => expect(isPublicPath(p)).toBe(false),
  );
  it("sends an anonymous request to /login with where it was going", () => {
    const url = loginRedirectUrl(new URL("https://signals.test/gambling/feed?q=acme&sort=score"));
    expect(url.origin + url.pathname).toBe("https://signals.test/login");
    expect(url.searchParams.get("next")).toBe("/gambling/feed?q=acme&sort=score");
    expect(safeNext(url.searchParams.get("next"))).toBe("/gambling/feed?q=acme&sort=score");
  });
});
