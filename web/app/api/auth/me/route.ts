import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

// GET /api/auth/me — the current session's profile (backend GET
// /api/v1/auth/me), camelCased. Used by Nav to know whether anyone's logged
// in and to show their name; a 401 here just means "not logged in", not an
// error worth surfacing.
export async function GET() {
  const res = await backendFetch("/api/v1/auth/me");
  if (!res.ok) {
    return NextResponse.json({ error: "Not logged in." }, { status: 401 });
  }

  const user = await res.json();
  return NextResponse.json({
    id: user.id as string,
    name: user.name as string,
    nickname: user.nickname as string,
    age: user.age as number,
  });
}
