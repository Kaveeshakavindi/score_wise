# ScoreWise — 20-Minute Video Presentation Script

**Presenter:** Kaveesha
**Total runtime:** ~20 minutes
**Format:** Slide-by-slide breakdown with verbatim speaker script and, for the demo section, click-by-click demo cues.

---

## 1. Introduction (~1.5 min)

### Slide: ScoreWise — AI-Assisted GCE A/L Past-Paper Practice Tool
- Presenter: Kaveesha
- ScoreWise: a web app for GCE Advanced Level exam practice
- Students practice real past papers under timed, scored conditions
- Every wrong answer unlocks an AI tutor grounded in the actual syllabus
- Today: the problem, the AI-assisted build process, a full live demo, and what's next

### Speaker script
Hi, I'm Kaveesha, and this is ScoreWise. ScoreWise is a web app built for GCE Advanced Level students in Sri Lanka — students in the final stretch of secondary school, preparing for the national A/L exam. It lets them practice real past exam papers under timed, scored conditions, the same way they'd sit the actual exam. But the part of this project I'm most excited to show you is what happens the moment a student gets a question wrong. Instead of just seeing a red X next to their answer, they can open a chat with an AI tutor about that exact question, and the tutor explains the correct answer using the actual syllabus content for that subject — not generic knowledge pulled from the open web. Over the next twenty minutes, I'll walk through the problem ScoreWise is trying to solve, how I used AI tools throughout the development process — both as a coding assistant and as a runtime part of the product itself — a full live demo of the running app, and where I want to take this next. Let's get into it.

---

## 2. Problem and Solution (~3–3.5 min)

### Slide: The Problem — An Unguided Practice Loop
- A/L students rely on past papers as their main revision method, but practice today is entirely unguided
- A four-part root-cause analysis points to the real drivers: time-constrained teachers, ungrounded tools, infrastructure/cost barriers, and passive grading methodology
- Problem statement: no centralized, free platform combines past-paper practice with grounded, syllabus-aligned AI explanations and personalised feedback
- The moment right after a mistake — when a student is most motivated to understand it — is exactly when nothing is available to help

### Speaker script
Let's start with the problem, and the thinking behind it, not just an assertion. GCE A/L is Sri Lanka's high-stakes pre-university exam, and past papers are how most students revise for it. When I mapped out why that practice stays so unguided, a root-cause analysis across four areas showed a consistent pattern. On the stakeholder side, teachers don't have time to review individual students' wrong answers, so preparation defaults to rote memorization. On the tools side, what's available is either static printed answer keys or generic AI chatbots that aren't grounded in the syllabus or the specific question. Infrastructure adds its own barriers — geographic concentration of good tutors, connectivity constraints, and cost. And the methodology itself is passive: grading is a binary correct-or-incorrect, with no active recall and no spaced repetition. Put simply, current examination preparation resources don't provide a centralized, free platform that combines past-paper practice with grounded, syllabus-aligned AI explanations and personalised feedback — and that gap limits how well students can actually understand their mistakes and close their own learning gaps.

---

### Slide: Existing Options Force a Compromise
- Physical past-paper books: cheap and familiar, but no feedback loop, no explanation
- Local tuition: deep subject expertise, but not personalised and schedule-bound
- Ranker.lk: broad curriculum coverage with progress tracking, but paywalled at 990 LKR/month
- BrainUs AI, ALevellers, general-purpose chatbots: can explain concepts on request, but aren't grounded in the specific paper or marking scheme, and offer no real exam-style scoring
- Nothing free on the market combines an actual timed exam simulation with grounded, per-question AI tutoring

### Speaker script
This isn't an unaddressed space, so I looked at what's already out there before building anything. Physical past-paper books are cheap and familiar, but they give zero feedback beyond a printed answer key. Local tuition gives real subject expertise, but it's not personalised and it's bound to a fixed schedule. A platform like Ranker.lk offers broader curriculum coverage and progress tracking, but sits behind a monthly paywall. And tools like BrainUs AI, ALevellers, or general-purpose chatbots can explain a concept if you ask, but they're not grounded in the specific paper or marking scheme a student is actually working from, and they don't offer real exam-style scoring. So existing options force students into a compromise between structure, personalisation, and cost — nothing free on the market combines an actual timed exam simulation with grounded, per-question AI tutoring.

