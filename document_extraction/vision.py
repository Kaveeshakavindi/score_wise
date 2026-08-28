from __future__ import annotations

import base64

from anthropic import APIError, APIStatusError, APITimeoutError, AsyncAnthropic

from document_extraction.models import DocumentExtractionError

_TRANSCRIBE_INSTRUCTION = (
    "Transcribe every page of this document into plain text, in reading "
    "order. Preserve paragraph breaks and page order. Do not summarize, "
    "comment on, or omit any content -- output the raw transcription only, "
    "no preamble."
)


async def extract_via_vision(
    pdf_bytes: bytes,
    filename: str,
    *,
    api_key: str,
    model: str,
    timeout_s: float,
) -> str:
    """One-shot Claude document-block transcription -- the only network call
    this package ever makes, and only reached once DocumentExtractionService
    has already determined pypdf's text layer is unusable. Uses the raw
    anthropic SDK directly (not langchain) so this package's only
    dependencies are pypdf + anthropic, importable with no FastAPI/
    SQLAlchemy/langchain coupling. Raises DocumentExtractionError on any
    SDK-level failure rather than leaking anthropic's own exception types
    out of this package's public surface."""
    client = AsyncAnthropic(api_key=api_key, timeout=timeout_s)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": _TRANSCRIBE_INSTRUCTION},
                    ],
                }
            ],
        )
    except (APITimeoutError, APIStatusError, APIError) as exc:
        raise DocumentExtractionError(f"Vision transcription of {filename!r} failed: {exc}") from exc

    return "".join(block.text for block in response.content if block.type == "text")
