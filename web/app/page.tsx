"use client";

import Link from "next/link";
import { BookOpen, Bot, GraduationCap, ListChecks, MoveHorizontal, Target, TimerReset } from "lucide-react";
import { DecorativeBlobs } from "./_components/DecorativeBlobs";
import { Nav } from "./_components/Nav";
import { Reveal } from "./_components/Reveal";

const PRIMARY_PILL_LG =
  "rounded-full bg-coral px-8 py-4 text-lg font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02]";
const SECONDARY_PILL_LG =
  "rounded-full border border-stone-200 bg-white px-8 py-4 text-lg font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02]";
const CARD = "rounded-3xl border border-stone-100 bg-white p-6 shadow-soft";

const HOW_IT_WORKS = [
  { icon: ListChecks, title: "Start the timed test", body: "Jump into a short practice set of real past-paper multiple-choice questions." },
  { icon: MoveHorizontal, title: "Answer at your own pace", body: "Move between questions with Previous and Next — the clock keeps running the whole time, no pausing." },
  { icon: Target, title: "Review your results", body: "The moment you submit, every question is scored and marked correct or incorrect, side by side with the right answer." },
  { icon: Bot, title: "Ask the AI Tutor", body: "For anything you got wrong, open a tutor grounded in the syllabus — with expandable citations back to the source." },
];

const FEATURES = [
  { icon: TimerReset, title: "Real exam time pressure", body: "A single continuous countdown across the whole set, matching real GCE A/L timed conditions instead of an untimed quiz." },
  { icon: Target, title: "Instant, per-question review", body: "No waiting for a marking scheme — see exactly which questions you got right or wrong the moment you submit." },
  { icon: Bot, title: "AI Tutor, grounded in the syllabus", body: "Ask follow-up questions on anything you missed. Every answer cites the syllabus passages it's actually drawing from." },
  { icon: BookOpen, title: "Real past-paper questions", body: "Practice on actual GCE A/L past-paper questions, not invented ones — the same format you'll sit for on exam day." },
];

const WHY_IT_HELPS = [
  { title: "Practice under real pressure", body: "A ticking clock changes how you think. Training under it now means exam day won't be the first time you feel it." },
  { title: "Learn from mistakes immediately", body: "Feedback the moment you finish beats getting a marked script back days later, when the reasoning has gone cold." },
  { title: "Understand why, not just what", body: "The AI Tutor explains why the correct answer is correct — and why your answer wasn't — grounded in your actual syllabus." },
];

export default function MarketingPage() {
  return (
    <>
      <Nav />

      <main className="flex flex-col">
        <Hero />

        <Section id="how-it-works" eyebrow="How it works" title="From start to review, in four steps">
          <div className="grid gap-4 sm:grid-cols-2">
            {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
              <div key={title} className={`${CARD} flex flex-col gap-3`}>
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sage text-text-dark">
                    <Icon size={18} strokeWidth={2} />
                  </span>
                  <p className="text-sm font-medium text-text-muted">Step {i + 1}</p>
                </div>
                <h3 className="text-lg font-medium text-text-dark">{title}</h3>
                <p className="text-sm text-text-muted">{body}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section id="features" eyebrow="What you get" title="Everything a focused practice session needs">
          <div className="grid gap-4 sm:grid-cols-2">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <div key={title} className={`${CARD} flex flex-col gap-3`}>
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-lavender text-text-dark">
                  <Icon size={18} strokeWidth={2} />
                </span>
                <h3 className="text-lg font-medium text-text-dark">{title}</h3>
                <p className="text-sm text-text-muted">{body}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section id="why-it-helps" eyebrow="Why it helps" title="Built for how you actually improve">
          <div className="grid gap-6 sm:grid-cols-3">
            {WHY_IT_HELPS.map(({ title, body }) => (
              <div key={title} className="flex flex-col gap-2">
                <h3 className="text-base font-medium text-text-dark">{title}</h3>
                <p className="text-sm text-text-muted">{body}</p>
              </div>
            ))}
          </div>
        </Section>

        <ClosingCta />
      </main>

      <footer className="px-6 pb-10 pt-4 text-center text-sm text-text-muted">
        <p className="font-medium text-text-dark">ScoreWise</p>
        <p>Timed GCE A/L practice, with an AI tutor for every question you miss.</p>
      </footer>
    </>
  );
}

function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
      <DecorativeBlobs />
      <div className="relative z-10 flex max-w-2xl flex-col items-center gap-6 animate-reveal">
        <h1 className="text-5xl font-medium leading-[1.05] tracking-tight text-text-dark sm:text-6xl md:text-7xl lg:text-8xl">
          Practice <span className="font-accent text-coral-dark">smarter</span> for your GCE A/L
        </h1>
        <p className="max-w-[500px] text-lg text-text-muted">
          Practice for the real GCE A/L exam — multiple-choice questions, strictly timed. Once you finish, get
          instant AI tutoring on anything you got wrong.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link href="/exams" className={PRIMARY_PILL_LG}>
            Start Exam
          </Link>
          <a href="#how-it-works" className={SECONDARY_PILL_LG}>
            See how it works
          </a>
        </div>
      </div>
    </section>
  );
}

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mx-auto w-full max-w-4xl px-6 py-20">
      <Reveal className="flex flex-col gap-10">
        <div className="flex flex-col gap-2 text-center">
          <p className="text-sm font-medium tracking-wide text-coral-dark">{eyebrow}</p>
          <h2 className="text-3xl font-medium text-text-dark sm:text-4xl">{title}</h2>
        </div>
        {children}
      </Reveal>
    </section>
  );
}

function ClosingCta() {
  return (
    <section className="px-6 pb-24 pt-4">
      <Reveal className="relative mx-auto max-w-4xl overflow-hidden rounded-[2rem] border border-stone-100 bg-sage/40 px-6 py-16 text-center shadow-soft">
        <DecorativeBlobs />
        <div className="relative z-10 flex flex-col items-center gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-stone-800 text-bg-base">
            <GraduationCap size={22} strokeWidth={2} />
          </span>
          <h2 className="text-3xl font-medium text-text-dark sm:text-4xl">Ready to practice?</h2>
          <p className="max-w-md text-text-muted">
            Two minutes from now you could be looking at your first scored, AI-tutored practice round.
          </p>
          <Link href="/exams" className={`${PRIMARY_PILL_LG} mt-2`}>
            Start Exam
          </Link>
        </div>
      </Reveal>
    </section>
  );
}