---

### Slide: The Solution — ScoreWise
- Timed, scored practice attempts on real past-paper questions, marked server-side against the official answer key
- Handles real exam edge cases, like officially voided questions where every answer is accepted
- A question-scoped AI tutor chat for any wrong answer — grounded via retrieval-augmented generation over the actual syllabus, not general web knowledge
- Explains the correct answer, addresses the student's specific wrong choice, and cites the syllabus material it used
- A personal dashboard tracking accuracy trends, per-subject performance, and commonly-missed topics over time
- Free and browser-based — closing the exact gap the market research turned up

### Speaker script
So that's the gap ScoreWise fills. Students take real past-paper questions as a timed, scored attempt, marked entirely server-side against the official answer key — including edge cases like officially voided questions, where every submitted answer is accepted as correct. Then, for any question they got wrong, they can open an AI tutor chat scoped to that one question, grounded through retrieval-augmented generation over the actual syllabus content for that subject rather than general web knowledge — so it explains the correct answer, addresses the specific wrong choice the student made, and cites exactly which syllabus material it used. A personal dashboard then tracks accuracy trends, per-subject performance, and commonly-missed topics over time, so practice compounds into visible progress instead of disappearing after each attempt. And it does all of this as a free, browser-based tool — which matters at scale too: AI in education is already a 10.6 billion dollar global market, and locally, platforms like DP Education, with over a million active students, show there's real demand in Sri Lanka for exactly this kind of tool.

---

## 3. AI-Assisted Development (~3 min)

### Slide: Building ScoreWise With AI — End to End
- Built solo, using Claude Code as an agentic coding assistant across the whole stack
- FastAPI backend (routers/services/repositories), SQLAlchemy models, Alembic migrations, the RAG pipeline, the Next.js frontend, and the test suite — 183 tests across 28 files
- Design and requirements docs written spec-first with AI assistance, so implementation had a written source of truth to check against
- AI isn't just a dev tool here — Claude also runs at runtime, inside the product: the tutor, and a two-tier PDF extraction pipeline
- Every AI-authored change reviewed against those spec docs, backed by the automated test suite as a correctness gate
- Tutor prompts deliberately constrained and manually checked; cost-tracking code independently verified with its own unit tests

### Speaker script
This project was built solo, and AI was involved at almost every stage — so I want to be specific about how, rather than just saying "I used AI." For the actual coding, I used Claude Code, Anthropic's CLI-based coding agent, throughout the build: scaffolding the FastAPI backend's layered architecture of routers, services, and repositories; writing and iterating on the SQLAlchemy models and Alembic migrations; implementing the RAG pipeline — the embedding step, the ChromaDB retrieval, and the prompt assembly; building the Next.js frontend; and writing the automated test suite, which ended up at 183 test functions across 28 test files. Beyond code, I also used AI to help generate and refine design and requirements documentation — a software requirements spec listing every dependency, its version, and why it's there, and a precise screen-by-screen UI specification — so the build stayed spec-driven instead of ad hoc, with a written source of truth I could check implementation against.

It's also worth calling out that AI isn't just something I used to build this — it's a runtime part of the product itself. ScoreWise calls Claude, via Anthropic's API, for two live features: the syllabus-grounded question tutor, and a two-tier PDF extraction pipeline that falls back to Claude's vision capability for scanned syllabus documents.

Given how much of this was AI-generated, review discipline mattered a lot, so let me be concrete about what that actually looked like. Every AI-authored change was checked against the written architecture and spec docs before I accepted it, rather than merged blindly. The 183-test suite acted as a concrete correctness gate on AI-generated backend code — services, repositories, and routers all have corresponding test files. The tutor's system prompt — which is itself AI-generated — was deliberately constrained: it's instructed to answer only from the supplied syllabus excerpts, never contradict the stored correct answer, cite sources as [1] and [2], and decline off-topic questions, and I tested a fallback path for when retrieval itself fails. And because this code makes paid LLM calls, I didn't just trust estimated costs — I added a token-usage ledger and a per-model pricing table and unit-tested those independently. On top of all that, I did manual end-to-end testing of the running app, backend and frontend together, to catch integration issues that AI-written unit tests wouldn't surface on their own.

