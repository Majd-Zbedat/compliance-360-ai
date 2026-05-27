"""Schemas for an audit: the top-level workflow object stored by the orchestrator."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from auditor_schemas.contract import ContractClause
from auditor_schemas.finding import Finding, RiskLevel


class AuditStatus(str, Enum):
    """LangGraph state field. The agent advances it as nodes execute."""

    DRAFTING = "Drafting"
    REVIEWING = "Reviewing"
    FLAGGING = "Flagging"
    DONE = "Done"
    REJECTED = "Rejected"


class OverallRisk(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    UNKNOWN = "Unknown"


class AuditCreate(BaseModel):
    """Payload accepted by `POST /audits` on the orchestrator."""

    filename: str
    document_b64: str = Field(..., description="Base64-encoded PDF contents")
    parties: list[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    requester: Optional[str] = Field(default=None, description="Auditor / user name")


class AuditSummary(BaseModel):
    """Lightweight shape used by list endpoints (dashboard table)."""

    id: str
    filename: str
    status: AuditStatus
    overall_risk: OverallRisk
    findings_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: datetime
    requester: Optional[str] = None


class Audit(BaseModel):
    """Full audit record returned by `/audits/{id}`."""

    id: str
    filename: str
    status: AuditStatus
    overall_risk: OverallRisk
    parties: list[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    requester: Optional[str] = None
    clauses: list[ContractClause] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    report_markdown: Optional[str] = None
    safe_report_markdown: Optional[str] = None
    input_guardrail_passed: bool = True
    output_guardrail_passed: bool = True
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    def risk_counts(self) -> dict[str, int]:
        counts = {RiskLevel.HIGH.value: 0, RiskLevel.MEDIUM.value: 0, RiskLevel.LOW.value: 0}
        for f in self.findings:
            counts[f.risk.value] = counts.get(f.risk.value, 0) + 1
        return counts
