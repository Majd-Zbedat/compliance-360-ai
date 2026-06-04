"""Orchestrator service - UI API + audit persistence.

When ``N8N_WEBHOOK_URL`` is set, ``POST /audits`` forwards to the n8n
compliance-audit webhook (Layer 2) and persists the response. Otherwise the
in-process Python pipeline (``pipeline.run_pipeline``) is used as a fallback.

Endpoints (all return JSON consumed by the Next.js dashboard):

  POST /audits            - kick off a full Compliance 360 audit
  GET  /audits            - list audits (dashboard table)
  GET  /audits/{id}       - single audit detail
  GET  /audits/stats      - dashboard KPI cards
  GET  /regulations       - browse the seeded regulatory corpus
  GET  /healthz           - readiness check (probes downstream services)
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc

from .rag_contracts import query_contract_rag, sync_audit_to_rag, sync_portfolio_to_rag
from .chat_db_stats import answer_db_stats, answer_meta_query

from .config import settings
from .chat_router import route_chat
from .chat_synthesis import (
    build_audit_llm_context,
    synthesise_audit_answer,
    synthesise_contract_rag_answer,
    synthesise_portfolio_answer,
    synthesise_regulatory_answer,
    synthesise_with_llm,
)
from .contract_datasets import (
    category_defaults,
    get_contract,
    get_portfolio_stats,
    list_categories,
    list_contract_summaries,
    search_contracts,
)
from .audit_enrichment import enrich_findings, parse_contract_metadata, parties_from_metadata
from .corpus import append_uploaded, load_corpus
from .db import AuditRow, init_db, row_to_dict, session_scope
from .n8n_pipeline import run_n8n_pipeline
from .pipeline import run_pipeline
from .schemas import (
    AuditCreateRequest,
    AuditDetail,
    AuditSummary,
    ChatRequest,
    ChatResponse,
    ChatSource,
    ClauseOut,
    ContractCategoryOut,
    ContractListResponse,
    ContractMetadataOut,
    ContractSummaryOut,
    FindingOut,
    PortfolioHitOut,
    PortfolioStatsOut,
    RegulationCreateRequest,
    RegulationCreateResponse,
    RegulationOut,
    StatsResponse,
)

app = FastAPI(
    title="Regulatory Auditor Orchestrator",
    description=(
        "Layer 2 of the Compliance 360 architecture. Drives the audit "
        "pipeline: guardrails -> doc-analyzer -> langgraph agent -> "
        "guardrails -> persist."
    ),
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/healthz")
def healthz() -> dict:
    n8n_url = (settings.n8n_webhook_url or "").strip()
    return {
        "status": "ok",
        "service": settings.service_name,
        "pipeline_driver": "n8n" if n8n_url else "python",
        "n8n_webhook_url": n8n_url or None,
        "downstream": {
            "rag": settings.rag_service_url,
            "doc_analyzer": settings.doc_analyzer_service_url,
            "guardrails": settings.guardrails_service_url,
            "langgraph_agent": settings.langgraph_agent_service_url,
        },
    }


# ---------------------------------------------------------------------------
# Audits
# ---------------------------------------------------------------------------


def _prepare_audit_request(req: AuditCreateRequest) -> AuditCreateRequest:
    """Apply dataset category defaults and resolve dataset row → document_b64."""
    data = req.model_dump()

    if req.contract_category:
        defaults = category_defaults(req.contract_category)
        if not data.get("jurisdiction"):
            data["jurisdiction"] = defaults.get("default_jurisdiction")
        if not data.get("contract_type"):
            data["contract_type"] = defaults.get("default_contract_type")
        if not data.get("industry_sector"):
            data["industry_sector"] = defaults.get("industry_sector")
        if not data.get("regulatory_focus"):
            data["regulatory_focus"] = defaults.get("regulatory_focus")
        if not data.get("regulatory_sources"):
            data["regulatory_sources"] = defaults.get("regulation_sources")

    if req.dataset_contract_id:
        if not req.contract_category:
            raise HTTPException(
                status_code=400,
                detail="contract_category required when dataset_contract_id is set",
            )
        row = get_contract(req.contract_category, req.dataset_contract_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Contract {req.dataset_contract_id!r} not found in category {req.contract_category!r}",
            )
        text = str(row.get("text") or "")
        if not text.strip():
            raise HTTPException(status_code=400, detail="Dataset contract has no text")
        data["document_b64"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
        ext = row.get("external_id") or row.get("id") or "contract"
        data["filename"] = f"{ext}.txt"

    if not data.get("document_b64"):
        raise HTTPException(
            status_code=400,
            detail="document_b64 required (upload a file or select a dataset contract)",
        )

    return AuditCreateRequest(**data)


# ---------------------------------------------------------------------------
# Contract datasets (bank / cybersecurity / ai)
# ---------------------------------------------------------------------------


@app.get("/contracts/categories", response_model=list[ContractCategoryOut])
def contract_categories() -> list[ContractCategoryOut]:
    return [ContractCategoryOut(**c) for c in list_categories()]


@app.get("/contracts", response_model=ContractListResponse)
def list_contracts(
    category: str = Query(..., description="bank | cybersecurity | ai"),
    q: Optional[str] = Query(None, description="Search supplier, id, or text"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ContractListResponse:
    if category not in {"bank", "cybersecurity", "ai"}:
        raise HTTPException(status_code=400, detail="category must be bank, cybersecurity, or ai")
    items, total = list_contract_summaries(category, limit=limit, offset=offset, q=q)
    return ContractListResponse(
        category=category,
        total=total,
        items=[ContractSummaryOut(**it) for it in items],
    )


@app.get("/contracts/portfolio-stats", response_model=PortfolioStatsOut)
def portfolio_stats(
    category: str = Query(..., description="bank | cybersecurity | ai"),
) -> PortfolioStatsOut:
    if category not in {"bank", "cybersecurity", "ai"}:
        raise HTTPException(status_code=400, detail="category must be bank, cybersecurity, or ai")
    return PortfolioStatsOut(**get_portfolio_stats(category))


@app.post("/contracts/sync-rag")
async def sync_portfolio_rag(
    reset: bool = Query(False, description="Clear portfolio rows in RAG before re-index"),
) -> dict:
    """Index bank / cybersecurity / AI jsonl contracts into RAG for chat retrieval."""
    try:
        n = await sync_portfolio_to_rag(reset=reset)
        return {"indexed": n, "message": "Portfolio contracts synced to RAG"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"RAG sync failed: {exc}") from exc


@app.post("/audits/sync-rag")
async def sync_audits_rag(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Re-index recent uploaded audits into RAG so chat can answer about them."""
    synced = 0
    with session_scope() as s:
        rows = s.query(AuditRow).order_by(desc(AuditRow.created_at)).limit(limit).all()
        for row in rows:
            d = row_to_dict(row)
            if not d.get("clauses"):
                continue
            await sync_audit_to_rag(
                d["id"],
                d["filename"],
                d["clauses"] or [],
                d["findings"] or [],
                parties=d.get("parties"),
                jurisdiction=d.get("jurisdiction"),
                overall_risk=d.get("overall_risk"),
            )
            synced += 1
    return {"synced": synced, "message": "Audit clauses synced to RAG"}


