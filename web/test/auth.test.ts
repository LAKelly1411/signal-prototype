import { describe, expect, it } from "vitest";
import { allowSignIn, buildProviders, devLoginEnabled, entraConfigured } from "@/auth";

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

describe("allowSignIn (the group check)", () => {
  const entraAccount = { provider: "microsoft-entra-id" };
  const env = (over: Record<string, string>) => ({ NODE_ENV: "production", ...over }) as unknown as NodeJS.ProcessEnv;

  it("lets in an Entra user carrying the required group", () => {
    expect(allowSignIn({ account: entraAccount, profile: { groups: ["other", "staff"] } }, env({ AUTH_REQUIRED_GROUP_ID: "staff" }))).toBe(true);
  });
  it("refuses an Entra user without the group", () => {
    expect(allowSignIn({ account: entraAccount, profile: { groups: ["other"] } }, env({ AUTH_REQUIRED_GROUP_ID: "staff" }))).toBe(false);
  });
  it("refuses an Entra user whose token has no groups claim (e.g. the >200 groups overage)", () => {
    expect(allowSignIn({ account: entraAccount, profile: { _claim_names: { groups: "src1" } } }, env({ AUTH_REQUIRED_GROUP_ID: "staff" }))).toBe(false);
    expect(allowSignIn({ account: entraAccount, profile: undefined }, env({ AUTH_REQUIRED_GROUP_ID: "staff" }))).toBe(false);
  });
  it("fails closed in production when no group is configured", () => {
    expect(allowSignIn({ account: entraAccount, profile: { groups: ["staff"] } }, env({}))).toBe(false);
  });
  it("allows Entra without a group in development", () => {
    expect(allowSignIn({ account: entraAccount, profile: {} }, env({ NODE_ENV: "development" }))).toBe(true);
  });
  it("leaves the dev password provider alone", () => {
    expect(allowSignIn({ account: { provider: "dev-password" } }, env({ AUTH_REQUIRED_GROUP_ID: "staff" }))).toBe(true);
  });
});
