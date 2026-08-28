import { NextResponse } from "next/server";
import { clearSessionCookies, getAccessToken, getRefreshToken } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// POST /api/auth/logout — best-effort revokes the refresh token on the
// backend (POST /api/v1/auth/logout requires a valid access token *and* the
// refresh token to revoke), then always clears the session cookies
// regardless of whether the backend call succeeded — an already-expired or
// already-revoked token shouldn't be able to strand the browser in a
// logged-in-looking state.
export async function POST() {
  const accessToken = getAccessToken();
  const refreshToken = getRefreshToken();

  if (accessToken && refreshToken) {
    await fetch(`${BACKEND_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    }).catch(() => {
      // Best-effort — cookies get cleared below regardless.
    });
  }

  clearSessionCookies();
  return NextResponse.json({ ok: true });
}
