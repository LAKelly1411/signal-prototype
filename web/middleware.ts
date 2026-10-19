import { auth } from "@/auth";
import { NextResponse } from "next/server";

const PUBLIC = [/^\/login(\/|$)/, /^\/api\/(health|ready|auth)(\/|$)/, /^\/_next\//, /^\/favicon/, /^\/pa-logo\.svg$/, /^\/logos\//];

export default auth((req) => {
  const { pathname, search } = req.nextUrl;
  if (PUBLIC.some((re) => re.test(pathname))) return NextResponse.next();
  if (!req.auth?.user) {
    const url = new URL("/login", req.nextUrl);
    url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
});

export const config = { matcher: ["/((?!_next/static|_next/image).*)"] };
