from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SyllabusDocument


class SyllabusDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        document_id: uuid.UUID | None,
        filename: str,
        subject: str,
        topic: str | None,
        chunk_count: int,
    ) -> SyllabusDocument:
        document = SyllabusDocument(
            id=document_id or uuid.uuid4(),
            filename=filename,
            subject=subject,
            topic=topic,
            chunk_count=chunk_count,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def list_all(self, *, limit: int, offset: int) -> list[SyllabusDocument]:
        result = await self._session.execute(
            select(SyllabusDocument).order_by(SyllabusDocument.uploaded_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def count_all(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(SyllabusDocument))
        return int(result.scalar_one())

    async def get_by_id(self, document_id: uuid.UUID) -> SyllabusDocument | None:
        return await self._session.get(SyllabusDocument, document_id)

    async def get_many_by_ids(self, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, SyllabusDocument]:
        """Used by TutorRagService to resolve citation filenames for a batch
        of retrieved chunks in one round trip rather than N lookups."""
        if not document_ids:
            return {}
        result = await self._session.execute(select(SyllabusDocument).where(SyllabusDocument.id.in_(document_ids)))
        return {d.id: d for d in result.scalars().all()}

    async def delete(self, document_id: uuid.UUID) -> None:
        await self._session.execute(delete(SyllabusDocument).where(SyllabusDocument.id == document_id))
