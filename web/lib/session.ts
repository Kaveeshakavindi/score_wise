import { cookies } from "next/headers";

// Cookie-based session for real (non-demo) users. Both cookies are httpOnly —
// the access token never reaches client JS, matching this app's existing rule
// that backend credentials/tokens only ever live server-side (see
// lib/backend.ts). Reading AND writing cookies here is only valid from Route
// Handlers / Server Actions, not from plain Server Components.

const ACCESS_COOKIE = "sw_access";
const REFRESH_COOKIE = "sw_refresh";

// The token response (TokenPair) only carries the access token's TTL
// (`expires_in`), not the refresh token's — so the refresh cookie's maxAge is
// hardcoded here to match the backend's REFRESH_TOKEN_EXPIRE_DAYS default (14).
// If that env var is ever changed on the backend, update this too.
const REFRESH_COOKIE_MAX_AGE_S = 14 * 24 * 60 * 60;

const baseCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

export function setSessionCookies(tokens: TokenPair): void {
  const jar = cookies();
  jar.set(ACCESS_COOKIE, tokens.access_token, { ...baseCookieOptions, maxAge: tokens.expires_in });
  jar.set(REFRESH_COOKIE, tokens.refresh_token, { ...baseCookieOptions, maxAge: REFRESH_COOKIE_MAX_AGE_S });
}

export function clearSessionCookies(): void {
  const jar = cookies();
  jar.set(ACCESS_COOKIE, "", { ...baseCookieOptions, maxAge: 0 });
  jar.set(REFRESH_COOKIE, "", { ...baseCookieOptions, maxAge: 0 });
}

export function getAccessToken(): string | null {
  return cookies().get(ACCESS_COOKIE)?.value ?? null;
}

export function getRefreshToken(): string | null {
  return cookies().get(REFRESH_COOKIE)?.value ?? null;
}
