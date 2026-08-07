from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.deps import dispose_redis
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, logger
from app.core.middleware import RequestIDMiddleware, SecureHeadersMiddleware, TimingMiddleware
from app.db.base import dispose_engine, init_engine
from app.routers import auth, documents, health, messages, sessions, tools, ws_chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings)
    logger.info("app_startup", app_env=settings.app_env)
    try:
        yield
    finally:
        await dispose_engine()
        await dispose_redis()
        logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Custom Chatbot API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
    )

    # Middleware runs bottom-up relative to add_middleware call order, so the
    # last-added wraps the request first. Request-ID must be outermost so
    # every subsequent log line (including CORS/security-header responses)
    # carries it.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=bool(settings.cors_origin_list) and "*" not in settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    register_exception_handlers(app)

    # Routers are thin: parse/validate via schema, call one service method,
    # map result/exception to a response. No SQL, no LLM calls, no business
    # rules here (§2 layering rule).
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(messages.router)
    app.include_router(documents.router)
    app.include_router(tools.router)
    app.include_router(ws_chat.router)

    return app


app = create_app()
