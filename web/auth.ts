import NextAuth, { type NextAuthConfig } from "next-auth";
import type { Provider } from "next-auth/providers";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import Credentials from "next-auth/providers/credentials";

export const entraConfigured = (env: NodeJS.ProcessEnv) =>
  Boolean(env.AUTH_MICROSOFT_ENTRA_ID_ID && env.AUTH_MICROSOFT_ENTRA_ID_SECRET && env.AUTH_MICROSOFT_ENTRA_ID_ISSUER);

export const devLoginEnabled = (env: NodeJS.ProcessEnv) =>
  env.NODE_ENV === "development" && Boolean(env.AUTH_DEV_PASSWORD);

// Constant-time compare in plain JS: middleware imports this file and runs on
// the Edge runtime, where node:crypto isn't available.
function samePassword(given: string, expected: string): boolean {
  const enc = new TextEncoder();
  const a = enc.encode(given);
  const b = enc.encode(expected);
  let diff = a.length ^ b.length;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ (b[i % (b.length || 1)] ?? 0);
  return diff === 0;
}

export function buildProviders(env: NodeJS.ProcessEnv): Provider[] {
  const providers: Provider[] = [];
  if (entraConfigured(env)) {
    providers.push(
      MicrosoftEntraID({
        clientId: env.AUTH_MICROSOFT_ENTRA_ID_ID,
        clientSecret: env.AUTH_MICROSOFT_ENTRA_ID_SECRET,
        issuer: env.AUTH_MICROSOFT_ENTRA_ID_ISSUER,
        authorization: { params: { scope: "openid profile email" } },
      }),
    );
  }
  if (devLoginEnabled(env)) {
    // Credentials() reports id "credentials" on the returned object (the id
    // option is only merged in at runtime), so set it on both.
    providers.push({
      ...Credentials({
        id: "dev-password",
        name: "Dev password",
        credentials: { password: { label: "Password", type: "password" } },
        authorize: (creds) =>
          typeof creds?.password === "string" && samePassword(creds.password, env.AUTH_DEV_PASSWORD!)
            ? { id: "dev", name: "Local developer", email: "dev@localhost" }
            : null,
      }),
      id: "dev-password",
    });
  }
  return providers;
}

type SignInParams = { account?: { provider?: string } | null; profile?: unknown };

/**
 * Staff only: an Entra sign-in must carry the required group in its `groups`
 * claim. Needs the app registration to emit that claim (Token configuration
 * -> Add groups claim -> Security groups). With no group configured,
 * production refuses Entra sign-ins rather than letting any tenant account
 * in; development allows them.
 */
export function allowSignIn({ account, profile }: SignInParams, env: NodeJS.ProcessEnv = process.env): boolean {
  if (account?.provider !== "microsoft-entra-id") return true;
  const group = env.AUTH_REQUIRED_GROUP_ID;
  if (!group) return env.NODE_ENV !== "production";
  const groups = (profile as { groups?: unknown } | undefined)?.groups;
  return Array.isArray(groups) && groups.includes(group);
}

const config: NextAuthConfig = {
  providers: buildProviders(process.env),
  // Errors (e.g. AccessDenied from the group check) land back on the sign-in page.
  pages: { signIn: "/login", error: "/login" },
  session: { strategy: "jwt" },
  // No `authorized` callback: middleware.ts passes its own handler to auth(),
  // which takes precedence, so the sign-in rule lives there.
  callbacks: {
    signIn: (params) => allowSignIn(params),
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(config);
