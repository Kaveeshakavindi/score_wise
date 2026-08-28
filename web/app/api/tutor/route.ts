import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

type BackendCitation = { document_id: string; filename: string; topic: string | null; snippet: string };

function mapCitations(citations: BackendCitation[] | null | undefined) {
  return (citations ?? []).map((c) => ({
    documentId: c.document_id,
    filename: c.filename,
    topic: c.topic,
    snippet: c.snippet,
  }));
}

// POST /api/tutor — proxies to the question-scoped AI tutor feedback
// endpoint (POST /api/v1/questions/{id}/tutor). Idempotent per exact
// (question, student, selectedAnswer) on the backend: asking again about the
// same recorded answer returns the same cached explanation instead of
// re-paying for an LLM call, but a different selectedAnswer (e.g. a retake)
// always generates a fresh one — it's never stuck showing feedback for an
// answer the student no longer has selected.
export async function POST(request: Request) {
  const { questionId, selectedAnswer } = await request.json();
  if (!questionId) {
    return NextResponse.json({ error: "questionId is required." }, { status: 400 });
  }

  const res = await backendFetch(`/api/v1/questions/${questionId}/tutor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      // null (left blank) is meaningful here, not just "omitted" — it picks
      // the backend's "missed" feedback branch instead of "wrong".
      selected_answer: typeof selectedAnswer === "number" ? selectedAnswer : null,
    }),
  });

  if (!res.ok) {
    return NextResponse.json({ error: `Tutor request failed (${res.status})` }, { status: 502 });
  }

  const { feedback } = await res.json();
  return NextResponse.json({
    content: feedback.content as string,
    isCorrect: feedback.is_correct as boolean | null,
    // The syllabus chunks that grounded this feedback, so the UI can show
    // them as citations proving the explanation isn't unsourced.
    citations: mapCitations(feedback.citations),
  });
}
