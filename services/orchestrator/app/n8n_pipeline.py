"""Orchestrator → n8n webhook adapter (Layer 1 → Layer 2).

Extracts contract text (PDF via doc-analyzer or pasted UTF-8), posts to the
n8n compliance-audit webhook, maps the JSON response into SQLite, and returns
the same ``PipelineResult`` shape as ``run_pipeline``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

import httpx

from .config import settings
from .db import AuditRow, session_scope
from .pipeline import PipelineResult, _decoded_text_from_b64, _persist_rejection, _post
from .schemas import AuditCreateRequest


def _normalize_finding(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_clause_id": raw.get("contract_clause_id")
        or raw.get("clause_id")
        or "clause_1",
        "matched_regulatory_clause_id": raw.get("matched_regulatory_clause_id"),
        "matched_regulatory_source": raw.get("matched_regulatory_source")
        or raw.get("regulation_source"),
        "matched_regulatory_article": raw.get("matched_regulatory_article")
        or raw.get("regulation_article"),
        "verdict": raw.get("verdict") or "ambiguous",
        "risk": raw.get("risk") or "Medium",
        "justification": str(raw.get("justification") or ""),
        "confidence": float(raw.get("confidence") or 0.0),
    }


def _build_report_markdown(data: dict[str, Any], report: dict[str, Any]) -> str:
    rag = report.get("rag_insight")
    if isinstance(rag, str) and rag.strip().startswith("#"):
        return rag.strip()
    channel = data.get("channel") or report.get("routing_decision") or "unknown"
    parts = [
        "# Compliance Audit Report",
        f"_Routing channel_: **{channel}**",
        "",
    ]
    if isinstance(rag, str) and rag.strip():
        parts.append(rag.strip())
    else:
        risk = report.get("overall_risk") or "Unknown"
        findings = report.get("findings") or []
        parts.append(f"**Overall risk:** {risk}")
        parts.append(f"**Findings:** {len(findings)}")
        for i, f in enumerate(findings[:10], 1):
            if not isinstance(f, dict):
                continue
            nf = _normalize_finding(f)
            parts.append(
                f"\n### {i}. {nf['contract_clause_id']} — {nf['risk']} ({nf['verdict']})\n"
                f"**Regulation:** {nf.get('matched_regulatory_source') or '—'} "
                f"{nf.get('matched_regulatory_article') or ''}\n\n"
                f"{nf['justification']}"
            )
    notes = report.get("enrichment_notes")
    if isinstance(notes, str) and notes.strip():
        parts.extend(["", f"_Notes:_ {notes.strip()}"])
    return "\n".join(parts)


async def _extract_clauses_and_description(
    client: httpx.AsyncClient, req: AuditCreateRequest, contract_id: str
) -> tuple[list[dict[str, Any]], str]:
    pre_text = _decoded_text_from_b64(req.document_b64)
    clauses: list[dict[str, Any]] = []
    try:
        analyse = await _post(
            client,
            settings.doc_analyzer_service_url.rstrip("/") + "/analyse",
            {
                "contract_id": contract_id,
                "filename": req.filename,
                "document_b64": req.document_b64,
            },
        )
        clauses = list(analyse.get("clauses") or [])
    except Exception:
        clauses = []
    description = pre_text.strip() or "\n\n".join(
        str(c.get("text") or "") for c in clauses if c.get("text")
    )
    return clauses, description


def _persist_success(
    *,
    audit_id: str,
    req: AuditCreateRequest,
    now: datetime,
    clauses: list[dict[str, Any]],
    data: dict[str, Any],
    report: dict[str, Any],
    status: str,
    input_passed: bool,
    output_passed: bool,
    rejection_reason: Optional[str],
) -> PipelineResult:
    findings_raw = report.get("findings") or []
    findings_out = [
        _normalize_finding(f) for f in findings_raw if isinstance(f, dict)
    ]
    overall_risk = str(report.get("overall_risk") or "Unknown")
    report_md = _build_report_markdown(data, report)
    parties = report.get("parties") if isinstance(report.get("parties"), list) else req.parties
    jurisdiction = report.get("jurisdiction") or req.jurisdiction
    contract_type = report.get("contract_type") or req.contract_type

    with session_scope() as s:
        row = AuditRow(
            id=audit_id,
            filename=req.filename,
            status=status,
            overall_risk=overall_risk,
            parties=parties or [],
            jurisdiction=jurisdiction,
            contract_type=contract_type,
            requester=req.requester,
            clauses=clauses,
            findings=findings_out,
            report_markdown=report_md,
            safe_report_markdown=report_md,
            input_guardrail_passed=input_passed,
            output_guardrail_passed=output_passed,
            rejection_reason=rejection_reason,
            created_at=now,
            updated_at=datetime.utcnow(),
        )
        s.add(row)

    return PipelineResult(
        audit_id=audit_id,
        status=status,
        overall_risk=overall_risk,
        rejected=status == "Rejected",
        rejection_reason=rejection_reason,
    )


async def run_n8n_pipeline(req: AuditCreateRequest) -> PipelineResult:
    webhook_url = (settings.n8n_webhook_url or "").strip()
    if not webhook_url:
        raise RuntimeError("n8n_webhook_url is not configured")

    audit_id = "aud_" + uuid.uuid4().hex[:10]
    contract_id = "ctr_" + uuid.uuid4().hex[:10]
    now = datetime.utcnow()
    timeout = settings.n8n_request_timeout_s or settings.request_timeout_s

    async with httpx.AsyncClient(timeout=timeout) as client:
        clauses, description = await _extract_clauses_and_description(
            client, req, contract_id
        )
        if not description.strip():
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason="No contract text could be extracted from the submission.",
            )

        payload = {
            "description": description[:50_000],
            "filename": req.filename,
            "requester": req.requester or "Web UI",
        }

        r = await client.post(webhook_url, json=payload)
        try:
            data = r.json()
        except Exception as exc:
            raise RuntimeError(
                f"n8n returned non-JSON (HTTP {r.status_code}): {r.text[:500]}"
            ) from exc

        if r.status_code == 422 or data.get("rejected"):
            reason = str(
                data.get("reason")
                or data.get("message")
                or "Submission rejected by n8n input guardrails."
            )
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason=reason,
            )

        if data.get("human_review_required"):
            report = data.get("report") if isinstance(data.get("report"), dict) else {}
            flag = data.get("flag_reason") or "Output flagged for human review."
            return _persist_success(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                data=data,
                report=report,
                status="Review",
                input_passed=True,
                output_passed=False,
                rejection_reason=str(flag),
            )

        if not data.get("success"):
            reason = str(data.get("message") or "n8n workflow returned success=false.")
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason=reason,
            )

        report = data.get("report") if isinstance(data.get("report"), dict) else {}
        return _persist_success(
            audit_id=audit_id,
            req=req,
            now=now,
            clauses=clauses,
            data=data,
            report=report,
            status="Done",
            input_passed=True,
            output_passed=True,
            rejection_reason=None,
        )
