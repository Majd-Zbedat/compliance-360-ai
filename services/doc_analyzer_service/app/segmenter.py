"""Heuristic contract clause segmenter.

We split extracted PDF text into clauses using simple but reliable cues
that show up across the vast majority of contract templates:

  * Numbered headings:  `1.`, `1.1`, `1.1.1`, `1)`, `(a)`
  * Keyword headings:   `Article 4`, `Section 12`, `Clause 3.2`
  * ALL-CAPS headings followed by a body (e.g. `CONFIDENTIALITY`)

After segmenting, we tag each clause with a coarse `clause_type` based on
keyword density (liability, indemnity, data_processing, termination,
payment, governing_law, confidentiality, ip, other).

PyTorch / LayoutLM fine-tuning is the next iteration — see plan.md.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Iterable, Optional

_HEADING_PATTERNS = [
    re.compile(r"^(?P<num>\d+(?:\.\d+){0,3})[.)]\s+(?P<rest>.+)$"),
    re.compile(
        r"^(?P<num>(?:Article|Section|Clause|ARTICLE|SECTION|CLAUSE)\s+\d+(?:\.\d+)?)\b[:.\-\s]*"
        r"(?P<rest>.*)$"
    ),
    re.compile(r"^(?P<num>[A-Z][A-Z &/'-]{4,80})\s*$"),  # ALL-CAPS heading on its own line
]

_CLAUSE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "liability": ("liability", "liable", "damages", "consequential", "indirect loss"),
    "indemnity": ("indemnify", "indemnification", "hold harmless"),
    "data_processing": (
        "personal data",
        "data protection",
        "gdpr",
        "data subject",
        "processor",
        "controller",
        "privacy",
    ),
    "termination": ("terminate", "termination", "notice period", "expiry"),
    "payment": ("invoice", "payment", "fees", "remuneration", "late payment"),
    "governing_law": ("governing law", "jurisdiction", "courts of", "venue"),
    "confidentiality": ("confidential", "non-disclosure", "trade secret"),
    "ip": ("intellectual property", "copyright", "patent", "trademark", "moral rights"),
    "security": ("encryption", "access control", "vulnerability", "iso 27001"),
}


@dataclass
class _Heading:
    line_idx: int
    label: str


def _find_headings(lines: list[str]) -> list[_Heading]:
    headings: list[_Heading] = []
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line or len(line) > 160:
            continue
        for pat in _HEADING_PATTERNS:
            m = pat.match(line)
            if not m:
                continue
            num = m.group("num").strip()
            rest = (m.groupdict().get("rest") or "").strip()
            label = f"{num} {rest}".strip() if rest else num
            headings.append(_Heading(line_idx=i, label=label))
            break
    return headings


def _classify(text: str, section: str = "") -> str:
    haystack = (text + " " + section).lower()
    best_label = "other"
    best_score = 0
    for label, keywords in _CLAUSE_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_label = label
    return best_label


def segment(
    text: str,
    contract_id: str,
    page_offsets: Optional[list[int]] = None,
    min_chars: int = 40,
) -> list[dict]:
    """Split `text` into clause dicts.

    `page_offsets` (optional): list giving the character index at which
    each 1-indexed page starts in `text`. Used to attribute clauses to pages.
    """
    lines = text.split("\n")
    headings = _find_headings(lines)

    if not headings:
        body = text.strip()
        if len(body) < min_chars:
            return []
        return [_make_clause(contract_id, "Preamble", body, page=_page_for_offset(0, page_offsets))]

    clauses: list[dict] = []

    # Capture the preamble — everything before the first heading. This is where
    # cover-page metadata tables live (Contract ID, dates, parties, status…),
    # which would otherwise be discarded and never reach the auditor.
    preamble = "\n".join(lines[: headings[0].line_idx]).strip()
    if len(preamble) >= min_chars:
        clauses.append(
            _make_clause(
                contract_id,
                "Document Header",
                preamble,
                page=_page_for_offset(0, page_offsets),
            )
        )

    for idx, heading in enumerate(headings):
        body_start_line = heading.line_idx + 1
        body_end_line = headings[idx + 1].line_idx if idx + 1 < len(headings) else len(lines)
        body = "\n".join(lines[body_start_line:body_end_line]).strip()
        if len(body) < min_chars:
            continue
        char_offset = sum(len(line) + 1 for line in lines[:body_start_line])
        clauses.append(
            _make_clause(
                contract_id,
                heading.label,
                body,
                page=_page_for_offset(char_offset, page_offsets),
            )
        )
    return clauses


def _make_clause(contract_id: str, section: str, body: str, page: Optional[int]) -> dict:
    return {
        "id": f"{contract_id}-{uuid.uuid4().hex[:8]}",
        "contract_id": contract_id,
        "section": section[:200],
        "text": body,
        "clause_type": _classify(body, section),
        "page": page,
    }


def _page_for_offset(char_offset: int, page_offsets: Optional[list[int]]) -> Optional[int]:
    if not page_offsets:
        return None
    page = 1
    for i, off in enumerate(page_offsets, start=1):
        if char_offset >= off:
            page = i
        else:
            break
    return page


def chunks(items: Iterable[dict], size: int):
    """Tiny helper for callers that need to batch-upsert."""
    buf: list[dict] = []
    for it in items:
        buf.append(it)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf
