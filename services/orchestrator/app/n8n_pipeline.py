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
from .pipeline import PipelineResult, _decoded_text_from_b64, _persist_rejection, _post, run_pipeline
from .audit_enrichment import apply_finding_clause_fields
from .rag_contracts import sync_audit_to_rag
from .recommendations import recommend
from .schemas import AuditCreateRequest


def _audit_context_block(req: AuditCreateRequest) -> str:
    """Prefix contract text with user-supplied analysis context for n8n / LangGraph."""
    lines: list[str] = []
    if req.contract_category:
        lines.append(f"Portfolio category: {req.contract_category}")
    if req.dataset_contract_id:
        lines.append(f"Dataset contract id: {req.dataset_contract_id}")
    if req.contract_type:
        lines.append(f"Contract type: {req.contract_type}")
    if req.jurisdiction:
        lines.append(f"Jurisdiction: {req.jurisdiction}")
    if req.industry_sector:
        lines.append(f"Industry sector: {req.industry_sector}")
    if req.regulatory_focus:
        lines.append(f"Regulatory focus: {req.regulatory_focus}")
    if req.regulatory_sources:
        lines.append(f"Regulations to prioritize: {', '.join(req.regulatory_sources)}")
    if not lines:
        return ""
    return "[Audit context]\n" + "\n".join(lines) + "\n\n[Contract text]\n"


def _normalize_finding(
    raw: dict[str, Any],
    clauses: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    out = {
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
    out["recommendation"] = raw.get("recommendation") or recommend(out)
    if clauses:
        out = apply_finding_clause_fields(out, clauses)
    return out


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
                f"{nf['justification']}\n\n"
                f"**Recommended correction:** {nf.get('recommendation') or '—'}"
            )
    notes = report.get("enrichment_notes")
    if isinstance(notes, str) and notes.strip():
        parts.extend(["", f"_Notes:_ {notes.strip()}"])
    return "\n".join(parts)


def _normalize_report(raw: Any) -> dict[str, Any]:
    """Flatten n8n report payloads (e.g. nested ``compliance_triage``)."""
    if not isinstance(raw, dict):
        return {}
    inner = raw.get("compliance_triage")
    if isinstance(inner, dict):
        merged = {**inner, **{k: v for k, v in raw.items() if k != "compliance_triage"}}
        risk = merged.get("overall_risk") or "Medium"
        if not merged.get("routing_decision"):
            merged["routing_decision"] = (
                "escalation"
                if risk == "High"
                else "auto_file"
                if risk == "Low"
                else "reviewer_queue"
            )
        return merged
    return raw


async def _extract_clauses_and_description(
    client: httpx.AsyncClient, req: AuditCreateRequest, contract_id: str
) -> tuple[list[dict[str, Any]], str]:
    pre_text = _decoded_text_from_b64(req.document_b64)
    is_pdf = not pre_text.strip()
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
    except Exception as exc:
        if is_pdf:
            url = settings.doc_analyzer_service_url.rstrip("/")
            raise RuntimeError(
                f"Cannot reach doc-analyzer at {url} (required for PDF upload). "
                f"Run .\\scripts\\run_dev.ps1 and ensure port 8002 is up. ({exc})"
            ) from exc
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
        _normalize_finding(f, clauses) for f in findings_raw if isinstance(f, dict)
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
            "description": (_audit_context_block(req) + description)[:50_000],
            "filename": req.filename,
            "requester": req.requester or "Web UI",
            "clauses": clauses,
            "contract_category": req.contract_category,
            "regulatory_sources": req.regulatory_sources or [],
        }

        try:
            r = await client.post(webhook_url, json=payload)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot reach n8n webhook at {webhook_url}. "
                "Ensure n8n is running, the workflow is Active, and "
                "N8N_WEBHOOK_URL uses the host port (9090 for Docker 9090:5678). "
                f"({exc})"
            ) from exc

        body_preview = (r.text or "").strip()
        if not body_preview:
            # n8n returned 200 with an empty body: the workflow finished without
            # reaching a "Respond to Webhook" node (a node failed mid-run, or the
            # workflow is not Active). Fall back to the Python pipeline when enabled.
            if settings.n8n_fallback_to_python:
                return await run_pipeline(req)
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason=(
                    f"The n8n workflow returned an empty response (HTTP {r.status_code}). "
                    "Check the n8n execution log — a node likely failed before the "
                    "Respond to Webhook step, or the workflow is not Active."
                ),
            )
        try:
            data = r.json()
        except Exception:
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason=(
                    f"The n8n workflow returned a non-JSON response (HTTP {r.status_code}): "
                    f"{body_preview[:300]}"
                ),
            )
        if not isinstance(data, dict):
            data = {"success": True, "report": data}

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
            report = _normalize_report(data.get("report"))
            flag = data.get("flag_reason") or "Output flagged for human review."
            result = _persist_success(
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
            await sync_audit_to_rag(
                audit_id,
                req.filename,
                clauses,
                report.get("findings") or [],
                parties=report.get("parties") or req.parties,
                jurisdiction=report.get("jurisdiction") or req.jurisdiction,
                overall_risk=report.get("overall_risk"),
            )
            return result

        if not data.get("success"):
            reason = str(data.get("message") or "n8n workflow returned success=false.")
            return _persist_rejection(
                audit_id=audit_id,
                req=req,
                now=now,
                clauses=clauses,
                reason=reason,
            )

        report = _normalize_report(data.get("report"))

        # If n8n returned 0 findings but we have extracted clauses, the AI agent
        # likely failed mid-run (e.g. Gemini 503). Fall back to the Python pipeline
        # which calls LangGraph directly without needing an LLM orchestrator.
        n8n_findings = report.get("findings") or []
        if not n8n_findings and clauses and settings.n8n_fallback_to_python:
            return await run_pipeline(req)

        result = _persist_success(
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
        await sync_audit_to_rag(
            audit_id,
            req.filename,
            clauses,
            report.get("findings") or [],
            parties=report.get("parties") or req.parties,
            jurisdiction=report.get("jurisdiction") or req.jurisdiction,
            overall_risk=report.get("overall_risk"),
        )
        return result
