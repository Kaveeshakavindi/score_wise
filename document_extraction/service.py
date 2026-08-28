from __future__ import annotations

from typing import Awaitable, Callable

from document_extraction.heuristics import read_pages, score_completeness
from document_extraction.models import ExtractionMethod, ExtractionResult
from document_extraction.vision import extract_via_vision

VisionExtractor = Callable[[bytes, str], Awaitable[str]]


class DocumentExtractionService:
    """Two-tier PDF text extraction: pypdf's embedded text layer first
    (cheap, instant), falling through to a one-shot Claude document-block
    transcription only when the text layer fails a completeness heuristic
    (scanned pages, partially scanned pages, near-empty layer). Depends only
    on pypdf + the anthropic SDK -- no langchain, no FastAPI, no
    SQLAlchemy -- so it's importable from anywhere, not just this app."""

    def __init__(
        self,
        *,
        anthropic_api_key: str,
        anthropic_model: str,
        vision_timeout_s: float = 60.0,
        vision_extractor: VisionExtractor | None = None,
    ) -> None:
        self._anthropic_api_key = anthropic_api_key
        self._anthropic_model = anthropic_model
        self._vision_timeout_s = vision_timeout_s
        # Injectable so tests can stub the network call out entirely rather
        # than mocking the anthropic SDK client.
        self._vision_extractor = vision_extractor or self._default_vision_extractor

    async def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        pages = read_pages(pdf_bytes)
        is_complete, confidence = score_completeness(pages)

        if is_complete:
            text = "\n\n".join(p for p in pages if p.strip())
            return ExtractionResult(
                text=text,
                method=ExtractionMethod.TEXT_LAYER,
                raw_pdf_bytes=pdf_bytes,
                page_count=len(pages),
                confidence_hint=confidence,
                filename=filename,
            )

        text = await self._vision_extractor(pdf_bytes, filename)
        return ExtractionResult(
            text=text,
            method=ExtractionMethod.VISION,
            raw_pdf_bytes=pdf_bytes,
            page_count=len(pages),
            confidence_hint=None,
            filename=filename,
        )

    async def _default_vision_extractor(self, pdf_bytes: bytes, filename: str) -> str:
        return await extract_via_vision(
            pdf_bytes,
            filename,
            api_key=self._anthropic_api_key,
            model=self._anthropic_model,
            timeout_s=self._vision_timeout_s,
        )
