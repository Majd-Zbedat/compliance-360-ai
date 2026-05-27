"""Wire schemas for the LangGraph agent service."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ClauseInput(BaseModel):
    id: str
    contract_id: str
    section: str
    text: str
    clause_type: str = "other"
    page: Optional[int] = None


class AgentRunRequest(BaseModel):
    audit_id: str
    contract_id: str
    clauses: list[ClauseInput]
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None


class FindingOut(BaseModel):
    contract_clause_id: str
    matched_regulatory_clause_id: Optional[str] = None
    matched_regulatory_source: Optional[str] = None
    matched_regulatory_article: Optional[str] = None
    verdict: str = Field(..., description="compliant | non_compliant | ambiguous")
    risk: str = Field(..., description="High | Medium | Low")
    justification: str
    confidence: float


class AgentTrace(BaseModel):
    node: str
    detail: str


class AgentRunResponse(BaseModel):
    audit_id: str
    contract_id: str
    status: str = Field(..., description="Drafting | Reviewing | Flagging | Done")
    overall_risk: str
    findings: list[FindingOut]
    report_markdown: str
    trace: list[AgentTrace] = Field(default_factory=list)
