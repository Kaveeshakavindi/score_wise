from __future__ import annotations

import io

from pypdf import PdfReader

from document_extraction.models import DocumentExtractionError

# Below this many characters per page on average, a text layer is treated as
# absent/unusable rather than real body text (e.g. pypdf pulling a handful
# of stray characters off a scanned page's embedded artifacts or a stamp).
MIN_CHARS_PER_PAGE = 120

# A page under this many characters counts as "empty" for the per-page
# coverage check below -- catches documents where only some pages are
# scanned images, which an aggregate average alone would miss.
MIN_CHARS_PER_NONEMPTY_PAGE = 40

# If more than this fraction of pages are empty, the text layer is rejected
# even if the *average* chars-per-page looks fine (dragged up by a few
# text-heavy pages while the rest are scanned images).
MAX_EMPTY_PAGE_FRACTION = 0.2

# confidence_hint = min(1.0, chars_per_page / TARGET_CHARS_PER_PAGE).
TARGET_CHARS_PER_PAGE = 800


def read_pages(pdf_bytes: bytes) -> list[str]:
    """Per-page text via pypdf's embedded text layer. Empty string for a
    page that errors out or has nothing extractable -- one corrupt page
    shouldn't sink the whole document. Raises DocumentExtractionError only
    if the file isn't a readable PDF at all."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:  # pypdf raises assorted error types for malformed input
        raise DocumentExtractionError("File is not a readable PDF.") from exc

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def score_completeness(pages: list[str]) -> tuple[bool, float]:
    """Decides whether a text layer is complete enough to trust, and a
    coarse 0.0-1.0 confidence_hint for it. Two independent checks, both must
    pass: (1) average chars/page clears MIN_CHARS_PER_PAGE, (2) no more than
    MAX_EMPTY_PAGE_FRACTION of pages are near-empty -- catches partially
    scanned documents that a single aggregate average would hide."""
    if not pages:
        return False, 0.0

    total_chars = sum(len(p) for p in pages)
    chars_per_page = total_chars / len(pages)

    empty_pages = sum(1 for p in pages if len(p) < MIN_CHARS_PER_NONEMPTY_PAGE)
    empty_fraction = empty_pages / len(pages)

    is_complete = chars_per_page >= MIN_CHARS_PER_PAGE and empty_fraction <= MAX_EMPTY_PAGE_FRACTION
    confidence = min(1.0, chars_per_page / TARGET_CHARS_PER_PAGE)
    return is_complete, confidence
