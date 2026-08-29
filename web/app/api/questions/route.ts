import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { orderedOptionKeys } from "@/lib/options";

// GET /api/questions?paperId=... — every question in that specific paper, in
// display order, for the timed-test flow at /exam/[paperId]. QuestionOut
// already carries subject/year/paper_id per question (denormalized on the
// backend's Question model), so this needs only one backend call — no
// separate papers fetch. `correct_answer` is never exposed here (the
// backend's own QuestionOut omits it too) — only /api/submit learns it,
// after grading.
export async function GET(request: Request) {
  const paperId = new URL(request.url).searchParams.get("paperId");
  if (!paperId) {
    return NextResponse.json({ error: "paperId is required." }, { status: 400 });
  }

  // 200 is the backend's own page-size cap (app/routers/papers.py) —
  // comfortably covers any paper at today's content scale; a paper bigger
  // than that would need real pagination here, not a concern yet.
  const questionsRes = await backendFetch(`/api/v1/papers/${paperId}/questions?limit=200&offset=0`);
  if (!questionsRes.ok) {
    return NextResponse.json({ error: `Failed to load questions (${questionsRes.status})` }, { status: questionsRes.status });
  }
  const questions = await questionsRes.json();
  if (!questions.items || questions.items.length === 0) {
    return NextResponse.json({ error: "This paper has no questions." }, { status: 404 });
  }

  return NextResponse.json({
    questions: questions.items.map((question: Record<string, unknown>) => {
      const options = question.options as Record<string, string>;
      const keys = orderedOptionKeys(options);
      return {
        paperId: question.paper_id,
        subject: question.subject,
        year: question.year,
        questionId: question.id,
        questionNumber: question.question_number,
        questionText: question.question_text,
        // index = position sent back as `selected_answer` on submit — matches
        // the backend's own ordering of question.options.
        options: keys.map((key, index) => ({ index, label: key, text: options[key] })),
      };
    }),
  });
}
