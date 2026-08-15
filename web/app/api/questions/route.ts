import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { orderedOptionKeys } from "@/lib/options";

// GET /api/questions?limit=2 — the first N questions of the first available
// paper, in display order, for the timed-test flow on the practice page.
// `correct_answer` is never exposed here (the backend's own QuestionOut
// omits it too) — only /api/submit learns it, after grading.
export async function GET(request: Request) {
  const limit = Number(new URL(request.url).searchParams.get("limit") ?? "2");

  const papersRes = await backendFetch("/api/v1/papers?limit=1&offset=0");
  if (!papersRes.ok) {
    return NextResponse.json({ error: `Failed to list papers (${papersRes.status})` }, { status: 502 });
  }
  const papers = await papersRes.json();
  const paper = papers.items?.[0];
  if (!paper) {
    return NextResponse.json({ error: "No papers found. Seed one first." }, { status: 404 });
  }

  const questionsRes = await backendFetch(`/api/v1/papers/${paper.id}/questions?limit=${limit}&offset=0`);
  if (!questionsRes.ok) {
    return NextResponse.json({ error: `Failed to list questions (${questionsRes.status})` }, { status: 502 });
  }
  const questions = await questionsRes.json();
  if (!questions.items || questions.items.length === 0) {
    return NextResponse.json({ error: "Paper has no questions." }, { status: 404 });
  }

  return NextResponse.json({
    questions: questions.items.map((question: Record<string, unknown>) => {
      const options = question.options as Record<string, string>;
      const keys = orderedOptionKeys(options);
      return {
        paperId: paper.id,
        subject: paper.subject,
        year: paper.year,
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
