"""Schemas describing the *uploaded* contract artefact and its clauses."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContractClause(BaseModel):
    """A single discrete clause extracted from a contract PDF.

    `clause_type` is a coarse label (liability, indemnity, data_processing,
    termination, payment, governing_law, other) produced by the doc-analyzer
    heuristic. It is intentionally a free-form `str` so future LayoutLM / LLM
    classifiers can introduce new labels without a schema migration.
    """

    id: str = Field(..., description="Stable identifier within a contract")
    contract_id: str
    section: str = Field(..., description="Source section heading or numbering")
    text: str
    clause_type: str = "other"
    page: Optional[int] = None


class ContractDocument(BaseModel):
    """Metadata + extracted clauses for a single uploaded contract."""

    id: str
    filename: str
    uploaded_at: datetime
    parties: list[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    clauses: list[ContractClause] = Field(default_factory=list)
