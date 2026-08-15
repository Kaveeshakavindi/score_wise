from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SyllabusDocumentOut(BaseModel):
    """Note on field naming: the upload endpoint's request field is named
    `grade_level` (per the ScoreWise spec's endpoint description), but the
    same spec names the storage/Chroma-metadata field `topic`. Reconciled by
    storing the request's `grade_level` value under `topic` everywhere
    downstream — one concept, two names across the spec's sections."""

    id: UUID
    filename: str
    subject: str
    topic: str | None
    uploaded_at: datetime
    chunk_count: int

    model_config = {"from_attributes": True}
