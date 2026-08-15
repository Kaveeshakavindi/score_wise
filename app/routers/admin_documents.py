from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.deps import CurrentUser, SettingsDep, get_syllabus_ingestion_service, rate_limit_per_user
from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError
from app.schemas.common import Page
from app.schemas.syllabus_document import SyllabusDocumentOut
from app.services.syllabus_ingestion_service import SyllabusIngestionService

router = APIRouter(
    prefix="/api/v1/admin/documents",
    tags=["admin-documents"],
    dependencies=[Depends(rate_limit_per_user("admin_documents", limit=10, window_s=60))],
)

IngestionServiceDep = Annotated[SyllabusIngestionService, Depends(get_syllabus_ingestion_service)]


@router.post("", response_model=SyllabusDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_syllabus_document(
    current_user: CurrentUser,
    ingestion_service: IngestionServiceDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    subject: Annotated[str, Form()],
    grade_level: Annotated[str, Form()],
    document_uuid: Annotated[UUID | None, Form(alias="uuid")] = None,
) -> SyllabusDocumentOut:
    """Upload one syllabus PDF: extract -> chunk -> embed -> store in
    ChromaDB, and record the upload in SQL (§2). PDF only — other content
    types get `415`. `413` if the file exceeds MAX_SYLLABUS_UPLOAD_BYTES
    (default 20MB). `409` if `uuid` is supplied and already used by another
    document.

    Requires standard authentication only — the current auth system has no
    admin-role concept, and auth is explicitly out of scope for this change,
    so this is gated the same as every other protected route rather than a
    genuine admin check. Implemented as a real, reusable endpoint (not a
    one-off script) so syllabus corrections/additions don't need a redeploy.
    """
    if file.content_type != "application/pdf":
        raise UnsupportedMediaTypeError("Only PDF files are accepted.")

    raw = await file.read()
    if len(raw) > settings.max_syllabus_upload_bytes:
        raise PayloadTooLargeError(f"Upload exceeded the {settings.max_syllabus_upload_bytes}-byte limit.")

    document = await ingestion_service.ingest_pdf(
        document_id=document_uuid,
        filename=file.filename or "syllabus.pdf",
        subject=subject,
        # The endpoint's request field is named `grade_level`; storage names
        # it `topic` — see SyllabusDocumentOut's docstring for why these are
        # reconciled to the same value.
        topic=grade_level,
        pdf_bytes=raw,
    )
    return SyllabusDocumentOut.model_validate(document)


@router.get("", response_model=Page[SyllabusDocumentOut])
async def list_syllabus_documents(
    current_user: CurrentUser,
    ingestion_service: IngestionServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SyllabusDocumentOut]:
    """List uploaded syllabus documents and their chunk counts. Requires auth."""
    items, total = await ingestion_service.list_documents(limit=limit, offset=offset)
    return Page(items=[SyllabusDocumentOut.model_validate(d) for d in items], total=total, limit=limit, offset=offset)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_syllabus_document(
    document_id: UUID, current_user: CurrentUser, ingestion_service: IngestionServiceDep
) -> Response:
    """Remove a syllabus document and its chunks from both SQL and ChromaDB
    (needed if a wrong/duplicate file gets uploaded, §2). Requires auth.
    `404` if the document doesn't exist."""
    await ingestion_service.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
