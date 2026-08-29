// Server-only helper: talks to the ScoreWise FastAPI backend. All calls run
// in Next.js Route Handlers (never in the browser), so tokens never reach the
// client — the browser only ever holds the httpOnly session cookies (see
// lib/session.ts), and those are read here to build the Authorization header
// the FastAPI backend actually expects (it knows nothing about cookies).

import { clearSessionCookies, getAccessToken, getRefreshToken, setSessionCookies } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

/** Unwraps the backend's error envelope (app/core/exceptions.py's
 * `{ error: { code, message, details, request_id } }`) into a plain message
 * string, so routes that need to surface a real reason (login/register) don't
 * have to know that shape themselves. Falls back to a generic message if the
 * body isn't JSON or doesn't match the envelope (e.g. a raw 502 from
 * somewhere in front of the backend). */
export async function extractBackendError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.error?.message === "string") return body.error.message;
  } catch {
    // not JSON — fall through
  }
  return `Request failed (${res.status})`;
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  const res = await fetch(`${BACKEND_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  if (!res.ok) {
    // Refresh token invalid/expired/revoked — nothing left to try, end the session.
    clearSessionCookies();
    return null;
  }
  const data = await res.json();
  setSessionCookies({ access_token: data.access_token, refresh_token: data.refresh_token, expires_in: data.expires_in });
  return data.access_token as string;
}

/** Calls the backend with the current session's access token, retrying once
 * on 401 by rotating the refresh token first (mirrors the old demo-account
 * version's "retry once on 401" shape, just sourced from the user's own
 * cookies instead of a shared demo login). If there's no session, or the
 * refresh token itself is no longer valid, the 401 is returned as-is — the
 * caller (an API route) passes it through, and the client redirects to
 * /login. */
export async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const attempt = (token: string | null) =>
    fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: { ...init.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      cache: "no-store",
    });

  const token = getAccessToken();
  let res = token ? await attempt(token) : new Response(null, { status: 401 });

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      res = await attempt(refreshed);
    }
  }
  return res;
}
