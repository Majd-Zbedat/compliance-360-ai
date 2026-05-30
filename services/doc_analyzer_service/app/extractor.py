"""PDF text extractor wrapping pdfplumber with optional OCR for scanned PDFs.

Extraction strategy:
  1. Non-PDF payloads are decoded as UTF-8 text.
  2. PDFs are parsed with pdfplumber (fast, accurate for digital PDFs).
  3. If pdfplumber yields little/no text (a scanned / image-only PDF) and the
     optional OCR stack (pytesseract + pdf2image + a Tesseract binary) is
     available, we fall back to OCR. Otherwise we return whatever text we have
     plus a human-readable `warning` so the UI can prompt the user to paste
     text or upload a text-based PDF.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Optional

# Below this average characters-per-page we assume the PDF is scanned/image-only.
_MIN_CHARS_PER_PAGE = 40


@dataclass
class ExtractedDocument:
    full_text: str
    page_count: int
    page_offsets: list[int]
    ocr_used: bool = False
    warning: Optional[str] = None


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

    page_count = len(page_texts) or 1
    full = "\n\n".join(page_texts)

    # A scanned / image-only PDF produces almost no extractable text.
    if len(full.strip()) < _MIN_CHARS_PER_PAGE * page_count:
        ocr_text = _try_ocr(raw)
        if ocr_text and len(ocr_text.strip()) > len(full.strip()):
            return _build(ocr_text.split("\f"), ocr_used=True)
        warning = (
            "This looks like a scanned or image-only PDF and little machine-readable "
            "text could be extracted. Install the OCR stack (pytesseract + pdf2image + "
            "Tesseract) for automatic recognition, or paste the contract text manually."
        )
        return _build(page_texts, warning=warning)

    return _build(page_texts)


def _build(
    page_texts: list[str],
    *,
    ocr_used: bool = False,
    warning: Optional[str] = None,
) -> ExtractedDocument:
    offsets: list[int] = []
    running = 0
    for pt in page_texts:
        offsets.append(running)
        running += len(pt) + 2  # account for the "\n\n" joiner
    full = "\n\n".join(page_texts)
    return ExtractedDocument(
        full_text=full,
        page_count=len(page_texts) or 1,
        page_offsets=offsets or [0],
        ocr_used=ocr_used,
        warning=warning,
    )


def _try_ocr(raw: bytes) -> Optional[str]:
    """Best-effort OCR. Returns form-feed-joined page text, or None if the
    optional OCR stack is not installed/configured."""
    try:
        import pytesseract  # type: ignore
        from pdf2image import convert_from_bytes  # type: ignore
    except Exception:
        return None
    try:
        images = convert_from_bytes(raw, dpi=200)
    except Exception:
        return None
    pages: list[str] = []
    for img in images:
        try:
            pages.append(pytesseract.image_to_string(img) or "")
        except Exception:
            pages.append("")
    text = "\f".join(pages)
    return text if text.strip() else None
