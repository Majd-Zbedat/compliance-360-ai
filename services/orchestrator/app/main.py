"""Orchestrator service - Layer 2 (n8n flow stand-in).

Endpoints (all return JSON consumed by the Next.js dashboard):

  POST /audits            - kick off a full Compliance 360 audit
  GET  /audits            - list audits (dashboard table)
  GET  /audits/{id}       - single audit detail
  GET  /audits/stats      - dashboard KPI cards
  GET  /regulations       - browse the seeded regulatory corpus
  GET  /healthz           - readiness check (probes downstream services)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc

from .config import settings
from .corpus import load_corpus
from .db import AuditRow, init_db, row_to_dict, session_scope
from .pipeline import run_pipeline
from .schemas import (
    AuditCreateRequest,
    AuditDetail,
    AuditSummary,
    ChatRequest,
    ChatResponse,
    ChatSource,
    ClauseOut,
    FindingOut,
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
    return {
        "status": "ok",
        "service": settings.service_name,
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


@app.post("/audits")
async def create_audit(req: AuditCreateRequest) -> dict:
    if not req.document_b64:
        raise HTTPException(status_code=400, detail="document_b64 required")
    try:
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


@app.get("/audits/stats", response_model=StatsResponse)
def audit_stats() -> StatsResponse:
    with session_scope() as s:
        rows = s.query(AuditRow).all()
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
        )

    cutoff = datetime.utcnow() - timedelta(days=7)
    last_7d = sum(1 for r in rows if r.created_at >= cutoff)
    rejected = sum(1 for r in rows if r.status == "Rejected")

    by_risk = {"High": 0, "Medium": 0, "Low": 0, "Unknown": 0}
    high_findings = medium_findings = low_findings = 0
    total_findings = 0
    for r in rows:
        by_risk[r.overall_risk] = by_risk.get(r.overall_risk, 0) + 1
        for f in r.findings or []:
            total_findings += 1
            risk = f.get("risk")
            if risk == "High":
                high_findings += 1
            elif risk == "Medium":
                medium_findings += 1
            elif risk == "Low":
                low_findings += 1

    return StatsResponse(
        total_audits=total,
        audits_last_7d=last_7d,
        high_risk_findings=high_findings,
        medium_risk_findings=medium_findings,
        low_risk_findings=low_findings,
        avg_findings_per_audit=round(total_findings / total, 2),
        rejection_rate=round(rejected / total, 3),
        by_overall_risk=by_risk,
    )


@app.get("/audits/{audit_id}", response_model=AuditDetail)
def get_audit(audit_id: str) -> AuditDetail:
    with session_scope() as s:
        row = s.query(AuditRow).filter(AuditRow.id == audit_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="audit not found")
        d = row_to_dict(row)
    return AuditDetail(
        id=d["id"],
        filename=d["filename"],
        status=d["status"],
        overall_risk=d["overall_risk"],
        parties=d["parties"],
        jurisdiction=d["jurisdiction"],
        contract_type=d["contract_type"],
        requester=d["requester"],
        clauses=[ClauseOut(**c) for c in d["clauses"]],
        findings=[FindingOut(**f) for f in d["findings"]],
        report_markdown=d["report_markdown"],
        safe_report_markdown=d["safe_report_markdown"],
        input_guardrail_passed=d["input_guardrail_passed"],
        output_guardrail_passed=d["output_guardrail_passed"],
        rejection_reason=d["rejection_reason"],
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


# ---------------------------------------------------------------------------
# Compliance Chat (RAG Q&A)
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def compliance_chat(req: ChatRequest) -> ChatResponse:
    """Answer a free-text compliance question by retrieving relevant regulatory
    clauses from the RAG service and synthesising a citation-grounded reply."""
    import httpx

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must be non-empty")

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

    raw_matches = rag_data.get("matches", [])
    sources = [
        ChatSource(
            id=m["id"],
            source=m["source"],
            article=m["article"],
            title=m.get("title"),
            text=m["text"],
            score=float(m["score"]),
        )
        for m in raw_matches
    ]

    answer = _synthesise_answer(req.question, sources)
    return ChatResponse(question=req.question, answer=answer, sources=sources)


def _synthesise_answer(question: str, sources: list[ChatSource]) -> str:
    """Build a grounded, citation-attributed answer from retrieved clauses.

    This deliberately avoids fabricating content: every factual statement
    is traceable to a specific retrieved clause.
    """
    if not sources:
        return (
            "I could not find any directly relevant regulatory clauses in the "
            "corpus for that question. Try rephrasing or broadening your query."
        )

    q_lower = question.lower()

    # ---- identify question intent ----
    is_obligation = any(
        kw in q_lower
        for kw in ("must", "require", "obligation", "shall", "need to", "mandatory")
    )
    is_right = any(
        kw in q_lower
        for kw in ("right", "entitled", "subject access", "erasure", "portability", "access")
    )
    is_penalty = any(
        kw in q_lower for kw in ("fine", "penalty", "sanction", "breach", "violation")
    )
    is_timeline = any(
        kw in q_lower for kw in ("when", "deadline", "days", "hours", "timeline", "within")
    )

    top = sources[0]
    citations = ", ".join(f"**{s.source} {s.article}**" for s in sources[:3])

    # ---- opening ----
    if is_obligation:
        intro = (
            f"Based on the retrieved regulatory clauses, the following obligations are relevant:\n\n"
        )
    elif is_right:
        intro = "The following regulatory clauses address the rights you asked about:\n\n"
    elif is_penalty:
        intro = "The retrieved clauses relevant to penalties and breaches state:\n\n"
    elif is_timeline:
        intro = "The following clauses contain timing or deadline requirements:\n\n"
    else:
        intro = (
            f"The most relevant regulatory provisions I found for your question are:\n\n"
        )

    # ---- clause summaries ----
    bullets: list[str] = []
    for s in sources[:4]:
        label = f"**{s.source} — {s.article}**"
        if s.title:
            label += f" (*{s.title}*)"
        # truncate to ~200 chars for readability
        snippet = s.text.strip()
        if len(snippet) > 220:
            snippet = snippet[:217].rstrip() + "…"
        bullets.append(f"• {label}: {snippet}")

    # ---- closing disclaimer ----
    disclaimer = (
        "\n\n---\n"
        "*This answer is grounded solely in the retrieved corpus clauses "
        f"({citations}) and does not constitute legal advice. "
        "Consult a qualified compliance officer for binding interpretations.*"
    )

    return intro + "\n".join(bullets) + disclaimer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_findings(findings: list[dict]) -> dict[str, int]:
    out = {"High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        risk = f.get("risk")
        if risk in out:
            out[risk] += 1
    return out
