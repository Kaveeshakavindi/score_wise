import { NextResponse } from "next/server";
import { extractBackendError, safeFetch } from "@/lib/backend";
import { setSessionCookies } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// POST /api/auth/login — { nickname, password } (JSON from the client) ->
// backend POST /api/v1/auth/login (OAuth2 Password Grant, form-encoded,
// field literally named "username"). On success, sets the httpOnly session
// cookies and returns { ok: true } — the token pair itself never reaches the
// browser. On failure, forwards the backend's real status + message (401
// invalid credentials, 429 rate-limited) rather than collapsing everything to
// a flat 502, since login UX depends on that distinction.
export async function POST(request: Request) {
  const { nickname, password } = await request.json();
  if (typeof nickname !== "string" || typeof password !== "string" || !nickname || !password) {
    return NextResponse.json({ error: "Nickname and password are required." }, { status: 400 });
  }

  const body = new URLSearchParams({ username: nickname, password });
  const res = await safeFetch(`${BACKEND_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    cache: "no-store",
  });

  if (!res.ok) {
    return NextResponse.json({ error: await extractBackendError(res) }, { status: res.status });
  }

  const tokens = await res.json();
  setSessionCookies({ access_token: tokens.access_token, refresh_token: tokens.refresh_token, expires_in: tokens.expires_in });
  return NextResponse.json({ ok: true });
}
