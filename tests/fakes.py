from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from document_extraction import ExtractionMethod, ExtractionResult

from app.core.exceptions import NotFoundError
from app.db.models import (
    Attempt,
    AttemptAnswer,
    ChatSession,
    Message,
    Paper,
    PasswordResetToken,
    Question,
    RagDocument,
    RefreshToken,
    SyllabusDocument,
    TutorMessage,
    User,
)


class FakeUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}

    async def create(self, *, name: str, nickname: str, password_hash: str, age: int, email: str | None = None) -> User:
        user = User(id=uuid.uuid4(), name=name, nickname=nickname, password_hash=password_hash, age=age, email=email)
        user.created_at = datetime.now(timezone.utc)
        self._by_id[user.id] = user
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_nickname(self, nickname: str) -> User | None:
        return next((u for u in self._by_id.values() if u.nickname == nickname), None)

    async def exists_by_nickname(self, nickname: str) -> bool:
        return any(u.nickname == nickname for u in self._by_id.values())

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        user = self._by_id.get(user_id)
        if user is not None:
            user.password_hash = password_hash


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self._by_hash: dict[str, RefreshToken] = {}

    async def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(id=uuid.uuid4(), user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._by_hash[token_hash] = token
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self._by_hash.get(token_hash)

    async def revoke(self, token_id: uuid.UUID, revoked_at: datetime) -> None:
        for token in self._by_hash.values():
            if token.id == token_id:
                token.revoked_at = revoked_at

    async def revoke_all_for_user(self, user_id: uuid.UUID, revoked_at: datetime) -> None:
        for token in self._by_hash.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = revoked_at


class FakePasswordResetTokenRepository:
    def __init__(self) -> None:
        self._by_hash: dict[str, PasswordResetToken] = {}

    async def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        token = PasswordResetToken(id=uuid.uuid4(), user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._by_hash[token_hash] = token
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self._by_hash.get(token_hash)

    async def mark_used(self, token_id: uuid.UUID, used_at: datetime) -> None:
        for token in self._by_hash.values():
            if token.id == token_id:
                token.used_at = used_at


class FakeEmailSender:
    """Records sent emails instead of calling any real provider — lets tests
    assert on what would have been sent without any AWS dependency."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []  # (to, reset_url)
        self.fail_next: bool = False

    async def send_password_reset_email(self, *, to: str, reset_url: str) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated email send failure")
        self.sent.append((to, reset_url))


class FakeSessionRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, ChatSession] = {}

    async def create(self, user_id: uuid.UUID) -> ChatSession:
        now = datetime.now(timezone.utc)
        session = ChatSession(id=uuid.uuid4(), user_id=user_id, title=None, created_at=now, last_active=now)
        self._by_id[session.id] = session
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> ChatSession | None:
        return self._by_id.get(session_id)

    async def list_by_user(self, user_id: uuid.UUID, *, limit: int, offset: int) -> list[ChatSession]:
        items = sorted(
            (s for s in self._by_id.values() if s.user_id == user_id), key=lambda s: s.last_active, reverse=True
        )
        return items[offset : offset + limit]

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        return sum(1 for s in self._by_id.values() if s.user_id == user_id)

    async def set_title(self, session_id: uuid.UUID, title: str) -> None:
        if session_id in self._by_id:
            self._by_id[session_id].title = title

    async def set_title_if_null(self, session_id: uuid.UUID, title: str) -> None:
        if not title:
            return
        session = self._by_id.get(session_id)
        if session is not None and session.title is None:
            session.title = title

    async def touch(self, session_id: uuid.UUID) -> None:
        if session_id in self._by_id:
            self._by_id[session_id].last_active = datetime.now(timezone.utc)

    async def delete(self, session_id: uuid.UUID) -> None:
        self._by_id.pop(session_id, None)

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        for sid in [sid for sid, s in self._by_id.items() if s.user_id == user_id]:
            del self._by_id[sid]


class FakeMessageRepository:
    def __init__(self) -> None:
        self._by_session: dict[uuid.UUID, list[Message]] = {}

    async def create(self, session_id: uuid.UUID, role: str, content: str) -> Message:
        message = Message(id=uuid.uuid4(), session_id=session_id, role=role, content=content)
        message.created_at = datetime.now(timezone.utc)
        self._by_session.setdefault(session_id, []).append(message)
        return message

    async def list_by_session(self, session_id: uuid.UUID, *, limit: int, offset: int) -> list[Message]:
        return self._by_session.get(session_id, [])[offset : offset + limit]

    async def count_by_session(self, session_id: uuid.UUID) -> int:
        return len(self._by_session.get(session_id, []))

    async def history(self, session_id: uuid.UUID) -> list[Message]:
        return list(self._by_session.get(session_id, []))


@dataclass
class FakeToolCallResult:
    name: str
    args: dict
    status: str
    output: str
    duration_ms: int = 1
    error_message: str | None = None


@dataclass
class FakeDocument:
    id: uuid.UUID
    session_id: uuid.UUID
    source: str
    indexed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FakeRagService:
    def __init__(self, retrieved: list[str] | None = None) -> None:
        self.retrieved = retrieved or []
        self.indexed: list[tuple[uuid.UUID, str, str]] = []
        self._documents: dict[uuid.UUID, FakeDocument] = {}
        self._by_session: dict[uuid.UUID, list[uuid.UUID]] = {}

    async def retrieve(self, session_id: uuid.UUID, query: str, k: int = 4) -> list[str]:
        return self.retrieved

    async def index_text(self, session_id: uuid.UUID, source: str, text: str, **kwargs) -> FakeDocument:
        self.indexed.append((session_id, source, text))
        document = FakeDocument(id=uuid.uuid4(), session_id=session_id, source=source)
        self._documents[document.id] = document
        self._by_session.setdefault(session_id, []).append(document.id)
        return document

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        return 1

    async def list_documents(self, session_id: uuid.UUID, *, limit: int, offset: int) -> list[FakeDocument]:
        ids = self._by_session.get(session_id, [])[offset : offset + limit]
        return [self._documents[i] for i in ids]

    async def count_documents(self, session_id: uuid.UUID) -> int:
        return len(self._by_session.get(session_id, []))

    async def delete_document(self, session_id: uuid.UUID, document_id: uuid.UUID) -> None:
        document = self._documents.get(document_id)
        if document is None or document.session_id != session_id:
            raise NotFoundError(f"Document {document_id} was not found.")
        del self._documents[document_id]
        self._by_session[session_id].remove(document_id)


class FakeRagChunkRepository:
    """In-memory stand-in for RagChunkRepository (bypasses pgvector/Postgres),
    used to unit test RagService's chunk/store/list/delete orchestration (§13)."""

    def __init__(self) -> None:
        self._documents: dict[uuid.UUID, RagDocument] = {}
        self._chunks: dict[uuid.UUID, list[str]] = {}

    async def create_document(self, session_id: uuid.UUID, source: str) -> RagDocument:
        document = RagDocument(id=uuid.uuid4(), session_id=session_id, source=source)
        document.indexed_at = datetime.now(timezone.utc)
        self._documents[document.id] = document
        self._chunks[document.id] = []
        return document

    async def create_chunks(
        self, document_id: uuid.UUID, session_id: uuid.UUID, chunks: list[str], embeddings: list[list[float]]
    ) -> int:
        self._chunks[document_id].extend(chunks)
        return len(chunks)

    async def list_documents(self, session_id: uuid.UUID, *, limit: int, offset: int) -> list[RagDocument]:
        items = [d for d in self._documents.values() if d.session_id == session_id]
        return items[offset : offset + limit]

    async def count_documents(self, session_id: uuid.UUID) -> int:
        return sum(1 for d in self._documents.values() if d.session_id == session_id)

    async def get_document(self, document_id: uuid.UUID) -> RagDocument | None:
        return self._documents.get(document_id)

    async def chunk_count(self, document_id: uuid.UUID) -> int:
        return len(self._chunks.get(document_id, []))

    async def delete_document(self, document_id: uuid.UUID) -> None:
        self._documents.pop(document_id, None)
        self._chunks.pop(document_id, None)

    async def retrieve(self, session_id: uuid.UUID, query_embedding: list[float], k: int) -> list[str]:
        pool: list[str] = []
        for document_id, chunks in self._chunks.items():
            if self._documents[document_id].session_id == session_id:
                pool.extend(chunks)
        return pool[:k]


class FakeToolService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, session_id: uuid.UUID, name: str, args: dict) -> FakeToolCallResult:
        self.calls.append((name, args))
        return FakeToolCallResult(name=name, args=args, status="ok", output=f"result of {name}")


class FakeTitleService:
    async def generate(self, user_input: str, assistant_output: str) -> str:
        return "Fake Generated Title"


class FakeToolInvocationRepository:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def create(
        self,
        session_id: uuid.UUID,
        tool_name: str,
        args: dict,
        status: str,
        duration_ms: int,
        error_message: str | None = None,
    ) -> None:
        self.records.append(
            {
                "session_id": session_id,
                "tool_name": tool_name,
                "args": args,
                "status": status,
                "duration_ms": duration_ms,
                "error_message": error_message,
            }
        )


class FakePaperRepository:
    def __init__(self, *, question_repo: "FakeQuestionRepository | None" = None) -> None:
        self._by_id: dict[uuid.UUID, Paper] = {}
        self._questions = question_repo

    async def create(self, subject: str, year: int) -> Paper:
        paper = Paper(id=uuid.uuid4(), subject=subject, year=year)
        paper.created_at = datetime.now(timezone.utc)
        self._by_id[paper.id] = paper
        return paper

    async def list_by_subject(self, subject: str | None, *, limit: int, offset: int) -> list[Paper]:
        items = sorted(
            (p for p in self._by_id.values() if subject is None or p.subject == subject),
            key=lambda p: p.year,
            reverse=True,
        )
        return items[offset : offset + limit]

    async def count_by_subject(self, subject: str | None) -> int:
        return sum(1 for p in self._by_id.values() if subject is None or p.subject == subject)

    async def get_by_id(self, paper_id: uuid.UUID) -> Paper | None:
        return self._by_id.get(paper_id)

    async def count_questions_by_paper_ids(self, paper_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        wanted = set(paper_ids)
        counts: dict[uuid.UUID, int] = {}
        for question in self._questions._by_id.values():
            if question.paper_id in wanted:
                counts[question.paper_id] = counts.get(question.paper_id, 0) + 1
        return counts


class FakeQuestionRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Question] = {}

    async def create(
        self,
        paper_id: uuid.UUID,
        *,
        subject: str,
        year: int,
        question_number: int,
        question_text: str,
        options: dict[str, str],
        correct_answer: int,
    ) -> Question:
        question = Question(
            id=uuid.uuid4(),
            paper_id=paper_id,
            subject=subject,
            year=year,
            question_number=question_number,
            question_text=question_text,
            options=options,
            correct_answer=correct_answer,
        )
        question.created_at = datetime.now(timezone.utc)
        self._by_id[question.id] = question
        return question

    async def list_by_paper(self, paper_id: uuid.UUID, *, limit: int, offset: int) -> list[Question]:
        items = sorted(
            (q for q in self._by_id.values() if q.paper_id == paper_id), key=lambda q: q.question_number
        )
        return items[offset : offset + limit]

    async def count_by_paper(self, paper_id: uuid.UUID) -> int:
        return sum(1 for q in self._by_id.values() if q.paper_id == paper_id)

    async def get_by_id(self, question_id: uuid.UUID) -> Question | None:
        return self._by_id.get(question_id)

    async def get_many_by_ids(self, question_ids: list[uuid.UUID]) -> dict[uuid.UUID, Question]:
        return {qid: self._by_id[qid] for qid in question_ids if qid in self._by_id}


class FakeSyllabusDocumentRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, SyllabusDocument] = {}

    async def create(
        self, *, document_id: uuid.UUID | None, filename: str, subject: str, topic: str | None, chunk_count: int
    ) -> SyllabusDocument:
        document = SyllabusDocument(
            id=document_id or uuid.uuid4(), filename=filename, subject=subject, topic=topic, chunk_count=chunk_count
        )
        document.uploaded_at = datetime.now(timezone.utc)
        self._by_id[document.id] = document
        return document

    async def list_all(self, *, limit: int, offset: int) -> list[SyllabusDocument]:
        items = sorted(self._by_id.values(), key=lambda d: d.uploaded_at, reverse=True)
        return items[offset : offset + limit]

    async def count_all(self) -> int:
        return len(self._by_id)

    async def get_by_id(self, document_id: uuid.UUID) -> SyllabusDocument | None:
        return self._by_id.get(document_id)

    async def get_many_by_ids(self, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, SyllabusDocument]:
        return {did: self._by_id[did] for did in document_ids if did in self._by_id}

    async def delete(self, document_id: uuid.UUID) -> None:
        self._by_id.pop(document_id, None)


