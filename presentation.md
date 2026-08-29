# Presentation Generation Prompt

Copy everything below the line into another LLM (e.g. Claude, ChatGPT) to generate a full 20-minute video presentation script/slide deck for this project.

---

You are an expert presentation coach and technical writer. Build me a complete **20-minute video presentation** (script + slide-by-slide breakdown + speaker notes + approximate timing per section) for a university/course project submission. Write it so I can read it almost verbatim on camera while screen-sharing a live demo. Use a confident, clear, non-salesy tone — this is an academic/technical project presentation, not a startup pitch.

Use ONLY the factual material given below — do not invent metrics, user counts, interview quotes, or test results that aren't stated here. Where I've given you raw facts, turn them into natural spoken narration. Where something isn't specified (e.g. exact interview numbers), phrase it honestly and generally rather than fabricating precision.

Structure the output into these five sections, matching this rough time budget for 20 minutes total:

1. **Introduction** (~1.5 min)
2. **Problem and Solution** (~3 min)
3. **AI-Assisted Development** (~3 min)
4. **Project Demonstration** (~10 min — this is the main section)
5. **Future Roadmap** (~2.5 min)

For each section, give me: a slide title, 3–6 bullet points to display on the slide, and a "speaker script" paragraph written in first person as if I (Kaveesha) am speaking.

---

## Facts to use

### 1. Introduction
- Presenter name: **Kaveesha**
- Project title: **ScoreWise: AI-assisted GCE A/L past-paper practice tool**
- One-line summary: ScoreWise is a web app that lets GCE Advanced Level students practice real past exam papers under timed, scored conditions, and — for every question they get wrong — talk to an AI tutor that explains the answer using the actual syllabus content, not generic web knowledge.

### 2. Problem and Solution

