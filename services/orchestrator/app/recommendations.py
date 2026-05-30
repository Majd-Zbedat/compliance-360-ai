"""Derive a human-readable "recommended correction" for a finding.

Layer 2 helper: turns a verdict + cited regulation + justification into an
actionable remediation sentence the UI can show next to each finding. Kept in
the orchestrator (not the LangGraph reasoning layer) so it works for both the
n8n-driven and the in-process Python pipelines.
"""

from __future__ import annotations

from typing import Any


def _citation(finding: dict[str, Any]) -> str:
    src = finding.get("matched_regulatory_source") or finding.get("regulation_source")
    art = finding.get("matched_regulatory_article") or finding.get("regulation_article")
    if src and art:
        return f"{src} {art}"
    if src:
        return str(src)
    return "the cited regulation"


def recommend(finding: dict[str, Any]) -> str:
    """Return a short, actionable remediation string for a finding dict."""
    verdict = str(finding.get("verdict") or "").lower()
    risk = str(finding.get("risk") or "Medium")
    citation = _citation(finding)
    justification = str(finding.get("justification") or "").strip()

    if verdict == "compliant":
        return f"No remediation required — the clause aligns with {citation}."

    if verdict == "non_compliant":
        prefix = (
            "Escalate to legal and revise before signing"
            if risk == "High"
            else "Revise the clause"
        )
        base = f"{prefix} to bring it into compliance with {citation}."
        if justification:
            base += f" Address the specific gap: {justification}"
        return base

    # ambiguous / unknown
    base = (
        f"Clarify the clause wording and confirm alignment with {citation} "
        "with the counterparty or compliance officer."
    )
    if justification:
        base += f" Open question: {justification}"
    return base
