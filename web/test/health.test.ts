import { describe, expect, it, vi, afterEach } from "vitest";
import { GET } from "@/app/api/health/route";

describe("/api/health", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("reports ok and the build tag", async () => {
    vi.stubEnv("BUILD_TAG", "2026-10-19.abc1234");
    const res = await GET();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, tag: "2026-10-19.abc1234" });
  });

  it("says dev when no tag is set", async () => {
    vi.stubEnv("BUILD_TAG", "");
    expect((await (await GET()).json()).tag).toBe("dev");
  });
});
