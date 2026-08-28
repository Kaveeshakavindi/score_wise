"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, ChevronDown, GraduationCap, MessagesSquare, Target } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";
import { TutorHistoryView, type TutorMessage } from "../_components/TutorPanel";

type SubjectAccuracy = { subject: string; correct: number; total: number };
type TrendPoint = {
  attemptId: string;
  paperId: string;
  subject: string;
  year: number;
  score: number;
  total: number;
  createdAt: string;
};
type TopicCount = { topic: string; count: number };
type DashboardSummary = {
  overallCorrect: number;
  overallTotal: number;
  attemptsCount: number;
  subjects: SubjectAccuracy[];
  trend: TrendPoint[];
  mistakesTotal: number;
  mistakesUnreviewed: number;
  followThroughRate: number;
  tutorHelpedCount: number;
  topTopics: TopicCount[];
};
type TutorHelpedQuestion = {
  questionId: string;
  subject: string;
  year: number;
  questionNumber: number;
  questionText: string;
  lastDiscussedAt: string;
  messages: TutorMessage[];
};

const HISTORY_PAGE_SIZE = 6;

// Shared design-system treatments (design.md §5) — same tokens exam/page.tsx
// already established, reused rather than re-invented.
const CARD = "rounded-3xl border border-stone-100 bg-white shadow-soft";
const PILL_FILTER =
  "rounded-full border px-4 py-1.5 text-sm font-medium shadow-soft transition-transform duration-300 hover:scale-[1.02]";
const PILL_FILTER_ACTIVE = "border-coral-dark bg-coral-dark text-white";
const PILL_FILTER_INACTIVE = "border-stone-200 bg-white text-text-dark";
const PRIMARY_PILL_LG =
  "rounded-full bg-coral px-8 py-4 text-lg font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02]";

