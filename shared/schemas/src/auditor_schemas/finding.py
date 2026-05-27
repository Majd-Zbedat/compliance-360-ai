"""Schemas for the reasoning output: per-clause findings."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AMBIGUOUS = "ambiguous"


class RiskLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Finding(BaseModel):
    """One row of the audit's findings table.

    A finding always cites a *specific* regulatory clause (via id) so the
    frontend can fetch and render the exact source on demand. This satisfies
    the Explainability pillar in the project vision.
    """

    contract_clause_id: str
    matched_regulatory_clause_id: Optional[str] = None
    matched_regulatory_source: Optional[str] = None
    matched_regulatory_article: Optional[str] = None
    verdict: Verdict
    risk: RiskLevel
    justification: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    safe_justification: Optional[str] = Field(
        default=None,
        description="Guardrail-rewritten justification when the original was flagged",
    )
