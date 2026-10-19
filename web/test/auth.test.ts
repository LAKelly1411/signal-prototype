import { describe, expect, it } from "vitest";
import { buildProviders, devLoginEnabled, entraConfigured } from "@/auth";

const entra = {
  AUTH_MICROSOFT_ENTRA_ID_ID: "id",
  AUTH_MICROSOFT_ENTRA_ID_SECRET: "secret",
  AUTH_MICROSOFT_ENTRA_ID_ISSUER: "https://login.microsoftonline.com/tenant/v2.0",
};
const ids = (env: Record<string, string>) => buildProviders(env as NodeJS.ProcessEnv).map((p) => (typeof p === "function" ? p().id : p.id));

describe("providers", () => {
  it("offers Entra when it is configured", () => {
    expect(entraConfigured(entra as never)).toBe(true);
    expect(ids({ ...entra, NODE_ENV: "production" })).toEqual(["microsoft-entra-id"]);
  });

  it("never offers the dev password outside development", () => {
    expect(devLoginEnabled({ NODE_ENV: "production", AUTH_DEV_PASSWORD: "x" } as never)).toBe(false);
    expect(devLoginEnabled({ NODE_ENV: "test", AUTH_DEV_PASSWORD: "x" } as never)).toBe(false);
    expect(ids({ NODE_ENV: "production", AUTH_DEV_PASSWORD: "x" })).toEqual([]);
  });

  it("needs both development and a password for the dev provider", () => {
    expect(devLoginEnabled({ NODE_ENV: "development" } as never)).toBe(false);
    expect(ids({ NODE_ENV: "development", AUTH_DEV_PASSWORD: "local" })).toEqual(["dev-password"]);
  });

  it("offers nothing when nothing is configured", () => {
    expect(ids({ NODE_ENV: "production" })).toEqual([]);
  });
});
