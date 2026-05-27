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
