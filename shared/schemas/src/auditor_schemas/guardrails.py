"""Schemas exchanged with the guardrails service."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class GuardrailKind(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class GuardrailRequest(BaseModel):
    text: str
    kind: GuardrailKind = GuardrailKind.INPUT


class GuardrailResult(BaseModel):
    """Mirrors the PDF's `Output` schema: { pass, reason, safe_text }.

    `safe_text` is only meaningful for output checks where the guard rewrote
    the report to remove unqualified legal advice.
    """

    passed: bool
    reason: Optional[str] = None
    safe_text: Optional[str] = None
    matched_rules: list[str] = []
