import { NextResponse } from "next/server";
import { extractBackendError } from "@/lib/backend";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// POST /api/auth/register — { name, nickname, password, age, email } ->
// backend POST /api/v1/auth/register (see app/schemas/auth.py::RegisterRequest
// for the exact constraints). Does not log the student in — registering only
// creates the account; the client sends them to /login to start a session
// with the credentials they just chose. Forwards the backend's real status +
// message on failure — 409 (nickname taken), 422 (validation — including a
// malformed email), 429 (rate-limited).
export async function POST(request: Request) {
  const { name, nickname, password, age, email } = await request.json();
  if (
    typeof name !== "string" ||
    typeof nickname !== "string" ||
    typeof password !== "string" ||
    typeof age !== "number" ||
    typeof email !== "string"
  ) {
    return NextResponse.json({ error: "Name, nickname, password, age, and email are required." }, { status: 400 });
  }

  const registerRes = await fetch(`${BACKEND_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, nickname, password, age, email }),
    cache: "no-store",
  });

  if (!registerRes.ok) {
    return NextResponse.json({ error: await extractBackendError(registerRes) }, { status: registerRes.status });
  }

  return NextResponse.json({ ok: true });
}
