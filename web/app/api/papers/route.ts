import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

// GET /api/papers?subject=&limit=&offset= — the available past papers
// (backend GET /api/v1/papers), camelCased for the /exams listing page.
// Fetches a generous page (default 100) since the listing page filters by
// subject client-side rather than refetching per pill — fine at the current
// content scale (tens of papers, not thousands).
export async function GET(request: Request) {
  const url = new URL(request.url);
  const subject = url.searchParams.get("subject");
  const limit = url.searchParams.get("limit") ?? "100";
  const offset = url.searchParams.get("offset") ?? "0";

  const params = new URLSearchParams({ limit, offset });
  if (subject) params.set("subject", subject);

  const res = await backendFetch(`/api/v1/papers?${params}`);
  if (!res.ok) {
    return NextResponse.json({ error: `Failed to load papers (${res.status})` }, { status: res.status });
  }

  const data = await res.json();
  return NextResponse.json({
    items: (data.items ?? []).map((p: Record<string, unknown>) => ({
      id: p.id as string,
      subject: p.subject as string,
      year: p.year as number,
      questionCount: p.question_count as number,
    })),
    total: data.total as number,
    limit: data.limit as number,
    offset: data.offset as number,
  });
}
