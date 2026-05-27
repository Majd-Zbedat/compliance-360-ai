"""RAG service - Layer 3.1 of the Compliance 360 architecture.

POST /query   - retrieve top-k regulatory clauses matching a contract clause.
POST /upsert  - bulk-insert regulatory clauses (used by the seed script).
GET  /healthz - readiness probe and corpus count.

The "insight" field is the single-line, citation-grounded summary that the
LangGraph agent and the n8n LLM Chain consume. It deliberately refuses to
synthesise statements not present in the retrieved documents.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    RetrievedClause,
    UpsertRequest,
)
from .store import get_store

app = FastAPI(
    title="Regulatory RAG Service",
    description="Retrieves matching regulatory clauses from ChromaDB for the audit pipeline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    store = get_store()
    return HealthResponse(status="ok", regulations_indexed=store.regulations_count())


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must be non-empty")
    store = get_store()
    raw_matches = store.query_regulations(
        text=req.text,
        top_k=req.top_k or settings.top_k_default,
        sources=req.sources,
    )
    matches = [_to_retrieved(m) for m in raw_matches]
    return QueryResponse(query=req.text, matches=matches, insight=_build_insight(matches))


@app.post("/upsert")
def upsert(req: UpsertRequest) -> dict:
    store = get_store()
    if req.reset:
        store.reset_regulations()
    ids = [item.id for item in req.items]
    docs = [item.text for item in req.items]
    metas = [
        {
            "source": item.source,
            "article": item.article,
            "title": item.title or "",
            "tags": ",".join(item.tags),
        }
        for item in req.items
    ]
    store.upsert_regulations(ids=ids, documents=docs, metadatas=metas)
    return {"upserted": len(ids), "total": store.regulations_count()}


def _to_retrieved(row: dict) -> RetrievedClause:
    meta = row.get("metadata") or {}
    return RetrievedClause(
        id=row["id"],
        source=str(meta.get("source", "UNKNOWN")),
        article=str(meta.get("article", "")),
        title=meta.get("title") or None,
        text=row.get("text", ""),
        score=float(row.get("score") or 0.0),
    )


def _build_insight(matches: list[RetrievedClause]) -> str:
    """Citation-grounded one-liner.

    The wording deliberately attributes statements to the *retrieved* clauses
    so the agent downstream cannot pretend the RAG service fabricated content.
    """
    if not matches:
        return "No regulatory clauses retrieved; cannot ground analysis."
    top = matches[0]
    refs = ", ".join(f"{m.source} {m.article}" for m in matches)
    return (
        f"Top match {top.source} {top.article} (score {top.score:.2f}). "
        f"Compared against retrieved: {refs}."
    )
