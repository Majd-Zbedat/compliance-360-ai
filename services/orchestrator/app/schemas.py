"""Wire schemas for the orchestrator API (consumed by the Next.js dashboard)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditCreateRequest(BaseModel):
    filename: str = "contract.txt"
    document_b64: str = Field(
        default="",
        description="Base64-encoded PDF or UTF-8 text; optional if dataset_contract_id is set",
    )
    parties: list[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    requester: Optional[str] = None
    industry_sector: Optional[str] = Field(
        None, description="Industry context e.g. Banking, Healthcare, AI"
    )
    regulatory_focus: Optional[str] = Field(
        None, description="Preferred regulation pack e.g. GDPR, SOX/PCI, HIPAA"
    )
    contract_category: Optional[str] = Field(
        None, description="Dataset category: bank | cybersecurity | ai"
    )
    dataset_contract_id: Optional[str] = Field(
        None, description="ID of a contract row from the normalized dataset"
    )
    regulatory_sources: Optional[list[str]] = Field(
        default=None,
        description="RAG source filter, e.g. ['SOX', 'PCI_DSS']",
    )


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
    recommendation: Optional[str] = None
    clause_section: Optional[str] = None
    clause_excerpt: Optional[str] = None
    clause_type: Optional[str] = None
    regulatory_title: Optional[str] = None
    regulatory_excerpt: Optional[str] = None


class ContractMetadataOut(BaseModel):
    contract_number: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    jurisdiction: Optional[str] = None
    contract_value: Optional[str] = None
    payment_terms: Optional[str] = None
    contract_manager: Optional[str] = None
    status: Optional[str] = None
    party_a: Optional[str] = None
    party_a_address: Optional[str] = None
    party_a_regulated_by: Optional[str] = None
    party_a_lei: Optional[str] = None
    party_b: Optional[str] = None
    party_b_address: Optional[str] = None
    party_b_regulated_by: Optional[str] = None
    party_b_lei: Optional[str] = None
    party_b_abn: Optional[str] = None
    term: Optional[str] = None
    governing_law: Optional[str] = None


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
    review_status: Optional[str] = None  # Approved | Pending | Rejected | null
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
    review_status: Optional[str] = None
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
    contract_metadata: Optional[ContractMetadataOut] = None
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
    regulation_count: int = 0
    regulations_uploaded: int = 0
    pending_reviews: int = 0
    compliance_score: int = 0
    high_risk_delta_7d: int = 0
    pending_reviews_last_7d: int = 0
    compliance_score_delta: int = 0
    monthly_compliance: list[dict[str, int | str]] = Field(default_factory=list)
    last_audit_at: Optional[datetime] = None


class RegulationOut(BaseModel):
    id: str
    source: str
    article: str
    title: Optional[str] = None
    text: str
    tags: list[str] = []


class RegulationCreateRequest(BaseModel):
    source: str = Field(..., description="Regulation family, e.g. GDPR, SOX, Custom")
    article: Optional[str] = Field(None, description="Article / section label")
    title: Optional[str] = None
    text: Optional[str] = Field(None, description="Raw regulation text (clauses)")
    document_b64: Optional[str] = Field(None, description="Base64 PDF/text to extract")
    filename: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class RegulationCreateResponse(BaseModel):
    added: int
    total_indexed: int
    source: str
    ocr_used: bool = False
    warning: Optional[str] = None


class RegulationRef(BaseModel):
    source: str
    name: str


class ContractCategoryOut(BaseModel):
    id: str
    label: str
    description: str
    source_file: str
    contract_count: int
    industry_sector: Optional[str] = None
    regulatory_focus: Optional[str] = None
    default_jurisdiction: Optional[str] = None
    default_contract_type: Optional[str] = None
    regulations: list[RegulationRef] = Field(default_factory=list)
    regulation_sources: list[str] = Field(default_factory=list)


class ContractSummaryOut(BaseModel):
    id: str
    external_id: Optional[str] = None
    category: str
    title: Optional[str] = None
    source_file: Optional[str] = None
    risk_level: Optional[str] = None
    compliance_standard: Optional[str] = None
    preview: str = ""


class ContractListResponse(BaseModel):
    category: str
    total: int
    items: list[ContractSummaryOut]


# ---------------------------------------------------------------------------
# Compliance Chat (RAG Q&A)
# ---------------------------------------------------------------------------


class PortfolioHitOut(BaseModel):
    id: str
    category: str
    title: Optional[str] = None
    preview: str = ""
    risk_level: Optional[str] = None
    compliance_standard: Optional[str] = None


class PortfolioStatsOut(BaseModel):
    category: str
    label: str
    total_contracts: int
    active_contracts: Optional[int] = None
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    summary_kpis: dict[str, str] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(..., description="Free-text compliance question")
    top_k: int = Field(5, ge=1, le=20, description="Number of clauses to retrieve")
    sources: Optional[list[str]] = Field(
        default=None,
        description="Restrict retrieval to specific regulatory sources, e.g. ['GDPR']",
    )
    contract_category: Optional[str] = Field(
        None, description="Portfolio filter: bank | cybersecurity | ai"
    )
    audit_id: Optional[str] = Field(
        None, description="Optional audit id to include uploaded clause context"
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
    sources: list[ChatSource] = Field(default_factory=list)
    portfolio_hits: list[PortfolioHitOut] = Field(default_factory=list)
    portfolio_stats: Optional[PortfolioStatsOut] = None
    intent: str = "regulatory"
    refused: bool = False
