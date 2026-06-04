"""Index and query contract text in the RAG service contracts collection."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .config import settings
from .contract_datasets import load_contracts
from .audit_enrichment import parse_contract_metadata


def _rag_base() -> str:
    return settings.rag_service_url.rstrip("/")


async def query_contract_rag(
    question: str,
    *,
    top_k: int = 5,
    category: Optional[str] = None,
    audit_id: Optional[str] = None,
    include_portfolio: bool = True,
) -> list[dict[str, Any]]:
    payload = {
        "text": question,
        "top_k": top_k,
        "category": category,
        "audit_id": audit_id,
        "include_portfolio": include_portfolio,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
            resp = await client.post(f"{_rag_base()}/query/contracts", json=payload)
            resp.raise_for_status()
            return list(resp.json().get("matches") or [])
    except Exception:
        return []


def build_portfolio_upsert_items() -> list[dict[str, Any]]:
    """All rows from bank / cybersecurity / ai jsonl for RAG indexing."""
    items: list[dict[str, Any]] = []
    for category in ("bank", "cybersecurity", "ai"):
        for row in load_contracts(category):
            cid = str(row.get("id") or row.get("external_id") or "")
            if not cid:
                continue
            text = str(row.get("text") or "").strip()
            if len(text) < 20:
                continue
            items.append(
                {
                    "id": f"portfolio:{category}:{cid}",
                    "text": text,
                    "doc_type": "portfolio",
                    "category": category,
                    "contract_id": cid,
                    "title": row.get("title"),
                }
            )
    return items


def _build_metadata_text(meta: dict[str, Any], filename: str, overall_risk: str) -> str:
    """Build a dense structured-text chunk from extracted contract metadata."""
    lines = [f"Contract metadata — {filename}"]
    fields = [
        ("Contract ID", meta.get("contract_number")),
        ("Contract Value", meta.get("contract_value")),
        ("Effective Date", meta.get("effective_date")),
        ("Expiry Date", meta.get("expiry_date")),
        ("Jurisdiction", meta.get("jurisdiction")),
        ("Governing Law", meta.get("governing_law")),
        ("Payment Terms", meta.get("payment_terms")),
        ("Contract Manager", meta.get("contract_manager")),
        ("Status", meta.get("status")),
        ("Term", meta.get("term")),
        ("Party A", meta.get("party_a")),
        ("Party A Address", meta.get("party_a_address")),
        ("Party A Regulated By", meta.get("party_a_regulated_by")),
        ("Party A LEI", meta.get("party_a_lei")),
        ("Party B", meta.get("party_b")),
        ("Party B Address", meta.get("party_b_address")),
        ("Party B Regulated By", meta.get("party_b_regulated_by")),
        ("Party B LEI", meta.get("party_b_lei")),
        ("Party B ABN", meta.get("party_b_abn")),
        ("Overall Risk", overall_risk),
    ]
    for label, value in fields:
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def build_audit_upsert_items(
    audit_id: str,
    filename: str,
    clauses: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    parties: Optional[list[str]] = None,
    jurisdiction: Optional[str] = None,
    overall_risk: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Chunks for one uploaded audit (metadata + summary + per-clause text)."""
    items: list[dict[str, Any]] = []

    # Extract structured metadata from clauses
    meta = parse_contract_metadata(clauses)
    effective_jurisdiction = jurisdiction or meta.get("jurisdiction") or "unknown"

    # ── Metadata chunk (searchable structured facts) ──────────────────────
    meta_text = _build_metadata_text(meta, filename, overall_risk or "unknown")
    items.append({
        "id": f"audit:{audit_id}:metadata",
        "text": meta_text,
        "doc_type": "audit",
        "audit_id": audit_id,
        "filename": filename,
        "section": "Contract Metadata",
        "title": filename,
        "contract_value": meta.get("contract_value"),
        "expiry_date": meta.get("expiry_date"),
        "effective_date": meta.get("effective_date"),
        "party_a": meta.get("party_a"),
        "party_b": meta.get("party_b"),
        "jurisdiction": effective_jurisdiction,
        "contract_number": meta.get("contract_number"),
    })

    # ── Summary chunk ──────────────────────────────────────────────────────
    party_str = ", ".join(parties or []) or meta.get("party_a") or "unknown"
    finding_lines = []
    for f in findings[:12]:
        if not isinstance(f, dict):
            continue
        finding_lines.append(
            f"{f.get('clause_section') or f.get('contract_clause_id')}: "
            f"{f.get('risk')} {f.get('verdict')} — {(f.get('justification') or '')[:200]}"
        )
    summary = (
        f"Uploaded contract audit {audit_id}. File: {filename}. "
        f"Contract ID: {meta.get('contract_number') or 'unknown'}. "
        f"Contract Value: {meta.get('contract_value') or 'unknown'}. "
        f"Parties: {party_str}. Jurisdiction: {effective_jurisdiction}. "
        f"Overall risk: {overall_risk or 'unknown'}. "
        f"Expires: {meta.get('expiry_date') or 'unknown'}. "
        f"Findings: {'; '.join(finding_lines) if finding_lines else 'none'}."
    )
    items.append({
        "id": f"audit:{audit_id}:summary",
        "text": summary,
        "doc_type": "audit",
        "audit_id": audit_id,
        "filename": filename,
        "title": filename,
    })

    # ── Per-clause chunks ─────────────────────────────────────────────────
    for c in clauses:
        text = str(c.get("text") or "").strip()
        if len(text) < 30:
            continue
        cid = str(c.get("id") or "clause")
        section = str(c.get("section") or "")
        items.append({
            "id": f"audit:{audit_id}:clause:{cid}",
            "text": f"{section}\n{text}"[:4000],
            "doc_type": "audit",
            "audit_id": audit_id,
            "filename": filename,
            "section": section[:200],
            "title": filename,
        })
    return items


async def upsert_contract_items(items: list[dict[str, Any]], *, reset_portfolio: bool = False) -> int:
    if not items:
        return 0
    payload = {"items": items, "reset_portfolio": reset_portfolio}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{_rag_base()}/upsert/contracts", json=payload)
        resp.raise_for_status()
        return int(resp.json().get("upserted") or 0)


async def sync_portfolio_to_rag(*, reset: bool = False) -> int:
    items = build_portfolio_upsert_items()
    return await upsert_contract_items(items, reset_portfolio=reset)


async def sync_audit_to_rag(
    audit_id: str,
    filename: str,
    clauses: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    parties: Optional[list[str]] = None,
    jurisdiction: Optional[str] = None,
    overall_risk: Optional[str] = None,
) -> None:
    """Best-effort index of uploaded audit into RAG (non-blocking for pipeline)."""
    items = build_audit_upsert_items(
        audit_id,
        filename,
        clauses,
        findings,
        parties=parties,
        jurisdiction=jurisdiction,
        overall_risk=overall_risk,
    )
    if not items:
        return
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.post(
                f"{_rag_base()}/upsert/contracts",
                json={"items": items, "reset_portfolio": False},
            )
    except Exception:
        pass
