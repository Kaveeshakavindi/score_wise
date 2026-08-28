"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { BookOpen, Bot, Plus, Sparkles } from "lucide-react";

// Button-triggered, structured AI tutor explanation — one fixed explanation
// per question (why it's correct / wrong / what the right answer was), not
// a chat. Shown beside the question on the results screen, not stacked
// under it: the student explicitly asks for it per question via "Explain
// why" rather than it loading automatically (an earlier version auto-fired
// on scroll-into-view, which fetched explanations for questions the student
// only glanced at, and buried the explanation below a lot of question
// content instead of letting the two sit side by side for comparison).

export type Citation = { documentId: string; filename: string; topic: string | null; snippet: string };
export type TutorMessage = { role: "user" | "assistant"; content: string; citations?: Citation[] };

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 px-1 py-2" aria-label="Generating explanation">
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

// Explanation text first, citations as expandables at the end — the student
// reads the reasoning before optionally digging into what grounded it.
function ExplanationBody({ content, citations }: { content: string; citations?: Citation[] }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="max-w-full text-sm text-text-dark">
        <TutorMarkdown content={content} />
      </div>
      {citations && citations.length > 0 && (
        <div className="flex w-full flex-col gap-1.5">
          {citations.map((c, ci) => (
            <CitationChip key={ci} index={ci} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}

type ExplanationState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; content: string; citations: Citation[] }
  | { status: "error"; error: string };

// Right-hand panel next to a result-screen question: starts as just an
// "Explain why" button; clicking it fires the (idempotent) explanation
// fetch once — a second click while already loaded does nothing new, the
// backend would just return the same cached row anyway.
export function QuestionExplanation({
  questionId,
  selectedAnswer,
}: {
  questionId: string;
  selectedAnswer: number | null;
}) {
  const [state, setState] = useState<ExplanationState>({ status: "idle" });

  function explain() {
    setState({ status: "loading" });
    fetch("/api/tutor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questionId, selectedAnswer }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
        return res.json();
      })
      .then(({ content, citations }) => setState({ status: "loaded", content, citations }))
      .catch((err) => setState({ status: "error", error: err instanceof Error ? err.message : String(err) }));
  }

  if (state.status === "idle") {
    return (
      <button
        onClick={explain}
        className="flex items-center gap-2 self-start rounded-full border border-stone-200 bg-white px-5 py-2 text-sm font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02]"
      >
        <Sparkles size={15} strokeWidth={2} /> Explain why
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="flex items-center gap-1.5 text-sm font-medium text-text-muted">
        <Bot size={16} strokeWidth={2} /> AI Tutor explanation
      </p>
      {state.status === "loading" && <ThinkingDots />}
      {state.status === "loaded" && <ExplanationBody content={state.content} citations={state.citations} />}
      {state.status === "error" && (
        <div className="flex flex-col items-start gap-2">
          <p className="rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-700">{state.error}</p>
          <button onClick={explain} className="text-sm font-medium text-text-dark underline underline-offset-2">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}

// Read-only rendering of an already-fetched explanation — used by the
// dashboard's "Tutor helped with" list, which embeds the saved message in
// what it already fetched. No fetch of its own, no button.
export function TutorHistoryView({ messages }: { messages: TutorMessage[] }) {
  return (
    <div className="flex flex-col gap-3 rounded-3xl border border-stone-100 bg-white p-4 shadow-soft">
      <p className="flex items-center gap-1.5 text-sm font-medium text-text-muted">
        <Bot size={16} strokeWidth={2} /> AI Tutor explanation
      </p>
      <div className="flex flex-col gap-3">
        {messages.map((m, i) => (
          <ExplanationBody key={i} content={m.content} citations={m.citations} />
        ))}
      </div>
    </div>
  );
}