---

## 4. Project Demonstration (~10 min)

### Slide: Live Demo — What We'll Walk Through
- Auth: register/login, JWT access + refresh tokens, password reset
- Papers list and the timed exam-taking flow
- Server-side scoring, including the voided-question edge case
- Results screen with per-question review
- The AI tutor — syllabus-cited answers, with a follow-up question
- The personal dashboard — accuracy trends and commonly-missed topics
- A quick look at the admin side that feeds all of this

### Speaker script
Okay, let's switch over and I'll walk you through the actual running app.

### Demo cues
Switch to screen share. Have the app already running locally or deployed, with a test student account and an admin account ready so you don't waste demo time on setup.

---

### Slide: Auth
- Register / login
- JWT access token + refresh token
- Password reset flow
- bcrypt password hashing under the hood

### Speaker script
First, authentication. I'll register a new student account and log in. Behind the scenes this issues a short-lived JWT access token plus a refresh token, so the session stays valid without forcing the user to re-enter their password constantly. Passwords are hashed with bcrypt before they're ever stored. There's also a password reset flow for when a student forgets their password, which I'll show quickly.

### Demo cues
Register a new account on screen → show the login → briefly open the password reset flow and show it exists, without necessarily completing a full email round-trip if that's slow to demo live.

---

### Slide: Papers List and the Exam Flow
- Browse available past papers, filterable by subject
- Open a paper and see its questions — without the answers
- Submit all answers as a single timed attempt

### Speaker script
Once logged in, the student lands on the papers list, which they can filter by subject. I'll open one paper. Notice the questions are shown without any answers — the correct answers never reach the client at this stage. I'll go through and answer a few questions, including deliberately getting a couple wrong so I have something to show the tutor on in a minute, and then submit the whole thing as a single timed attempt.

### Demo cues
Filter papers by subject → open a paper → click through several questions, answering some correctly and some incorrectly on purpose → submit the attempt.

---

### Slide: Scoring
- Scoring happens entirely server-side against the stored answer key
- The client never has access to correct answers before submission
- Edge case: officially voided questions — every answer is accepted as correct

### Speaker script
When I hit submit, scoring happens entirely on the server, against the answer key stored in the database — the client never had access to the correct answers before this point, so there's no way to game it from the browser. There's also a real exam edge case handled here: sometimes a question is officially voided by the examination body, and in that case every answer a student gave is accepted as correct, rather than marked wrong against an answer that was later invalidated.

### Demo cues
Show the submission completing and transitioning to the results screen.

---

### Slide: Results Screen
- Per-question review
- Correct answer vs. the student's own answer, clearly marked

### Speaker script
Here's the results screen. For every question, it shows the correct answer next to what the student actually chose, clearly marked, so it's immediately obvious where they went right and where they went wrong.

### Demo cues
Scroll through the results list, pointing out at least one correct and one incorrect question.

---

### Slide: The AI Tutor
- Opens scoped to one specific wrong question
- Grounded via RAG over the actual uploaded syllabus for that subject
- Answers cite sources as [1], [2] — expandable to the excerpt and source document
- Chat continues in context for natural follow-up questions

### Speaker script
Now the part I've been building toward — the AI tutor. I'll click into one of the questions I got wrong. This opens a chat scoped to that exact question. I'll ask it to explain why my answer was wrong, and you'll see it responds using citations — these bracketed numbers — which expand to show the actual syllabus excerpt and which source document it came from. This isn't the model just recalling general knowledge; it's answering from the syllabus content I uploaded for this subject. And it's a real conversation, not a one-shot answer — I'll ask a natural follow-up question and you'll see it stays in context and keeps responding based on the same grounded material.

### Demo cues
Click into a wrong answer → open the tutor chat → let it respond → click a [1] or [2] citation to expand the source excerpt and document name → type and send a natural follow-up question → show the reply staying in context.

---

### Slide: Dashboard — Progress Over Time
- Accuracy trend across recent attempts
- Per-subject accuracy breakdown
- Commonly-missed topics

