from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    nickname: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable at the DB level only for safe migration over any pre-existing
    # rows — required for every new registration via RegisterRequest.email
    # (app/schemas/auth.py). Lowercased before storage; needed for password
    # reset (there's nowhere to send a reset link without it).
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    last_active: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    documents: Mapped[list["RagDocument"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_chat_sessions_user_last_active", "user_id", last_active.desc()),)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="messages_role_check"),
        Index("idx_messages_session_created", "session_id", created_at.asc()),
    )


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="documents")
    chunks: Mapped[list["RagChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized for fast per-session vector search (avoids a join on the hot retrieval path).
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    document: Mapped["RagDocument"] = relationship(back_populates="chunks")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(Base):
    """Mirrors RefreshToken field-for-field except `revoked_at` -> `used_at` —
    a reset token is *used* once, not revoked/rotated. Opaque token, stored
    only as its SHA-256 hash (app/core/security.py's existing
    generate_refresh_token/hash_refresh_token, reused as-is)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    args: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('ok', 'error')", name="tool_invocations_status_check"),
        Index("idx_tool_invocations_session", "session_id", created_at.desc()),
    )


class UsageDaily(Base):
    __tablename__ = "usage_daily"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    usage_date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("user_id", "usage_date"),)


# --- ScoreWise: GCE A/L past-paper practice tool ---------------------------
# Additive only — nothing above this line is touched. These tables sit
# alongside the generic chat schema; auth (users/refresh_tokens) is reused
# as-is and not modified.


class Paper(Base):
    """A single past exam paper (one subject + year), the unit questions are
    grouped under. Listed via GET /api/v1/papers."""

    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    questions: Mapped[list["Question"]] = relationship(back_populates="paper", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_papers_subject_year", "subject", "year"),)


class Question(Base):
    """One multiple-choice question within a paper. `options` is a JSON object
    keyed by the option numbers/letters as printed on the source paper (e.g.
    "1"-"5"); `correct_answer` is a 0-based index into that ordering. Some
    official marking schemes void a question and accept every response as
    correct (marked "All" rather than a specific option) — that's carried by
    `accept_all`, in which case `correct_answer` is null and AttemptService
    scores any selection (including none) as correct. `subject`/`year` are
    denormalized from the parent `Paper` (mirrors `rag_chunks.session_id`'s
    denormalization) so the tutor RAG pipeline can filter Chroma metadata by
    subject without a join."""

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accept_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    paper: Mapped["Paper"] = relationship(back_populates="questions")

    __table_args__ = (
        UniqueConstraint("paper_id", "question_number", name="questions_paper_number_unique"),
        Index("idx_questions_paper", "paper_id"),
    )


class SyllabusDocument(Base):
    """One admin-uploaded syllabus PDF. Its chunks/embeddings live in
    ChromaDB (source_document_id metadata = this row's id); this row is the
    SQL-side record that makes uploads listable/deletable (§2)."""

    __tablename__ = "syllabus_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    # Populated from the upload request's `grade_level` field — the proposal
    # names this input "grade_level" but names the storage/Chroma-metadata
    # field "topic"; reconciled here by storing grade_level as topic (see
    # app/schemas/syllabus_document.py for the full note).
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Attempt(Base):
    """One student's full submission of answers for a paper."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    answers: Mapped[list["AttemptAnswer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_attempts_user_created", "user_id", created_at.desc()),)


class AttemptAnswer(Base):
    """Per-question result within an Attempt — one row per question in the
    paper, whether or not the student actually selected an answer."""

    __tablename__ = "attempt_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    selected_answer: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = left unanswered
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    attempt: Mapped["Attempt"] = relationship(back_populates="answers")

    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="attempt_answers_unique"),)


class TutorMessage(Base):
    """One auto-generated feedback message for a (question, user) pair —
    explaining why the student's recorded answer was correct, wrong, or
    (if left blank) what they needed to know. Not a chat: there is at most
    one row per (question_id, user_id, selected_answer), created the first
    time the student views that question's result with that answer, and
    returned as-is on every later view of that same answer. A different
    selected_answer (e.g. a retake where the student picked something else)
    always generates and stores a new row rather than reusing an old one
    (see TutorRagService.generate_feedback)."""

    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Always "assistant" for rows created by the current feedback flow; kept
    # (rather than dropped) so pre-existing chat-turn rows from before this
    # redesign still load without a migration rewriting historical data.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # The syllabus chunks retrieved from ChromaDB that grounded this
    # feedback (document/topic/snippet), so the UI can show "citations"
    # proving the explanation isn't unsourced.
    citations: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    # The option the student had selected (mirrors AttemptSubmitRequest's
    # 0-based index convention); null if they left the question blank.
    selected_answer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Whether that selected_answer was correct (also true for accept_all
    # voided questions). Null only for legacy pre-redesign rows. Lets
    # dashboard analytics (follow-through rate, top-cited topics) stay
    # scoped to mistakes instead of counting every question the student
    # viewed feedback for.
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="tutor_messages_role_check"),
        Index("idx_tutor_messages_question_user_created", "question_id", "user_id", created_at.asc()),
    )
