# ScoreWise

A FastAPI backend for GCE A/L past-paper practice: students take scored MCQ attempts against real past papers, and get a per-question AI tutor grounded in the uploaded syllabus. Built on top of a generic chatbot backend (auth, chat sessions, RAG-over-documents, tool-calling) that ships alongside it, reused as-is.

## What happens in the system

1. **Admin ingestion.** An admin uploads syllabus PDFs (chunked, embedded, stored in ChromaDB) and past papers — questions, options, and the official marking scheme — stored in Postgres, including the edge case where a question is officially voided and every answer is accepted.
2. **Student practice.** A logged-in student lists papers, opens one, and submits answers for its questions in a single attempt. Scoring happens server-side against the stored answer key — nothing about correctness is ever trusted from the client.
3. **AI tutor.** For any question, the student can ask a tutor chat scoped to just that question — see below.
4. **Generic chatbot.** Independently, the same backend also serves a general-purpose chat product: sessions, streaming WebSocket chat, ad-hoc document/URL RAG, and tool-calling — unrelated to ScoreWise but hosted in the same API.

## How the AI tutor is grounded

Each tutor turn is retrieval-augmented and deliberately narrow — one LLM call, no tool-calling loop, no outside knowledge:

1. **Deterministic lookup, not search, for the question itself.** The question's text, options, correct answer (or "voided — all answers accepted"), and the student's own selected answer (if any) are fetched straight from Postgres by ID.
2. **Vector retrieval for supporting material.** The question text + the student's message are embedded and used to query ChromaDB for the top-4 syllabus chunks, filtered to the question's subject. Each chunk is resolved back to its source document for a real citation (filename/topic), not just raw text.
3. **Everything is assembled into one system prompt**: question + options + correct answer + the student's answer + the numbered, citable syllabus excerpts. The model is instructed to answer using *only* that material, never contradict the stated correct answer, address the student's specific wrong choice when they got it wrong, cite excerpts as `[1]`/`[2]`, and decline anything off-topic.
4. If retrieval fails (e.g. ChromaDB briefly down), the turn still proceeds on question/answer data alone rather than failing outright.

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | — | Liveness check |
| GET | `/readyz` | — | Readiness (DB + LLM reachability) |
| GET | `/api/v1/version` | — | Build/version info |
| POST | `/api/v1/auth/register` | — | Create a user account |
| POST | `/api/v1/auth/login` | — | Exchange nickname+password for tokens |
| POST | `/api/v1/auth/refresh` | — | Rotate refresh token → new access token |
| POST | `/api/v1/auth/logout` | ✓ | Revoke a refresh token |
| GET | `/api/v1/auth/me` | ✓ | Current user profile |
| GET | `/api/v1/papers` | ✓ | List past papers, optionally by subject |
| GET | `/api/v1/papers/{paper_id}/questions` | ✓ | List a paper's questions (no answers) |
| POST | `/api/v1/attempts` | ✓ | Submit answers for a paper; scored immediately |
| POST | `/api/v1/questions/{question_id}/tutor` | ✓ | Send a message to that question's grounded AI tutor |
| POST | `/api/v1/admin/documents` | ✓ | Upload a syllabus PDF (ingested into ChromaDB) |
| GET | `/api/v1/admin/documents` | ✓ | List uploaded syllabus documents |
| DELETE | `/api/v1/admin/documents/{document_id}` | ✓ | Remove a syllabus document + its chunks |
| POST | `/api/v1/sessions` | ✓ | Create a chat session (generic chatbot) |
| GET | `/api/v1/sessions` | ✓ | List caller's chat sessions |
| GET | `/api/v1/sessions/{session_id}` | ✓ | Get one session |
| PATCH | `/api/v1/sessions/{session_id}` | ✓ | Rename a session |
| DELETE | `/api/v1/sessions/{session_id}` | ✓ | Delete one session |
| DELETE | `/api/v1/sessions` | ✓ | Delete all of caller's sessions |
| GET | `/api/v1/sessions/{session_id}/messages` | ✓ | Full message history |
| POST | `/api/v1/sessions/{session_id}/messages` | ✓ | Send a message; runs the full LLM+tool+RAG turn |
| WS | `/api/v1/sessions/{session_id}/stream` | ✓ | Streaming chat over WebSocket |
| POST | `/api/v1/sessions/{session_id}/documents` | ✓ | Ingest a file or URL into the session's RAG store |
| GET | `/api/v1/sessions/{session_id}/documents` | ✓ | List indexed sources for a session |
| DELETE | `/api/v1/sessions/{session_id}/documents/{document_id}` | ✓ | Remove an indexed source |
| GET | `/api/v1/tools` | ✓ | List tool definitions available to the model (introspection only) |

`✓` = requires a bearer access token from `/api/v1/auth/login`.

## How to run the program

The app has two parts: the FastAPI **backend** (`app/`, this repo root) and the Next.js **frontend** (`web/`).

### Backend

**Option A — Docker Compose (recommended):** brings up Postgres (pgvector), Redis, ChromaDB, runs Alembic migrations, then starts the API.

1. Fill in `.env` at the repo root (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`, etc. — see the keys already listed there).
2. `docker compose up --build`
3. API is live at `http://localhost:8000` — check `http://localhost:8000/healthz` and `http://localhost:8000/readyz`.

**Option B — run locally with `uv`:**

1. Install deps: `uv sync`
2. Start the datastores (or point `.env` at your own): `docker compose up postgres redis chromadb`
3. Run migrations: `uv run alembic upgrade head`
4. Start the API with reload: `uv run uvicorn app.main:app --reload --port 8000`

### Frontend

1. `cd web`
2. `npm install`
3. Set `web/.env.local` (`BACKEND_URL` pointing at the API, e.g. `http://localhost:8000`, plus `DEMO_NICKNAME` / `DEMO_PASSWORD`)
4. `npm run dev`
5. Open `http://localhost:3000`

The frontend expects the backend to already be running at `BACKEND_URL`.