function pct(correct: number, total: number): number {
  return total > 0 ? Math.round((correct / total) * 100) : 0;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Which trend-point indices get an x-axis date label: all of them if there
// are few, else a handful spread across the range (always including the
// first and last) — marks-and-anatomy.md's "label selectively."
function pickLabelIndices(n: number): number[] {
  if (n <= 5) return Array.from({ length: n }, (_, i) => i);
  const picks = new Set([0, n - 1, Math.round((n - 1) / 4), Math.round((n - 1) / 2), Math.round((3 * (n - 1)) / 4)]);
  return Array.from(picks).sort((a, b) => a - b);
}

export default function DashboardPage() {
  const router = useRouter();
  const [userName, setUserName] = useState<string | null>(null);

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const [helped, setHelped] = useState<TutorHelpedQuestion[]>([]);
  const [helpedTotal, setHelpedTotal] = useState(0);
  const [helpedLoading, setHelpedLoading] = useState(true);
  const [helpedError, setHelpedError] = useState<string | null>(null);

  const [subjectFilter, setSubjectFilter] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUserName(data?.name ?? null))
      .catch(() => setUserName(null));
  }, []);

  useEffect(() => {
    fetch("/api/dashboard/summary")
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
        setSummary(await res.json());
      })
      .catch((err) => setSummaryError(err instanceof Error ? err.message : String(err)))
      .finally(() => setSummaryLoading(false));
  }, []);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/");
    router.refresh();
  }

  async function loadTutorHistory(offset: number, append: boolean) {
    setHelpedLoading(true);
    setHelpedError(null);
    try {
      const params = new URLSearchParams({ limit: String(HISTORY_PAGE_SIZE), offset: String(offset) });
      const res = await fetch(`/api/dashboard/tutor-history?${params}`);
      if (!res.ok) throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      const data = await res.json();
      setHelped((prev) => (append ? [...prev, ...data.items] : data.items));
      setHelpedTotal(data.total);
    } catch (err) {
      setHelpedError(err instanceof Error ? err.message : String(err));
    } finally {
      setHelpedLoading(false);
    }
  }

  useEffect(() => {
    loadTutorHistory(0, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (summaryLoading) {
    return (
      <>
        <Nav />
        <main className="flex min-h-screen items-center justify-center px-6">
          <p className="text-text-muted">Loading your dashboard…</p>
        </main>
      </>
    );
  }

  if (summaryError || !summary) {
    return (
      <>
        <Nav />
        <main className="flex min-h-screen items-center justify-center px-6">
          <p className="rounded-2xl bg-red-50 px-4 py-3 text-red-700">{summaryError ?? "Something went wrong."}</p>
        </main>
      </>
    );
  }

  if (summary.attemptsCount === 0) {
    return (
      <>
        <Nav />
        <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
          <DecorativeBlobs />
          {userName && (
            <div className="absolute right-6 top-24 z-10">
              <AccountBar name={userName} onLogout={handleLogout} />
            </div>
          )}
          <div className="relative z-10 flex max-w-md flex-col items-center gap-4 animate-reveal">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-coral text-text-dark">
              <GraduationCap size={22} strokeWidth={2} />
            </span>
            <h1 className="text-2xl font-medium text-text-dark">No practice yet</h1>
            <p className="text-text-muted">
              Take your first practice test and this page will fill in with your accuracy, progress over time, and
              the AI Tutor feedback worth revisiting.
            </p>
            <Link href="/exams" className={PRIMARY_PILL_LG}>
              Start Exam
            </Link>
          </div>
        </main>
      </>
    );
  }

  const overallPct = pct(summary.overallCorrect, summary.overallTotal);
  const followThroughPct = Math.round(summary.followThroughRate * 100);

  return (
    <>
      <Nav />
      <main className="relative overflow-hidden px-6 py-28">
        <DecorativeBlobs />
        <div className="relative z-10 mx-auto flex max-w-5xl flex-col gap-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium tracking-wide text-coral-dark">Your progress</p>
              <h1 className="text-3xl font-medium text-text-dark sm:text-4xl">Here&apos;s how practice has gone</h1>
              <p className="text-text-muted">
                Score across your recent attempts, where you&apos;re strongest, and what&apos;s worth a second look.
              </p>
            </div>
            {userName && <AccountBar name={userName} onLogout={handleLogout} />}
          </div>

          {summary.subjects.length > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-sm text-text-muted">Subject</span>
              <button
                onClick={() => setSubjectFilter(null)}
                className={`${PILL_FILTER} ${subjectFilter === null ? PILL_FILTER_ACTIVE : PILL_FILTER_INACTIVE}`}
              >
                All subjects
              </button>
              {summary.subjects.map((s) => (
                <button
                  key={s.subject}
                  onClick={() => setSubjectFilter(s.subject)}
                  className={`${PILL_FILTER} ${subjectFilter === s.subject ? PILL_FILTER_ACTIVE : PILL_FILTER_INACTIVE}`}
                >
                  {s.subject}
                </button>
              ))}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            <KpiTile label="Overall accuracy" value={`${overallPct}%`} caption={`${summary.overallCorrect} of ${summary.overallTotal} correct`} />
            <KpiTile label="Papers attempted" value={String(summary.attemptsCount)} />
            <KpiTile
              label="Tutor helped with"
              value={String(summary.tutorHelpedCount)}
              caption="wrong answers you've reviewed AI Tutor feedback for"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr] lg:items-start">
            <div className="flex min-w-0 flex-col gap-6">
              <TrendChart trend={summary.trend} />
              <SubjectMeters subjects={summary.subjects} activeSubject={subjectFilter} />
            </div>

            <div className={`${CARD} flex min-w-0 flex-col gap-1 p-6`}>
              <h2 className="text-lg font-medium text-text-dark">Tutor helped with</h2>
              <p className="mb-4 text-sm text-text-muted">Every question you&apos;ve reviewed AI Tutor feedback for</p>

              {helpedError && <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-700">{helpedError}</p>}
              {!helpedError && helped.length === 0 && !helpedLoading && (
                <p className="text-sm text-text-muted">
                  Nothing here yet — review the AI Tutor feedback on a question on your next practice test, and
                  it&apos;ll show up here for you to revisit.
                </p>
              )}

              <div className="flex flex-col">
                {helped.map((h) => (
                  <TutorHelpedRow
                    key={h.questionId}
                    item={h}
                    expanded={expandedId === h.questionId}
                    onToggle={() => setExpandedId((cur) => (cur === h.questionId ? null : h.questionId))}
                  />
                ))}
              </div>

              {helped.length < helpedTotal && (
                <button
                  onClick={() => loadTutorHistory(helped.length, true)}
                  disabled={helpedLoading}
                  className="mt-3 self-start text-sm font-medium text-coral-dark hover:underline disabled:opacity-50"
                >
                  {helpedLoading ? "Loading…" : `Load more (${helpedTotal - helped.length} left)`}
                </button>
              )}
            </div>
          </div>

          <TutorActivity followThroughPct={followThroughPct} mistakesTotal={summary.mistakesTotal} mistakesUnreviewed={summary.mistakesUnreviewed} topics={summary.topTopics} />
        </div>
      </main>
    </>
  );
}

// The one place a session can be ended, and the only place the student's
// name is shown — Nav itself is deliberately static/session-unaware.
function AccountBar({ name, onLogout }: { name: string; onLogout: () => void }) {
  return (
    <div className={`${CARD} flex shrink-0 items-center gap-3 px-4 py-2 text-sm`}>
      <span className="text-text-muted">
        Signed in as <span className="font-medium text-text-dark">{name}</span>
      </span>
      <button type="button" onClick={onLogout} className="font-medium text-coral-dark hover:underline">
        Log out
      </button>
    </div>
  );
}

function KpiTile({
  label,
  value,
  caption,
  attention,
}: {
  label: string;
  value: string;
  caption?: string;
  attention?: boolean;
}) {
  return (
    <div className={`${CARD} relative overflow-hidden p-5`}>
      {attention && <span className="absolute inset-y-0 left-0 w-1 bg-red-500" aria-hidden="true" />}
      <p className="text-sm text-text-muted">{label}</p>
      <p className="mt-1 text-3xl font-medium text-text-dark">{value}</p>
      {caption && (
        <p className={`mt-1 flex items-center gap-1 text-sm ${attention ? "text-red-700" : "text-text-muted"}`}>
          {attention && <AlertCircle size={13} strokeWidth={2} />}
          {caption}
        </p>
      )}
    </div>
  );
}

function TrendChart({ trend }: { trend: TrendPoint[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const width = 760;
  const height = 240;
  const padLeft = 44;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 40;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;
  const baseline = padTop + plotH;

  const n = trend.length;
  const points = trend.map((t, i) => {
    const scorePct = t.total > 0 ? (t.score / t.total) * 100 : 0;
    const x = n <= 1 ? padLeft + plotW / 2 : padLeft + (i / (n - 1)) * plotW;
    const y = padTop + ((100 - scorePct) / 100) * plotH;
    return { x, y, pct: Math.round(scorePct), t };
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const areaPath =
    points.length > 0
      ? `${linePath} L${points[points.length - 1].x.toFixed(1)},${baseline} L${points[0].x.toFixed(1)},${baseline} Z`
      : "";

  const labelIndices = new Set(pickLabelIndices(n));
  const last = points[points.length - 1];

  function handlePointerMove(e: React.PointerEvent<SVGRectElement>) {
    const svg = svgRef.current;
    if (!svg || points.length === 0) return;
    const rect = svg.getBoundingClientRect();
    const relX = ((e.clientX - rect.left) / rect.width) * width;
    let best = 0;
    let bestDist = Infinity;
    points.forEach((p, i) => {
      const d = Math.abs(p.x - relX);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    });
    setHoverIndex(best);
  }

  const hovered = hoverIndex !== null ? points[hoverIndex] : null;

  return (
    <div className={`${CARD} p-6`}>
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium text-text-dark">Score across your recent attempts</h2>
          <p className="text-sm text-text-muted">Hover a point for details</p>
        </div>
        {last && <span className="text-2xl font-medium text-text-dark">{last.pct}%</span>}
      </div>

      <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} className="block w-full overflow-visible">
          {[0, 25, 50, 75, 100].map((v) => {
            const y = padTop + ((100 - v) / 100) * plotH;
            return (
              <g key={v}>
                <line x1={padLeft} y1={y} x2={width - padRight} y2={y} stroke="#e7e5e4" strokeWidth={1} />
                <text x={padLeft - 8} y={y + 3} textAnchor="end" fontSize={9.5} fill="#78716c">
                  {v}
                </text>
              </g>
            );
          })}

          {points.map((p, i) =>
            labelIndices.has(i) ? (
              <text key={i} x={p.x} y={height - padBottom + 18} textAnchor="middle" fontSize={9.5} fill="#78716c">
                {formatDate(p.t.createdAt)}
              </text>
            ) : null,
          )}

          {areaPath && <path d={areaPath} fill="#e06a5c" opacity={0.1} />}
          {linePath && <path d={linePath} fill="none" stroke="#e06a5c" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />}

          {last && <circle cx={last.x} cy={last.y} r={4.5} fill="#e06a5c" stroke="#fdfcf8" strokeWidth={2} />}

          {hovered && (
            <>
              <line x1={hovered.x} y1={padTop} x2={hovered.x} y2={baseline} stroke="#e7e5e4" strokeWidth={1} />
              <circle cx={hovered.x} cy={hovered.y} r={5} fill="#e06a5c" stroke="#fff" strokeWidth={2} />
            </>
          )}

          <rect
            x={padLeft}
            y={0}
            width={plotW}
            height={height}
            fill="transparent"
            onPointerMove={handlePointerMove}
            onPointerLeave={() => setHoverIndex(null)}
          />
        </svg>

        {hovered && (
          <div
            className="pointer-events-none absolute rounded-xl bg-text-dark px-3 py-2 text-xs text-white shadow-soft"
            style={{
              left: `${(hovered.x / width) * 100}%`,
              top: `${(hovered.y / height) * 100}%`,
              transform: "translate(-50%, -115%)",
            }}
          >
            <div className="font-semibold">{hovered.pct}%</div>
            <div className="text-white/70">
              {hovered.t.subject} · {hovered.t.year} · {formatDate(hovered.t.createdAt)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SubjectMeters({ subjects, activeSubject }: { subjects: SubjectAccuracy[]; activeSubject: string | null }) {
  return (
    <div className={`${CARD} p-6`}>
      <h2 className="mb-4 text-lg font-medium text-text-dark">Accuracy by subject</h2>
      <div className="flex flex-col gap-4">
        {subjects.map((s) => {
          const dimmed = activeSubject !== null && activeSubject !== s.subject;
          const value = pct(s.correct, s.total);
          return (
            <div key={s.subject} className={`flex flex-col gap-1.5 transition-opacity ${dimmed ? "opacity-35" : ""}`}>
              <div className="flex items-baseline justify-between">
                <span className="font-medium text-text-dark">{s.subject}</span>
                <span className="font-medium text-text-dark">{value}%</span>
              </div>
              <div className="h-4 overflow-hidden rounded-full bg-coral/15">
                <div className="h-full rounded-full bg-coral-dark" style={{ width: `${value}%` }} />
              </div>
              <span className="text-xs text-text-muted">
                {s.correct} of {s.total} correct
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TutorHelpedRow({
  item,
  expanded,
  onToggle,
}: {
  item: TutorHelpedQuestion;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-stone-100 last:border-none">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 py-3 text-left transition-colors hover:bg-lavender/60"
      >
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-sage px-2 py-0.5 text-xs font-medium text-text-dark">
              {item.subject} · {item.year}
            </span>
            <span className="text-xs text-text-muted">{formatDate(item.lastDiscussedAt)}</span>
          </div>
          <p className={expanded ? "text-sm text-text-dark" : "truncate text-sm text-text-dark"}>
            Q{item.questionNumber} — {item.questionText}
          </p>
        </div>
        <ChevronDown
          size={16}
          strokeWidth={2}
          className={`shrink-0 text-text-muted transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <div className="pb-4">
          <TutorHistoryView messages={item.messages} />
        </div>
      )}
    </div>
  );
}

function TutorActivity({
  followThroughPct,
  mistakesTotal,
  mistakesUnreviewed,
  topics,
}: {
  followThroughPct: number;
  mistakesTotal: number;
  mistakesUnreviewed: number;
  topics: TopicCount[];
}) {
  const reviewedCount = mistakesTotal - mistakesUnreviewed;
  const maxCount = topics[0]?.count ?? 1;

  return (
    <div className={`${CARD} grid gap-8 p-6 sm:grid-cols-[1fr_1.3fr]`}>
      <div className="flex flex-col gap-3">
        <p className="flex items-center gap-1.5 text-sm text-text-muted">
          <MessagesSquare size={15} strokeWidth={2} /> Follow-through rate
        </p>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-medium text-text-dark">{followThroughPct}%</span>
          <span className="text-sm text-text-muted">
            {reviewedCount} of {mistakesTotal} wrong answers reviewed with the tutor
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-sage">
          <div className="h-full rounded-full bg-coral-dark" style={{ width: `${followThroughPct}%` }} />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <p className="flex items-center gap-1.5 text-sm text-text-muted">
          <Target size={15} strokeWidth={2} /> Most-discussed topics
        </p>
        {topics.length === 0 ? (
          <p className="text-sm text-text-muted">Review some AI Tutor feedback and topics will show up here.</p>
        ) : (
          <div className="flex flex-col gap-2.5">
            {topics.map((t) => (
              <div key={t.topic} className="grid grid-cols-[1fr_auto] items-center gap-3 text-sm">
                <span className="text-text-dark">{t.topic}</span>
                <span className="text-text-muted">{t.count}</span>
                <div className="col-span-2 h-2 overflow-hidden rounded-full bg-stone-100">
                  <div className="h-full rounded-full bg-coral-dark" style={{ width: `${(t.count / maxCount) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
