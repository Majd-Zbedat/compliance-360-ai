"""Wire schemas specific to the doc-analyzer service."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AnalyseRequest(BaseModel):
    contract_id: str = Field(..., description="Caller-provided id; used to namespace clauses")
    filename: str
    document_b64: str = Field(..., description="Base64-encoded PDF contents")


class AnalysedClause(BaseModel):
    id: str
    contract_id: str
    section: str
    text: str
    clause_type: str
    page: Optional[int] = None


class AnalyseResponse(BaseModel):
    contract_id: str
    filename: str
    page_count: int
    raw_text_chars: int
    clauses: list[AnalysedClause]
