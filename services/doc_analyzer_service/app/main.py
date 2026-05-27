"""Doc-Analyzer service - Layer 3.2.

POST /analyse - accept a base64-encoded PDF (or raw text payload) and
return a list of `ContractClause` objects ready to feed into the
LangGraph agent.

Repurposes the PDF's "Image Analyser" slot for the legal-contract
domain. A future iteration can swap the heuristic segmenter for a
LayoutLMv3 / fine-tuned clause-type classifier without breaking the
schema.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .extractor import extract_from_b64
from .schemas import AnalysedClause, AnalyseRequest, AnalyseResponse
from .segmenter import segment

app = FastAPI(
    title="Contract Doc Analyzer",
    description="Extracts clauses from uploaded contract PDFs.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.post("/analyse", response_model=AnalyseResponse)
def analyse(req: AnalyseRequest) -> AnalyseResponse:
    if not req.document_b64:
        raise HTTPException(status_code=400, detail="document_b64 required")
    try:
        doc = extract_from_b64(req.document_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"could not parse document: {exc}") from exc

    clauses_dicts = segment(
        text=doc.full_text,
        contract_id=req.contract_id,
        page_offsets=doc.page_offsets,
        min_chars=settings.min_clause_chars,
    )
    clauses = [AnalysedClause(**c) for c in clauses_dicts]

    return AnalyseResponse(
        contract_id=req.contract_id,
        filename=req.filename,
        page_count=doc.page_count,
        raw_text_chars=len(doc.full_text),
        clauses=clauses,
    )
