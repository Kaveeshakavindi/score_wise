import Link from "next/link";
import { Sparkles } from "lucide-react";

const PRIMARY_PILL_SM =
  "rounded-full bg-coral px-5 py-2 text-sm font-medium text-text-dark shadow-soft transition-transform duration-300 hover:scale-[1.02]";

// Shared floating pill nav (design.md's nav-bar spec: 70% white opacity, 20px
// backdrop blur, constrained width with side margins on mobile). Used on the
// marketing page itself and, once a student has actually finished a test, on
// the exam app's Result screen — so there's always a way back to the rest of
// the site without breaking the anchor links, which always point at "/"
// regardless of which route they're clicked from.
export function Nav() {
  return (
    <div className="fixed inset-x-4 top-4 z-40 mx-auto flex max-w-3xl items-center justify-between rounded-full border border-stone-100 bg-white/70 px-4 py-2.5 shadow-soft backdrop-blur-[20px]">
      <Link href="/" className="flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-coral text-text-dark">
          <Sparkles size={16} strokeWidth={2} />
        </span>
        <span className="font-medium text-text-dark">ScoreWise</span>
      </Link>

      <div className="flex items-center gap-4">
        <a href="/#how-it-works" className="hidden text-sm text-text-muted hover:text-text-dark sm:inline">
          How it works
        </a>
        <a href="/#why-it-helps" className="hidden text-sm text-text-muted hover:text-text-dark sm:inline">
          Why it helps
        </a>
        <Link href="/exam" className={PRIMARY_PILL_SM}>
          Start Exam
        </Link>
      </div>
    </div>
  );
}
