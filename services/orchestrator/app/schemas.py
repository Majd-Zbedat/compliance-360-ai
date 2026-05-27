"""Wire schemas for the orchestrator API (consumed by the Next.js dashboard)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditCreateRequest(BaseModel):
    filename: str
    document_b64: str = Field(..., description="Base64-encoded PDF contents")
    parties: list[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    requester: Optional[str] = None


class FindingOut(BaseModel):
    contract_clause_id: str
    matched_regulatory_clause_id: Optional[str] = None
    matched_regulatory_source: Optional[str] = None
    matched_regulatory_article: Optional[str] = None
    verdict: str
    risk: str
    justification: str
    confidence: float
    safe_justification: Optional[str] = None


class ClauseOut(BaseModel):
    id: str
    contract_id: str
    section: str
    text: str
    clause_type: str
    page: Optional[int] = None


class AuditSummary(BaseModel):
    id: str
    filename: str
    status: str
    overall_risk: str
    findings_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: datetime
    requester: Optional[str] = None


class AuditDetail(BaseModel):
    id: str
    filename: str
    status: str
    overall_risk: str
    parties: list[str] = []
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    requester: Optional[str] = None
    clauses: list[ClauseOut] = []
    findings: list[FindingOut] = []
    report_markdown: Optional[str] = None
    safe_report_markdown: Optional[str] = None
    input_guardrail_passed: bool = True
    output_guardrail_passed: bool = True
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StatsResponse(BaseModel):
    total_audits: int
    audits_last_7d: int
    high_risk_findings: int
    medium_risk_findings: int
    low_risk_findings: int
    avg_findings_per_audit: float
    rejection_rate: float
    by_overall_risk: dict[str, int]


class RegulationOut(BaseModel):
    id: str
    source: str
    article: str
    title: Optional[str] = None
    text: str
    tags: list[str] = []


# ---------------------------------------------------------------------------
# Compliance Chat (RAG Q&A)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(..., description="Free-text compliance question")
    top_k: int = Field(5, ge=1, le=20, description="Number of clauses to retrieve")
    sources: Optional[list[str]] = Field(
        default=None,
        description="Restrict retrieval to specific regulatory sources, e.g. ['GDPR']",
    )


class ChatSource(BaseModel):
    id: str
    source: str
    article: str
    title: Optional[str] = None
    text: str
    score: float


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[ChatSource]
