# Current UI

What the ScoreWise demo frontend (`web/app/page.tsx`, a single-file Next.js App Router page) looks like today, scene by scene, precise enough to sketch without opening a browser. It's one page component with three mutually-exclusive screens (`"start" | "test" | "result"`) swapped via `if` returns — never all mounted at once.

Styling is Tailwind CSS with **no custom theme** — `tailwind.config.ts` only maps `background`/`foreground` to two CSS variables (used solely by `body`, not by any component below); every color named here (`blue-600`, `gray-200`, etc.) is Tailwind's stock default palette, unmodified.

## Global shell

- **Font**: despite two Geist font files being loaded as CSS variables in `layout.tsx`, `globals.css` hard-sets `body { font-family: Arial, Helvetica, sans-serif; }` and nothing in `page.tsx` opts into the Geist variables — so the entire app actually renders in **Arial/Helvetica**, not Geist. The loaded Geist fonts are effectively dead weight today.
- **Page background / text color**: set once, on `body`, via CSS custom properties — **not** Tailwind utilities, and **not** touched by any of the three screens:
  - Light (default / `prefers-color-scheme: light`): background `#ffffff` (white), text `#171717` (near-black).
  - Dark (`prefers-color-scheme: dark`): background `#0a0a0a` (near-black), text `#ededed` (near-white).
  - This is the **only** dark-mode-aware styling in the app. Every card, border, and text color inside the three screens below is a fixed light-mode Tailwind color with no `dark:` variant — so in a dark-mode browser, the page background goes black while every card/border/label keeps its light-mode colors (white cards, gray-200 borders, gray-500/700 text). That mismatch is a known, unaddressed quirk, not an intentional dark theme.
