import { NextRequest, NextResponse } from "next/server";

// Gates /exams, /exam/[paperId], and /dashboard behind a session. This is a presence-only check
// (does the refresh cookie exist?) for UX — it saves an anonymous visitor
// from loading a page that would just 401 everywhere. It is NOT the real
// enforcement: every actual backend call still requires a valid access token
// (refreshed via lib/backend.ts's backendFetch), checked server-side on each
// request regardless of what this middleware does.
export function middleware(request: NextRequest) {
  const hasSession = request.cookies.has("sw_refresh");
  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/exams/:path*", "/exam/:path*", "/dashboard/:path*"],
};