@app.post("/audits")
async def create_audit(req: AuditCreateRequest) -> dict:
    req = _prepare_audit_request(req)
    try:
        if (settings.n8n_webhook_url or "").strip():
            result = await run_n8n_pipeline(req)
        else:
            result = await run_pipeline(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"pipeline failed: {exc}") from exc
    return {
        "audit_id": result.audit_id,
        "status": result.status,
        "overall_risk": result.overall_risk,
        "rejected": result.rejected,
        "rejection_reason": result.rejection_reason,
    }


@app.get("/audits", response_model=list[AuditSummary])
def list_audits(limit: int = Query(50, ge=1, le=200)) -> list[AuditSummary]:
    out: list[AuditSummary] = []
    with session_scope() as s:
        rows = s.query(AuditRow).order_by(desc(AuditRow.created_at)).limit(limit).all()
        for row in rows:
            counts = _count_findings(row.findings or [])
            out.append(
                AuditSummary(
                    id=row.id,
                    filename=row.filename,
                    status=row.status,
                    review_status=row.review_status,
                    overall_risk=row.overall_risk,
                    findings_count=len(row.findings or []),
                    high_count=counts["High"],
                    medium_count=counts["Medium"],
                    low_count=counts["Low"],
                    created_at=row.created_at,
                    requester=row.requester,
                )
            )
    return out


