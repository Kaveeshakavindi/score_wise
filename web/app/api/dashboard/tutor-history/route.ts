import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

type BackendCitation = { document_id: string; filename: string; topic: string | null; snippet: string };
type BackendMessage = {
  role: "user" | "assistant";
  content: string;
  citations: BackendCitation[] | null;
  created_at: string;
};

function mapCitations(citations: BackendCitation[] | null | undefined) {
  return (citations ?? []).map((c) => ({
    documentId: c.document_id,
    filename: c.filename,
    topic: c.topic,
    snippet: c.snippet,
  }));
}

function mapMessages(messages: BackendMessage[] | undefined) {
  return (messages ?? []).map((m) => ({
    role: m.role,
    content: m.content,
    citations: mapCitations(m.citations),
    createdAt: m.created_at,
  }));
}

// GET /api/dashboard/tutor-history?limit=&offset= — questions this student
// has discussed with the tutor, most recently discussed first, each with
// its full saved (read-only) conversation (backend GET
// /api/v1/dashboard/tutor-history), camelCased for the dashboard page.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = url.searchParams.get("limit") ?? "6";
  const offset = url.searchParams.get("offset") ?? "0";

  const res = await backendFetch(`/api/v1/dashboard/tutor-history?${new URLSearchParams({ limit, offset })}`);
  if (!res.ok) {
    return NextResponse.json({ error: `Failed to load tutor history (${res.status})` }, { status: res.status });
  }

  const data = await res.json();
  return NextResponse.json({
    items: (data.items ?? []).map((h: Record<string, unknown>) => ({
      questionId: h.question_id as string,
      subject: h.subject as string,
      year: h.year as number,
      questionNumber: h.question_number as number,
      questionText: h.question_text as string,
      lastDiscussedAt: h.last_discussed_at as string,
      messages: mapMessages(h.messages as BackendMessage[] | undefined),
    })),
    total: data.total as number,
    limit: data.limit as number,
    offset: data.offset as number,
  });
}