### Speaker script
Stepping back from a single attempt, here's the dashboard. It shows an accuracy trend across recent attempts, a breakdown of accuracy by subject, and a list of the topics the student most commonly gets wrong. The idea is that practice compounds into a picture of where someone's actually weak, instead of each attempt's insight disappearing the moment they close the tab.

### Demo cues
Show the accuracy trend chart → show the per-subject breakdown → show the commonly-missed-topics list.

---

### Slide: Admin Side (Brief)
- Upload a syllabus PDF → ingested, chunked, embedded, stored in ChromaDB
- Manage past papers, questions, and answer keys that feed the student-facing app

### Speaker script
Finally, a quick look at the admin side, since this is what feeds everything I've just shown. An admin uploads a syllabus PDF, which gets ingested, chunked, embedded, and stored in ChromaDB — that's what the tutor retrieves from. The admin app is also where past papers, individual questions, and their answer keys are entered and managed.

### Demo cues
Switch to the admin app → upload a syllabus PDF and show the ingestion happening → briefly show the paper/question/answer-key management screens.

---

### Slide: Under the Hood — Architecture
- FastAPI backend, layered: routers → services → repositories
- PostgreSQL via async SQLAlchemy + asyncpg; ChromaDB for syllabus embeddings; Redis for rate limiting
- Next.js frontend (App Router, TypeScript, Tailwind) with its own API routes
- A separate Vite + React admin app for content management

### Speaker script
Let me explain briefly what's running underneath all of that. The backend is FastAPI, in Python, structured in layers — routers, then services, then repositories — talking to PostgreSQL through async SQLAlchemy and asyncpg. There's a separate ChromaDB vector store just for syllabus embeddings, and Redis handles rate limiting. The student-facing frontend is Next.js, using the App Router, TypeScript, and Tailwind, calling the backend through its own API routes. The admin tool for content management is a small, separate app built with Vite and React.

### Demo cues
No new screen needed — narrate over the results/dashboard screen, or show a simple architecture diagram slide if one is prepared.

---

### Slide: The RAG Pipeline, Explained
- One LLM call per tutor turn — deliberately narrow, no open-ended tool-calling loop
- Question, options, correct answer, and student's answer fetched directly from Postgres by ID
- Question text + student message embedded locally (all-MiniLM-L6-v2) — no external embedding API cost
- Top-4 most relevant syllabus chunks retrieved from ChromaDB, filtered to that question's subject
- Chunks resolved back to a real source document for citation, assembled into one system prompt sent to Claude
- If ChromaDB retrieval fails, the tutor still responds using just the question/answer data

### Speaker script
Here's how the tutor actually works underneath. It's deliberately narrow and deterministic — one LLM call per turn, no open-ended agentic tool-calling loop. The question, its options, the correct answer, and the student's own answer are fetched directly from Postgres by ID, not searched for. The question text and the student's message are embedded using a local sentence-transformers model, all-MiniLM-L6-v2, which means embedding has no external API cost. That embedding is used to query ChromaDB for the top four most relevant syllabus chunks, filtered down to that question's subject, and each chunk is resolved back to its real source document so it can be cited properly. All of that gets assembled into a single system prompt sent to Claude, which is instructed to answer only from that material and to cite it. And there's a resilience path built in: if ChromaDB retrieval itself fails for any reason, the tutor turn still proceeds using just the question and answer data instead of failing the whole request.

### Demo cues
No new screen needed — this can be narrated as a short "under the hood" beat right after the tutor demo, optionally over a simple pipeline diagram slide.

---

### Slide: Cost Tracking, Testing, and Known Limitations
- Every LLM call logged to an append-only usage table with input/output token counts, keyed by user and feature
- Per-model $/token pricing table converts that into estimated USD cost; optional daily per-user token budget enforced before each call, surfaced via a usage API
- 183 automated tests (unit + integration) across 28 files, using fakes/in-memory doubles — plus manual end-to-end testing
- Honest limitations: incomplete dark-mode styling, single-shot RAG with no multi-step reasoning, local embedding model trades some retrieval quality for zero cost, admin-driven content ingestion, logging-only observability so far