**Problem:**
- GCE A/L students (Sri Lanka's high-stakes pre-university exam, roughly equivalent to A-Levels) prepare heavily using past papers, but practicing past papers today is a passive, unguided process: a student marks their own answers against an answer key (or a teacher does it days later), gets a right/wrong verdict, and is left to figure out *why* they were wrong entirely on their own — usually by re-reading a textbook chapter cold, or waiting for the next class/tuition session.
- There is no immediate, question-specific, syllabus-grounded explanation available at the moment of the mistake — which is exactly when a student is most motivated to understand it.
- This is worse for self-study students and students without easy access to a tutor/teacher outside class hours, and for subjects with dense, fact-heavy syllabi (e.g. ICT) where "why is this option wrong" isn't obvious from the answer key alone.

**Target user:**
- GCE Advanced Level students (Sri Lankan curriculum) in their final 1–2 years of secondary education, preparing for the national A/L exam, who already practice past papers as their primary revision method but currently do so without an on-demand explainer.

**Evidence the problem is real:**
- Personal/direct observation of how A/L past-paper practice actually works today (self-marking against answer keys, delayed or absent explanations) rather than formal user interviews at this stage — be explicit that this was grounded in direct familiarity with the A/L exam system and how students currently self-study, not a formal research study. Frame it honestly as founder/personal-experience-based evidence, not survey data.

**Solution:**
- ScoreWise: students take real past-paper questions as a scored, timed practice attempt (server-side scoring against the official answer key, including edge cases like officially voided questions where every answer is accepted).
- For any question they got wrong, they can open a **question-scoped AI tutor chat** — grounded via retrieval-augmented generation (RAG) over the actual uploaded syllabus content for that subject, not general internet knowledge — that explains the correct answer, addresses their specific wrong choice, and cites the syllabus material it used.
- A personal dashboard shows accuracy trends over time, per-subject performance, and commonly-missed topics, so practice compounds into visible progress instead of disappearing after each attempt.

**Value provided:**
- Turns passive self-marking into active, explained learning at the exact moment of the mistake.
- Keeps explanations grounded and syllabus-accurate (via RAG + citations) instead of an LLM hallucinating or going off-syllabus.
- Gives students a longitudinal view of where they're actually weak (by subject/topic), not just a single attempt's score.
- Available any time, with no dependency on a teacher/tutor's schedule.

### 3. AI-Assisted Development

Be explicit and specific about the following (this project was built solo, heavily leveraging AI tools across the whole SDLC):

- **Coding assistant / agentic development**: Claude Code (Anthropic's CLI-based coding agent) was used throughout — for scaffolding the FastAPI backend architecture (routers/services/repositories layering), writing and iterating on SQLAlchemy models and Alembic migrations, implementing the RAG pipeline (embedding + ChromaDB retrieval + prompt assembly), building the Next.js frontend, and writing the automated test suite (183 test functions across 28 test files, unit + integration, using pytest/pytest-asyncio/httpx).
- **AI for design/spec generation**: Design and requirements documentation (e.g. a software requirements spec listing every dependency/version/purpose, and a precise UI specification describing the frontend screen-by-screen) were generated and refined with AI assistance to keep the build spec-driven rather than ad hoc, so implementation could be checked against a written source of truth.
- **AI as a runtime component of the product itself, not just a dev tool**: the product also *uses* an LLM (Claude, via Anthropic's API, `claude-sonnet-5`) at runtime for two features — the syllabus-grounded question tutor, and a two-tier PDF extraction pipeline (pypdf text-layer extraction first, falling back to one-shot Claude vision transcription for scanned/partially-scanned syllabus PDFs where the text layer is incomplete).
- **Review/validation of AI output** — be concrete about the actual review discipline used, don't just say "I reviewed it":
  - Every AI-authored change was reviewed against the written architecture/spec docs (README, software requirements doc, UI spec) before being accepted, rather than accepted blindly.
  - Automated test coverage (183 tests, unit + integration, run via pytest) was used as a concrete correctness gate on AI-generated backend code — services, repositories, and routers all have corresponding test files.
  - AI-generated LLM-facing prompts (the tutor's system prompt) were deliberately constrained and then manually checked: instructed to answer only from supplied syllabus excerpts, never contradict the stored correct answer, cite sources as `[1]`/`[2]`, and decline off-topic questions — with a fallback path tested for when retrieval itself fails (ChromaDB unavailable), so the tutor still responds using just the question/answer data rather than erroring out.
  - Cost/token behavior of AI-generated LLM-calling code was independently verified: a token-usage ledger (`llm_usage_events` table) and per-model pricing table were added and unit-tested (e.g. `test_token_budget.py`, `test_pricing.py`) rather than trusting estimated costs blindly.
  - Manual end-to-end testing of the running app (backend + frontend together) was used to catch integration issues AI-written unit tests wouldn't surface.

### 4. Project Demonstration

This is the longest section (~10 minutes) — structure it as a live-demo narration with clear beats. Give me a walk-through script assuming I am screen-sharing the running app.

**System walkthrough (functionality-first, in this order):**
1. **Auth**: register/login flow, JWT access + refresh tokens, password reset flow.
2. **Papers list & exam flow**: student browses available past papers (filterable by subject), opens a paper, sees its questions (without answers), and submits answers as a single timed attempt.
3. **Scoring**: explain that scoring happens entirely server-side against the stored answer key — the client never has access to correct answers before submission — including the voided-question edge case (all answers accepted).
4. **Results screen**: per-question review showing correct answer vs. the student's answer, clearly marked.
5. **AI Tutor**: for a wrong answer, open the tutor chat scoped to that one question; show it answering using syllabus citations (`[1]`, `[2]`) that expand to show the excerpt and source document; ask a natural follow-up question to show the chat continuing in context.
6. **Dashboard**: show accuracy trend over recent attempts, per-subject accuracy breakdown, and top commonly-missed topics — the longitudinal progress view.
7. **Admin side** (brief): an admin uploads a syllabus PDF (ingested → chunked → embedded → stored in ChromaDB) and manages past papers/questions/answer keys that feed the student-facing app.

**Technical implementation (explain briefly, in plain language, while demoing):**
- **Architecture**: FastAPI (Python) backend with a layered structure — routers → services → repositories — talking to PostgreSQL (via async SQLAlchemy + asyncpg), a separate ChromaDB vector store for syllabus embeddings, and Redis for rate limiting. Next.js (App Router, TypeScript, Tailwind) frontend calling the backend via its own API routes. A small separate admin web app (Vite + React) for content management.
- **AI/RAG pipeline for the tutor**: deliberately narrow and deterministic — one LLM call per turn, no open-ended tool-calling loop. The question, its options, the correct answer, and the student's own answer are fetched directly from Postgres by ID (not searched). The question text + student's message are embedded (local `all-MiniLM-L6-v2` sentence-transformers model — no external embedding API cost) and used to query ChromaDB for the top-4 most relevant syllabus chunks, filtered to that question's subject, each resolved back to a real source document for citation. Everything is assembled into one system prompt sent to Claude (`claude-sonnet-5` via Anthropic's API), which is instructed to answer only from that material and cite it.
- **Resilience**: if ChromaDB retrieval fails, the tutor turn still proceeds using just the question/answer data instead of failing the whole request.
- **PDF ingestion**: two-tier extraction — pypdf's text layer is used when a completeness heuristic accepts it; otherwise it falls back to a one-shot Claude vision transcription for scanned/partially-scanned PDFs.
- **Cost tracking & token optimization**: every LLM call (tutor replies, chat, title generation) is logged to an append-only `llm_usage_events` table with input/output token counts, keyed by user and feature. A per-model $/token pricing table converts that into an estimated USD cost. An optional daily per-user token budget (`DAILY_TOKEN_BUDGET`) can hard-cap usage, enforced by a dependency-injected budget check before each LLM call, surfaced to the user via a `GET /api/v1/usage/me` endpoint showing tokens used today / remaining. Retrieval is deliberately capped at the top-4 syllabus chunks per turn (not the whole document) to keep prompt size — and therefore cost — bounded per tutor call.
- **Auth & security**: JWT access tokens + opaque, SHA-256-hashed refresh tokens; bcrypt password hashing; server-side answer scoring so correctness can never be inferred or tampered with client-side; SSRF-hardened URL ingestion for the generic chatbot's document feature.
- **Database**: PostgreSQL with the pgvector extension (used by the generic chatbot's own RAG feature), managed via Alembic migrations (8 migrations at time of this presentation, each additive and reversible).

**Testing/validation:**
- 183 automated test functions across 28 test files (unit tests for services/repositories/pricing/token-budget logic, integration tests hitting the FastAPI routers and the WebSocket chat endpoint), run with pytest + pytest-asyncio, using fakes/in-memory doubles for repositories so tests don't require a live database.
- Manual end-to-end testing of the deployed/running app across the full student journey (register → practice → tutor → dashboard) and the admin ingestion journey.
- Deliberate testing of edge cases: voided questions (all-answers-accepted scoring), blank/unanswered questions, retrieval failure fallback for the tutor, and token-budget enforcement at/over the configured limit.

**Challenges / current limitations (be honest, don't oversell):**
- The frontend currently has incomplete dark-mode styling (only the page background/text color respond to color scheme; cards and borders are still fixed light-mode colors) — a known cosmetic gap, not a functional one.
- The tutor pipeline is intentionally single-shot RAG with no tool-calling/agentic reasoning loop, so it can't do multi-step research or pull in material beyond the top-4 retrieved syllabus chunks for a given question.
- Local embedding model (`all-MiniLM-L6-v2`) trades some retrieval quality for zero marginal embedding cost and no external API dependency.
- Question/paper/syllabus content ingestion is still admin-driven (manual upload), not automated at scale from an external question bank.
- Observability is currently structured JSON logging only — metrics (Prometheus) and distributed tracing (OpenTelemetry) are planned but not yet implemented.

### 5. Future Roadmap

**What's planned next:**
- Metrics and tracing (Prometheus + OpenTelemetry) for production observability of the AI pipeline's latency/cost/error rate.
- Prompt caching for the tutor's system prompt (syllabus excerpts repeat across students asking about the same question) to cut per-call cost further, once traffic justifies it.
- Expanding subject/paper coverage and streamlining admin ingestion so more past papers and syllabi can be onboarded faster than one-by-one manual upload.
- Richer dashboard analytics (e.g. topic-level mastery over time, not just accuracy trend and top-missed topics).

**Still needed before real-world use:**
- Fixing the dark-mode styling gap and a general UI/UX polish pass for a non-technical student audience.
- Production-grade observability (metrics/tracing above) so issues in the AI tutor pipeline can be caught proactively rather than via user reports.
- Load/cost testing at realistic concurrent-student volume, particularly around the LLM tutor calls and the token-budget system, before opening access beyond a pilot group.
- A content-moderation/abuse review pass on the tutor chat (rate limiting exists via Redis; a broader look at misuse patterns would still be warranted before a public launch).
- Formal user testing with actual A/L students to validate the tutor's explanations are genuinely helpful (versus the personal-experience-based problem validation used so far).

---

## Output format requested

For each of the 5 sections, produce:
```
## [Section number]. [Section title]  (~X min)

### Slide: [slide title]
- bullet
- bullet
- bullet

### Speaker script
[first-person paragraph(s), timed to roughly the section's minute budget, natural spoken English, no jargon left unexplained]

### Demo cues (only for section 4)
[what to click/show on screen at each beat]
```

End with a short **"Closing line"** (one or two sentences) to end the video on, thanking the viewer and inviting questions.
