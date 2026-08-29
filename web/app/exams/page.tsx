"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, GraduationCap } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";

type Paper = { id: string; subject: string; year: number; questionCount: number };

// Shared design-system treatments (design.md §5) — same tokens exam/page.tsx
// and dashboard/page.tsx already established, reused rather than re-invented.
const CARD = "rounded-3xl border border-stone-100 bg-white shadow-soft";
const PILL_FILTER =
  "rounded-full border px-4 py-1.5 text-sm font-medium shadow-soft transition-transform duration-300 hover:scale-[1.02]";
const PILL_FILTER_ACTIVE = "border-coral-dark bg-coral-dark text-white";
const PILL_FILTER_INACTIVE = "border-stone-200 bg-white text-text-dark";

export default function ExamsPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subjectFilter, setSubjectFilter] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/papers")
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
        const data = await res.json();
        setPapers(data.items);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  const subjects = Array.from(new Set(papers.map((p) => p.subject))).sort();
  const visiblePapers = subjectFilter ? papers.filter((p) => p.subject === subjectFilter) : papers;

  return (
    <>
      <Nav />
      <main className="relative overflow-hidden px-6 py-28">
        <DecorativeBlobs />
        <div className="relative z-10 mx-auto flex max-w-5xl flex-col gap-8">
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium tracking-wide text-coral-dark">Practice</p>
            <h1 className="text-3xl font-medium text-text-dark sm:text-4xl">Choose an exam</h1>
            <p className="text-text-muted">Pick a past paper — you&apos;ll get the full, timed set of questions.</p>
          </div>

          {subjects.length > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-sm text-text-muted">Subject</span>
              <button
                onClick={() => setSubjectFilter(null)}
                className={`${PILL_FILTER} ${subjectFilter === null ? PILL_FILTER_ACTIVE : PILL_FILTER_INACTIVE}`}
              >
                All subjects
              </button>
              {subjects.map((s) => (
                <button
                  key={s}
                  onClick={() => setSubjectFilter(s)}
                  className={`${PILL_FILTER} ${subjectFilter === s ? PILL_FILTER_ACTIVE : PILL_FILTER_INACTIVE}`}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {loading && <p className="text-text-muted">Loading exams…</p>}
          {error && <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

          {!loading && !error && visiblePapers.length === 0 && (
            <div className={`${CARD} flex flex-col items-center gap-3 p-10 text-center`}>
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-sage text-text-dark">
                <GraduationCap size={20} strokeWidth={2} />
              </span>
              <p className="text-text-muted">No exams available yet — check back soon.</p>
            </div>
          )}

          {!loading && !error && visiblePapers.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {visiblePapers.map((paper) => (
                <Link
                  key={paper.id}
                  href={`/exam/${paper.id}`}
                  className={`${CARD} group flex flex-col gap-4 p-6 transition-transform duration-300 hover:scale-[1.02]`}
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-lavender text-text-dark">
                    <BookOpen size={18} strokeWidth={2} />
                  </span>
                  <div className="flex flex-col gap-1">
                    <h2 className="text-lg font-medium text-text-dark">{paper.subject}</h2>
                    <p className="text-sm text-text-muted">{paper.year} past paper</p>
                  </div>
                  <div className="mt-auto flex items-center justify-between pt-2">
                    <span className="text-sm text-text-muted">{paper.questionCount} questions</span>
                    <span className="flex items-center gap-1 text-sm font-medium text-coral-dark">
                      Start <ArrowRight size={14} strokeWidth={2} className="transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
