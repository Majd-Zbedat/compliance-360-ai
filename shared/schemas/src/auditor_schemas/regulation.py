"""Schemas describing entries in the regulatory corpus."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RegulatorySource(str, Enum):
    GDPR = "GDPR"
    ISO_27001 = "ISO27001"
    LOCAL_LAW = "LocalLaw"


class RegulatoryClause(BaseModel):
    """A single regulatory clause used as a retrieval target.

    The `id` doubles as the ChromaDB document id; `embedding_id` is reserved
    for stores that disambiguate logical id from vector id.
    """

    id: str
    source: RegulatorySource
    article: str = Field(..., description="e.g. 'Art. 5(1)(c)' or 'A.8.1.3'")
    title: Optional[str] = None
    text: str
    tags: list[str] = Field(default_factory=list)
    embedding_id: Optional[str] = None
