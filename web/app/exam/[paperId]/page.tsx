"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bot, CheckCircle2, Clock, ListChecks, MoveHorizontal, XCircle } from "lucide-react";
import { DecorativeBlobs } from "../../_components/DecorativeBlobs";
import { Nav } from "../../_components/Nav";
import { QuestionExplanation } from "../../_components/TutorPanel";

type Option = { index: number; label: string; text: string };
type TestQuestion = {
  paperId: string;
  subject: string;
  year: number;
  questionId: string;
  questionNumber: number;
  questionText: string;
  options: Option[];
};
type QuestionResult = {
  questionId: string;
  selectedAnswer: number | null;
  correctAnswer: number | null; // null = voided question, every answer accepted
  isCorrect: boolean;
};

type Screen = "start" | "test" | "result";

// A picked exam is taken in full (every question in that paper), duration
// scaled to match — not a fixed demo slice. 90s/question ~ a 50-question
// paper works out to 75 minutes, matching real GCE A/L MCQ pacing.
const SECONDS_PER_QUESTION = 90;

// Shared design-system button/card treatments (design.md §5) — pill shapes,
// soft shadow, warm palette.
const CARD = "rounded-3xl border border-stone-100 bg-white shadow-soft";
const PRIMARY_PILL_LG =
  "rounded-full bg-coral px-8 py-4 text-lg font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100";
// Test screen's Previous/Next: equal-weight, neutral navigation — no color,
// so Submit (the one committing action) is the only accent on the screen.
const NEUTRAL_PILL =
  "rounded-full border border-stone-200 bg-white px-5 py-2 font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100";
// Test screen's one primary/colored action — deliberately not the base
// --coral (reserved for the marketing site + Start/Begin/Take Another Test),
// so Submit reads as this screen's own distinct, deeper accent.
const SUBMIT_PILL =
  "self-start rounded-full bg-coral-dark px-6 py-2.5 font-medium text-white shadow-soft transition-transform duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100";