class FakeDocumentExtractionService:
    """Stands in for document_extraction.DocumentExtractionService in tests
    -- always returns a canned TEXT_LAYER result, never touches pypdf or
    calls the real Anthropic API."""

    def __init__(self, text: str = "a" * 1000) -> None:
        self._text = text

    async def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        return ExtractionResult(
            text=self._text,
            method=ExtractionMethod.TEXT_LAYER,
            raw_pdf_bytes=pdf_bytes,
            page_count=1,
            confidence_hint=1.0,
            filename=filename,
        )


class FakeAttemptRepository:
    """The dashboard read methods below need Paper/Question data to answer
    what the real repo gets via a SQL join — rather than duplicating that
    data into this fake, it optionally takes the same FakePaperRepository/
    FakeQuestionRepository instances a test already built, and resolves
    through their public get_by_id. `create`/`add_answer` don't need either,
    so existing callers that build `FakeAttemptRepository()` with no args
    (e.g. test_attempt_service.py) are unaffected."""

    def __init__(
        self,
        *,
        paper_repo: "FakePaperRepository | None" = None,
        question_repo: "FakeQuestionRepository | None" = None,
    ) -> None:
        self.attempts: dict[uuid.UUID, Attempt] = {}
        self.answers: list[AttemptAnswer] = []
        self._papers = paper_repo
        self._questions = question_repo

    async def create(self, *, user_id: uuid.UUID, paper_id: uuid.UUID, score: int, total: int) -> Attempt:
        attempt = Attempt(id=uuid.uuid4(), user_id=user_id, paper_id=paper_id, score=score, total=total)
        attempt.created_at = datetime.now(timezone.utc)
        self.attempts[attempt.id] = attempt
        return attempt

    async def add_answer(
        self, *, attempt_id: uuid.UUID, question_id: uuid.UUID, selected_answer: int | None, is_correct: bool
    ) -> AttemptAnswer:
        answer = AttemptAnswer(
            id=uuid.uuid4(),
            attempt_id=attempt_id,
            question_id=question_id,
            selected_answer=selected_answer,
            is_correct=is_correct,
        )
        self.answers.append(answer)
        return answer

    # --- Dashboard reads (mirrors app/repositories/attempt_repository.py) ---

    async def list_recent_with_paper(self, user_id: uuid.UUID, *, limit: int) -> list[tuple[Attempt, Paper]]:
        items = sorted(
            (a for a in self.attempts.values() if a.user_id == user_id), key=lambda a: a.created_at, reverse=True
        )[:limit]
        return [(a, await self._papers.get_by_id(a.paper_id)) for a in items]

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        return sum(1 for a in self.attempts.values() if a.user_id == user_id)

    async def subject_accuracy_by_user(self, user_id: uuid.UUID) -> list[tuple[str, int, int]]:
        attempt_ids = {a.id for a in self.attempts.values() if a.user_id == user_id}
        totals: dict[str, list[int]] = {}
        for answer in self.answers:
            if answer.attempt_id not in attempt_ids:
                continue
            question = await self._questions.get_by_id(answer.question_id)
            bucket = totals.setdefault(question.subject, [0, 0])
            bucket[1] += 1
            if answer.is_correct:
                bucket[0] += 1
        return [(subject, correct, total) for subject, (correct, total) in totals.items()]

    async def wrong_question_ids_by_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        attempt_ids = {a.id for a in self.attempts.values() if a.user_id == user_id}
        return [a.question_id for a in self.answers if a.attempt_id in attempt_ids and not a.is_correct]


class FakeTutorMessageRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[uuid.UUID, uuid.UUID], list[TutorMessage]] = {}

    async def create(
        self,
        *,
        question_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        selected_answer: int | None = None,
        is_correct: bool | None = None,
    ) -> TutorMessage:
        message = TutorMessage(
            id=uuid.uuid4(),
            question_id=question_id,
            user_id=user_id,
            role=role,
            content=content,
            citations=citations,
            selected_answer=selected_answer,
            is_correct=is_correct,
        )
        message.created_at = datetime.now(timezone.utc)
        self._by_key.setdefault((question_id, user_id), []).append(message)
        return message

    async def history(self, *, question_id: uuid.UUID, user_id: uuid.UUID) -> list[TutorMessage]:
        # Mirrors the real repo: display-only, scoped to role="assistant".
        return [m for m in self._by_key.get((question_id, user_id), []) if m.role == "assistant"]

    async def get_one(
        self, *, question_id: uuid.UUID, user_id: uuid.UUID, selected_answer: int | None = None
    ) -> TutorMessage | None:
        # Mirrors the real repo: only a genuine structured-feedback row
        # (role="assistant", is_correct set) for this exact selected_answer
        # counts as a cache hit — see
        # app/repositories/tutor_message_repository.py's get_one docstring.
        match = None
        for message in self._by_key.get((question_id, user_id), []):
            if (
                message.role == "assistant"
                and message.is_correct is not None
                and message.selected_answer == selected_answer
            ):
                match = message  # keep scanning so the most recent one wins, like ORDER BY created_at.desc()
        return match

    # --- Dashboard reads (mirrors app/repositories/tutor_message_repository.py) ---

    async def reviewed_question_ids(self, user_id: uuid.UUID, question_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        wanted = set(question_ids)
        return {
            question_id
            for (question_id, uid), messages in self._by_key.items()
            if uid == user_id and question_id in wanted and messages
        }

    async def top_cited_topics_by_user(self, user_id: uuid.UUID, *, limit: int = 5) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for (_, uid), messages in self._by_key.items():
            if uid != user_id:
                continue
            for message in messages:
                if message.role != "assistant" or message.is_correct is not False or not message.citations:
                    continue
                for citation in message.citations:
                    topic = citation.get("topic")
                    if topic:
                        counts[topic] = counts.get(topic, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]

    async def count_threaded_questions_by_user(self, user_id: uuid.UUID) -> int:
        return sum(1 for (_, uid), messages in self._by_key.items() if uid == user_id and messages)

    async def list_threaded_question_ids_by_user(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[uuid.UUID]:
        entries = [
            (question_id, max(m.created_at for m in messages))
            for (question_id, uid), messages in self._by_key.items()
            if uid == user_id and messages
        ]
        entries.sort(key=lambda entry: entry[1], reverse=True)
        return [question_id for question_id, _ in entries[offset : offset + limit]]


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis, enough for the
    INCR+EXPIRE rate-limit dependency in tests without a real Redis server."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def ttl(self, key: str) -> int:
        return 60
