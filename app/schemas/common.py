from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyChecks(BaseModel):
    db: Literal["ok", "error"]
    llm: Literal["ok", "error"]


class ReadyOut(BaseModel):
    status: Literal["ready"]
    checks: ReadyChecks


class VersionOut(BaseModel):
    api_version: str
    git_sha: str
