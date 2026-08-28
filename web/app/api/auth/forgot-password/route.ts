import { NextResponse } from "next/server";
import { extractBackendError } from "@/lib/backend";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// POST /api/auth/forgot-password — { email } -> backend POST
// /api/v1/auth/forgot-password. The backend's own response is already
// generic (same message whether or not the email has an account) — this
// route just forwards it as-is, no anti-enumeration logic needed here.
export async function POST(request: Request) {
  const { email } = await request.json();
  if (typeof email !== "string" || !email) {
    return NextResponse.json({ error: "Email is required." }, { status: 400 });
  }

  const res = await fetch(`${BACKEND_URL}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
    cache: "no-store",
  });

  if (!res.ok) {
    return NextResponse.json({ error: await extractBackendError(res) }, { status: res.status });
  }

  return NextResponse.json(await res.json());
}