- **Page container**: every screen is a `<main>` that's a vertical flexbox (`flex flex-col gap-6`) at minimum, `min-h-screen` tall. The Test and Result screens additionally center themselves as a `max-w-2xl` (42rem / 672px) column with `mx-auto` and `px-6 py-16` padding — so on wide viewports there's a single centered reading column with wide empty margins left/right; the Start screen has no such column, it just centers its one button both axes.
- **Cards** (question card, result-item card, tutor panel) all share the same visual language: white background (implicit — no bg class means it shows the page background, so white in light mode), `rounded-lg` (0.5rem) corners, a 1px `border-gray-200` (#e5e7eb) hairline border, and `p-6` (1.5rem) padding (tutor panel uses `p-4`).
- **Buttons** are consistently `rounded-md` (0.375rem), medium-weight text, with a `disabled:opacity-40` dimmed state — no other disabled treatment (cursor doesn't change, no `disabled:cursor-not-allowed` class is set).
- **Emoji are used in place of icons** throughout — no icon library. ⏱ for the timer, ✅/❌ for grading, 🤖 for the tutor entry point, 📖 for citations.

---

## Scene 1 — Start screen

The entire screen is empty except one button, centered.

- `<main>`: `flex min-h-screen flex-col items-center justify-center gap-4` — full viewport height, content centered both vertically and horizontally, no header, no title, no logo, no page chrome of any kind. Background is plain white (light) / near-black (dark), per the global body rule above.
- **"Start Test" button**: solid `bg-blue-600` (#2563eb) rounded rectangle, white text, noticeably larger than any other button in the app — `px-8 py-4` (2rem × 1rem) padding, `text-lg font-semibold`. Label reads **"Start Test"**; while the initial questions fetch is in flight it swaps to **"Loading…"** and the button dims to 40% opacity and becomes unclickable (native `disabled`).
- **Error state**: if the questions fetch fails, a rose/red banner appears below the button — `bg-red-50` (#fef2f2) background, `text-red-700` (#b91c1c) text, `rounded-md px-4 py-3`, holding the raw error message. No retry button; the student just clicks "Start Test" again.

That's the whole screen — no question preview, no instructions, no branding.

---

## Scene 2 — Test screen (one question per "window")

Two question windows exist (`TEST_QUESTION_COUNT = 2`), shown one at a time; a single continuous 60-second countdown runs underneath both.

### Layout, top to bottom
1. **Header row** (`flex items-center justify-between`, sits above the card, no border of its own):
   - Left: small gray progress label, `text-sm text-gray-500` (#6b7280) — *"Question 1 of 2"* / *"Question 2 of 2"*.
   - Right: the **timer pill** — `rounded-md px-3 py-1`, monospace font (`font-mono`), small text. Reads **⏱ 00:60** counting down to **⏱ 00:00** (format is literally `00:` + two-digit seconds, so it visibly shows `00:60` at the very start rather than rolling over to a minutes digit). Two color states:
     - Normal (>10s left): `bg-gray-100` (#f3f4f6) pill, `text-gray-700` (#374151) text.
     - Urgent (≤10s left): `bg-red-50` (#fef2f2) pill, `text-red-700` (#b91c1c) text — the only visual urgency cue; there's no animation/pulsing, just a hard color swap at the 10-second mark.
2. **Question card** (white, bordered, rounded, `p-6`, contents stacked with `gap-6`):
   - **Meta line**: `text-sm text-gray-500` — *"{subject} · {year} · Question {number}"* (e.g. "Information & Communication Technology · 2022 · Question 4"), centered-dot separated.
   - **Question text**: `mt-2 text-lg`, `whitespace-pre-wrap` so any line breaks in the source text are preserved.
   - **Options list** (`flex flex-col gap-3`, wrapped in a `<fieldset>`): each option is a full-width clickable `<label>` row — `flex items-start gap-3`, `rounded-md border px-4 py-3` — containing a radio input (`mt-1`, aligned to the top of the text so multi-line option text doesn't misalign the dot) and the option text as `**(Label)** option text` (e.g. "**(A)** Newton"). Two visual states per row:
     - Unselected: `border-gray-200`, no fill.
     - Selected: `border-blue-500` (#3b82f6) + `bg-blue-50` (#eff6ff) tint — the entire row highlights, not just the radio dot.
   - **Navigation/submit block** (`flex flex-col gap-3`, sits below the options):
     - A button row (`flex gap-3`):
       - **"Previous"** — only rendered at all on window 2 (absent entirely on window 1, not just disabled). Outlined style: `border-gray-300` border, `text-gray-700` text, no fill.
       - **"Next"** — always present. Solid `bg-blue-600` white-text button. Enabled on window 1 (advances to window 2); on window 2 it's rendered `disabled` (40% opacity, inert) since there's no third question.
     - **"Submit"** — directly under that button row (its own line, `self-start` so it doesn't stretch), solid `bg-green-600` (#16a34a) white-text button, present and clickable on *every* window regardless of answered/unanswered state. Label swaps to **"Submitting…"** and dims while the request is in flight.
   - **Error banner**: if submit fails, the same red-50/red-700 banner style as the Start screen appears at the bottom of the card.

### Behavior notes relevant to layout
- Switching windows via Previous/Next does **not** reset or pause the timer — the countdown pill keeps ticking continuously across both windows.
- Reaching `00:00` auto-triggers Submit (whatever's marked, unmarked questions submitted as blank) and the screen transitions straight to the Result screen — there's no "time's up" interstitial or modal.

---

## Scene 3 — Result screen

A vertical stack of everything: a heading, a score line, one card per question (each optionally containing a full tutor sub-panel), and a restart button.

### Layout, top to bottom
1. **"Results"** — plain `text-2xl font-semibold` heading, no card/border around it.
2. **Score line** — `text-gray-600`, e.g. *"Score: 1 / 2"*.
3. **Per-question result cards** (`flex flex-col gap-6` stack; each card same white/bordered/rounded/`p-6` style as the question card, contents `gap-4`):
   - Same meta line + question text treatment as the Test screen.
   - **Options list**, but now read-only review rows instead of radio buttons (`flex flex-col gap-2`, each row `rounded-md border px-4 py-3 text-sm`). Every option row is always shown (not just the picked one), with three possible states:
     - The **correct option**: `border-green-500` + `bg-green-50` (#f0fdf4), with an inline right-aligned tag **"✅ Correct answer"** in `text-green-700` (#15803d), bold.
     - The student's **wrong pick** (only rendered when they got it wrong and this row is the one they chose): `border-red-500` + `bg-red-50`, with inline tag **"❌ Your answer"** in `text-red-700`, bold.
     - Everything else: plain `border-gray-200`, no tag.
     - If the student answered correctly, only the green highlight appears (no red row at all, since their pick *is* the correct one).
     - If they left the question blank, no row is red-highlighted and a standalone note appears below the options list: `text-sm text-gray-500` — *"You left this question blank."*
   - **"🤖 Ask AI Tutor" button** — appears **only on cards for questions the student got wrong** (correct answers show no tutor entry point at all). Outlined style: `border-blue-600` border, `text-blue-600` text, no fill, same padding as other secondary buttons. Clicking it replaces itself with the Tutor Panel (see Scene 4) for that specific question; each wrong question has its own independent panel/thread, so two can be open on screen at once with no shared state.
4. **"Take Another Test"** — solid `bg-blue-600` white-text button at the very bottom of the page (outside/after the question-cards stack), same style as "Start Test" but smaller (`px-5 py-2`, no `text-lg`). Clicking it re-fetches a fresh 2-question set and returns to the Test screen, resetting the timer and clearing all tutor threads' open/loaded state in local UI (the backend's tutor history persists regardless — see below).

---

## Scene 4 — AI Tutor panel (nested inside a wrong-answer result card)

Replaces the "Ask AI Tutor" button in place once opened. Same card-ish treatment as its parent but one level in: `rounded-lg border border-gray-200 p-4`, `flex flex-col gap-3`.

1. **Label**: small caption **"AI Tutor"** — `text-sm font-medium text-gray-500`.
2. **Message thread** (`flex flex-col gap-2`, capped at `max-h-96` i.e. 24rem with `overflow-y-auto` — scrolls internally once it grows past that, rather than pushing the page taller):
   - Each turn is its own row, right-aligned if it's the student ("user") or left-aligned if it's the tutor ("assistant") — `items-end` vs `items-start` on a per-message flex column.
   - **Student bubble**: `bg-blue-50`, `text-blue-900` (#1e3a8a), `rounded-md px-3 py-2 text-sm`, right-aligned.
   - **Tutor bubble**: `bg-gray-100`, `text-gray-800` (#1f2937), same shape, left-aligned. Text is `whitespace-pre-wrap` so the model's own markdown-ish line breaks/paragraphs survive as plain line breaks (no markdown rendering — bold/lists from the model would show as literal `**text**`/`- item` characters, not formatted).
   - **Citation boxes** (see below) render directly above a tutor bubble, as part of the same message row, when that reply had any.
   - While a request is in flight, a standalone line **"Thinking…"** in `text-sm text-gray-400` appears at the bottom of the thread (not a spinner/animation).
3. **Error banner**: same red-50/red-700 style as elsewhere, shown between the thread and the input form if a tutor call fails.
4. **Composer row** (`flex gap-2`, a `<form>`):
   - Text input: `flex-1`, `border-gray-200`, `rounded-md px-3 py-2 text-sm`, placeholder *"Ask a follow-up…"*, disabled while a request is in flight.
   - **"Send"** button: small solid `bg-blue-600` white-text button (`px-4 py-2 text-sm`), disabled while sending or while the input is empty/whitespace-only.

### Citation boxes (nested inside a tutor bubble's message row)

Rendered as a stack (`flex flex-col gap-1`) of native `<details>`/`<summary>` elements, **above** the tutor's text bubble, one per syllabus chunk that grounded that specific reply:

- Each is its own small white box: `rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs`.
- **Collapsed by default** — the visible `<summary>` line is `text-gray-600 font-medium`: **"📖 Citation {n}: {filename}"**, with `· {topic}` appended if the syllabus document had one (e.g. "📖 Citation 1: TeachersGuide12.pdf · 12").
- **Expanded** (native browser `<details>` toggle, click-to-open, no custom animation): reveals the raw retrieved snippet text below the summary line, `text-gray-500`, `whitespace-pre-wrap`, `mt-1`.
- If a reply had zero citations (e.g. syllabus retrieval found nothing, or degraded due to a Chroma outage), no citation boxes render at all — the tutor bubble appears alone.

---

## Summary color reference

| Purpose | Class | Hex |
|---|---|---|
| Page background (light) | body `--background` | `#ffffff` |
| Page background (dark) | body `--background` | `#0a0a0a` |
| Page text (light) | body `--foreground` | `#171717` |
| Page text (dark) | body `--foreground` | `#ededed` |
| Card border | `border-gray-200` | `#e5e7eb` |
| Secondary/meta text | `text-gray-500` | `#6b7280` |
| Body text on tutor reply bubble | `text-gray-800` | `#1f2937` |
| Primary action (Start/Next/Send/Take Another Test) | `bg-blue-600` | `#2563eb` |
| Selected option fill | `bg-blue-50` / `border-blue-500` | `#eff6ff` / `#3b82f6` |
| Student chat bubble | `bg-blue-50` / `text-blue-900` | `#eff6ff` / `#1e3a8a` |
| Submit action | `bg-green-600` | `#16a34a` |
| Correct-answer highlight | `bg-green-50` / `border-green-500` / `text-green-700` | `#f0fdf4` / `#22c55e` / `#15803d` |
| Wrong-answer / error highlight | `bg-red-50` / `border-red-500` / `text-red-700` | `#fef2f2` / `#ef4444` / `#b91c1c` |
| Timer pill (normal) | `bg-gray-100` / `text-gray-700` | `#f3f4f6` / `#374151` |
| Timer pill (≤10s) | `bg-red-50` / `text-red-700` | `#fef2f2` / `#b91c1c` |
