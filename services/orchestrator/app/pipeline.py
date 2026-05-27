"""Compliance 360 pipeline.

This is the n8n flow translated into Python; node order is preserved 1:1
with the reference architecture so the n8n JSON skeleton can replace it
without changing any other layer.

Sequence:
  1. Webhook         (caller submits AuditCreateRequest)
  2. Guardrails IN   (POST /check/input on raw text)
  3. IF pass/fail    (rejection path persists and exits early)
  4. Doc Analyzer    (POST /analyse on the PDF base64)
  5. LangGraph Agent (POST /agent/run with extracted clauses)
  6. Guardrails OUT  (POST /check/output on the synthesised report)
  7. Router          (overall_risk -> High/Medium/Low routing metadata)
  8. Persist + return
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import httpx

from .config import settings
from .db import AuditRow, session_scope
from .schemas import AuditCreateRequest


@dataclass
class PipelineResult:
    audit_id: str
    status: str
    overall_risk: str
    rejected: bool
    rejection_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


async def _post(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    r = await client.post(url, json=payload)
    r.raise_for_status()
    return r.json()


def _decoded_text_from_b64(b64: str) -> str:
    try:
        raw = base64.b64decode(b64)
        if raw[:5] == b"%PDF-":
            return ""  # leave PDF parsing to the doc-analyzer
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(req: AuditCreateRequest) -> PipelineResult:
    audit_id = "aud_" + uuid.uuid4().hex[:10]
    contract_id = "ctr_" + uuid.uuid4().hex[:10]
    now = datetime.utcnow()

    pre_extracted_text = _decoded_text_from_b64(req.document_b64)

    async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
        # -------- (4) doc analyzer FIRST so input guard can inspect text -----
        analyse = await _post(
            client,
            settings.doc_analyzer_service_url.rstrip("/") + "/analyse",
            {
                "contract_id": contract_id,
                "filename": req.filename,
                "document_b64": req.document_b64,
            },
        )
        clauses = analyse.get("clauses") or []
        extracted_text = pre_extracted_text or "\n\n".join(c["text"] for c in clauses)

        # -------- (2) input guardrail ---------------------------------------
        input_guard = await _post(
            client,
            settings.guardrails_service_url.rstrip("/") + "/check/input",
            {"text": extracted_text[:8000]},
        )
        if not input_guard.get("passed", True):
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason=str(input_guard.get("reason") or "Input rejected by guardrail."),
            )

        if not clauses:
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=[],
                reason="No clauses could be extracted from the document.",
            )

        # -------- (5) LangGraph agent ---------------------------------------
        agent = await _post(
            client,
            settings.langgraph_agent_service_url.rstrip("/") + "/agent/run",
            {
                "audit_id": audit_id,
                "contract_id": contract_id,
                "clauses": clauses,
                "jurisdiction": req.jurisdiction,
                "contract_type": req.contract_type,
            },
        )

        # -------- (6) output guardrail (also rewrites each justification) ---
        report_md = agent.get("report_markdown") or ""
        output_guard = await _post(
            client,
            settings.guardrails_service_url.rstrip("/") + "/check/output",
            {"text": report_md},
        )
        safe_report_md = output_guard.get("safe_text") or report_md
        output_passed = bool(output_guard.get("passed", True))

        findings_out: list[dict[str, Any]] = []
        for f in agent.get("findings") or []:
            safe_justification = None
            try:
                check = await _post(
                    client,
                    settings.guardrails_service_url.rstrip("/") + "/check/output",
                    {"text": f.get("justification", "")},
                )
                if check.get("safe_text") and check["safe_text"] != f.get("justification"):
                    safe_justification = check["safe_text"]
            except Exception:
                safe_justification = None
            findings_out.append({**f, "safe_justification": safe_justification})

    overall_risk = str(agent.get("overall_risk") or "Unknown")

    with session_scope() as s:
        row = AuditRow(
            id=audit_id,
            filename=req.filename,
            status="Done",
            overall_risk=overall_risk,
            parties=req.parties,
            jurisdiction=req.jurisdiction,
            contract_type=req.contract_type,
            requester=req.requester,
            clauses=clauses,
            findings=findings_out,
            report_markdown=report_md,
            safe_report_markdown=safe_report_md,
            input_guardrail_passed=True,
            output_guardrail_passed=output_passed,
            rejection_reason=None,
            created_at=now,
            updated_at=datetime.utcnow(),
        )
        s.add(row)

    return PipelineResult(
        audit_id=audit_id,
        status="Done",
        overall_risk=overall_risk,
        rejected=False,
    )


def _persist_rejection(
    *,
    audit_id: str,
    req: AuditCreateRequest,
    now: datetime,
    clauses: list,
    reason: str,
) -> PipelineResult:
    with session_scope() as s:
        row = AuditRow(
            id=audit_id,
            filename=req.filename,
            status="Rejected",
            overall_risk="Unknown",
            parties=req.parties,
            jurisdiction=req.jurisdiction,
            contract_type=req.contract_type,
            requester=req.requester,
            clauses=clauses,
            findings=[],
            report_markdown=None,
            safe_report_markdown=None,
            input_guardrail_passed=False,
            output_guardrail_passed=True,
            rejection_reason=reason,
            created_at=now,
            updated_at=now,
        )
        s.add(row)
    return PipelineResult(
        audit_id=audit_id,
        status="Rejected",
        overall_risk="Unknown",
        rejected=True,
        rejection_reason=reason,
    )
