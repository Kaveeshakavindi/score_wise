from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import SyllabusDocument
from app.llm.embedder import embed_documents, get_embedder
from app.repositories.syllabus_document_repository import SyllabusDocumentRepository
from app.services.pdf_extraction import extract_text_from_pdf
from app.services.rag_service import _chunk_text  # reused as-is — see §2 step 2, chunk_size=800/overlap=120 fit here too
from app.vectorstore import chroma_client


class SyllabusIngestionService:
    """Admin document upload pipeline (§2): extract -> chunk -> embed -> store
    in ChromaDB, and record the upload in SQL so it stays listable/deletable
    instead of a fire-and-forget vector-store write."""

    def __init__(self, repo: SyllabusDocumentRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    async def ingest_pdf(
        self,
        *,
        document_id: uuid.UUID | None,
        filename: str,
        subject: str,
        topic: str | None,
        pdf_bytes: bytes,
    ) -> SyllabusDocument:
        if document_id is not None:
            existing = await self._repo.get_by_id(document_id)
            if existing is not None:
                raise ConflictError(f"Syllabus document {document_id} already exists.")

        # Step 1: extract raw text.
        text = extract_text_from_pdf(pdf_bytes)

        # Step 2: chunk — reuses the chatbot RAG module's existing
        # chunk_size=800/overlap=120 params, which are already tuned for this
        # embedding model's ~256-token context window and worked fine for
        # prose-heavy source text; syllabus PDFs are the same kind of prose
        # content, so there's no reason to diverge.
        chunks = list(_chunk_text(text, chunk_size=800, overlap=120))

        resolved_id = document_id or uuid.uuid4()

        if chunks:
            # Step 3: embed with the existing local model (all-MiniLM-L6-v2).
            embedder = await get_embedder(self._settings.embedding_model)
            vectors = await embed_documents(embedder, chunks)

            # Step 4: store chunk + embedding + metadata in ChromaDB.
            await chroma_client.upsert_chunks(
                self._settings,
                ids=[f"{resolved_id}:{i}" for i in range(len(chunks))],
                embeddings=vectors,
                documents=chunks,
                metadatas=[
                    {
                        "subject": subject,
                        "topic": topic or "",  # Chroma metadata values can't be null
                        "source_document_id": str(resolved_id),
                        "chunk_index": i,
                    }
                    for i in range(len(chunks))
                ],
            )

        # Step 5: record the upload in SQL.
        return await self._repo.create(
            document_id=resolved_id,
            filename=filename,
            subject=subject,
            topic=topic,
            chunk_count=len(chunks),
        )

    async def list_documents(self, *, limit: int, offset: int) -> tuple[list[SyllabusDocument], int]:
        items = await self._repo.list_all(limit=limit, offset=offset)
        total = await self._repo.count_all()
        return items, total

    async def delete_document(self, document_id: uuid.UUID) -> None:
        document = await self._repo.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Syllabus document {document_id} was not found.")
        await chroma_client.delete_document_chunks(self._settings, source_document_id=str(document_id))
        await self._repo.delete(document_id)
