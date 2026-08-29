import { NextResponse } from "next/server";
import { extractBackendError } from "@/lib/backend";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// POST /api/auth/reset-password — { token, newPassword } -> backend POST
// /api/v1/auth/reset-password. On success the backend has already revoked
// every existing refresh token for the account — this route has no session
// of its own to clear (the reset token isn't a session cookie).
export async function POST(request: Request) {
  const { token, newPassword } = await request.json();
  if (typeof token !== "string" || !token || typeof newPassword !== "string" || !newPassword) {
    return NextResponse.json({ error: "Token and new password are required." }, { status: 400 });
  }

  const res = await fetch(`${BACKEND_URL}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
    cache: "no-store",
  });

  if (!res.ok) {
    return NextResponse.json({ error: await extractBackendError(res) }, { status: res.status });
  }

  return NextResponse.json({ ok: true });
}
