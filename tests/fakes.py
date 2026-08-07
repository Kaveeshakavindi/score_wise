from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.exceptions import NotFoundError
from app.db.models import ChatSession, Message, RagDocument, RefreshToken, User


class FakeUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, User] = {}

    async def create(self, *, name: str, nickname: str, password_hash: str, age: int) -> User:
        user = User(id=uuid.uuid4(), name=name, nickname=nickname, password_hash=password_hash, age=age)
        user.created_at = datetime.now(timezone.utc)
        self._by_id[user.id] = user
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_nickname(self, nickname: str) -> User | None:
        return next((u for u in self._by_id.values() if u.nickname == nickname), None)

    async def exists_by_nickname(self, nickname: str) -> bool:
        return any(u.nickname == nickname for u in self._by_id.values())


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
