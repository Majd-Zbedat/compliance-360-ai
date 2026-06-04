"""Answer synthesis for Compliance Chat (rules + optional OpenAI)."""

from __future__ import annotations

from typing import Any, Optional

from .config import settings


def synthesise_regulatory_answer(question: str, sources: list[dict[str, Any]]) -> str:
    """Template answer from RAG regulatory matches (existing orchestrator logic)."""
    if not sources:
        return (
            "I could not find any directly relevant regulatory clauses in the "
            "corpus for that question. Try rephrasing or broadening your query."
        )

    q_lower = question.lower()
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

    if is_obligation:
        intro = "Based on the retrieved regulatory clauses, the following obligations are relevant:\n\n"
    elif is_right:
        intro = "The following regulatory clauses address the rights you asked about:\n\n"
    elif is_penalty:
        intro = "The retrieved clauses relevant to penalties and breaches state:\n\n"
    elif is_timeline:
        intro = "The following clauses contain timing or deadline requirements:\n\n"
    else:
        intro = "The most relevant regulatory provisions I found for your question are:\n\n"

    bullets = []
    for m in sources[:5]:
        src = m.get("source", "")
        art = m.get("article", "")
        text = (m.get("text") or "")[:280]
        bullets.append(f"• **{src} {art}** — {text}")

    footer = (
        "\n\n---\n_Answers are grounded in the seeded regulatory corpus only; "
        "not legal advice._"
    )
    return intro + "\n".join(bullets) + footer


def synthesise_portfolio_answer(
    question: str,
    stats: Optional[dict[str, Any]],
    hits: list[dict[str, Any]],
) -> str:
    if not stats and not hits:
        return (
            "No contract portfolio data is loaded. Run "
            "`python scripts/import_contract_datasets.py` after placing the Excel files "
            "under `data/contract_datasets/raw/`."
        )

    total = int((stats or {}).get("total_contracts") or 0)
    if total == 0 and not hits:
        return (
            "No contracts found in the portfolio dataset (0 rows). Copy the bank / "
            "cybersecurity / AI Excel files into `data/contract_datasets/raw/`, then run:\n\n"
            "`python scripts/import_contract_datasets.py`"
        )

    lines = [f"**Portfolio: {stats.get('label', stats.get('category', 'all'))}**\n"]
    if stats:
        lines.append(f"- Total contracts in dataset: **{stats.get('total_contracts', 0)}**")
        if stats.get("active_contracts") is not None:
            lines.append(f"- Active contracts: **{stats['active_contracts']}**")
        for k, v in (stats.get("by_status") or {}).items():
            lines.append(f"- Status «{k}»: {v}")
        for k, v in (stats.get("summary_kpis") or {}).items():
            lines.append(f"- {k}: **{v}**")

    if hits:
        lines.append("\n**Matching contracts:**")
        for h in hits[:5]:
            lines.append(
                f"• {h.get('id')} — {h.get('title') or 'Untitled'} "
                f"({h.get('risk_level') or 'risk n/a'}, {h.get('compliance_standard') or 'standard n/a'})"
            )

    lines.append(
        "\n---\n_Sourced from normalized Excel datasets (bank / cybersecurity / AI); "
        "not legal advice._"
    )
    return "\n".join(lines)


def _audit_clause_snippet(clauses: list[dict[str, Any]], q_lower: str) -> str:
    for c in clauses:
        text = str(c.get("text") or "")
        section = str(c.get("section") or "")
        if not text.strip():
            continue
        blob = (section + " " + text).lower()
        if any(k in q_lower for k in ("terminat", "notice", "party", "parties")):
            if "terminat" in q_lower and (
                "terminat" in blob or c.get("clause_type") == "termination"
            ):
                return f"**{section}**\n{text[:600]}"
            if "part" in q_lower and ("party" in blob or "section 1" in section.lower()):
                return f"**{section}**\n{text[:600]}"
    if clauses:
        c = clauses[0]
        return f"**{c.get('section', 'Clause')}**\n{str(c.get('text') or '')[:600]}"
    return ""


def synthesise_audit_answer(
    question: str,
    audit: dict[str, Any],
) -> str:
    """Answer from stored audit clauses, findings, and metadata (no RAG)."""
    filename = audit.get("filename") or "contract"
    parties = audit.get("parties") or []
    jurisdiction = audit.get("jurisdiction") or "—"
    overall = audit.get("overall_risk") or "Unknown"
    findings = audit.get("findings") or []
    clauses = audit.get("clauses") or []
    q_lower = question.lower()

    if any(w in q_lower for w in ("parties", "party", "who is", "counterpart")):
        if parties:
            return (
                f"**Parties** in audit `{audit.get('id')}` ({filename}):\n\n"
                + "\n".join(f"- {p}" for p in parties)
                + f"\n\n_Jurisdiction:_ {jurisdiction}"
            )
        snippet = _audit_clause_snippet(clauses, q_lower)
        if snippet:
            return f"Parties were not stored on the audit row; from the contract text:\n\n{snippet}"
        return "No party names were extracted for this audit."

    if findings and any(
        w in q_lower for w in ("finding", "gap", "risk", "why", "flagged", "terminat", "compliant")
    ):
        lines = [
            f"**Audit** `{audit.get('id')}` — {filename}\n"
            f"Overall risk: **{overall}** · {len(findings)} finding(s)\n"
        ]
        for i, f in enumerate(findings[:6], 1):
            if not isinstance(f, dict):
                continue
            section = f.get("clause_section") or f.get("contract_clause_id") or "clause"
            lines.append(
                f"\n### {i}. {section} — {f.get('risk')} ({f.get('verdict')})\n"
                f"**Regulation:** {f.get('matched_regulatory_source') or '—'} "
                f"{f.get('matched_regulatory_article') or ''}\n"
            )
            if f.get("clause_excerpt"):
                lines.append(f"**Contract term:** {f['clause_excerpt']}\n")
            lines.append(f"**Gap:** {f.get('justification') or '—'}\n")
            if f.get("recommendation"):
                lines.append(f"**Correction:** {f['recommendation']}\n")
        lines.append("\n---\n_Based on your uploaded contract audit; not legal advice._")
        return "".join(lines)

    if any(w in q_lower for w in ("summar", "overview", "report")):
        return synthesise_audit_answer(
            question + " findings",
            audit,
        )

    snippet = _audit_clause_snippet(clauses, q_lower)
    header = (
        f"**Contract:** {filename}\n"
        f"Risk: **{overall}** · Jurisdiction: {jurisdiction}\n"
        f"Clauses stored: {len(clauses)} · Findings: {len(findings)}\n\n"
    )
    if snippet:
        return header + snippet + "\n\n---\n_Ask about findings, parties, or a specific clause._"
    return (
        header
        + "Select a specific topic (findings, parties, termination) or re-run the audit "
        "with doc-analyzer available so clause text is stored."
    )


