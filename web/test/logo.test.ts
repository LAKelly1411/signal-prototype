import { describe, expect, it, vi, afterEach } from "vitest";
import { GET } from "@/app/api/logo/[domain]/route";
import { SOURCE_DOMAINS } from "@/lib/brand";

const call = (domain: string) => GET(new Request(`http://x/api/logo/${domain}`), { params: Promise.resolve({ domain }) });

describe("/api/logo", () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

  it("404s without a token", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "");
    expect((await call(SOURCE_DOMAINS.gambling_commission)).status).toBe(404);
  });

  it("404s a domain we don't know", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "t");
    expect((await call("evil.example")).status).toBe(404);
  });

  it("proxies a known domain without exposing the token", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "secret-token");
    const fetchMock = vi.fn(async (..._a: unknown[]) => new Response(new Uint8Array([1, 2, 3]), { headers: { "content-type": "image/png" } }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await call(SOURCE_DOMAINS.gambling_commission);
    expect(res.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toContain("img.logo.dev/gamblingcommission.gov.uk");
    expect(res.headers.get("cache-control")).toContain("max-age=86400");
    expect(JSON.stringify([...res.headers])).not.toContain("secret-token");
  });

  it("404s when upstream fails", async () => {
    vi.stubEnv("LOGO_DEV_TOKEN", "t");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("no", { status: 500 })));
    expect((await call(SOURCE_DOMAINS.gazette)).status).toBe(404);
  });
});
