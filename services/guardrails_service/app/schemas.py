"""Wire schemas for the guardrails service.

Mirrors the shared `GuardrailResult` shape but exposes them at the local
import path so the FastAPI app can declare them as response models without
depending on the shared package being installed.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GuardrailCheckRequest(BaseModel):
    text: str


class GuardrailCheckResponse(BaseModel):
    passed: bool
    reason: Optional[str] = None
    safe_text: Optional[str] = None
    matched_rules: list[str] = []
