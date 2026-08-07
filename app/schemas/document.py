from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    """Body for URL ingestion; file uploads use multipart form data instead
    (handled by the router directly, not via this schema)."""

    url: str = Field(min_length=1)


class DocumentOut(BaseModel):
    id: UUID
    source: str
    chunk_count: int
    indexed_at: datetime

    model_config = {"from_attributes": True}
