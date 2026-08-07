from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.deps import DbSession, SettingsDep
from app.llm.anthropic_client import get_llm
from app.schemas.common import HealthOut, ReadyChecks, ReadyOut, VersionOut

router = APIRouter(tags=["health"])

API_VERSION = "1.0.0"


@router.get("/healthz", response_model=HealthOut)
async def healthz() -> HealthOut:
    """Liveness — process is up. No auth. Kept separate from /readyz on purpose:
    a load balancer should stop routing to a pod that's up but DB-less without
    killing/restarting it, which healthz failing would trigger (§12)."""
    return HealthOut(status="ok")


@router.get("/readyz", response_model=ReadyOut)
async def readyz(db: DbSession, settings: SettingsDep, response: Response) -> ReadyOut:
    """Readiness — DB reachable + LLM client constructible. No auth."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    llm_status = "ok"
    try:
        get_llm(settings)
    except Exception:
        llm_status = "error"

    checks = ReadyChecks(db=db_status, llm=llm_status)
    if db_status != "ok" or llm_status != "ok":
        response.status_code = 503
    return ReadyOut(status="ready", checks=checks)


@router.get("/api/v1/version", response_model=VersionOut)
async def version() -> VersionOut:
    """Build/version info for client/ops visibility. No auth."""
    import os

    git_sha = os.environ.get("GIT_SHA", "unknown")
    return VersionOut(api_version=API_VERSION, git_sha=git_sha)
