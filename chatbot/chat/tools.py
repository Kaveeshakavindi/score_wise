from __future__ import annotations

import urllib.request
from datetime import datetime
from pathlib import Path
import re

from langchain_core.tools import tool
from chat.rag import index_text


@tool
def get_current_time() -> str:
    """Return the current local time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a local text file by path (workspace only)."""
    root = Path(__file__).resolve().parents[2]
    requested = Path(path)
    if not requested.is_absolute():
        requested = root / requested
    try:
        requested = requested.resolve()
        requested.relative_to(root)
    except Exception:
        return "Error: path is outside the project workspace."

    if not requested.exists():
        return "Error: file not found."
    if not requested.is_file():
        return "Error: path is not a file."

    text = requested.read_text(encoding="utf-8", errors="replace")
    if max_chars > 0:
        text = text[:max_chars]
    index_note = ""
    try:
        count = index_text(str(requested), text)
        index_note = f"\n\n[Indexed {count} chunks from {requested}]"
    except Exception as exc:
        index_note = f"\n\n[Indexing failed: {exc}]"
    return text + index_note

@tool
def fetch_url(url: str, max_chars: int = 2000, timeout_s: int = 8) -> str:
    """Fetch text content from a URL via HTTP GET."""
    if not url.startswith(("http://", "https://")):
        return "Error: only http(s) URLs are allowed."

    req = urllib.request.Request(url, headers={"User-Agent": "custom-chatbot/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        content_type = resp.headers.get("Content-Type", "")
        raw = resp.read()

    text = raw.decode("utf-8", errors="replace")
    if max_chars > 0:
        text = text[:max_chars]

    if content_type:
        return f"Content-Type: {content_type}\n{text}"
    return text

@tool
def read_url(url: str, max_chars: int = 8000, timeout_s: int = 8) -> str:
    """Read a website URL and return cleaned text (best-effort)."""
    if not url.startswith(("http://", "https://")):
        return "Error: only http(s) URLs are allowed."

    req = urllib.request.Request(url, headers={"User-Agent": "custom-chatbot/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()

    text = raw.decode("utf-8", errors="replace")
    text = _strip_html(text)
    if max_chars > 0:
        text = text[:max_chars]
    index_note = ""
    try:
        count = index_text(url, text)
        index_note = f"\n\n[Indexed {count} chunks from {url}]"
    except Exception as exc:
        index_note = f"\n\n[Indexing failed: {exc}]"
    return text + index_note


def _strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_tools():
    return [get_current_time, read_file, read_url, fetch_url]
