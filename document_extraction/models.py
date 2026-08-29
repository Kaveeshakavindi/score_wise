from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExtractionMethod(str, Enum):
    """How `DocumentExtractionService.extract` obtained a document's text.
    TEXT_LAYER means pypdf's embedded text layer passed the completeness
    heuristic and `text` came from that layer -- free, instant. VISION means
    no usable text layer was found (scanned pages, partially scanned pages,
    or a mostly-empty layer), so `text` came from a one-shot Claude
    document-block transcription instead -- the only network call this
    package ever makes, and only reached when the cheap path fails."""

    TEXT_LAYER = "text_layer"
    VISION = "vision"


@dataclass(frozen=True)
class ExtractionResult:
    """Result of one `extract()` call. `raw_pdf_bytes` and `page_count` are
    always populated -- even on TEXT_LAYER results -- so a caller that wants
    to do its own richer vision call later (e.g. structured extraction, not
    just transcription) never has to re-read the upload. `confidence_hint`
    is a coarse, deliberately simple 0.0-1.0 signal derived from the
    completeness heuristic -- not a calibrated probability -- and is None
    for VISION results, since nothing was scored there."""

    text: str | None
    method: ExtractionMethod
    raw_pdf_bytes: bytes
    page_count: int
    confidence_hint: float | None
    filename: str


class DocumentExtractionError(Exception):
    """Raised when extraction can't produce text at all: the file isn't a
    parseable PDF (pypdf can't even open it), or the vision fallback call
    itself fails (timeout, rate limit, API error). Distinct from "no text
    layer", which is a normal, silent trigger for the VISION path, not an
    error."""
