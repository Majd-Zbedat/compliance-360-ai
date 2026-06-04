"""Wire schemas specific to the RAG service."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    text: str = Field(..., description="Contract clause text to compare against the corpus")
    top_k: int = Field(3, ge=1, le=20)
    sources: Optional[list[str]] = Field(
        default=None,
        description="Restrict retrieval to one or more regulatory sources, e.g. ['GDPR']",
    )


class ContractQueryRequest(BaseModel):
    text: str = Field(..., description="Natural-language question about contracts")
    top_k: int = Field(5, ge=1, le=20)
    category: Optional[str] = Field(
        None, description="Portfolio filter: bank | cybersecurity | ai"
    )
    audit_id: Optional[str] = Field(
        None, description="Restrict to clauses from a specific uploaded audit"
    )
    include_portfolio: bool = Field(
        True, description="Include Excel portfolio contracts in search"
    )


class ContractUpsertItem(BaseModel):
    id: str
    text: str
    doc_type: str = Field(..., description="portfolio | audit")
    category: Optional[str] = None
    audit_id: Optional[str] = None
    contract_id: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    filename: Optional[str] = None


class ContractUpsertRequest(BaseModel):
    items: list[ContractUpsertItem]
    reset_portfolio: bool = False


class ContractRetrieved(BaseModel):
    id: str
    text: str
    score: float
    doc_type: str
    category: Optional[str] = None
    audit_id: Optional[str] = None
    contract_id: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    filename: Optional[str] = None


class ContractQueryResponse(BaseModel):
    query: str
    matches: list[ContractRetrieved]


class RetrievedClause(BaseModel):
    id: str
    source: str
    article: str
    title: Optional[str] = None
    text: str
    score: float = Field(..., description="Cosine similarity in [0,1]; higher is better")


class QueryResponse(BaseModel):
    query: str
    matches: list[RetrievedClause]
    insight: str = Field(
        ...,
        description="One-line, citation-grounded summary suitable for the agent",
    )


class UpsertItem(BaseModel):
    id: str
    source: str
    article: str
    title: Optional[str] = None
    text: str
    tags: list[str] = []


class UpsertRequest(BaseModel):
    items: list[UpsertItem]
    reset: bool = False


class HealthResponse(BaseModel):
    status: str
    regulations_indexed: int
    contracts_indexed: int = 0
    embedding_backend: str = "unknown"
