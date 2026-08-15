from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.services.pdf_extraction import extract_text_from_pdf

# Minimal hand-written single-page PDF with a real text-showing content
# stream (no reportlab/fpdf dependency needed just for a test fixture).
# pypdf repairs the deliberately-wrong startxref offset via its object-stream
# fallback parser, same as it would for a real-world malformed upload.
_MINIMAL_PDF_WITH_TEXT = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length 44>>
stream
BT /F1 24 Tf 10 100 Td (Hello Syllabus) Tj ET
endstream
endobj
trailer<</Size 6/Root 1 0 R>>
startxref
0
%%EOF"""


def test_extracts_text_from_a_valid_pdf() -> None:
    text = extract_text_from_pdf(_MINIMAL_PDF_WITH_TEXT)
    assert "Hello Syllabus" in text


def test_rejects_bytes_that_are_not_a_pdf() -> None:
    with pytest.raises(ValidationError):
        extract_text_from_pdf(b"this is definitely not a pdf")


def test_rejects_empty_bytes() -> None:
    with pytest.raises(ValidationError):
        extract_text_from_pdf(b"")
