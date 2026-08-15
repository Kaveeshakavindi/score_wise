# Software Requirements

Everything needed to build, run, and deploy the backend — the legacy CLI core (`chatbot/`), the generic FastAPI API layer (`app/`, per `api.md`), and ScoreWise, the GCE A/L past-paper practice tool built on top of it (papers/questions/attempts + a question-scoped AI tutor RAG pipeline). Versions are pulled verbatim from `pyproject.toml`/`uv.lock`/`requirments.txt`/`docker-compose.yml`; nothing pinned here is guessed.

## Language / Runtime

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Interpreter | Python | 3.10 (`.python-version`; `requires-python = ">=3.10"`) | Runs both `chatbot/` CLI and `app/` API | Required |
| Package/venv manager | uv | 0.5.11 (Dockerfile build stage); local dev unpinned | Resolves `pyproject.toml` → `uv.lock`, manages the venv | Required |

## Web Framework & Server

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Web framework | FastAPI | 0.115.6 | Routing, request/response models, DI (`core/deps.py`), OpenAPI docs | Required |
| ASGI toolkit | Starlette | 0.41.3 (transitive via FastAPI) | Middleware base classes, WebSocket support, `TestClient` | Required |
| Dev/ASGI server | Uvicorn (`[standard]`) | 0.34.0 | Local dev server (`uvicorn app.main:app --reload`) and gunicorn's worker class | Required |
| Production process manager | Gunicorn | 23.0.0 | `-k uvicorn.workers.UvicornWorker -w $WORKERS` (Dockerfile CMD) | Required |
| WebSocket protocol | websockets | 14.1 | Backs `WS /api/v1/sessions/{id}/stream` | Required |
| Multipart parsing | python-multipart | 0.0.20 | Parses uploaded files on `POST /sessions/{id}/documents` and the OAuth2 login form | Required |

## Database & ORM/Driver

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Database | PostgreSQL | 16 (`pgvector/pgvector:pg16` image, `docker-compose.yml`) | Primary datastore — users, sessions, messages, RAG chunks, tokens | Required |
| Vector extension | pgvector (Postgres extension) | Unpinned — whatever ships in the `pgvector/pgvector:pg16` image | `ivfflat` cosine-distance index for RAG chunk retrieval (§9) | Required |
| ORM | SQLAlchemy (`[asyncio]`) | 2.0.36 | Async ORM/models (`app/db/models.py`) and query layer | Required |
| Async driver | asyncpg | 0.30.0 | Async Postgres driver under SQLAlchemy's async engine | Required |
| Vector column type | pgvector (Python package) | 0.3.6 | `Vector(384)` SQLAlchemy column type for `rag_chunks.embedding` | Required |
| Sync driver | psycopg (`[binary]`) | 3.2.3 | Used only by the legacy CLI (`chatbot/db/conn.py`) | Required (CLI only) |