_VALID_REVIEW_STATUSES = {"Approved", "Pending", "Rejected"}


@app.patch("/audits/{audit_id}/status")
def update_audit_review_status(audit_id: str, body: dict) -> dict:
    """Set the human reviewer decision for an audit: Approved | Pending | Rejected."""
    new_status = (body.get("review_status") or "").strip()
    if new_status not in _VALID_REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"review_status must be one of {sorted(_VALID_REVIEW_STATUSES)}",
        )
    with session_scope() as s:
        row = s.query(AuditRow).filter(AuditRow.id == audit_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="audit not found")
        row.review_status = new_status
        row.updated_at = datetime.utcnow()
    return {"id": audit_id, "review_status": new_status}


@app.get("/audits/stats", response_model=StatsResponse)
def audit_stats() -> StatsResponse:
    with session_scope() as s:
        rows = s.query(AuditRow).all()
        return _build_dashboard_stats(rows)


@app.get("/audits/{audit_id}", response_model=AuditDetail)
def get_audit(audit_id: str) -> AuditDetail:
    with session_scope() as s:
        row = s.query(AuditRow).filter(AuditRow.id == audit_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="audit not found")
        d = row_to_dict(row)
    corpus = load_corpus()
    clauses = d["clauses"] or []
    enriched = enrich_findings(d["findings"] or [], clauses, corpus)
    meta = parse_contract_metadata(clauses)
    parties = list(d["parties"] or [])
    if not parties:
        parties = parties_from_metadata(meta)
    jurisdiction = d["jurisdiction"] or meta.get("jurisdiction")
    return AuditDetail(
        id=d["id"],
        filename=d["filename"],
        status=d["status"],
        review_status=d.get("review_status"),
        overall_risk=d["overall_risk"],
        parties=parties,
        jurisdiction=jurisdiction,
        contract_type=d["contract_type"],
        requester=d["requester"],
        clauses=[ClauseOut(**c) for c in clauses],
        findings=[FindingOut(**f) for f in enriched],
        report_markdown=d["report_markdown"],
        safe_report_markdown=d["safe_report_markdown"],
        input_guardrail_passed=d["input_guardrail_passed"],
        output_guardrail_passed=d["output_guardrail_passed"],
        rejection_reason=d["rejection_reason"],
        contract_metadata=ContractMetadataOut(**meta),
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


# ---------------------------------------------------------------------------
# Regulations browser
# ---------------------------------------------------------------------------


@app.get("/regulations", response_model=list[RegulationOut])
def list_regulations(
    source: Optional[str] = Query(None, description="GDPR | ISO27001 | LocalLaw"),
    q: Optional[str] = Query(None, description="Free-text filter"),
) -> list[RegulationOut]:
    items = load_corpus()
    if source:
        items = [it for it in items if it.get("source") == source]
    if q:
        needle = q.lower()
        items = [
            it
            for it in items
            if needle in (it.get("text", "").lower() + " " + (it.get("title") or "").lower())
        ]
    return [RegulationOut(**it) for it in items]


def _slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    s = "".join(keep)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "reg"


@app.post("/regulations", response_model=RegulationCreateResponse)
async def add_regulation(req: RegulationCreateRequest) -> RegulationCreateResponse:
    """Add a new regulation from raw text or an uploaded PDF/text file.

    Text is split into clause-sized items, indexed into the RAG store, and
    appended to the local corpus so it appears in the library and re-seeds.
    """
    import httpx

    source = req.source.strip()
    if not source:
        raise HTTPException(status_code=400, detail="source is required")

    ocr_used = False
    warning: Optional[str] = None
    clause_dicts: list[dict] = []

    text = (req.text or "").strip()
    if not text and req.document_b64:
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
                analyse = await client.post(
                    settings.doc_analyzer_service_url.rstrip("/") + "/analyse",
                    json={
                        "contract_id": "reg_" + _slug(source),
                        "filename": req.filename or f"{source}.pdf",
                        "document_b64": req.document_b64,
                    },
                )
                analyse.raise_for_status()
                adata = analyse.json()
            ocr_used = bool(adata.get("ocr_used"))
            warning = adata.get("warning")
            clause_dicts = list(adata.get("clauses") or [])
            if not clause_dicts:
                text = ""
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"doc-analyzer failed: {exc}"
            ) from exc

    # Build regulation items: one per extracted clause, or chunk raw text.
    base = _slug(source)
    items: list[dict] = []
    if clause_dicts:
        for i, c in enumerate(clause_dicts, 1):
            body = str(c.get("text") or "").strip()
            if not body:
                continue
            items.append(
                {
                    "id": f"{base}-{i}",
                    "source": source,
                    "article": req.article or str(c.get("section") or f"Clause {i}"),
                    "title": req.title,
                    "text": body,
                    "tags": req.tags,
                }
            )
    elif text:
        for i, chunk in enumerate(_chunk_text(text), 1):
            items.append(
                {
                    "id": f"{base}-{i}",
                    "source": source,
                    "article": req.article or (f"Clause {i}" if i > 1 else (req.article or "Clause 1")),
                    "title": req.title,
                    "text": chunk,
                    "tags": req.tags,
                }
            )

    if not items:
        raise HTTPException(
            status_code=400,
            detail=warning or "No regulation text could be extracted from the input.",
        )

    # Index into the RAG store so audits can retrieve the new regulation.
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
            up = await client.post(
                settings.rag_service_url.rstrip("/") + "/upsert",
                json={"items": items, "reset": False},
            )
            up.raise_for_status()
            up_body = up.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"RAG upsert failed: {exc}"
        ) from exc

    # Persist to the local corpus so the library reflects it and re-seeds.
    append_uploaded([{k: v for k, v in it.items() if v is not None} for it in items])

    return RegulationCreateResponse(
        added=len(items),
        total_indexed=int(up_body.get("total") or 0),
        source=source,
        ocr_used=ocr_used,
        warning=warning,
    )


