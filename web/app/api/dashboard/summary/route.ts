import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

// GET /api/dashboard/summary — this student's performance overview (backend
// GET /api/v1/dashboard/summary), camelCased for the dashboard page.
export async function GET() {
  const res = await backendFetch("/api/v1/dashboard/summary");
  if (!res.ok) {
    return NextResponse.json({ error: `Failed to load dashboard summary (${res.status})` }, { status: res.status });
  }

  const data = await res.json();
  return NextResponse.json({
    overallCorrect: data.overall_correct as number,
    overallTotal: data.overall_total as number,
    attemptsCount: data.attempts_count as number,
    subjects: (data.subjects ?? []).map((s: Record<string, unknown>) => ({
      subject: s.subject as string,
      correct: s.correct as number,
      total: s.total as number,
    })),
    trend: (data.trend ?? []).map((t: Record<string, unknown>) => ({
      attemptId: t.attempt_id as string,
      paperId: t.paper_id as string,
      subject: t.subject as string,
      year: t.year as number,
      score: t.score as number,
      total: t.total as number,
      createdAt: t.created_at as string,
    })),
    mistakesTotal: data.mistakes_total as number,
    mistakesUnreviewed: data.mistakes_unreviewed as number,
    followThroughRate: data.follow_through_rate as number,
    tutorHelpedCount: data.tutor_helped_count as number,
    topTopics: (data.top_topics ?? []).map((t: Record<string, unknown>) => ({
      topic: t.topic as string,
      count: t.count as number,
    })),
    tutorActivity: (data.tutor_activity ?? []).map((a: Record<string, unknown>) => ({
      date: a.date as string,
      count: a.count as number,
    })),
  });
}
