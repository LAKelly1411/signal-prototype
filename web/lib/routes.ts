// Path rules shared by the middleware and the sign-in actions. Kept free of
// Next and Auth.js imports so they can be unit-tested directly.

/** Paths reachable without signing in. */
export const PUBLIC_PATHS = [
  /^\/login(\/|$)/,
  /^\/api\/(health|ready|auth)(\/|$)/,
  /^\/_next\//,
  /^\/favicon/,
  /^\/pa-logo\.svg$/,
  /^\/logos\//,
];

export const isPublicPath = (pathname: string) => PUBLIC_PATHS.some((re) => re.test(pathname));

/** Where an anonymous request is sent: /login, remembering where it was going. */
export function loginRedirectUrl(url: URL): URL {
  const login = new URL("/login", url);
  login.searchParams.set("next", url.pathname + url.search);
  return login;
}

// Backslashes (browsers read "/\x" as "//x") and control characters (a tab or
// newline inside "//" is stripped by URL parsers) could turn a path into an
// off-site URL.
const UNSAFE = /[\\\u0000-\u001f\u007f]/;

/** A same-site path to return to after sign-in, or "/" for anything else. */
export function safeNext(next: unknown): string {
  return typeof next === "string" && next.startsWith("/") && !next.startsWith("//") && !UNSAFE.test(next) ? next : "/";
}