### Speaker script
A couple more things worth being upfront about. Every LLM call the app makes — tutor replies, chat, title generation — is logged to an append-only usage table with input and output token counts, keyed by user and feature, and a per-model pricing table converts that into an estimated dollar cost. There's an optional daily per-user token budget that can hard-cap usage, checked before each LLM call, and a student can see their own usage — tokens used today and remaining — through a usage endpoint. Retrieval itself is capped at the top four syllabus chunks per turn, which keeps prompt size, and therefore cost, bounded on every tutor call. On testing: the backend has 183 automated test functions across 28 files, covering services, repositories, pricing, and token-budget logic as unit tests, plus integration tests against the API routers and the tutor's WebSocket endpoint, using fakes and in-memory doubles so the suite doesn't need a live database. I also tested edge cases deliberately — voided questions, blank answers, the retrieval-failure fallback, and hitting the token budget limit.

I also want to be honest about where this stands today, because no project this size is finished. The frontend's dark mode is incomplete — only the page background and text respond to it right now, cards and borders are still fixed to light mode, which is a cosmetic gap, not a functional one. The tutor is intentionally single-shot RAG, so it can't do multi-step research beyond the top four chunks for a given question. The local embedding model trades away some retrieval quality in exchange for zero marginal cost and no external dependency. Content ingestion — papers, syllabi, questions — is still admin-driven and manual rather than automated at scale. And right now, observability is structured JSON logging only; metrics and tracing are planned but not built yet.

### Demo cues
No new screen needed — this is a narrated wrap-up over the dashboard or a summary slide before moving to the roadmap.

---

## 5. Future Roadmap (~2.5 min)

### Slide: What's Next for ScoreWise
- Production observability: Prometheus metrics + OpenTelemetry tracing for the AI pipeline's latency, cost, and error rate
- Prompt caching for the tutor's system prompt to cut per-call cost further as traffic grows
- Expanding subject/paper coverage and streamlining admin ingestion beyond one-by-one manual upload
- Richer dashboard analytics — topic-level mastery over time, not just accuracy trend

### Slide: What's Still Needed Before Real-World Use
- Fix the dark-mode styling gap and do a general UI/UX polish pass for a non-technical student audience
- Production-grade observability so AI-pipeline issues surface proactively, not via user reports
- Load and cost testing at realistic concurrent-student volume, especially the LLM tutor calls and token-budget system
- A content-moderation and abuse-review pass on the tutor chat, beyond the rate limiting already in place
- Formal user testing with real A/L students, to validate the tutor's explanations are genuinely helpful — moving past the personal-experience-based validation I've relied on so far

### Speaker script
So, where does this go from here? On the technical side, I want to add Prometheus metrics and OpenTelemetry tracing so I can actually observe the AI pipeline's latency, cost, and error rate in production, rather than only having logs. I'd also like to add prompt caching for the tutor's system prompt — since syllabus excerpts repeat across students asking about the same question, that's a straightforward way to cut per-call cost further once there's enough traffic to justify it. Beyond that, I want to expand subject and paper coverage and streamline the admin ingestion process so onboarding new content doesn't stay a one-by-one manual upload forever, and build out richer dashboard analytics — topic-level mastery over time, not just the accuracy trend and top-missed-topics view it has today.

But before this is ready for real students to rely on, there's a shorter list of things that genuinely need to happen first. The dark-mode styling gap needs fixing, alongside a broader UI and UX polish pass aimed at a non-technical student audience. I need the production observability I just mentioned, so problems in the AI tutor pipeline get caught proactively instead of through user complaints. I need to load-and-cost-test the system at realistic concurrent-student volume — particularly the LLM tutor calls and the token-budget system — before opening this up beyond a small pilot group. I want a proper content-moderation and abuse-review pass on the tutor chat, beyond the rate limiting that's already there. And most importantly, I want formal user testing with actual A/L students, to validate that the tutor's explanations are genuinely helpful in practice — moving beyond the personal-experience-based validation the problem definition has rested on so far.

---

## Closing Line

Thank you for watching — that's ScoreWise. I'm happy to answer any questions.