// design.md's usability fix: real MM:SS with rollover (1:00 → 0:00) instead
// of the old literal "00:" + two-digit-seconds display.
function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ExamPage({ params }: { params: { paperId: string } }) {
  const { paperId } = params;

  const [screen, setScreen] = useState<Screen>("start");
  const [questions, setQuestions] = useState<TestQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [timeLeft, setTimeLeft] = useState(0);
  const [results, setResults] = useState<QuestionResult[] | null>(null);

  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // The full paper's questions load as soon as this page mounts — the
  // "Before you begin" screen below needs the real count/duration to show,
  // not a hardcoded placeholder, so there's nothing useful to render before
  // this resolves. Clicking "Begin" is then an instant local transition, no
  // fetch-on-click delay.
  async function loadQuestions() {
    setLoadingQuestions(true);
    setLoadError(null);
    try {
      const res = await fetch(`/api/questions?paperId=${paperId}`);
      if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      const { questions: loaded } = await res.json();
      setQuestions(loaded);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingQuestions(false);
    }
  }

  useEffect(() => {
    loadQuestions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId]);

  // One continuous countdown for the whole test, ticking while on the test
  // screen regardless of which question window is showing.
  useEffect(() => {
    if (screen !== "test") return;
    const id = setInterval(() => setTimeLeft((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(id);
  }, [screen]);

  useEffect(() => {
    if (screen === "test" && timeLeft === 0) handleSubmit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeLeft, screen]);

  function beginTest() {
    setAnswers(new Array(questions.length).fill(null));
    setCurrentIndex(0);
    setTimeLeft(questions.length * SECONDS_PER_QUESTION);
    setResults(null);
    setSubmitError(null);
    setScreen("test");
  }

  function selectOption(index: number) {
    setAnswers((prev) => prev.map((a, i) => (i === currentIndex ? index : a)));
  }

  async function handleSubmit() {
    if (submitting || results !== null || questions.length === 0) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paperId,
          answers: questions.map((q, i) => ({ questionId: q.questionId, selectedAnswer: answers[i] })),
        }),
      });
      if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      const { results: graded } = await res.json();
      setResults(graded);
      setScreen("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (screen === "start") {
    const totalMinutes = Math.round((questions.length * SECONDS_PER_QUESTION) / 60);
    const instructions = [
      {
        icon: ListChecks,
        text: `This practice set has ${questions.length} multiple-choice questions, one shown at a time.`,
      },
      {
        icon: Clock,
        text: `You'll have ${totalMinutes} minute${totalMinutes === 1 ? "" : "s"} on the clock, and it runs continuously across every question — no pausing, no per-question reset.`,
      },
      {
        icon: MoveHorizontal,
        text: "Previous and Next just move between questions — neither one submits anything. Submit ends the test immediately, wherever you are; anything left blank counts as unanswered.",
      },
      {
        icon: Bot,
        text: "Once you finish, each question has an \"Explain why\" button next to it — click it for an AI Tutor explanation grounded in the syllabus, shown right beside the question. Expand a citation to see the exact source snippet it's using.",
      },
    ];
    return (
      <>
        <Nav />
        <main key="start" className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-16">
        <DecorativeBlobs />
        <div className="relative z-10 flex w-full max-w-md animate-reveal flex-col items-center gap-6">
          <div className="flex flex-col items-center gap-2 text-center">
            <h1 className="text-2xl font-medium text-text-dark">Before you begin</h1>
          </div>

          {loadingQuestions && <p className="text-text-muted">Loading this exam…</p>}

          {loadError && (
            <div className="w-full rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
              <p>{loadError}</p>
              <button type="button" onClick={loadQuestions} className="mt-2 font-medium underline underline-offset-2">
                Try again
              </button>
            </div>
          )}

          {!loadingQuestions && !loadError && questions.length > 0 && (
            <>
              <div className={`${CARD} flex w-full flex-col gap-4 p-6`}>
                {instructions.map(({ icon: Icon, text }, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sage text-text-dark">
                      <Icon size={16} strokeWidth={2} />
                    </span>
                    <p className="pt-1.5 text-sm text-text-muted">{text}</p>
                  </div>
                ))}
              </div>

              <button onClick={beginTest} className={`${PRIMARY_PILL_LG} w-full`}>
                Begin
              </button>
            </>
          )}

          <Link href="/exams" className="text-sm text-text-muted underline underline-offset-2 hover:text-text-dark">
            Choose a different exam
          </Link>
        </div>
        </main>
      </>
    );
  }

  if (screen === "test") {
    const q = questions[currentIndex];
    const isFirst = currentIndex === 0;
    const isLast = currentIndex === questions.length - 1;
    const urgent = timeLeft <= 10;
    return (
      <main key="test" className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-16">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <p className="text-sm text-text-muted">
              Question {currentIndex + 1} of {questions.length}
            </p>
            <ProgressDots total={questions.length} current={currentIndex} />
          </div>
          <div
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-sm ${
              urgent ? "animate-timer-pulse bg-red-50 text-red-700" : "bg-stone-100 text-text-muted"
            }`}
          >
            <Clock size={14} strokeWidth={2} />
            {formatTime(timeLeft)}
          </div>
        </div>

        <div key={currentIndex} className={`${CARD} flex animate-reveal flex-col gap-6 p-6`}>
          <div>
            <p className="text-sm text-text-muted">
              {q.subject} · {q.year} · Question {q.questionNumber}
            </p>
            <p className="mt-2 whitespace-pre-wrap text-lg text-text-dark">{q.questionText}</p>
          </div>

          <fieldset className="flex flex-col gap-3">
            {q.options.map((opt) => {
              const selected = answers[currentIndex] === opt.index;
              return (
                <label
                  key={opt.index}
                  className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-5 py-4 transition-colors ${
                    selected ? "border-coral bg-coral/15" : "border-stone-200 bg-white hover:border-stone-300 hover:bg-sage/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="option"
                    className="mt-1 accent-coral"
                    checked={selected}
                    onChange={() => selectOption(opt.index)}
                  />
                  <span className="text-text-dark">
                    <span className="font-medium">({opt.label})</span> {opt.text}
                  </span>
                </label>
              );
            })}
          </fieldset>

          <div className="flex flex-col gap-3">
            <div className="flex gap-3">
              {!isFirst && (
                <button onClick={() => setCurrentIndex((i) => i - 1)} className={NEUTRAL_PILL}>
                  Previous
                </button>
              )}
              <button onClick={() => setCurrentIndex((i) => i + 1)} disabled={isLast} className={NEUTRAL_PILL}>
                Next
              </button>
            </div>
            <button onClick={handleSubmit} disabled={submitting} className={SUBMIT_PILL}>
              {submitting ? "Submitting…" : "Submit"}
            </button>
          </div>

          {submitError && <p className="rounded-2xl bg-red-50 px-4 py-3 text-red-700">{submitError}</p>}
        </div>
      </main>
    );
  }

  // screen === "result" — once the student has actually finished, show the
  // nav so there's a way back to the rest of the site (its anchor links
  // point at "/#..." precisely so they work from here too).
  return (
    <>
      <Nav />
      <main key="result" className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 px-6 py-16">
      <div className="flex animate-reveal flex-col gap-6">
        <div>
          <h1 className="text-2xl font-medium text-text-dark">Results</h1>
          <p className="text-text-muted">
            Score:{" "}
            <span className="font-accent text-3xl text-coral">
              {results?.filter((r) => r.isCorrect).length ?? 0} / {results?.length ?? 0}
            </span>
          </p>
        </div>

        <div className="flex flex-col gap-6">
          {questions.map((q) => {
            const r = results?.find((res) => res.questionId === q.questionId);
            if (!r) return null;
            return (
              <div key={q.questionId} className={`${CARD} grid grid-cols-1 gap-6 p-6 md:grid-cols-2`}>
                <div className="flex flex-col gap-4">
                  <div>
                    <p className="text-sm text-text-muted">
                      {q.subject} · {q.year} · Question {q.questionNumber}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-lg text-text-dark">{q.questionText}</p>
                  </div>

                  <div className="flex flex-col gap-2">
                    {q.options.map((opt) => {
                      const isCorrectOption = r.correctAnswer !== null && opt.index === r.correctAnswer;
                      const isStudentWrongPick = !r.isCorrect && r.selectedAnswer === opt.index;
                      return (
                        <div
                          key={opt.index}
                          className={`flex items-center justify-between gap-2 rounded-2xl border px-4 py-3 text-sm ${
                            isCorrectOption
                              ? "border-green-500 bg-green-50"
                              : isStudentWrongPick
                                ? "border-red-500 bg-red-50"
                                : "border-stone-200"
                          }`}
                        >
                          <span>
                            <span className="font-medium">({opt.label})</span> {opt.text}
                          </span>
                          {isCorrectOption && (
                            <span className="flex shrink-0 items-center gap-1 font-medium text-green-700">
                              <CheckCircle2 size={16} strokeWidth={2} /> Correct answer
                            </span>
                          )}
                          {isStudentWrongPick && (
                            <span className="flex shrink-0 items-center gap-1 font-medium text-red-700">
                              <XCircle size={16} strokeWidth={2} /> Your answer
                            </span>
                          )}
                        </div>
                      );
                    })}
                    {r.selectedAnswer === null && (
                      <span className="inline-block w-fit rounded-full bg-stone-50 px-3 py-1 text-sm text-text-muted">
                        You left this question blank.
                      </span>
                    )}
                  </div>
                </div>

                {/* Explanation sits beside the question, not under it — a
                    top border on mobile (stacked) becomes a left border on
                    md+ (side by side) to read as a divider either way. */}
                <div className="flex flex-col gap-3 border-t border-stone-100 pt-6 md:border-l md:border-t-0 md:pl-6 md:pt-0">
                  <QuestionExplanation questionId={q.questionId} selectedAnswer={r.selectedAnswer} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button onClick={beginTest} className={PRIMARY_PILL_LG}>
            Take Another Test
          </button>
          <Link href="/exams" className={NEUTRAL_PILL}>
            Choose another exam
          </Link>
        </div>
      </div>
      </main>
    </>
  );
}

function ProgressDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-1.5" aria-hidden="true">
      {Array.from({ length: total }).map((_, i) => (
        <span key={i} className={`h-2 w-2 rounded-full transition-colors ${i <= current ? "bg-coral" : "bg-stone-200"}`} />
      ))}
    </div>
  );
}
