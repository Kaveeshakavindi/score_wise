import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

// POST /api/submit — scores a full test attempt (every question in the
// window set, in one call) via the real backend (POST /api/v1/attempts), so
// correctness is decided server-side against the stored marking scheme,
// never in the browser. Unanswered questions are submitted with
// selectedAnswer: null, same as the backend's own "left blank" convention.
export async function POST(request: Request) {
  const { paperId, answers } = await request.json();
  if (!paperId || !Array.isArray(answers) || answers.length === 0) {
    return NextResponse.json({ error: "paperId and a non-empty answers array are required." }, { status: 400 });
  }

  const res = await backendFetch("/api/v1/attempts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      paper_id: paperId,
      answers: answers.map((a: { questionId: string; selectedAnswer: number | null }) => ({
        question_id: a.questionId,
        selected_answer: a.selectedAnswer,
      })),
    }),
  });

  if (!res.ok) {
    return NextResponse.json({ error: `Backend scoring failed (${res.status})` }, { status: 502 });
  }

  const attempt = await res.json();
  return NextResponse.json({
    results: (attempt.results ?? []).map((r: Record<string, unknown>) => ({
      questionId: r.question_id as string,
      selectedAnswer: r.selected_answer as number | null,
      correctAnswer: r.correct_answer as number | null, // null = voided question, every answer accepted
      isCorrect: r.is_correct as boolean,
    })),
  });
}
