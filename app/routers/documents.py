from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.core.deps import CurrentUser, SettingsDep, get_rag_service, get_session_service, rate_limit_per_user
from app.core.exceptions import PayloadTooLargeError, ValidationError
from app.schemas.common import Page
from app.schemas.document import DocumentIngestRequest, DocumentOut
from app.services.rag_service import RagService
from app.services.session_service import SessionService
from app.services.url_fetch import fetch_url_safely, strip_html

router = APIRouter(prefix="/api/v1/sessions/{session_id}/documents", tags=["documents"])

SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
RagServiceDep = Annotated[RagService, Depends(get_rag_service)]


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_per_user("documents_ingest", limit=10, window_s=60))],
)
async def ingest_document(
    session_id: UUID,
    request: Request,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    rag_service: RagServiceDep,
    settings: SettingsDep,
) -> DocumentOut:
    """Ingest a URL or uploaded file into this session's RAG store. Requires
    auth + session ownership. 10 req/min per user (§8 — network fetch + embedding
    compute). Accepts multipart `file` **or** JSON `{"url": "..."}` (§6.5)."""
    await session_service.get_owned(current_user.id, session_id)

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        source, text = await _ingest_from_upload(request, settings.max_ingest_bytes)
    else:
        source, text = await _ingest_from_url(request, settings.max_ingest_bytes)

    document = await rag_service.index_text(session_id, source, text)
    chunk_count = await rag_service.chunk_count(document.id)
    return DocumentOut(id=document.id, source=source, chunk_count=chunk_count, indexed_at=document.indexed_at)


async def _ingest_from_upload(request: Request, max_bytes: int) -> tuple[str, str]:
    # File uploads are never resolved against a server filesystem path from
    # client input — only uploaded bytes are accepted, eliminating the
    # path-traversal surface entirely for this endpoint (§6.5).
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise ValidationError("multipart request must include a 'file' field.")

    raw = await upload.read()
    if len(raw) > max_bytes:
        raise PayloadTooLargeError(f"Upload exceeded the {max_bytes}-byte ingest limit.")

    text = raw.decode("utf-8", errors="replace")
    source = upload.filename or "uploaded-file"
    return source, text


async def _ingest_from_url(request: Request, max_bytes: int) -> tuple[str, str]:
    body = await request.json()
    payload = DocumentIngestRequest.model_validate(body)

    result = await fetch_url_safely(payload.url, max_bytes=max_bytes)
    text = result.text
    if "html" in result.content_type.lower():
        text = strip_html(text)
    return payload.url, text


@router.get("", response_model=Page[DocumentOut])
async def list_documents(
    session_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    rag_service: RagServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DocumentOut]:
    """List indexed sources for this session. Requires auth + session ownership."""
    await session_service.get_owned(current_user.id, session_id)
    documents = await rag_service.list_documents(session_id, limit=limit, offset=offset)
    total = await rag_service.count_documents(session_id)
    items = []
    for doc in documents:
        chunk_count = await rag_service.chunk_count(doc.id)
        items.append(DocumentOut(id=doc.id, source=doc.source, chunk_count=chunk_count, indexed_at=doc.indexed_at))
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    session_id: UUID,
    document_id: UUID,
    current_user: CurrentUser,
    session_service: SessionServiceDep,
    rag_service: RagServiceDep,
) -> Response:
    """Remove an indexed source and its chunks. Requires auth + session ownership."""
    await session_service.get_owned(current_user.id, session_id)
    await rag_service.delete_document(session_id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
