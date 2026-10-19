import { auth } from "@/auth";
import { NextResponse } from "next/server";
import { isPublicPath, loginRedirectUrl } from "@/lib/routes";

export default auth((req) => {
  if (isPublicPath(req.nextUrl.pathname)) return NextResponse.next();
  if (!req.auth?.user) return NextResponse.redirect(loginRedirectUrl(req.nextUrl));
  return NextResponse.next();
});

export const config = { matcher: ["/((?!_next/static|_next/image).*)"] };
