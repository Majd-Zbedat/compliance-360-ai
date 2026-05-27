"""PDF text extractor wrapping pdfplumber with a plain-text fallback."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    full_text: str
    page_count: int
    page_offsets: list[int]


def extract_from_b64(b64: str) -> ExtractedDocument:
    raw = base64.b64decode(b64)
    return extract_from_bytes(raw)


def extract_from_bytes(raw: bytes) -> ExtractedDocument:
    """Try pdfplumber; if the payload is not a PDF, treat it as UTF-8 text."""
    try:
        import pdfplumber
    except Exception as exc:
        raise RuntimeError(f"pdfplumber unavailable: {exc}") from exc

    if raw[:5] != b"%PDF-":
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        return ExtractedDocument(full_text=text, page_count=1, page_offsets=[0])

    page_texts: list[str] = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            page_texts.append(page.extract_text() or "")

    offsets: list[int] = []
    running = 0
    for pt in page_texts:
        offsets.append(running)
        running += len(pt) + 2  # account for joiner

    full = "\n\n".join(page_texts)
    return ExtractedDocument(full_text=full, page_count=len(page_texts), page_offsets=offsets)
