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
    ContractQueryRequest,
    ContractQueryResponse,
    ContractRetrieved,
    ContractUpsertRequest,
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
    return HealthResponse(
        status="ok",
        regulations_indexed=store.regulations_count(),
        contracts_indexed=store.contracts_count(),
        embedding_backend=store.embedder_name,
    )


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


@app.post("/query/contracts", response_model=ContractQueryResponse)
def query_contracts(req: ContractQueryRequest) -> ContractQueryResponse:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must be non-empty")
    store = get_store()
    raw = store.query_contracts(
        text=req.text,
        top_k=req.top_k,
        category=req.category,
        audit_id=req.audit_id,
        include_portfolio=req.include_portfolio,
    )
    matches = [_to_contract_retrieved(m) for m in raw]
    return ContractQueryResponse(query=req.text, matches=matches)


@app.post("/upsert/contracts")
def upsert_contracts(req: ContractUpsertRequest) -> dict:
    store = get_store()
    if req.reset_portfolio:
        try:
            store.contracts.delete(where={"doc_type": "portfolio"})
        except Exception:
            pass
    if not req.items:
        return {"upserted": 0, "total": store.contracts_count()}
    ids = [it.id for it in req.items]
    docs = [it.text for it in req.items]
    metas = [
        {
            "doc_type": it.doc_type,
            "category": it.category or "",
            "audit_id": it.audit_id or "",
            "contract_id": it.contract_id or "",
            "title": it.title or "",
            "section": it.section or "",
            "filename": it.filename or "",
        }
        for it in req.items
    ]
    store.upsert_contract_chunks(ids=ids, documents=docs, metadatas=metas)
    return {"upserted": len(ids), "total": store.contracts_count()}


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


def _to_contract_retrieved(row: dict) -> ContractRetrieved:
    meta = row.get("metadata") or {}
    return ContractRetrieved(
        id=row["id"],
        text=row.get("text", ""),
        score=float(row.get("score") or 0.0),
        doc_type=str(meta.get("doc_type") or "portfolio"),
        category=meta.get("category") or None,
        audit_id=meta.get("audit_id") or None,
        contract_id=meta.get("contract_id") or None,
        title=meta.get("title") or None,
        section=meta.get("section") or None,
        filename=meta.get("filename") or None,
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
