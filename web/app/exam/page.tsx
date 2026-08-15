"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { BookOpen, Bot, CheckCircle2, Clock, ListChecks, MoveHorizontal, Plus, XCircle } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";

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
type Citation = { documentId: string; filename: string; topic: string | null; snippet: string };
type TutorMessage = { role: "user" | "assistant"; content: string; citations?: Citation[] };
type TutorThread = { open: boolean; messages: TutorMessage[]; sending: boolean; error: string | null };

type Screen = "start" | "test" | "result";

const TEST_QUESTION_COUNT = 2;
const TEST_DURATION_SECONDS = 60;
const TUTOR_OPENER = "I got this question wrong — can you help me understand why?";
const EMPTY_THREAD: TutorThread = { open: false, messages: [], sending: false, error: null };

// Shared design-system button/card treatments (design.md §5) — pill shapes,
// soft shadow, warm palette.
const CARD = "rounded-3xl border border-stone-100 bg-white shadow-soft";
const PRIMARY_PILL_LG =
  "rounded-full bg-coral px-8 py-4 text-lg font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100";
// Test screen's Previous/Next: equal-weight, neutral navigation — no color,
// so Submit (the one committing action) is the only accent on the screen.
const NEUTRAL_PILL =
  "rounded-full border border-stone-200 bg-white px-5 py-2 font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100";
const SECONDARY_PILL = NEUTRAL_PILL;
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

