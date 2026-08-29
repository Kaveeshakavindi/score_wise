// Talks directly to the FastAPI backend from the browser (this SPA has no
// server of its own, unlike web/'s Next.js BFF) — so unlike web/lib/session.ts
// (httpOnly cookies, never touched by JS), the tokens genuinely have to live
// in the browser. sessionStorage rather than localStorage: cleared when the
// tab closes, since there's no reason for an admin session to outlive it.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "scorewise_admin_access_token";
const REFRESH_TOKEN_KEY = "scorewise_admin_refresh_token";

export class ApiError extends Error {}

type TokenPair = { access_token: string; refresh_token: string };

function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY);
}

function setTokens(tokens: TokenPair): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function isLoggedIn(): boolean {
  return getAccessToken() !== null;
}

/** Unwraps app/core/exceptions.py's error envelope
 * (`{ error: { code, message, details, request_id } }`) into a plain
 * message, same shape web/lib/backend.ts's extractBackendError parses —
 * falls back to a generic message for a non-JSON or differently-shaped
 * error body (e.g. a raw 502 from something in front of the backend). */
async function extractError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.error?.message === "string") return body.error.message;
  } catch {
    // not JSON — fall through
  }
  return `Request failed (${res.status})`;
}

export async function login(nickname: string, password: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: nickname, password }),
  });
  if (!res.ok) throw new ApiError(await extractError(res));
  const data = await res.json();
  setTokens({ access_token: data.access_token, refresh_token: data.refresh_token });
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) {
    clearTokens();
    return null;
  }
  const data = await res.json();
  setTokens({ access_token: data.access_token, refresh_token: data.refresh_token });
  return data.access_token as string;
}

/** Thrown by authedFetch when the access token is gone/invalid and refreshing
 * it didn't help either — callers should drop back to the login view rather
 * than showing this as a generic error message. */
export class SessionExpiredError extends ApiError {}

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const attempt = (token: string | null) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { ...init.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });

  let res = await attempt(getAccessToken());
  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    res = refreshed ? await attempt(refreshed) : res;
  }
  if (res.status === 401) {
    clearTokens();
    throw new SessionExpiredError("Your session has expired. Please log in again.");
  }
  return res;
}

export type SyllabusDocument = {
  id: string;
  filename: string;
  subject: string;
  topic: string | null;
  uploaded_at: string;
  chunk_count: number;
};

export async function listDocuments(): Promise<SyllabusDocument[]> {
  const res = await authedFetch("/api/v1/admin/documents?limit=100&offset=0");
  if (!res.ok) throw new ApiError(await extractError(res));
  const page = await res.json();
  return page.items as SyllabusDocument[];
}

export async function uploadDocument(params: {
  file: File;
  subject: string;
  gradeLevel: string;
}): Promise<SyllabusDocument> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("subject", params.subject);
  form.append("grade_level", params.gradeLevel);

  const res = await authedFetch("/api/v1/admin/documents", { method: "POST", body: form });
  if (!res.ok) throw new ApiError(await extractError(res));
  return (await res.json()) as SyllabusDocument;
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await authedFetch(`/api/v1/admin/documents/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new ApiError(await extractError(res));
}