## Vector Store (ScoreWise Syllabus RAG)

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Vector database | ChromaDB (server) | `chromadb/chroma:latest` image (`docker-compose.yml`) | Stores syllabus chunk embeddings, filtered by subject at query time (`app/vectorstore/chroma_client.py`) — deliberately a standalone service, not an embedded on-disk client, so Gunicorn's 4 worker processes don't race on one local store | Required (ScoreWise tutor) |
| Python client | chromadb | 1.5.9 | `HttpClient` used by `app/vectorstore/chroma_client.py`; pulls in grpcio/onnxruntime/opentelemetry as transitive deps (unused by this app — Chroma's own default embedding function is bypassed since embeddings are supplied directly) | Required (ScoreWise tutor) |
| ONNX runtime | onnxruntime | `<1.24` (explicitly capped) | Transitive dep of chromadb; capped because `1.24+` ships no `cp310` wheel, which would break local macOS dev | Required (transitive) |

## Document Processing (ScoreWise Syllabus Ingestion)

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| PDF text extraction | pypdf | 6.15.0 | Extracts raw text from uploaded syllabus PDFs (`app/services/pdf_extraction.py`), `POST /api/v1/admin/documents` | Required (ScoreWise admin upload) |

## Caching / Rate Limiting

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Cache/store | Redis | 7 (`redis:7-alpine` image) | Backend for the sliding-window rate limiter (§8) | Required |
| Redis client | redis (`redis.asyncio`) | 5.2.1 | Async Redis client used by `core/deps.py`'s rate-limit dependencies | Required |

## Authentication

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| JWT | PyJWT | 2.10.1 | Encodes/decodes access tokens (`core/security.py`) | Required |
| Password hashing | bcrypt | 4.2.1 | Hashes user passwords (shared with the CLI's `chatbot/db/users.py`) | Required |
| OAuth2 scaffolding | `fastapi.security` (bundled with FastAPI) | 0.115.6 (FastAPI's version) | `OAuth2PasswordBearer` / `OAuth2PasswordRequestForm` for the password-grant flow | Required |
| Refresh token entropy | stdlib `secrets`/`hashlib` | Python stdlib | Opaque refresh tokens, stored as SHA-256 hashes | Required |

## LLM / AI

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Orchestration | langchain | 0.3.14 | Message/prompt abstractions used across chat/title services | Required |
| Anthropic wrapper | langchain-anthropic | 0.3.14 | `ChatAnthropic` — chat completion, tool binding, streaming | Required |
| Anthropic SDK | anthropic | 0.120.2 (transitive via langchain-anthropic; imported directly in `app/core/exceptions.py` for error types) | Underlying HTTP client + typed exceptions (`APIStatusError`, `RateLimitError`, ...) | Required |
| Chat/title model | Claude — `claude-sonnet-5` (`ANTHROPIC_MODEL`, default) | External model, not a package | Chat completion and session-title generation | Required |

## Embeddings (RAG)

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Embedding library | sentence-transformers | 3.3.1 | Wraps the local embedding model (`app/llm/embedder.py`) | Required |
| ML backend | torch | 2.9.0 (vendored macOS arm64/cp310 wheel for local dev; resolved from PyPI on Linux) | Tensor backend for sentence-transformers | Required |
| Scientific computing | scipy | 1.15.3 (same vendoring split as torch) | sentence-transformers/scikit-learn dependency | Required |
| Embedding model | `all-MiniLM-L6-v2` (`EMBEDDING_MODEL`, default) | 384-dim, downloaded from Hugging Face Hub on first use | Embeds RAG chunks/queries; no external API needed | Required |

## Migration Tooling

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Schema migrations | Alembic | 1.14.0 | Versioned, reversible migrations for the API (`app/db/migrations/`) | Required (API) |
| Ad-hoc bootstrap | `chatbot/db/migrations.py` + `schema.sql` | N/A (hand-written SQL) | `CREATE TABLE IF NOT EXISTS` on every CLI boot — superseded by Alembic for the API (§16.7) | Required (CLI only) |

## Validation

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Data validation | Pydantic | 2.12.5 (transitive via FastAPI/pydantic-settings) | Request/response schemas (`app/schemas/`) | Required |
| Settings validation | pydantic-settings | 2.7.0 | Fail-fast typed env-var loading (`app/core/config.py`) | Required |

## Logging / Observability

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Structured logging | stdlib `logging` + custom JSON formatter | Python stdlib (`app/core/logging.py`) | One JSON line per log event, request-id correlation | Required |
| structlog | — | Not used | api.md §12 names it as an alternative; the app implemented the same shape over stdlib instead | Optional (superseded) |
| Metrics | prometheus-fastapi-instrumentator | Not in repo | `GET /metrics`, request/latency histograms | Planned (§12, Phase 2) |
| Tracing | OpenTelemetry (FastAPI + Postgres + httpx instrumentation) | Not in repo | Distributed trace per chat turn | Planned (§12, Phase 2) |

## Testing

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Test runner | pytest | 8.3.4 | Unit + integration test execution | Required (dev) |
| Async test support | pytest-asyncio | 0.25.0 | `asyncio_mode = "auto"` for async test functions/fixtures | Required (dev) |
| HTTP test client | httpx | 0.28.1 | `AsyncClient` + `ASGITransport` for router tests; also the app's real outbound URL-fetch client (`app/services/url_fetch.py`) | Required |
| WebSocket test client | starlette `TestClient` (bundled with Starlette) | 0.41.3 (Starlette's version) | Drives `websocket_connect()` for `tests/integration/test_ws_chat_router.py` | Required (dev) |

## Containerization / Deployment

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Container runtime | Docker | Host-installed, unpinned | Builds/runs the multi-stage image (`Dockerfile`) | Required |
| Local orchestration | Docker Compose | Host-installed, unpinned | Runs `api` + `postgres` + `redis` + `chromadb` + `migrate` together (`docker-compose.yml`) | Required (local/dev) |
| Base image | `python:3.10-slim` | 3.10-slim (Debian) | Build and runtime stage base, matched to `.python-version` | Required |
| Process manager (prod) | Gunicorn (see Web Framework table) | 23.0.0 | Container's `CMD` | Required |

## Third-Party APIs / External Services

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| LLM provider | Anthropic API (`api.anthropic.com`) | External service | Chat completion + title generation; needs `ANTHROPIC_API_KEY` | Required |
| Model hosting | Hugging Face Hub | External service | One-time download of the `all-MiniLM-L6-v2` embedding model, then cached locally | Required (first run) |
| User-supplied URLs | Arbitrary `http(s)` hosts | N/A | Fetched by `read_url`/`fetch_url` tools and `/documents` URL ingestion, SSRF-hardened (§6.5) | Optional (feature-dependent) |

## Environment Variables

Reference: api.md §10 / `app/core/config.py`.

| Component | Name/Tool | Version (if pinned) | Purpose | Required/Optional |
|---|---|---|---|---|
| Env var | `DATABASE_URL` | no default | Postgres connection string | Required |
| Env var | `ANTHROPIC_API_KEY` | no default | Anthropic API credential | Required |
| Env var | `ANTHROPIC_MODEL` | default: `claude-sonnet-5` | Chat/title model name | Optional |
| Env var | `EMBEDDING_MODEL` | default: `all-MiniLM-L6-v2` | Local embedding model name | Optional |
| Env var | `JWT_SECRET_KEY` | no default | HMAC signing secret for access tokens | Required |
| Env var | `JWT_ALGORITHM` | default: `HS256` | JWT signing algorithm | Optional |
| Env var | `ACCESS_TOKEN_EXPIRE_MINUTES` | default: `30` | Access token TTL | Optional |
| Env var | `REFRESH_TOKEN_EXPIRE_DAYS` | default: `14` | Refresh token TTL | Optional |
| Env var | `CORS_ORIGINS` | default: `""` (empty) | Comma-separated CORS allow-list; required (non-empty) in production | Required (prod) |
| Env var | `REDIS_URL` | no default | Rate-limiting/token-cache backend | Required |
| Env var | `MAX_INGEST_BYTES` | default: `2000000` | Cap on `/documents` upload/fetch size | Optional |
| Env var | `DAILY_TOKEN_BUDGET` | default: unset (disabled) | Optional per-user daily token quota | Optional |
| Env var | `CHROMA_HOST` | default: `localhost` | ChromaDB server hostname (ScoreWise tutor RAG); docker-compose overrides to `chromadb` | Optional |
| Env var | `CHROMA_PORT` | default: `8001` | ChromaDB server port; docker-compose overrides to `8000` (container-internal) | Optional |
| Env var | `MAX_SYLLABUS_UPLOAD_BYTES` | default: `20971520` (20MB) | Cap on `POST /admin/documents` PDF upload size | Optional |
| Env var | `LOG_LEVEL` | default: `INFO` | Logging verbosity | Optional |
| Env var | `APP_ENV` | default: `development` | `development`\|`staging`\|`production`; gates `/docs` exposure | Optional |
| Env var | `WORKERS` | default: `4` | Gunicorn/Uvicorn worker count (deployment only) | Optional |
| Env var | `GIT_SHA` | default: `"unknown"` | Build SHA surfaced by `GET /api/v1/version`; read directly via `os.environ`, not part of `Settings` | Optional |
