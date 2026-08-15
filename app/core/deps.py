from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
import redis.asyncio as redis
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import RateLimitedError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.base import get_db_session
from app.db.models import User
from app.repositories.message_repository import MessageRepository
from app.repositories.rag_chunk_repository import RagChunkRepository
from app.repositories.attempt_repository import AttemptRepository
from app.repositories.paper_repository import PaperRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.syllabus_document_repository import SyllabusDocumentRepository
from app.repositories.tool_invocation_repository import ToolInvocationRepository
from app.repositories.tutor_message_repository import TutorMessageRepository
from app.repositories.user_repository import UserRepository
from app.services.attempt_service import AttemptService
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.paper_service import PaperService
from app.services.rag_service import RagService
from app.services.session_service import SessionService
from app.services.syllabus_ingestion_service import SyllabusIngestionService
from app.services.title_service import TitleService
from app.services.tool_service import ToolService
from app.services.tutor_rag_service import TutorRagService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# --- Redis (rate limiting / token cache backend, §8) ---


@lru_cache
def _redis_pool_holder() -> dict[str, redis.Redis]:
    return {}


def get_redis(settings: SettingsDep) -> redis.Redis:
    pool = _redis_pool_holder()
    client = pool.get(settings.redis_url)
    if client is None:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        pool[settings.redis_url] = client
    return client


async def dispose_redis() -> None:
    pool = _redis_pool_holder()
    for client in pool.values():
        await client.aclose()
    pool.clear()


# --- Repositories ---


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_session_repository(db: DbSession) -> SessionRepository:
    return SessionRepository(db)


def get_message_repository(db: DbSession) -> MessageRepository:
    return MessageRepository(db)


def get_rag_chunk_repository(db: DbSession) -> RagChunkRepository:
    return RagChunkRepository(db)


def get_refresh_token_repository(db: DbSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(db)


def get_tool_invocation_repository(db: DbSession) -> ToolInvocationRepository:
    return ToolInvocationRepository(db)


# --- Repositories: ScoreWise ---


def get_paper_repository(db: DbSession) -> PaperRepository:
    return PaperRepository(db)


def get_question_repository(db: DbSession) -> QuestionRepository:
    return QuestionRepository(db)


def get_syllabus_document_repository(db: DbSession) -> SyllabusDocumentRepository:
    return SyllabusDocumentRepository(db)


def get_attempt_repository(db: DbSession) -> AttemptRepository:
    return AttemptRepository(db)


def get_tutor_message_repository(db: DbSession) -> TutorMessageRepository:
    return TutorMessageRepository(db)


# --- Services ---


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_token_repo: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
    settings: SettingsDep,
) -> AuthService:
    return AuthService(user_repo, refresh_token_repo, settings)


def get_session_service(
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
) -> SessionService:
    return SessionService(session_repo)


def get_rag_service(
    rag_chunk_repo: Annotated[RagChunkRepository, Depends(get_rag_chunk_repository)],
    settings: SettingsDep,
) -> RagService:
    return RagService(rag_chunk_repo, settings)


def get_tool_service(
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    invocation_repo: Annotated[ToolInvocationRepository, Depends(get_tool_invocation_repository)],
    settings: SettingsDep,
) -> ToolService:
    return ToolService(rag_service, invocation_repo, settings)


def get_title_service(settings: SettingsDep) -> TitleService:
    return TitleService(settings)


def get_chat_service(
    message_repo: Annotated[MessageRepository, Depends(get_message_repository)],
    session_repo: Annotated[SessionRepository, Depends(get_session_repository)],
    rag_service: Annotated[RagService, Depends(get_rag_service)],
    tool_service: Annotated[ToolService, Depends(get_tool_service)],
    title_service: Annotated[TitleService, Depends(get_title_service)],
    settings: SettingsDep,
) -> ChatService:
    return ChatService(message_repo, session_repo, rag_service, tool_service, title_service, settings)


# --- Services: ScoreWise ---


def get_paper_service(
    paper_repo: Annotated[PaperRepository, Depends(get_paper_repository)],
    question_repo: Annotated[QuestionRepository, Depends(get_question_repository)],
) -> PaperService:
    return PaperService(paper_repo, question_repo)


def get_attempt_service(
    attempt_repo: Annotated[AttemptRepository, Depends(get_attempt_repository)],
    paper_repo: Annotated[PaperRepository, Depends(get_paper_repository)],
    question_repo: Annotated[QuestionRepository, Depends(get_question_repository)],
) -> AttemptService:
    return AttemptService(attempt_repo, paper_repo, question_repo)


def get_syllabus_ingestion_service(
    syllabus_document_repo: Annotated[SyllabusDocumentRepository, Depends(get_syllabus_document_repository)],
    settings: SettingsDep,
) -> SyllabusIngestionService:
    return SyllabusIngestionService(syllabus_document_repo, settings)


def get_tutor_rag_service(
    question_repo: Annotated[QuestionRepository, Depends(get_question_repository)],
    tutor_message_repo: Annotated[TutorMessageRepository, Depends(get_tutor_message_repository)],
    syllabus_document_repo: Annotated[SyllabusDocumentRepository, Depends(get_syllabus_document_repository)],
    settings: SettingsDep,
) -> TutorRagService:
    return TutorRagService(question_repo, tutor_message_repo, syllabus_document_repo, settings)


# --- Auth ---


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: SettingsDep,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    if not token:
        raise UnauthorizedError("Not authenticated.")
    try:
        payload = decode_access_token(token, settings)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired access token.") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid access token.")

    user = await user_repo.get_by_id(UUID(user_id))
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# --- Rate limiting (§8) — Redis-backed so limits hold across all worker
# processes/instances; a hand-rolled INCR+EXPIRE fixed-window counter behind a
# FastAPI dependency, testable/mockable like any other dependency. ---


async def _check_rate_limit(client: redis.Redis, key: str, limit: int, window_s: int) -> None:
    current = await client.incr(key)
    if current == 1:
        await client.expire(key, window_s)
    if current > limit:
        ttl = await client.ttl(key)
        raise RateLimitedError("Rate limit exceeded.", retry_after=max(ttl, 1))


def rate_limit_per_user(scope: str, limit: int, window_s: int = 60):
    """Per-user limiter for authenticated routes (§8 table, per-user rows)."""

    async def _dependency(
        current_user: CurrentUser,
        redis_client: Annotated[redis.Redis, Depends(get_redis)],
    ) -> None:
        key = f"ratelimit:{scope}:user:{current_user.id}"
        await _check_rate_limit(redis_client, key, limit, window_s)

    return _dependency


def rate_limit_per_ip(scope: str, limit: int, window_s: int = 60):
    """Per-IP limiter, applied before auth succeeds (login/register) so it must
    key on IP, not user (§8 table, per-IP row)."""

    async def _dependency(
        request: Request,
        redis_client: Annotated[redis.Redis, Depends(get_redis)],
    ) -> None:
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        key = f"ratelimit:{scope}:ip:{client_ip}"
        await _check_rate_limit(redis_client, key, limit, window_s)

    return _dependency