export default function ExamPage() {
  const [screen, setScreen] = useState<Screen>("start");
  const [questions, setQuestions] = useState<TestQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [timeLeft, setTimeLeft] = useState(TEST_DURATION_SECONDS);
  const [results, setResults] = useState<QuestionResult[] | null>(null);

  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [tutorThreads, setTutorThreads] = useState<Record<string, TutorThread>>({});

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

  async function startTest() {
    setLoadingQuestions(true);
    setLoadError(null);
    try {
      const res = await fetch(`/api/questions?limit=${TEST_QUESTION_COUNT}`);
      if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      const { questions: loaded } = await res.json();
      setQuestions(loaded);
      setAnswers(new Array(loaded.length).fill(null));
      setCurrentIndex(0);
      setTimeLeft(TEST_DURATION_SECONDS);
      setResults(null);
      setSubmitError(null);
      setTutorThreads({});
      setScreen("test");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingQuestions(false);
    }
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
          paperId: questions[0].paperId,
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

  function updateThread(questionId: string, patch: Partial<TutorThread> | ((t: TutorThread) => Partial<TutorThread>)) {
    setTutorThreads((prev) => {
      const current = prev[questionId] ?? EMPTY_THREAD;
      const delta = typeof patch === "function" ? patch(current) : patch;
      return { ...prev, [questionId]: { ...current, ...delta } };
    });
  }

  async function sendTutorMessage(questionId: string, content: string, selectedAnswer?: number) {
    if (!content.trim()) return;
    updateThread(questionId, (t) => ({ messages: [...t.messages, { role: "user", content }], sending: true, error: null }));
    try {
      const res = await fetch("/api/tutor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ questionId, content, selectedAnswer }),
      });
      if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      const { reply, citations } = await res.json();
      updateThread(questionId, (t) => ({ messages: [...t.messages, { role: "assistant", content: reply, citations }] }));
    } catch (err) {
      updateThread(questionId, { error: err instanceof Error ? err.message : String(err) });
    } finally {
      updateThread(questionId, { sending: false });
    }
  }

  async function openTutor(questionId: string, selectedAnswer: number | null) {
    updateThread(questionId, { open: true });
    if ((tutorThreads[questionId]?.messages.length ?? 0) > 0) return; // already loaded this render

    // Tutor threads have no session/reset concept — they're one permanent
    // thread per (question, student) on the backend. Load whatever's already
    // there first, so reopening this panel shows the ongoing conversation
    // instead of appending a duplicate opener to that permanent thread.
    updateThread(questionId, { sending: true, error: null });
    try {
      const res = await fetch(`/api/tutor?questionId=${questionId}`);
      if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      const { messages } = await res.json();
      if (messages.length > 0) {
        updateThread(questionId, { messages, sending: false });
        return;
      }
      await sendTutorMessage(questionId, TUTOR_OPENER, selectedAnswer ?? undefined);
    } catch (err) {
      updateThread(questionId, { error: err instanceof Error ? err.message : String(err), sending: false });
    }
  }

  if (screen === "start") {
    const minutes = TEST_DURATION_SECONDS / 60;
    const instructions = [
      {
        icon: ListChecks,
        text: `This practice set has ${TEST_QUESTION_COUNT} multiple-choice questions, one shown at a time.`,
      },
      {
        icon: Clock,
        text: `You'll have ${minutes} minute${minutes === 1 ? "" : "s"} on the clock, and it runs continuously across every question — no pausing, no per-question reset.`,
      },
      {
        icon: MoveHorizontal,
        text: "Previous and Next just move between questions — neither one submits anything. Submit ends the test immediately, wherever you are; anything left blank counts as unanswered.",
      },
      {
        icon: Bot,
        text: "Once you finish, any question you got wrong unlocks an AI Tutor grounded in the syllabus — expand its citations to see the exact source snippet it's using.",
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

          <button onClick={startTest} disabled={loadingQuestions} className={`${PRIMARY_PILL_LG} w-full`}>
            {loadingQuestions ? "Loading…" : "Begin"}
          </button>

          {loadError && (
            <div className="w-full rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
              <p>{loadError}</p>
              <button type="button" onClick={startTest} className="mt-2 font-medium underline underline-offset-2">
                Try again
              </button>
            </div>
          )}
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
      <main key="result" className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-16">
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
            const thread = tutorThreads[q.questionId] ?? EMPTY_THREAD;
            if (!r) return null;
            return (
              <div key={q.questionId} className={`${CARD} flex flex-col gap-4 p-6`}>
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

                {!r.isCorrect && (
                  <div className="flex flex-col gap-3">
                    {!thread.open && (
                      <button
                        onClick={() => openTutor(q.questionId, r.selectedAnswer)}
                        className={`${SECONDARY_PILL} flex items-center gap-2 self-start`}
                      >
                        <Bot size={16} strokeWidth={2} /> Ask AI Tutor
                      </button>
                    )}
                    {thread.open && (
                      <TutorPanel thread={thread} onSend={(content) => sendTutorMessage(q.questionId, content)} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <button onClick={startTest} className={`${PRIMARY_PILL_LG} self-start`}>
          Take Another Test
        </button>
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

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-2" aria-label="AI tutor is thinking">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-dot-pulse rounded-full bg-stone-400"
          style={{ animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  );
}

function TutorMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-text-dark">{children}</strong>,
        ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function CitationChip({ index, citation }: { index: number; citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-2xl border border-stone-100 bg-stone-50 text-xs">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left font-medium text-text-muted"
      >
        <span className="flex items-center gap-1.5">
          <BookOpen size={14} strokeWidth={2} className="shrink-0" />
          Citation {index + 1}: {citation.filename}
          {citation.topic ? ` · ${citation.topic}` : ""}
        </span>
        <Plus size={14} strokeWidth={2} className={`shrink-0 transition-transform duration-300 ${open ? "rotate-45" : ""}`} />
      </button>
      {/* design.md §6 accordion-expand: height 0→auto, 500ms ease-in-out —
          the grid-rows trick animates smoothly to intrinsic content height,
          which a native <details> toggle can't do. */}
      <div className="grid transition-[grid-template-rows] duration-500 ease-in-out" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
        <div className="overflow-hidden">
          <p className="whitespace-pre-wrap px-3 pb-3 text-text-muted">{citation.snippet}</p>
        </div>
      </div>
    </div>
  );
}

function TutorPanel({ thread, onSend }: { thread: TutorThread; onSend: (content: string) => void }) {
  const [input, setInput] = useState("");
  return (
    <div className={`${CARD} flex flex-col gap-3 p-4`}>
      <p className="flex items-center gap-1.5 text-sm font-medium text-text-muted">
        <Bot size={16} strokeWidth={2} /> AI Tutor
      </p>

      <div className="flex max-h-96 flex-col gap-3 overflow-y-auto">
        {thread.messages.map((m, i) => (
          <div key={i} className={`flex flex-col gap-1.5 ${m.role === "user" ? "items-end" : "items-start"}`}>
            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div className="flex w-full flex-col gap-1.5">
                {m.citations.map((c, ci) => (
                  <CitationChip key={ci} index={ci} citation={c} />
                ))}
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-3xl px-4 py-3 text-sm ${
                m.role === "user" ? "bg-lavender text-text-dark" : "bg-stone-50 text-text-dark"
              }`}
            >
              {m.role === "assistant" ? (
                <TutorMarkdown content={m.content} />
              ) : (
                <p className="whitespace-pre-wrap">{m.content}</p>
              )}
            </div>
          </div>
        ))}
        {thread.sending && <ThinkingDots />}
      </div>

      {thread.error && <p className="rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-700">{thread.error}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const content = input;
          setInput("");
          onSend(content);
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a follow-up…"
          disabled={thread.sending}
          className="flex-1 rounded-full border border-stone-200 bg-white px-4 py-2 text-sm text-text-dark placeholder:text-text-muted disabled:cursor-not-allowed disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={thread.sending || !input.trim()}
          className="rounded-full bg-coral px-4 py-2 text-sm font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
        >
          Send
        </button>
      </form>
    </div>
  );
}