def _chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    """Split free text into paragraph-aligned chunks for indexing."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        paras = [text.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks


# ---------------------------------------------------------------------------
# Compliance Chat (RAG Q&A)
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def compliance_chat(req: ChatRequest) -> ChatResponse:
    """Compliance assistant: regulatory RAG, portfolio datasets, optional audit context."""
    import httpx

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must be non-empty")

    effective_audit_id = req.audit_id
    q_lower = req.question.lower()
    if not effective_audit_id and any(
        k in q_lower
        for k in (
            "upload",
            "my contract",
            "last audit",
            "this audit",
            "finding",
            "parties in",
            "summarize",
            "summarise",
        )
    ):
        with session_scope() as s:
            latest = s.query(AuditRow).order_by(desc(AuditRow.created_at)).first()
            if latest:
                effective_audit_id = latest.id

    route = route_chat(req.question, req.contract_category, effective_audit_id)
    if route.refused:
        return ChatResponse(
            question=req.question,
            answer=route.refusal_message,
            sources=[],
            intent="off_topic",
            refused=True,
        )

    # DB-stats questions are answered directly from SQLite — no RAG needed.
    if route.intent == "db_stats":
        db_answer = answer_db_stats(req.question)
        return ChatResponse(
            question=req.question,
            answer=db_answer,
            sources=[],
            intent="db_stats",
            refused=False,
        )

    # Metadata queries (value, expiry, parties, jurisdiction) — parse from DB + clauses.
    if route.intent == "meta_query":
        meta_answer = answer_meta_query(req.question)
        if meta_answer:
            return ChatResponse(
                question=req.question,
                answer=meta_answer,
                sources=[],
                intent="meta_query",
                refused=False,
            )

    category = req.contract_category or route.inferred_category
    stats_dict: Optional[dict] = None
    portfolio_hits: list[PortfolioHitOut] = []
    if route.intent in ("portfolio", "hybrid"):
        cat = category or "bank"
        stats_dict = get_portfolio_stats(cat)
        raw_hits = search_contracts(category, req.question, limit=5)
        portfolio_hits = [PortfolioHitOut(**h) for h in raw_hits]

    contract_rag_matches: list[dict] = []
    if route.intent in ("portfolio", "audit", "hybrid"):
        contract_rag_matches = await query_contract_rag(
            req.question,
            top_k=req.top_k,
            category=category if category in ("bank", "cybersecurity", "ai") else None,
            audit_id=effective_audit_id if route.intent in ("audit", "hybrid") else None,
            include_portfolio=route.intent in ("portfolio", "hybrid"),
        )
        for m in contract_rag_matches:
            if m.get("doc_type") == "portfolio":
                portfolio_hits.append(
                    PortfolioHitOut(
                        id=m.get("contract_id") or m.get("id", ""),
                        category=m.get("category") or category or "bank",
                        title=m.get("title"),
                        preview=(m.get("text") or "")[:220],
                        risk_level=None,
                        compliance_standard=None,
                    )
                )

    audit_data: Optional[dict] = None
    if effective_audit_id and route.intent in ("audit", "hybrid"):
        with session_scope() as s:
            row = s.query(AuditRow).filter(AuditRow.id == effective_audit_id).first()
            if row:
                d = row_to_dict(row)
                clauses = d.get("clauses") or []
                enriched = enrich_findings(d.get("findings") or [], clauses, load_corpus())
                meta = parse_contract_metadata(clauses)
                parties = list(d.get("parties") or [])
                if not parties:
                    parties = parties_from_metadata(meta)
                audit_data = {
                    **d,
                    "findings": enriched,
                    "parties": parties,
                    "jurisdiction": d.get("jurisdiction") or meta.get("jurisdiction"),
                }

    sources: list[ChatSource] = []
    if route.intent in ("regulatory", "hybrid"):
        payload: dict = {"text": req.question, "top_k": req.top_k}
        if req.sources:
            payload["sources"] = req.sources
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
                resp = await client.post(
                    f"{settings.rag_service_url}/query",
                    json=payload,
                )
                resp.raise_for_status()
                rag_data = resp.json()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"RAG service unavailable: {exc}",
            ) from exc
        for m in rag_data.get("matches", []):
            sources.append(
                ChatSource(
                    id=m["id"],
                    source=m["source"],
                    article=m["article"],
                    title=m.get("title"),
                    text=m["text"],
                    score=float(m["score"]),
                )
            )

    audit_context = build_audit_llm_context(audit_data) if audit_data else ""
    audit_text = synthesise_audit_answer(req.question, audit_data) if audit_data else ""

    reg_dicts = [s.model_dump() for s in sources]
    portfolio_text = synthesise_portfolio_answer(
        req.question, stats_dict, [h.model_dump() for h in portfolio_hits]
    )
    contract_rag_text = synthesise_contract_rag_answer(
        req.question, contract_rag_matches, stats=stats_dict
    )
    regulatory_text = synthesise_regulatory_answer(req.question, reg_dicts)

    portfolio_llm = "\n\n".join(p for p in (portfolio_text, contract_rag_text) if p)
    llm_answer = synthesise_with_llm(
        req.question,
        regulatory_sources=reg_dicts,
        portfolio_context=portfolio_llm if route.intent in ("portfolio", "hybrid", "audit") else "",
        audit_context=audit_context,
    )

    if route.intent == "audit":
        parts = [p for p in (audit_text, contract_rag_text) if p]
        answer = llm_answer or ("\n\n".join(parts) if parts else (
            "No audit found. Run a contract audit first, then select it in the chat header."
        ))
    elif route.intent == "portfolio":
        answer = llm_answer or contract_rag_text or portfolio_text
    elif route.intent == "regulatory":
        answer = llm_answer or regulatory_text
    else:
        parts = [p for p in (audit_text, contract_rag_text, portfolio_text, regulatory_text) if p]
        answer = llm_answer or ("\n\n".join(parts) if parts else regulatory_text)

    return ChatResponse(
        question=req.question,
        answer=answer,
        sources=sources,
        portfolio_hits=portfolio_hits,
        portfolio_stats=PortfolioStatsOut(**stats_dict) if stats_dict else None,
        intent=route.intent,
        refused=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _risk_score(overall_risk: str) -> int:
    """Map audit overall risk to a 0–100 compliance score."""
    return {"Low": 92, "Medium": 74, "High": 48}.get(overall_risk, 60)


def _high_findings_in_row(row: AuditRow) -> int:
    return sum(1 for f in (row.findings or []) if f.get("risk") == "High")


def _build_dashboard_stats(rows: list[AuditRow]) -> StatsResponse:
    """Compute dashboard KPIs from persisted audit rows."""
    now = datetime.utcnow()
    cutoff_7d = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)
    cutoff_30d = now - timedelta(days=30)
    cutoff_60d = now - timedelta(days=60)

    total = len(rows)
    if total == 0:
        return StatsResponse(
            total_audits=0,
            audits_last_7d=0,
            high_risk_findings=0,
            medium_risk_findings=0,
            low_risk_findings=0,
            avg_findings_per_audit=0.0,
            rejection_rate=0.0,
            by_overall_risk={"High": 0, "Medium": 0, "Low": 0, "Unknown": 0},
            regulation_count=len(load_corpus()),
            regulations_uploaded=len(_read_uploaded_regulations()),
        )

    last_7d = sum(1 for r in rows if r.created_at >= cutoff_7d)
    rejected = sum(1 for r in rows if r.status == "Rejected")
    pending = sum(1 for r in rows if r.status == "Review")
    pending_last_7d = sum(
        1 for r in rows if r.status == "Review" and r.created_at >= cutoff_7d
    )

    by_risk: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0, "Unknown": 0}
    high_findings = medium_findings = low_findings = 0
    total_findings = 0
    high_last_7d = high_prev_7d = 0
    scores_recent: list[int] = []
    scores_prior: list[int] = []
    monthly: dict[str, list[int]] = {}

    for r in rows:
        by_risk[r.overall_risk] = by_risk.get(r.overall_risk, 0) + 1
        hi = _high_findings_in_row(r)
        if r.created_at >= cutoff_7d:
            high_last_7d += hi
        elif r.created_at >= cutoff_14d:
            high_prev_7d += hi

        for f in r.findings or []:
            total_findings += 1
            risk = f.get("risk")
            if risk == "High":
                high_findings += 1
            elif risk == "Medium":
                medium_findings += 1
            elif risk == "Low":
                low_findings += 1

        if r.status != "Rejected":
            score = _risk_score(r.overall_risk)
            if r.created_at >= cutoff_30d:
                scores_recent.append(score)
            elif r.created_at >= cutoff_60d:
                scores_prior.append(score)
            month_key = r.created_at.strftime("%Y-%m")
            monthly.setdefault(month_key, []).append(score)

    compliance_score = round(
        sum(_risk_score(r.overall_risk) for r in rows if r.status != "Rejected")
        / max(1, sum(1 for r in rows if r.status != "Rejected"))
    )
    score_recent_avg = round(sum(scores_recent) / len(scores_recent)) if scores_recent else compliance_score
    score_prior_avg = round(sum(scores_prior) / len(scores_prior)) if scores_prior else score_recent_avg
    compliance_delta = score_recent_avg - score_prior_avg

    # Last 12 calendar months for trend chart (oldest → newest).
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_compliance: list[dict[str, int | str]] = []
    for i in range(11, -1, -1):
        dt = now - timedelta(days=30 * i)
        key = dt.strftime("%Y-%m")
        bucket = monthly.get(key, [])
        monthly_compliance.append(
            {
                "month": month_labels[dt.month - 1],
                "score": round(sum(bucket) / len(bucket)) if bucket else compliance_score,
            }
        )

    last_audit_at = max(r.created_at for r in rows)

    return StatsResponse(
        total_audits=total,
        audits_last_7d=last_7d,
        high_risk_findings=high_findings,
        medium_risk_findings=medium_findings,
        low_risk_findings=low_findings,
        avg_findings_per_audit=round(total_findings / total, 2),
        rejection_rate=round(rejected / total, 3),
        by_overall_risk=by_risk,
        regulation_count=len(load_corpus()),
        regulations_uploaded=len(_read_uploaded_regulations()),
        pending_reviews=pending,
        compliance_score=compliance_score,
        high_risk_delta_7d=high_last_7d - high_prev_7d,
        pending_reviews_last_7d=pending_last_7d,
        compliance_score_delta=compliance_delta,
        monthly_compliance=monthly_compliance,
        last_audit_at=last_audit_at,
    )


def _read_uploaded_regulations() -> list[dict]:
    from .corpus import UPLOADED_FILE

    if not UPLOADED_FILE.exists():
        return []
    try:
        import json

        with UPLOADED_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _count_findings(findings: list[dict]) -> dict[str, int]:
    out = {"High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        risk = f.get("risk")
        if risk in out:
            out[risk] += 1
    return out