def synthesise_contract_rag_answer(
    question: str,
    matches: list[dict[str, Any]],
    *,
    stats: Optional[dict[str, Any]] = None,
) -> str:
    """Answer from vector search over portfolio jsonl + uploaded audits in RAG."""
    if not matches and not stats:
        return (
            "No contract text is indexed in RAG yet. Run:\n\n"
            "`python scripts/import_contract_datasets.py`\n"
            "`python scripts/seed_contract_corpus.py --remote http://localhost:8001`\n\n"
            "Then re-upload contracts so audits are indexed for chat."
        )

    lines = ["**Contract knowledge (RAG retrieval)**\n"]
    if stats:
        lines.append(
            f"Portfolio **{stats.get('label', stats.get('category'))}**: "
            f"**{stats.get('total_contracts', 0)}** contracts in dataset.\n"
        )

    for m in matches[:6]:
        label = m.get("title") or m.get("contract_id") or m.get("id")
        dtype = m.get("doc_type") or "contract"
        cat = m.get("category") or ""
        section = m.get("section") or ""
        score = float(m.get("score") or 0)
        excerpt = (m.get("text") or "")[:420]
        header = f"• **{label}** ({dtype}"
        if cat:
            header += f", {cat}"
        if section:
            header += f", {section}"
        header += f", relevance {score:.0%})"
        lines.append(f"{header}\n  {excerpt}")

    lines.append(
        "\n---\n_Grounded in indexed portfolio Excel data and/or your uploaded audit clauses._"
    )
    return "\n".join(lines)


def build_audit_llm_context(audit: dict[str, Any]) -> str:
    parts = [
        f"Audit {audit.get('id')}: {audit.get('filename')}, risk {audit.get('overall_risk')}.",
        f"Parties: {', '.join(audit.get('parties') or []) or 'unknown'}.",
        f"Jurisdiction: {audit.get('jurisdiction') or 'unknown'}.",
    ]
    for f in (audit.get("findings") or [])[:5]:
        if not isinstance(f, dict):
            continue
        parts.append(
            f"Finding {f.get('clause_section') or f.get('contract_clause_id')}: "
            f"{f.get('risk')} — {(f.get('clause_excerpt') or '')[:300]} — "
            f"{(f.get('justification') or '')[:200]}"
        )
    return "\n".join(parts)


def _build_llm_prompt(
    question: str,
    regulatory_sources: list[dict[str, Any]],
    portfolio_context: str,
    audit_context: str,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the LLM."""
    reg_block = "\n".join(
        f"- {s.get('source')} {s.get('article')}: {(s.get('text') or '')[:400]}"
        for s in regulatory_sources[:6]
    )
    system = (
        "You are Compliance 360 assistant. Answer ONLY using the provided regulatory "
        "clauses, portfolio facts, contract RAG excerpts, and audit context. "
        "Cite sources as **Source Article** or contract id. "
        "If the question is outside compliance/contracts scope, refuse briefly. "
        "Never invent statutes. This is not legal advice."
    )
    user = f"Question: {question}\n\nRegulatory context:\n{reg_block}\n\n"
    if portfolio_context:
        user += f"Portfolio / contract RAG context:\n{portfolio_context}\n\n"
    if audit_context:
        user += f"Recent audit context:\n{audit_context}\n\n"
    return system, user


def _gemini_call(system: str, user: str) -> Optional[str]:
    try:
        from google import genai  # type: ignore
        from google.genai import types as genai_types  # type: ignore
    except ImportError:
        return None
    client = genai.Client(api_key=settings.gemini_api_key)
    model_name = settings.gemini_model
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
    resp = client.models.generate_content(
        model=model_name,
        contents=user,
        config=genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            max_output_tokens=800,
        ),
    )
    return (resp.text or "").strip() or None


def _openai_call(system: str, user: str) -> Optional[str]:
    try:
        from openai import OpenAI
    except ImportError:
        return None
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return (resp.choices[0].message.content or "").strip() or None


def synthesise_with_llm(
    question: str,
    *,
    regulatory_sources: list[dict[str, Any]],
    portfolio_context: str,
    audit_context: str = "",
) -> Optional[str]:
    if not settings.gemini_api_key and not settings.openai_api_key:
        return None
    try:
        system, user = _build_llm_prompt(question, regulatory_sources, portfolio_context, audit_context)
        if settings.gemini_api_key:
            return _gemini_call(system, user)
        return _openai_call(system, user)
    except Exception as exc:
        print(f"[chat-llm] error: {exc!r}")
        return None
