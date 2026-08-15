from __future__ import annotations

from typing import Any

import anthropic
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_request_id, logger


class AppError(Exception):
    """Base of the service-layer error hierarchy. Services raise these — never a
    raw HTTPException — so services stay framework-agnostic and testable, and the
    router layer never has to know the mapping to HTTP status codes."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after: int, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)
        self.retry_after = retry_after


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "payload_too_large"


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"


class UpstreamError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "llm_upstream_error"


class UpstreamTimeoutError(AppError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    code = "llm_timeout"


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": get_request_id() or "",
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic embeds the raw exception that triggered a coercion failure
        # (e.g. a ValueError from `UUID("")`) in errors()[i]["ctx"]["error"].
        # That's not JSON-serializable, so it must be stringified before it
        # can go into the response body.
        errors = []
        for error in exc.errors():
            error = dict(error)
            ctx = error.get("ctx")
            if ctx and "error" in ctx:
                error["ctx"] = {**ctx, "error": str(ctx["error"])}
            errors.append(error)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("validation_error", "Request validation failed.", {"errors": errors}),
        )

    @app.exception_handler(anthropic.APITimeoutError)
    async def _anthropic_timeout_handler(request: Request, exc: anthropic.APITimeoutError) -> JSONResponse:
        logger.error("llm_timeout", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content=_envelope("llm_timeout", "The upstream language model timed out."),
        )

    @app.exception_handler(anthropic.RateLimitError)
    async def _anthropic_rate_limit_handler(request: Request, exc: anthropic.RateLimitError) -> JSONResponse:
        logger.error("llm_rate_limited", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_envelope("llm_rate_limited", "The upstream language model rate-limited this request."),
        )

    @app.exception_handler(anthropic.APIStatusError)
    async def _anthropic_status_handler(request: Request, exc: anthropic.APIStatusError) -> JSONResponse:
        logger.error("llm_upstream_error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=_envelope("llm_upstream_error", "The upstream language model returned an error."),
        )

    @app.exception_handler(Exception)
    async def _catch_all_handler(request: Request, exc: Exception) -> JSONResponse:
        # Full exception logged server-side with request_id; never surfaced to the client.
        logger.exception("unhandled_exception", error=str(exc), exc_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )
