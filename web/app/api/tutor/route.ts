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

// GET /api/tutor?questionId=... — loads this student's existing tutor thread
// for the question (GET /api/v1/questions/{id}/tutor/history). The practice
// page calls this before auto-sending its opener message, so reopening the
// panel (e.g. after a page refresh) shows the ongoing conversation instead
// of appending a duplicate opener to the permanent backend thread — tutor
// threads have no session/reset concept, they're one thread per question
// forever, so client-side de-duping is what keeps them from padding
// themselves with repeats.
export async function GET(request: Request) {
  const questionId = new URL(request.url).searchParams.get("questionId");
  if (!questionId) {
    return NextResponse.json({ error: "questionId is required." }, { status: 400 });
  }

  const res = await backendFetch(`/api/v1/questions/${questionId}/tutor/history`);
  if (!res.ok) {
    return NextResponse.json({ error: `Tutor history request failed (${res.status})` }, { status: 502 });
  }

  const messages = (await res.json()) as { role: "user" | "assistant"; content: string; citations: BackendCitation[] | null }[];
  return NextResponse.json({
    messages: messages.map((m) => ({
      role: m.role,
      content: m.content,
      citations: mapCitations(m.citations),
    })),
  });
}

// POST /api/tutor — proxies one chat turn to the question-scoped AI tutor
// (POST /api/v1/questions/{id}/tutor). Surfaced from the "Ask AI Tutor"
// button shown alongside a wrong-answer result on the practice page.
export async function POST(request: Request) {
  const { questionId, content, selectedAnswer } = await request.json();
  if (!questionId || typeof content !== "string" || !content.trim()) {
    return NextResponse.json({ error: "questionId and content are required." }, { status: 400 });
  }

  const res = await backendFetch(`/api/v1/questions/${questionId}/tutor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content,
      // Only meaningful on the opening turn — lets the tutor address the
      // student's actual wrong choice instead of only explaining the
      // correct answer in the abstract.
      ...(typeof selectedAnswer === "number" ? { selected_answer: selectedAnswer } : {}),
    }),
  });

  if (!res.ok) {
    return NextResponse.json({ error: `Tutor request failed (${res.status})` }, { status: 502 });
  }

  const data = await res.json();
  return NextResponse.json({
    reply: data.assistant_message.content as string,
    // The syllabus chunks that grounded this reply, so the UI can show them
    // as citations proving the answer isn't unsourced.
    citations: mapCitations(data.assistant_message.citations),
  });
}
