from __future__ import annotations

import pytest

from document_extraction import DocumentExtractionError, DocumentExtractionService, ExtractionMethod
from document_extraction.heuristics import score_completeness

# Minimal hand-written single-page PDF with a real text-showing content
# stream (no reportlab/fpdf dependency needed just for a fixture). pypdf
# repairs the deliberately-wrong startxref offset via its object-stream
# fallback parser, same as it would for a real-world malformed upload.
_PDF_WITH_TEXT_LAYER = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length 176>>
stream
BT /F1 12 Tf 10 180 Td (This is a long enough passage of body text used only to clear the extraction completeness heuristic threshold set in this unit test fixture file.) Tj ET
endstream
endobj
trailer<</Size 6/Root 1 0 R>>
startxref
0
%%EOF"""

# Same page structure but with an empty content stream -- simulates a
# scanned page with no embedded text layer at all.
_PDF_WITHOUT_TEXT_LAYER = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Resources<<>>/MediaBox[0 0 200 200]/Contents 5 0 R>>endobj
5 0 obj<</Length 0>>
stream
endstream
endobj
trailer<</Size 6/Root 1 0 R>>
startxref
0
%%EOF"""


def _service(vision_extractor=None) -> DocumentExtractionService:
    return DocumentExtractionService(
        anthropic_api_key="test-key",
        anthropic_model="claude-sonnet-5",
        vision_extractor=vision_extractor,
    )


async def _unused_vision_extractor(pdf_bytes: bytes, filename: str) -> str:
    raise AssertionError("vision extractor should not be called for a usable text layer")


async def test_uses_text_layer_when_present_and_never_touches_vision() -> None:
    service = _service(vision_extractor=_unused_vision_extractor)
    result = await service.extract(_PDF_WITH_TEXT_LAYER, "paper.pdf")

    assert result.method == ExtractionMethod.TEXT_LAYER
    assert result.text is not None and "long enough passage of body text" in result.text
    assert result.page_count == 1
    assert result.confidence_hint is not None and 0.0 < result.confidence_hint <= 1.0
    assert result.raw_pdf_bytes == _PDF_WITH_TEXT_LAYER
    assert result.filename == "paper.pdf"


async def test_falls_back_to_vision_when_text_layer_is_empty() -> None:
    async def fake_vision(pdf_bytes: bytes, filename: str) -> str:
        assert pdf_bytes == _PDF_WITHOUT_TEXT_LAYER
        assert filename == "scanned.pdf"
        return "transcribed by claude"

    service = _service(vision_extractor=fake_vision)
    result = await service.extract(_PDF_WITHOUT_TEXT_LAYER, "scanned.pdf")

    assert result.method == ExtractionMethod.VISION
    assert result.text == "transcribed by claude"
    assert result.confidence_hint is None
    assert result.raw_pdf_bytes == _PDF_WITHOUT_TEXT_LAYER


async def test_vision_failure_raises_document_extraction_error() -> None:
    async def failing_vision(pdf_bytes: bytes, filename: str) -> str:
        raise DocumentExtractionError("upstream timed out")

    service = _service(vision_extractor=failing_vision)
    with pytest.raises(DocumentExtractionError):
        await service.extract(_PDF_WITHOUT_TEXT_LAYER, "scanned.pdf")


async def test_unreadable_file_raises_before_any_vision_call() -> None:
    service = _service(vision_extractor=_unused_vision_extractor)
    with pytest.raises(DocumentExtractionError):
        await service.extract(b"this is definitely not a pdf", "junk.pdf")


# --- score_completeness: pure-function heuristic edge cases, no PDF needed ---


def test_completeness_accepts_dense_uniform_pages() -> None:
    pages = ["word " * 200, "word " * 200, "word " * 200]  # ~1000 chars/page
    is_complete, confidence = score_completeness(pages)
    assert is_complete is True
    assert confidence == 1.0


def test_completeness_rejects_sparse_pages() -> None:
    pages = ["a short stamp", "", ""]
    is_complete, _ = score_completeness(pages)
    assert is_complete is False


def test_completeness_rejects_partially_scanned_document_even_with_good_average() -> None:
    # One dense page drags the *average* well above the per-page threshold,
    # but half the pages are empty -- exactly the case an aggregate-only
    # heuristic would miss.
    pages = ["word " * 400, ""]  # ~2000 chars on page 1, 0 on page 2 -> avg ~1000
    is_complete, _ = score_completeness(pages)
    assert is_complete is False


def test_completeness_rejects_empty_document() -> None:
    is_complete, confidence = score_completeness([])
    assert is_complete is False
    assert confidence == 0.0
