from __future__ import annotations

import io

from pypdf import PdfReader

from app.core.exceptions import ValidationError


def extract_text_from_pdf(data: bytes) -> str:
    """Extracts and concatenates text from every page of a PDF (§2 step 1).
    Raises ValidationError on an unreadable file or one with no extractable
    text, rather than letting a cryptic parser exception escape to the
    client."""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf raises assorted error types for malformed input
        raise ValidationError("File is not a readable PDF.") from exc

    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            continue  # one corrupt/unparseable page shouldn't fail the whole upload

    text = "\n\n".join(t for t in pages_text if t.strip())
    if not text.strip():
        raise ValidationError("No extractable text was found in this PDF.")
    return text
